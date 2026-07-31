from __future__ import annotations

import threading
from copy import deepcopy
from typing import Any

from flask import jsonify, request

try:
    from . import alarm_audio_core as _core
    from .alarm_audio import AlarmAudioManager as ControlledAlarmAudioManager
    from .alarm_audio import normalise_audio_settings as _normalise_test_audio_settings
except ImportError:  # Supports direct execution imports.
    import alarm_audio_core as _core
    from alarm_audio import AlarmAudioManager as ControlledAlarmAudioManager
    from alarm_audio import normalise_audio_settings as _normalise_test_audio_settings


MAX_CONTROLLED_TEST_SECONDS = 30
MAX_SCHEDULED_RING_SECONDS = 630
DEFAULT_SCHEDULED_VOLUME_CAP_PERCENT = 100

# The preserved player clamps rendered files through this module constant.
# Scheduled occurrences may render a complete ten-minute ring cycle plus a small
# scheduler handover margin. The promoted normaliser below separately pins all
# deliberate tests back to their original 30-second safety limit.
_core.MAX_TEST_SECONDS = max(_core.MAX_TEST_SECONDS, MAX_SCHEDULED_RING_SECONDS)


def _integer(value: Any, fallback: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return fallback


def normalise_audio_settings(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    settings = _normalise_test_audio_settings(source)
    master_enabled = bool(settings.get("master_enabled"))
    settings.update(
        {
            # Extending the shared renderer for scheduled rings must never widen
            # the explicit test window.
            "test_duration_seconds": max(
                3,
                min(
                    MAX_CONTROLLED_TEST_SECONDS,
                    _integer(source.get("test_duration_seconds"), 12),
                ),
            ),
            # This is deliberately a second key. Turning off the master switch
            # also clears scheduled playback instead of leaving a latent alarm.
            "scheduled_enabled": master_enabled and bool(source.get("scheduled_enabled", False)),
            "scheduled_volume_cap_percent": max(
                1,
                min(
                    100,
                    _integer(
                        source.get("scheduled_volume_cap_percent"),
                        DEFAULT_SCHEDULED_VOLUME_CAP_PERCENT,
                    ),
                ),
            ),
        }
    )
    return settings


class ScheduledAlarmAudioManager(ControlledAlarmAudioManager):
    """Promote the proven test player to opt-in scheduled alarm playback.

    The visual scheduler remains the sole clock and occurrence authority. This
    manager only mirrors its active ringing state into the existing acp_alarm
    stream when both audio safety keys are enabled.
    """

    def settings(self) -> dict[str, Any]:
        config = self.config_loader()
        return normalise_audio_settings(config.get("alarm_audio") if isinstance(config, dict) else None)

    @staticmethod
    def _is_real_scheduled_occurrence(occurrence: dict[str, Any]) -> bool:
        return bool(occurrence.get("scheduled_alarm")) and not bool(occurrence.get("test_mode"))

    def _start(self, occurrence: dict[str, Any], cycle: str) -> None:
        settings = self.settings()
        if not settings.get("master_enabled"):
            raise ValueError("Alarm audio is locked by the master switch.")

        payload = deepcopy(occurrence)
        is_test = bool(payload.get("audio_test"))
        is_scheduled = self._is_real_scheduled_occurrence(payload)
        if not is_test and not is_scheduled:
            raise ValueError("Alarm playback requires an armed test or an enabled scheduled occurrence.")
        if is_scheduled and not settings.get("scheduled_enabled"):
            raise ValueError("Scheduled alarm playback is disabled.")

        playback_settings = deepcopy(settings)
        playback_kind = "scheduled" if is_scheduled else "test"
        if is_scheduled:
            ring_minutes = max(1, min(10, _integer(payload.get("ring_minutes"), 3)))
            payload["audio_duration_seconds"] = min(
                MAX_SCHEDULED_RING_SECONDS,
                ring_minutes * 60 + 20,
            )
            playback_settings["test_volume_cap_percent"] = settings.get(
                "scheduled_volume_cap_percent",
                DEFAULT_SCHEDULED_VOLUME_CAP_PERCENT,
            )

        with self.lock:
            if cycle in self.played_cycles:
                return
        self.stop_playback(reason=f"replaced-by-new-{playback_kind}")
        with self.lock:
            self.played_cycles.add(cycle)
            self.stop_event.clear()
            self.state["playback_kind"] = playback_kind
            self.worker_thread = threading.Thread(
                target=self._play,
                args=(payload, playback_settings),
                name=f"alarm-audio-{playback_kind}-player",
                daemon=True,
            )
            self.worker_thread.start()

    def reconcile_scheduler_audio(self) -> None:
        scheduler = self.scheduler_status()
        if not isinstance(scheduler, dict):
            scheduler = {}
        active = scheduler.get("active_occurrence") if isinstance(scheduler.get("active_occurrence"), dict) else None
        completed = {str(value) for value in scheduler.get("completed_occurrence_keys", []) if value}
        with self.lock:
            self.armed.difference_update(completed)

        key = str(active.get("occurrence_key", "")) if active else ""
        phase = active.get("phase") if active else None
        cycle = f"{key}|{active.get('ring_cycle_started_at', '')}" if active else ""
        settings = self.settings()

        with self.lock:
            armed = key in self.armed
            playing = bool(self.state.get("playback_active"))
            worker_alive = bool(self.worker_thread and self.worker_thread.is_alive())
            current = str(self.state.get("current_occurrence_key") or "")
            standalone = bool(self.state.get("standalone_audio_test"))
            playback_kind = str(self.state.get("playback_kind") or "")

        if active and phase == "ringing" and key and not playing and not worker_alive:
            occurrence = deepcopy(active)
            if active.get("test_mode"):
                if armed:
                    occurrence["audio_test"] = True
                    self._start(occurrence, cycle)
            elif settings.get("master_enabled") and settings.get("scheduled_enabled"):
                occurrence["scheduled_alarm"] = True
                self._start(occurrence, cycle)

        scheduled_disabled = playback_kind == "scheduled" and not (
            settings.get("master_enabled") and settings.get("scheduled_enabled")
        )
        occurrence_left_ringing = (
            (playing or worker_alive)
            and not standalone
            and (not active or phase != "ringing" or current != key)
        )
        if scheduled_disabled or occurrence_left_ringing:
            self.stop_playback(
                reason=(
                    "scheduled-audio-disabled"
                    if scheduled_disabled
                    else "alarm-left-ringing-state"
                )
            )

    def _monitor(self) -> None:
        while not self.monitor_stop.wait(0.25):
            try:
                self.reconcile_scheduler_audio()
            except Exception as exc:
                with self.lock:
                    self.state["last_error"] = f"Could not reconcile scheduled alarm audio: {exc}"

    def diagnostics(self) -> dict[str, Any]:
        payload = deepcopy(super().diagnostics())
        settings = self.settings()
        scheduled_enabled = bool(
            settings.get("master_enabled") and settings.get("scheduled_enabled")
        )
        payload["settings"] = settings
        payload["scheduled_playback_enabled"] = scheduled_enabled
        payload["scheduled_policy"] = {
            "requires_master_switch": True,
            "requires_scheduled_switch": True,
            "visual_tests_require_explicit_arm": True,
            "shared_pcm": settings.get("alsa_device"),
            "volume_cap_percent": settings.get("scheduled_volume_cap_percent"),
        }
        payload["safety_message"] = (
            "Scheduled alarms may make sound through the shared alarm PCM. Snooze, "
            "Dismiss, disabling either safety switch, or leaving the ringing phase "
            "stops playback immediately."
            if scheduled_enabled
            else "Alarm tests remain available behind the master switch; ordinary "
            "scheduled alarms remain silent until the second switch is enabled."
        )
        return payload

    def status(self) -> dict[str, Any]:
        status = deepcopy(super().status())
        settings = self.settings()
        status["scheduled_playback_enabled"] = bool(
            settings.get("master_enabled") and settings.get("scheduled_enabled")
        )
        status.setdefault("playback_kind", None)
        return status


def promote_scheduled_alarm_audio(dashboard: Any) -> ScheduledAlarmAudioManager:
    """Install scheduled playback before application-state providers are built."""
    existing = getattr(dashboard, "alarm_audio", None)
    if isinstance(existing, ScheduledAlarmAudioManager):
        return existing

    # main.load_config and its settings endpoint resolve this global at request
    # time, so promotion upgrades config normalisation without duplicating routes.
    dashboard.normalise_audio_settings = normalise_audio_settings
    manager = ScheduledAlarmAudioManager(
        dashboard.load_config,
        dashboard.alarm_tone_manifest,
        dashboard.alarm_scheduler.status,
        dashboard.ALARM_AUDIO_RUNTIME_PATH,
    )
    dashboard.alarm_audio = manager

    app = dashboard.app

    def api_alarm_audio_settings_scheduled():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "Audio settings must be a JSON object."}), 400

        current = dashboard.load_config().get("alarm_audio", {})
        settings = normalise_audio_settings({**current, **payload})
        raw_config = dashboard.core.load_json(dashboard.core.CONFIG_PATH, {})
        raw_config["alarm_audio"] = settings
        try:
            dashboard.core.save_json(dashboard.core.CONFIG_PATH, raw_config)
        except OSError as exc:
            return jsonify({"ok": False, "error": f"Could not save alarm audio settings: {exc}"}), 500

        if not settings.get("master_enabled"):
            manager.stop_playback(reason="master-audio-lock-enabled", restore=True)
            manager.disarm_occurrence()
        elif not settings.get("scheduled_enabled") and manager.status().get("playback_kind") == "scheduled":
            manager.stop_playback(reason="scheduled-audio-disabled", restore=True)

        response = dashboard.audio_payload()
        if settings.get("scheduled_enabled"):
            response["message"] = (
                "Scheduled alarm audio enabled through the shared alarm mixer. "
                "Normal enabled alarms may now make sound."
            )
        elif settings.get("master_enabled"):
            response["message"] = "Alarm audio tests enabled; scheduled alarms remain silent."
        else:
            response["message"] = "Alarm audio locked. No alarm or test may make sound."
        return jsonify(response)

    app.view_functions["api_alarm_audio_settings"] = api_alarm_audio_settings_scheduled
    return manager
