from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any

from flask import jsonify

AIRPLAY_EVENT_FRESH_SECONDS = 60
AIRPLAY_PLAYING_EVENTS = {
    "resume",
    "play_resume",
    "play_start",
    "active_state_start",
    "metadata_start",
}
AIRPLAY_PAUSED_EVENTS = {"pause"}
AIRPLAY_STOPPED_EVENTS = {"play_end", "active_state_end"}


def _parse_dashboard_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _event_playback_status(airplay: dict[str, Any]) -> str:
    metadata = airplay.get("metadata") if isinstance(airplay.get("metadata"), dict) else {}
    event = str(metadata.get("last_event") or "").strip().lower()
    if event in AIRPLAY_PAUSED_EVENTS:
        return "paused"
    if event in AIRPLAY_STOPPED_EVENTS:
        return "stopped"
    if event in AIRPLAY_PLAYING_EVENTS:
        return "playing"
    return ""


def _event_is_fresh(airplay: dict[str, Any], now: datetime | None = None) -> bool:
    metadata = airplay.get("metadata") if isinstance(airplay.get("metadata"), dict) else {}
    updated_at = _parse_dashboard_time(metadata.get("updated_at"))
    if updated_at is None:
        return False
    current = now or (datetime.now(updated_at.tzinfo) if updated_at.tzinfo else datetime.now())
    if current.tzinfo is None and updated_at.tzinfo is not None:
        current = current.replace(tzinfo=updated_at.tzinfo)
    elif current.tzinfo is not None and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=current.tzinfo)
    age = (current - updated_at).total_seconds()
    return -5 <= age <= AIRPLAY_EVENT_FRESH_SECONDS


def _active_started_after_metadata_event(airplay: dict[str, Any]) -> bool:
    if airplay.get("active") is not True:
        return False
    metadata = airplay.get("metadata") if isinstance(airplay.get("metadata"), dict) else {}
    started_at = _parse_dashboard_time(airplay.get("started_at"))
    updated_at = _parse_dashboard_time(metadata.get("updated_at"))
    if started_at is None or updated_at is None:
        return False
    if started_at.tzinfo is None and updated_at.tzinfo is not None:
        started_at = started_at.replace(tzinfo=updated_at.tzinfo)
    elif started_at.tzinfo is not None and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=started_at.tzinfo)
    return started_at >= updated_at - timedelta(milliseconds=500)


def resolve_airplay_remote(
    airplay: dict[str, Any],
    remote: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Add one effective playback state without discarding raw MPRIS evidence."""
    resolved = deepcopy(remote) if isinstance(remote, dict) else {}
    raw_status = str(resolved.get("playback_status") or "").strip().lower()
    event_status = _event_playback_status(airplay)
    fresh_event = _event_is_fresh(airplay, now)

    if _active_started_after_metadata_event(airplay) and event_status in {"paused", "stopped"}:
        effective = "playing"
        source = "newer-session-start"
    elif fresh_event and event_status in {"paused", "stopped"}:
        effective = "paused"
        source = "fresh-metadata-event"
    elif raw_status == "playing":
        effective = "playing"
        source = "mpris"
    elif fresh_event and event_status == "playing":
        effective = "playing"
        source = "fresh-metadata-event"
    else:
        effective = event_status or raw_status or "unknown"
        source = "metadata-fallback" if event_status else "mpris"

    resolved["raw_playback_status"] = resolved.get("playback_status")
    resolved["effective_playback_status"] = effective
    resolved["playback_status_source"] = source
    return resolved


def _cancel_legacy_plexamp_handoff(audio_mixer: Any, reason: str) -> None:
    with audio_mixer._plexamp_handoff_lock:
        audio_mixer._plexamp_handoff_generation += 1
        audio_mixer._plexamp_handoff_runtime.update(
            {
                "status": "cancelled",
                "completed_at": audio_mixer._iso_now(),
                "method": reason,
                "last_error": None,
            }
        )


def _resolved_airplay_snapshot(audio_mixer: Any) -> dict[str, Any]:
    """Read one effective AirPlay snapshot without depending on /api/status wrappers."""
    config = audio_mixer._dashboard_core.load_config()
    state = audio_mixer._dashboard_core.load_state(config)
    source = state.get("airplay") if isinstance(state.get("airplay"), dict) else {}
    airplay = deepcopy(source)
    remote = audio_mixer._dashboard_core.mpris_remote_status()
    airplay["remote"] = resolve_airplay_remote(airplay, remote)
    return airplay


def register_airplay_coordination(app: Any) -> None:
    """Install one authoritative AirPlay state resolver and generation boundary."""
    try:
        from . import audio_mixer
    except ImportError:  # Supports direct execution imports.
        import audio_mixer

    if not getattr(audio_mixer._arm_plexamp_handoff, "_acp_generation_guarded", False):
        legacy_arm = audio_mixer._arm_plexamp_handoff

        def guarded_arm() -> None:
            # Even a not-needed arm must invalidate an older worker. Previously the
            # early return left a stale Plexamp-wins thread alive across AirPlay resume.
            _cancel_legacy_plexamp_handoff(audio_mixer, "plexamp-handoff-rearmed")
            legacy_arm()

        guarded_arm._acp_generation_guarded = True  # type: ignore[attr-defined]
        audio_mixer._arm_plexamp_handoff = guarded_arm

    if "api_airplay_effective_state" not in app.view_functions:
        @app.route("/api/airplay/state")
        def api_airplay_effective_state():
            return jsonify({"ok": True, "airplay": _resolved_airplay_snapshot(audio_mixer)})

    status_view = app.view_functions.get("api_status")
    if status_view and not getattr(status_view, "_acp_airplay_state_resolved", False):
        def resolved_status():
            response = status_view()
            payload = response.get_json(silent=True) or {}
            state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
            airplay = state.get("airplay") if isinstance(state.get("airplay"), dict) else {}
            remote = airplay.get("remote") if isinstance(airplay.get("remote"), dict) else {}
            airplay["remote"] = resolve_airplay_remote(airplay, remote)
            state["airplay"] = airplay
            payload["state"] = state
            return jsonify(payload)

        resolved_status._acp_airplay_state_resolved = True  # type: ignore[attr-defined]
        app.view_functions["api_status"] = resolved_status

    start_view = app.view_functions.get("api_airplay_start")
    if start_view and not getattr(start_view, "_acp_handoff_cancelled", False):
        def coordinated_airplay_start():
            # AirPlay START is the newest user intent. Cancel every Plexamp-wins
            # worker before publishing the new session state.
            _cancel_legacy_plexamp_handoff(audio_mixer, "airplay-start-won")
            return start_view()

        coordinated_airplay_start._acp_handoff_cancelled = True  # type: ignore[attr-defined]
        app.view_functions["api_airplay_start"] = coordinated_airplay_start
