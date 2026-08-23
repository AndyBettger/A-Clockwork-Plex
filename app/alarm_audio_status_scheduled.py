from __future__ import annotations

from copy import deepcopy
from typing import Any

from flask import jsonify, request


def scheduled_playback_enabled(audio: dict[str, Any]) -> bool:
    return bool(audio.get("scheduled_playback_enabled"))


def project_scheduler_status(
    status: dict[str, Any] | None,
    audio: dict[str, Any] | None,
) -> dict[str, Any]:
    """Project promoted audio policy onto the scheduler's public status.

    ActiveAlarmScheduler owns clock, occurrence, Snooze and Dismiss state. It
    deliberately does not own an audio player, so its internal playback flag is
    always false. User-facing endpoints must replace that implementation detail
    with the promoted ScheduledAlarmAudioManager truth.
    """

    projected = deepcopy(status) if isinstance(status, dict) else {}
    audio_status = audio if isinstance(audio, dict) else {}
    settings = (
        audio_status.get("settings")
        if isinstance(audio_status.get("settings"), dict)
        else {}
    )
    enabled = scheduled_playback_enabled(audio_status)

    projected["playback_enabled"] = enabled
    projected["playback_owner"] = "scheduled-alarm-audio-manager"
    projected["playback_policy"] = "two-key-safety-gate"
    projected["playback_lockout_reason"] = None

    if not enabled:
        if not settings.get("master_enabled"):
            projected["playback_lockout_reason"] = (
                "Alarm sound is locked by the master safety switch."
            )
        elif not settings.get("scheduled_enabled"):
            projected["playback_lockout_reason"] = (
                "Scheduled alarm sound is locked by its second safety switch."
            )
        else:
            projected["playback_lockout_reason"] = (
                "Scheduled alarm sound is unavailable because the promoted audio "
                "manager is not ready."
            )

    return projected


def register_scheduled_alarm_status_api(dashboard: Any) -> None:
    """Make user-facing alarm status endpoints reflect promoted audio policy."""

    def audio_state() -> dict[str, Any]:
        value = dashboard.alarm_audio.status()
        return value if isinstance(value, dict) else {}

    def scheduler_and_audio() -> tuple[dict[str, Any], dict[str, Any]]:
        audio = audio_state()
        status = project_scheduler_status(dashboard.alarm_scheduler.status(), audio)
        return status, audio

    def api_alarm_active_scheduled():
        status, audio = scheduler_and_audio()
        active = status.get("active_occurrence")
        labels = dashboard.tone_labels()
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
                "playback_enabled": scheduled_playback_enabled(audio),
                "scheduler": status,
                "audio": audio,
            }
        )

    def scheduler_payload_scheduled() -> dict[str, Any]:
        status, audio = scheduler_and_audio()
        return {
            "ok": True,
            "scheduler": status,
            "scheduler_active": status.get("running") is True,
            "playback_enabled": scheduled_playback_enabled(audio),
            "audio": audio,
        }

    def api_alarm_scheduler_scheduled():
        if request.method == "POST":
            audio = audio_state()
            status = project_scheduler_status(
                dashboard.alarm_scheduler.recalculate(),
                audio,
            )
            enabled = scheduled_playback_enabled(audio)
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
