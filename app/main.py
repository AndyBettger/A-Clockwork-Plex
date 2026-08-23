from __future__ import annotations

from copy import deepcopy
from typing import Any

from flask import jsonify, redirect, render_template, request, url_for

try:
    from . import dashboard_core as core
    from .alarm_audio import AlarmAudioManager, normalise_audio_settings
    from .alarm_config import (
        DAY_OPTIONS,
        load_tone_manifest,
        normalise_alarm_config,
        validate_submitted_alarm_config,
    )
    from .alarm_runtime import ActiveAlarmScheduler
except ImportError:  # Supports direct execution with: python app/main.py
    import dashboard_core as core
    from alarm_audio import AlarmAudioManager, normalise_audio_settings
    from alarm_config import (
        DAY_OPTIONS,
        load_tone_manifest,
        normalise_alarm_config,
        validate_submitted_alarm_config,
    )
    from alarm_runtime import ActiveAlarmScheduler

# Re-export the established application helpers for compatibility with existing
# imports, then replace only the alarm-aware functions below.
for _name in dir(core):
    if not _name.startswith("_") and _name not in globals():
        globals()[_name] = getattr(core, _name)

app = core.app
TONE_MANIFEST_PATH = core.BASE_DIR / "app" / "static" / "alarm-tones.json"
ALARM_RUNTIME_PATH = core.BASE_DIR / "alarm-runtime.json"
ALARM_AUDIO_RUNTIME_PATH = core.BASE_DIR / "alarm-audio-runtime.json"

_core_load_config = core.load_config
_core_save_settings_from_form = core.save_settings_from_form
_core_api_status = core.api_status


def alarm_tone_manifest() -> dict[str, Any]:
    return load_tone_manifest(TONE_MANIFEST_PATH)


def _has_explicit_alarm_list() -> bool:
    raw_config = core.load_json(core.CONFIG_PATH, {})
    raw_alarm = raw_config.get("alarm") if isinstance(raw_config, dict) else None
    return isinstance(raw_alarm, dict) and isinstance(raw_alarm.get("alarms"), list)


def load_config() -> dict[str, Any]:
    config = _core_load_config()
    config["alarm"] = normalise_alarm_config(
        config.get("alarm"),
        alarm_tone_manifest(),
        prefer_legacy=not _has_explicit_alarm_list(),
    )
    config["alarm_audio"] = normalise_audio_settings(config.get("alarm_audio"))
    return config


def save_settings_from_form(config: dict[str, Any]) -> dict[str, Any]:
    # The dedicated alarm APIs save the dynamic alarm collection and audio safety
    # settings. Preserve both while the core handler saves non-alarm fields.
    alarm_model = normalise_alarm_config(config.get("alarm"), alarm_tone_manifest())
    audio_settings = normalise_audio_settings(config.get("alarm_audio"))
    saved = _core_save_settings_from_form(config)
    saved["alarm"] = alarm_model
    saved["alarm_audio"] = audio_settings
    core.save_json(core.CONFIG_PATH, saved)

    scheduler = globals().get("alarm_scheduler")
    if scheduler is not None:
        scheduler.wake()
    return saved


core.load_config = load_config
core.save_settings_from_form = save_settings_from_form

alarm_scheduler = ActiveAlarmScheduler(
    load_config,
    ALARM_RUNTIME_PATH,
)
alarm_audio = AlarmAudioManager(
    load_config,
    alarm_tone_manifest,
    alarm_scheduler.status,
    ALARM_AUDIO_RUNTIME_PATH,
)


def scheduler_payload() -> dict[str, Any]:
    status = alarm_scheduler.status()
    return {
        "ok": True,
        "scheduler": status,
        "scheduler_active": status["running"],
        "playback_enabled": status["playback_enabled"],
        "audio": alarm_audio.status(),
    }


def tone_labels() -> dict[str, str]:
    return {
        str(tone.get("id")): str(tone.get("label", tone.get("id", "Alarm tone")))
        for tone in alarm_tone_manifest().get("tones", [])
        if isinstance(tone, dict) and tone.get("id")
    }


def alarm_options() -> list[dict[str, Any]]:
    labels = tone_labels()
    config = load_config()
    alarm_config = config.get("alarm", {}) if isinstance(config, dict) else {}
    alarms = alarm_config.get("alarms", []) if isinstance(alarm_config, dict) else []
    options: list[dict[str, Any]] = []
    for alarm in alarms:
        if not isinstance(alarm, dict):
            continue
        source = alarm.get("source") if isinstance(alarm.get("source"), dict) else {}
        tone_id = str(source.get("tone_id", "classic-klaxon"))
        options.append(
            {
                "id": str(alarm.get("id", "")),
                "label": str(alarm.get("label", "Alarm")),
                "tone_id": tone_id,
                "tone_label": labels.get(tone_id, tone_id),
                "enabled": bool(alarm.get("enabled")),
            }
        )
    return options


def audio_payload() -> dict[str, Any]:
    diagnostics = alarm_audio.diagnostics()
    return {
        "ok": True,
        **diagnostics,
        "alarm_options": alarm_options(),
    }


def select_alarm_for_audio_test(alarm_id: Any = None) -> dict[str, Any]:
    config = load_config()
    alarm_config = config.get("alarm", {}) if isinstance(config, dict) else {}
    alarms = alarm_config.get("alarms", []) if isinstance(alarm_config, dict) else []
    selected = None
    for alarm in alarms:
        if not isinstance(alarm, dict):
            continue
        if alarm_id and str(alarm.get("id")) != str(alarm_id):
            continue
        selected = alarm
        break
    if selected is None:
        selected = next((alarm for alarm in alarms if isinstance(alarm, dict)), None)

    defaults = alarm_config.get("defaults", {}) if isinstance(alarm_config, dict) else {}
    selected = deepcopy(selected) if isinstance(selected, dict) else {}
    source = selected.get("source") if isinstance(selected.get("source"), dict) else {
        "type": "tone",
        "tone_id": defaults.get("tone_id", "classic-klaxon"),
        "fallback_tone_id": defaults.get("fallback_tone_id", "emergency-buzzer"),
    }
    volume = selected.get("volume") if isinstance(selected.get("volume"), dict) else {
        "start_percent": 60,
        "target_percent": 85,
        "fade_seconds": 10,
    }
    return {
        "alarm_id": str(selected.get("id", "audio-test")),
        "label": str(selected.get("label", "Alarm audio test")),
        "source": deepcopy(source),
        "volume": deepcopy(volume),
        "snooze_minutes": int(selected.get("snooze_minutes", defaults.get("snooze_minutes", 8))),
        "ring_minutes": int(selected.get("ring_minutes", defaults.get("ring_minutes", 3))),
        "occurrence_expiry_minutes": int(
            selected.get("occurrence_expiry_minutes", defaults.get("occurrence_expiry_minutes", 120))
        ),
    }


def api_status_with_alarm_scheduler():
    response = _core_api_status()
    payload = response.get_json(silent=True) or {}
    payload["alarm_scheduler"] = alarm_scheduler.status()
    payload["alarm_audio"] = alarm_audio.status()
    return jsonify(payload)


# Keep the established /api/status URL and endpoint name while enriching its
# response with scheduler and controlled-audio diagnostics.
app.view_functions["api_status"] = api_status_with_alarm_scheduler


@app.route("/alarm")
def alarm_page():
    status = alarm_scheduler.status()
    if not status.get("screen_required"):
        return redirect(url_for("clock"))
    return render_template("alarm.html", active_page="alarm")


@app.route("/api/alarms/config", methods=["GET", "POST"])
def api_alarm_config():
    manifest = alarm_tone_manifest()
    if request.method == "GET":
        config = load_config()
        status = alarm_scheduler.status()
        return jsonify(
            {
                "ok": True,
                "alarm": config["alarm"],
                "tones": manifest,
                "days": DAY_OPTIONS,
                "scheduler_active": status["running"],
                "scheduler": status,
                "playback_enabled": status["playback_enabled"],
                "audio": alarm_audio.status(),
            }
        )

    payload = request.get_json(silent=True)
    try:
        alarm_model = validate_submitted_alarm_config(payload, manifest)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    config = _core_load_config()
    config["alarm"] = alarm_model
    try:
        core.save_json(core.CONFIG_PATH, config)
    except OSError as exc:
        return jsonify({"ok": False, "error": f"Could not save alarm configuration: {exc}"}), 500

    alarm_scheduler.wake()
    status = (
        alarm_scheduler.recalculate()
        if alarm_scheduler.status()["running"]
        else alarm_scheduler.status()
    )

    return jsonify(
        {
            "ok": True,
            "alarm": alarm_model,
            "message": (
                "Alarm configuration saved. The active runtime has recalculated; "
                "scheduled audio remains locked."
            ),
            "scheduler_active": status["running"],
            "scheduler": status,
            "playback_enabled": status["playback_enabled"],
            "audio": alarm_audio.status(),
        }
    )


@app.route("/api/alarms/scheduler", methods=["GET", "POST"])
def api_alarm_scheduler():
    if request.method == "POST":
        status = alarm_scheduler.recalculate()
        return jsonify(
            {
                "ok": True,
                "message": "Alarm runtime recalculated. Scheduled audio remains locked.",
                "scheduler": status,
                "scheduler_active": status["running"],
                "playback_enabled": status["playback_enabled"],
                "audio": alarm_audio.status(),
            }
        )
    return jsonify(scheduler_payload())


@app.route("/api/alarms/active")
def api_alarm_active():
    status = alarm_scheduler.status()
    active = status.get("active_occurrence")
    labels = tone_labels()
    tone_id = None
    if isinstance(active, dict):
        source = active.get("source") if isinstance(active.get("source"), dict) else {}
        tone_id = source.get("tone_id")
    return jsonify(
        {
            "ok": True,
            "active": active,
            "screen_required": status.get("screen_required", False),
            "snoozed_until": status.get("snoozed_until"),
            "seconds_until_snooze_end": status.get("seconds_until_snooze_end"),
            "tone_label": labels.get(str(tone_id), str(tone_id or "Local tone")),
            "playback_enabled": False,
            "scheduler": status,
            "audio": alarm_audio.status(),
        }
    )


@app.route("/api/alarms/snooze", methods=["POST"])
def api_alarm_snooze():
    try:
        status = alarm_scheduler.snooze()
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 409
    audio_status = alarm_audio.stop_playback(reason="alarm-snoozed", restore=True)
    return jsonify(
        {
            "ok": True,
            "message": "Alarm snoozed. Audio stopped and the next takeover remains armed.",
            "scheduler": status,
            "snoozed_until": status.get("snoozed_until"),
            "playback_enabled": False,
            "audio": audio_status,
        }
    )


@app.route("/api/alarms/dismiss", methods=["POST"])
def api_alarm_dismiss():
    before = alarm_scheduler.status().get("active_occurrence")
    try:
        status = alarm_scheduler.dismiss()
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 409
    audio_status = alarm_audio.stop_playback(reason="alarm-dismissed", restore=True)
    if isinstance(before, dict):
        alarm_audio.disarm_occurrence(str(before.get("occurrence_key", "")))
    return jsonify(
        {
            "ok": True,
            "message": "Alarm dismissed. Audio stopped; sleep has won this round.",
            "scheduler": status,
            "playback_enabled": False,
            "audio": audio_status,
        }
    )


@app.route("/api/alarms/test", methods=["POST"])
def api_alarm_test():
    payload = request.get_json(silent=True) or {}
    try:
        delay_seconds = int(payload.get("delay_seconds", 10))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "delay_seconds must be an integer."}), 400
    alarm_id = payload.get("alarm_id")
    status = alarm_scheduler.schedule_test(delay_seconds=delay_seconds, alarm_id=alarm_id)
    pending = status.get("pending_test_occurrence")
    return jsonify(
        {
            "ok": True,
            "message": f"Visual alarm test scheduled in {max(1, min(300, delay_seconds))} seconds.",
            "pending_test": pending,
            "scheduler": status,
            "playback_enabled": False,
            "audio": alarm_audio.status(),
        }
    )


@app.route("/api/alarms/test/cancel", methods=["POST"])
def api_alarm_test_cancel():
    active = alarm_scheduler.status().get("active_occurrence")
    status = alarm_scheduler.clear_test()
    audio_status = alarm_audio.stop_playback(reason="visual-test-cleared", restore=True)
    if isinstance(active, dict):
        alarm_audio.disarm_occurrence(str(active.get("occurrence_key", "")))
    else:
        alarm_audio.disarm_occurrence()
    return jsonify(
        {
            "ok": True,
            "message": "Pending or active visual alarm test cleared.",
            "scheduler": status,
            "playback_enabled": False,
            "audio": audio_status,
        }
    )


@app.route("/api/alarms/audio", methods=["GET"])
def api_alarm_audio_status():
    return jsonify(audio_payload())


@app.route("/api/alarms/audio/settings", methods=["POST"])
def api_alarm_audio_settings():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "Audio settings must be a JSON object."}), 400
    current = load_config().get("alarm_audio", {})
    settings = normalise_audio_settings({**current, **payload})
    raw_config = core.load_json(core.CONFIG_PATH, {})
    raw_config["alarm_audio"] = settings
    try:
        core.save_json(core.CONFIG_PATH, raw_config)
    except OSError as exc:
        return jsonify({"ok": False, "error": f"Could not save alarm audio settings: {exc}"}), 500
    if not settings["master_enabled"]:
        alarm_audio.stop_playback(reason="master-audio-lock-enabled", restore=True)
        alarm_audio.disarm_occurrence()
    response = audio_payload()
    response["message"] = (
        "Alarm audio tests enabled. Scheduled alarms remain silent."
        if settings["master_enabled"]
        else "Alarm audio locked. No test may make sound."
    )
    return jsonify(response)


@app.route("/api/alarms/audio/test", methods=["POST"])
def api_alarm_audio_test():
    payload = request.get_json(silent=True) or {}
    settings = load_config().get("alarm_audio", {})
    if not settings.get("master_enabled"):
        return jsonify({"ok": False, "error": "Enable and save the alarm audio safety switch first."}), 409

    alarm_id = payload.get("alarm_id")
    full_screen = bool(payload.get("full_screen", False))
    if full_screen:
        try:
            delay_seconds = max(1, min(300, int(payload.get("delay_seconds", 10))))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "delay_seconds must be an integer."}), 400
        status = alarm_scheduler.schedule_test(delay_seconds=delay_seconds, alarm_id=alarm_id)
        pending = status.get("pending_test_occurrence")
        if not isinstance(pending, dict) or not pending.get("occurrence_key"):
            return jsonify({"ok": False, "error": "The full-screen audio test could not be armed."}), 500
        alarm_audio.arm_occurrence(str(pending["occurrence_key"]))
        response = audio_payload()
        response.update(
            {
                "message": f"Full alarm audio test armed in {delay_seconds} seconds.",
                "pending_test": pending,
                "scheduler": status,
            }
        )
        return jsonify(response)

    occurrence = select_alarm_for_audio_test(alarm_id)
    try:
        alarm_audio.test_tone(occurrence)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 409
    response = audio_payload()
    response["message"] = (
        f"Testing {occurrence['label']} for {settings.get('test_duration_seconds', 12)} seconds."
    )
    return jsonify(response)


@app.route("/api/alarms/audio/stop", methods=["POST"])
def api_alarm_audio_stop():
    alarm_audio.stop_playback(reason="emergency-stop-button", restore=True)
    response = audio_payload()
    response["message"] = "Alarm audio stopped and previous services were restored where possible."
    return jsonify(response)


if __name__ == "__main__":
    cfg = load_config()
    dashboard_cfg = cfg.get("dashboard", {})
    alarm_scheduler.start()
    alarm_audio.start()
    try:
        app.run(
            host=dashboard_cfg.get("host", "0.0.0.0"),
            port=int(dashboard_cfg.get("port", 8088)),
            debug=False,
            use_reloader=False,
        )
    finally:
        alarm_audio.shutdown()
        alarm_scheduler.stop()
