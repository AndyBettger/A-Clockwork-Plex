from __future__ import annotations

from typing import Any

from flask import jsonify, request


def register_scheduled_alarm_status_api(dashboard: Any) -> None:
    """Make user-facing alarm status endpoints reflect promoted audio policy."""

    def audio_state() -> dict[str, Any]:
        value = dashboard.alarm_audio.status()
        return value if isinstance(value, dict) else {}

    def playback_enabled(audio: dict[str, Any]) -> bool:
        return bool(audio.get("scheduled_playback_enabled"))

    def api_alarm_active_scheduled():
        status = dashboard.alarm_scheduler.status()
        active = status.get("active_occurrence")
        labels = dashboard.tone_labels()
        tone_id = None
        if isinstance(active, dict):
            source = active.get("source") if isinstance(active.get("source"), dict) else {}
            tone_id = source.get("tone_id")
        audio = audio_state()
        return jsonify(
            {
                "ok": True,
                "active": active,
                "screen_required": status.get("screen_required", False),
                "snoozed_until": status.get("snoozed_until"),
                "seconds_until_snooze_end": status.get("seconds_until_snooze_end"),
                "tone_label": labels.get(str(tone_id), str(tone_id or "Local tone")),
                "playback_enabled": playback_enabled(audio),
                "scheduler": status,
                "audio": audio,
            }
        )

    def scheduler_payload_scheduled() -> dict[str, Any]:
        status = dashboard.alarm_scheduler.status()
        audio = audio_state()
        return {
            "ok": True,
            "scheduler": status,
            "scheduler_active": status.get("running") is True,
            "playback_enabled": playback_enabled(audio),
            "audio": audio,
        }

    def api_alarm_scheduler_scheduled():
        if request.method == "POST":
            status = dashboard.alarm_scheduler.recalculate()
            audio = audio_state()
            enabled = playback_enabled(audio)
            return jsonify(
                {
                    "ok": True,
                    "message": (
                        "Alarm runtime recalculated. Scheduled audio is enabled."
                        if enabled
                        else "Alarm runtime recalculated. Scheduled audio remains locked."
                    ),
                    "scheduler": status,
                    "scheduler_active": status.get("running") is True,
                    "playback_enabled": enabled,
                    "audio": audio,
                }
            )
        return jsonify(scheduler_payload_scheduled())

    dashboard.scheduler_payload = scheduler_payload_scheduled
    dashboard.app.view_functions["api_alarm_active"] = api_alarm_active_scheduled
    dashboard.app.view_functions["api_alarm_scheduler"] = api_alarm_scheduler_scheduled
