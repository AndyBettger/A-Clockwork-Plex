from __future__ import annotations

import json
import threading
from collections import deque
from copy import deepcopy
from datetime import datetime
from typing import Any, Callable

try:
    from .airplay_coordination import resolve_airplay_remote
except ImportError:  # Supports direct execution imports.
    from airplay_coordination import resolve_airplay_remote


StatusProvider = Callable[[], dict[str, Any]]
ConfigProvider = Callable[[], dict[str, Any]]
StateProvider = Callable[[dict[str, Any]], dict[str, Any]]

EVENTS_BY_SOURCE = {
    "airplay": {"connected", "playing", "paused", "disconnected", "hold_expired"},
    "plexamp": {"playing", "paused", "stopped", "unavailable"},
    "alarm": {"active", "idle"},
    "dashboard": {"screen_changed"},
}
EXPLICIT_EVENT_FRESH_SECONDS = 90


def _dict(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _text(value: Any, fallback: str = "unknown") -> str:
    text = str(value or "").strip().lower()
    return text or fallback


def _safe_status(provider: StatusProvider, component: str) -> dict[str, Any]:
    try:
        value = provider()
    except Exception as exc:  # A failed observer must not take down the state hub.
        return {
            "available": False,
            "state": "unavailable",
            "error": f"{component} observer failed: {exc}",
        }
    if not isinstance(value, dict):
        return {
            "available": False,
            "state": "unavailable",
            "error": f"{component} observer returned a non-object value.",
        }
    return deepcopy(value)


def _now() -> datetime:
    return datetime.now().astimezone()


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.astimezone()


def _event_is_fresh(event: dict[str, Any] | None, *, seconds: int = EXPLICIT_EVENT_FRESH_SECONDS) -> bool:
    if not isinstance(event, dict):
        return False
    occurred_at = _parse_time(event.get("at"))
    if occurred_at is None:
        return False
    current = _now()
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=current.tzinfo)
    age = (current - occurred_at).total_seconds()
    return -5 <= age <= seconds


def _summary(source: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: deepcopy(source.get(key)) for key in keys if key in source}


class PlaybackEventJournal:
    """Bounded, thread-safe playback event history for adapters and observations."""

    def __init__(self, *, maximum_events: int = 48) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=max(8, int(maximum_events)))
        self._observed_signatures: dict[str, str] = {}
        self._sequence = 0
        self._lock = threading.RLock()

    def record(
        self,
        source: str,
        event: str,
        details: dict[str, Any] | None = None,
        *,
        kind: str = "explicit",
    ) -> dict[str, Any]:
        source_key = _text(source, "")
        event_key = _text(event, "")
        allowed = EVENTS_BY_SOURCE.get(source_key)
        if allowed is None or event_key not in allowed:
            raise ValueError(f"Unsupported playback event: {source_key}.{event_key}")
        if details is not None and not isinstance(details, dict):
            raise ValueError("Playback event details must be a JSON object.")

        with self._lock:
            self._sequence += 1
            item = {
                "sequence": self._sequence,
                "source": source_key,
                "event": event_key,
                "kind": _text(kind, "explicit"),
                "at": _now().isoformat(timespec="milliseconds"),
                "details": deepcopy(details or {}),
            }
            self._events.append(item)
            return deepcopy(item)

    def observe(self, source: str, event: str, details: dict[str, Any] | None = None) -> dict[str, Any] | None:
        signature = json.dumps(
            {"event": _text(event, ""), "details": details or {}},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        source_key = _text(source, "")
        with self._lock:
            if self._observed_signatures.get(source_key) == signature:
                return None
            self._observed_signatures[source_key] = signature
        return self.record(source_key, event, details, kind="observed")

    def latest_explicit(self, source: str) -> dict[str, Any] | None:
        source_key = _text(source, "")
        with self._lock:
            for item in reversed(self._events):
                if item["source"] == source_key and item["kind"] == "explicit":
                    return deepcopy(item)
        return None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            events = [deepcopy(item) for item in self._events]
            sequence = self._sequence
        return {
            "sequence": sequence,
            "last_event": events[-1] if events else None,
            "recent_events": events[-12:],
        }


class PlaybackCoordinator:
    """Describe playback from observations plus explicit source events.

    Stage two remains command-disabled. It accepts source events and resolves them
    against existing observers, but the established hooks still execute handoffs.
    """

    def __init__(
        self,
        *,
        load_config: ConfigProvider,
        load_state: StateProvider,
        plexamp_status: StatusProvider,
        airplay_status: StatusProvider,
        alarm_status: StatusProvider,
        alarm_audio_status: StatusProvider,
        event_journal: PlaybackEventJournal | None = None,
    ) -> None:
        self._load_config = load_config
        self._load_state = load_state
        self._plexamp_status = plexamp_status
        self._airplay_status = airplay_status
        self._alarm_status = alarm_status
        self._alarm_audio_status = alarm_audio_status
        self._events = event_journal or PlaybackEventJournal()

    def record_event(self, source: str, event: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._events.record(source, event, details, kind="explicit")

    def event_snapshot(self) -> dict[str, Any]:
        return self._events.snapshot()

    def snapshot(self) -> dict[str, Any]:
        config = self._load_config()
        stored = self._load_state(config)

        plexamp_raw = _safe_status(self._plexamp_status, "Plexamp")
        airplay_remote = _safe_status(self._airplay_status, "AirPlay")
        alarm = _safe_status(self._alarm_status, "Alarm scheduler")
        alarm_audio = _safe_status(self._alarm_audio_status, "Alarm audio")

        stored_airplay = _dict(stored.get("airplay"))
        resolved_airplay = resolve_airplay_remote(stored_airplay, airplay_remote)
        airplay_connected = stored_airplay.get("active") is True
        airplay_state = _text(resolved_airplay.get("effective_playback_status"), "connected")
        airplay_state_source = str(resolved_airplay.get("playback_status_source") or "observer")
        if not airplay_connected:
            airplay_state = "disconnected"
            airplay_state_source = "stored-session"

        explicit_airplay = self._events.latest_explicit("airplay")
        if _event_is_fresh(explicit_airplay):
            event = str(explicit_airplay.get("event"))
            if event in {"connected", "playing"}:
                airplay_connected = True
                airplay_state = "playing" if event == "playing" else "connected"
                airplay_state_source = "coordinator-event"
            elif event == "paused":
                airplay_connected = True
                airplay_state = "paused"
                airplay_state_source = "coordinator-event"
            elif event in {"disconnected", "hold_expired"}:
                airplay_connected = False
                airplay_state = "disconnected"
                airplay_state_source = "coordinator-event"

        plexamp_state = _text(plexamp_raw.get("playback_state"))
        if plexamp_raw.get("available") is False and plexamp_state == "unknown":
            plexamp_state = "unavailable"
        explicit_plexamp = self._events.latest_explicit("plexamp")
        if _event_is_fresh(explicit_plexamp):
            plexamp_state = str(explicit_plexamp.get("event"))

        alarm_screen_required = alarm.get("screen_required") is True
        alarm_playing = alarm_audio.get("playback_active") is True
        alarm_active = alarm_screen_required or alarm_playing
        explicit_alarm = self._events.latest_explicit("alarm")
        if _event_is_fresh(explicit_alarm):
            alarm_active = explicit_alarm.get("event") == "active"

        if alarm_active:
            active_source = "alarm"
            decision_reason = "alarm-active"
        elif airplay_connected:
            active_source = "airplay"
            decision_reason = "airplay-session-connected"
        elif plexamp_state == "playing":
            active_source = "plexamp"
            decision_reason = "plexamp-playing"
        else:
            active_source = "none"
            decision_reason = "idle-policy"

        dashboard = _dict(config.get("dashboard"))
        current_screen = _text(stored.get("mode"), "clock")
        idle_screen = _text(dashboard.get("default_mode"), "clock")
        if alarm_active:
            recommended_screen = "alarm"
        elif airplay_connected:
            recommended_screen = "airplay"
        elif plexamp_state == "playing":
            recommended_screen = "plexamp"
        else:
            recommended_screen = idle_screen

        airplay_event = "disconnected" if not airplay_connected else (
            airplay_state if airplay_state in {"playing", "paused"} else "connected"
        )
        plexamp_event = plexamp_state if plexamp_state in EVENTS_BY_SOURCE["plexamp"] else "unavailable"
        self._events.observe(
            "airplay",
            airplay_event,
            {"state": airplay_state, "state_source": airplay_state_source},
        )
        self._events.observe("plexamp", plexamp_event, {"state": plexamp_state})
        self._events.observe("alarm", "active" if alarm_active else "idle", {"active": alarm_active})
        self._events.observe("dashboard", "screen_changed", {"screen": current_screen})

        scheduler_summary = _summary(
            alarm,
            (
                "running",
                "thread_alive",
                "health",
                "active_phase",
                "screen_required",
                "next_occurrence",
                "snoozed_until",
                "last_error",
            ),
        )
        audio_summary = _summary(
            alarm_audio,
            ("manager_running", "worker_alive", "playback_active", "current_tone_label", "last_error"),
        )

        return {
            "authority": "event-assisted-observer",
            "commands_enabled": False,
            "active_source": active_source,
            "decision_reason": decision_reason,
            "current_screen": current_screen,
            "recommended_screen": recommended_screen,
            "screen_in_sync": current_screen == recommended_screen,
            "policy": {
                "priority": ["alarm", "newest-explicit-source", "held-airplay", "idle"],
                "airplay_pause_hold_seconds": 600,
                "service_restarts_for_handoffs": False,
            },
            "events": self._events.snapshot(),
            "sources": {
                "plexamp": {
                    "available": plexamp_raw.get("available") is True,
                    "state": plexamp_state,
                    "percent": plexamp_raw.get("percent"),
                    "error": plexamp_raw.get("error"),
                    "observed": plexamp_raw,
                },
                "airplay": {
                    "connected": airplay_connected,
                    "state": airplay_state,
                    "state_source": airplay_state_source,
                    "started_at": stored_airplay.get("started_at"),
                    "ended_at": stored_airplay.get("ended_at"),
                    "metadata": _dict(stored_airplay.get("metadata")),
                    "error": resolved_airplay.get("error"),
                    "observed": resolved_airplay,
                },
                "alarm": {
                    "active": alarm_active,
                    "screen_required": alarm_screen_required,
                    "playback_active": alarm_playing,
                    "scheduler": scheduler_summary,
                    "audio": audio_summary,
                },
            },
        }
