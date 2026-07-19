from __future__ import annotations

from typing import Any

from flask import jsonify, request

try:
    from . import dashboard_core as core
    from .alarm_config import (
        DAY_OPTIONS,
        load_tone_manifest,
        normalise_alarm_config,
        validate_submitted_alarm_config,
    )
except ImportError:  # Supports direct execution with: python app/main.py
    import dashboard_core as core
    from alarm_config import (
        DAY_OPTIONS,
        load_tone_manifest,
        normalise_alarm_config,
        validate_submitted_alarm_config,
    )

# Re-export the established application helpers for compatibility with existing
# imports, then replace only the alarm-aware functions below.
for _name in dir(core):
    if not _name.startswith("_") and _name not in globals():
        globals()[_name] = getattr(core, _name)

app = core.app
TONE_MANIFEST_PATH = core.BASE_DIR / "app" / "static" / "alarm-tones.json"

_core_load_config = core.load_config
_core_save_settings_from_form = core.save_settings_from_form


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
    return config


def save_settings_from_form(config: dict[str, Any]) -> dict[str, Any]:
    # The dedicated alarm API saves the dynamic collection immediately before
    # the ordinary Settings form posts. Preserve that validated model while the
    # core handler continues to save every non-alarm field unchanged.
    alarm_model = normalise_alarm_config(config.get("alarm"), alarm_tone_manifest())
    saved = _core_save_settings_from_form(config)
    saved["alarm"] = alarm_model
    core.save_json(core.CONFIG_PATH, saved)
    return saved


core.load_config = load_config
core.save_settings_from_form = save_settings_from_form


@app.route("/api/alarms/config", methods=["GET", "POST"])
def api_alarm_config():
    manifest = alarm_tone_manifest()
    if request.method == "GET":
        config = load_config()
        return jsonify(
            {
                "ok": True,
                "alarm": config["alarm"],
                "tones": manifest,
                "days": DAY_OPTIONS,
                "scheduler_active": False,
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

    return jsonify(
        {
            "ok": True,
            "alarm": alarm_model,
            "message": "Alarm configuration saved. The scheduler remains inactive.",
            "scheduler_active": False,
        }
    )


if __name__ == "__main__":
    cfg = load_config()
    dashboard_cfg = cfg.get("dashboard", {})
    app.run(
        host=dashboard_cfg.get("host", "0.0.0.0"),
        port=int(dashboard_cfg.get("port", 8088)),
        debug=False,
    )
