from __future__ import annotations

import json
import math
import threading
from collections import deque
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

try:
    from .airplay_coordination import resolve_airplay_remote
except ImportError:  # Supports direct execution imports.
    from airplay_coordination import resolve_airplay_remote


StatusProvider = Callable[[], dict[str, Any]]
ConfigProvider = Callable[[], dict[str, Any]]
StateProvider = Callable[[dict[str, Any]], dict[str, Any]]
NowProvider = Callable[[], datetime]
HoldCompletion = Callable[[str], None]

EVENTS_BY_SOURCE = {
    "airplay": {"connected", "playing", "paused", "disconnected", "hold_expired"},
    "plexamp": {"playing", "paused", "stopped", "unavailable"},
    "alarm": {"active", "idle"},
    "dashboard": {"screen_changed"},
}
EXPLICIT_EVENT_FRESH_SECONDS = 90
DEFAULT_AIRPLAY_HOLD_SECONDS = 600
DEFAULT_RECONCILE_SECONDS = 2.0
RUNTIME_SCHEMA_VERSION = 1


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


def _default_now() -> datetime:
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


def _event_is_fresh(
    event: dict[str, Any] | None,
    *,
    seconds: int = EXPLICIT_EVENT_FRESH_SECONDS,
    now: datetime | None = None,
) -> bool:
    if not isinstance(event, dict):
        return False
    occurred_at = _parse_time(event.get("at"))
    if occurred_at is None:
        return False
    current = now or _default_now()
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=current.tzinfo)
    age = (current - occurred_at).total_seconds()
    return -5 <= age <= seconds


def _summary(source: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: deepcopy(source.get(key)) for key in keys if key in source}


def _apply_airplay_event(event: dict[str, Any]) -> tuple[bool, str] | None:
    name = str(event.get("event") or "")
    if name in {"connected", "playing"}:
        return True, "playing" if name == "playing" else "connected"
    if name == "paused":
        return True, "paused"
    if name in {"disconnected", "hold_expired"}:
        return False, "disconnected"
    return None


def _default_runtime() -> dict[str, Any]:
    return {
        "schema_version": RUNTIME_SCHEMA_VERSION,
        "airplay": {
            "phase": "idle",
            "updated_at": None,
            "hold_started_at": None,
            "hold_until": None,
            "last_reason": None,
            "last_error": None,
        },
    }


class PlaybackRuntimeStore:
    """Small atomic store for deadlines that must survive dashboard restarts."""

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self._lock = threading.RLock()

    def load(self) -> dict[str, Any]:
        with self._lock:
            fallback = _default_runtime()
            if self.path is None or not self.path.exists():
                return fallback
            try:
                with self.path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
            except (OSError, json.JSONDecodeError):
                return fallback
            if not isinstance(payload, dict):
                return fallback
            airplay = payload.get("airplay")
            if not isinstance(airplay, dict):
                airplay = {}
            normalised = _default_runtime()
            normalised["airplay"].update(airplay)
            return normalised

    def save(self, payload: dict[str, Any]) -> None:
        if self.path is None:
            return
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            with temporary.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
            temporary.replace(self.path)


class PlaybackEventJournal:
    """Bounded, thread-safe playback event history for adapters and observations."""

    def __init__(self, *, maximum_events: int = 48, now_provider: NowProvider | None = None) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=max(8, int(maximum_events)))
        self._observed_signatures: dict[str, str] = {}
        self._sequence = 0
        self._lock = threading.RLock()
        self._now = now_provider or _default_now

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
                "at": self._now().isoformat(timespec="milliseconds"),
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

    def latest(self, source: str) -> dict[str, Any] | None:
        source_key = _text(source, "")
        with self._lock:
            for item in reversed(self._events):
                if item["source"] == source_key:
                    return deepcopy(item)
        return None

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
    """Own AirPlay lifecycle timing while source-control commands remain disabled."""

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
        runtime_path: Path | None = None,
        airplay_hold_seconds: int = DEFAULT_AIRPLAY_HOLD_SECONDS,
        reconcile_seconds: float = DEFAULT_RECONCILE_SECONDS,
        hold_completion: HoldCompletion | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._load_config = load_config
        self._load_state = load_state
        self._plexamp_status = plexamp_status
        self._airplay_status = airplay_status
        self._alarm_status = alarm_status
        self._alarm_audio_status = alarm_audio_status
        self._now = now_provider or _default_now
        self._events = event_journal or PlaybackEventJournal(now_provider=self._now)
        self._runtime_store = PlaybackRuntimeStore(runtime_path)
        self._runtime = self._runtime_store.load()
        self._runtime_lock = threading.RLock()
        self._airplay_hold_seconds = max(1, int(airplay_hold_seconds))
        self._reconcile_seconds = max(0.25, float(reconcile_seconds))
        self._hold_completion = hold_completion
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._worker: threading.Thread | None = None

    def _runtime_airplay(self) -> dict[str, Any]:
        with self._runtime_lock:
            airplay = self._runtime.get("airplay")
            return deepcopy(airplay) if isinstance(airplay, dict) else _default_runtime()["airplay"]

    def _save_airplay_runtime(
        self,
        *,
        phase: str,
        hold_started_at: str | None,
        hold_until: str | None,
        reason: str,
        error: str | None = None,
    ) -> None:
        with self._runtime_lock:
            self._runtime["schema_version"] = RUNTIME_SCHEMA_VERSION
            self._runtime["airplay"] = {
                "phase": phase,
                "updated_at": self._now().isoformat(timespec="milliseconds"),
                "hold_started_at": hold_started_at,
                "hold_until": hold_until,
                "last_reason": reason,
                "last_error": error,
            }
            payload = deepcopy(self._runtime)
        self._runtime_store.save(payload)
        self._wake_event.set()

    def _apply_airplay_runtime_event(self, event: str, *, reason: str) -> None:
        now = self._now()
        if event == "paused":
            hold_until = now + timedelta(seconds=self._airplay_hold_seconds)
            self._save_airplay_runtime(
                phase="holding",
                hold_started_at=now.isoformat(timespec="milliseconds"),
                hold_until=hold_until.isoformat(timespec="milliseconds"),
                reason=reason,
            )
        elif event in {"playing", "connected"}:
            self._save_airplay_runtime(
                phase="playing" if event == "playing" else "connected",
                hold_started_at=None,
                hold_until=None,
                reason=reason,
            )
        elif event in {"disconnected", "hold_expired"}:
            self._save_airplay_runtime(
                phase="disconnected" if event == "disconnected" else "expired",
                hold_started_at=None,
                hold_until=None,
                reason=reason,
            )

    def _record_event(
        self,
        source: str,
        event: str,
        details: dict[str, Any] | None,
        *,
        kind: str,
    ) -> dict[str, Any]:
        item = self._events.record(source, event, details, kind=kind)
        if item["source"] == "airplay":
            reason = str((details or {}).get("origin") or f"{kind}-{event}")
            self._apply_airplay_runtime_event(item["event"], reason=reason)
        return item

    def record_event(self, source: str, event: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._record_event(source, event, details, kind="explicit")

    def event_snapshot(self) -> dict[str, Any]:
        return self._events.snapshot()

    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop_event.clear()
        self._worker = threading.Thread(
            target=self._worker_loop,
            name="playback-coordinator",
            daemon=True,
        )
        self._worker.start()

    def shutdown(self, timeout: float = 3.0) -> None:
        self._stop_event.set()
        self._wake_event.set()
        worker = self._worker
        if worker and worker.is_alive():
            worker.join(timeout=max(0.1, timeout))

    def worker_status(self) -> dict[str, Any]:
        worker = self._worker
        return {
            "running": bool(worker and worker.is_alive()),
            "reconcile_seconds": self._reconcile_seconds,
        }

    def _finish_airplay_session(self, reason: str, *, success_phase: str) -> bool:
        if self._hold_completion is None:
            return True
        before = self._runtime_airplay()
        try:
            self._hold_completion(reason)
        except Exception as exc:
            self._save_airplay_runtime(
                phase="action_failed",
                hold_started_at=before.get("hold_started_at"),
                hold_until=before.get("hold_until"),
                reason=reason,
                error=str(exc),
            )
            return False
        self._save_airplay_runtime(
            phase=success_phase,
            hold_started_at=None,
            hold_until=None,
            reason=reason,
        )
        return True

    def _fresh_playing_transition_after_hold(self, stored_airplay: dict[str, Any], remote: dict[str, Any]) -> bool:
        runtime = self._runtime_airplay()
        hold_started = _parse_time(runtime.get("hold_started_at"))
        metadata = _dict(stored_airplay.get("metadata"))
        metadata_updated = _parse_time(metadata.get("updated_at"))
        if hold_started is None or metadata_updated is None or metadata_updated <= hold_started:
            return False
        resolved = resolve_airplay_remote(stored_airplay, remote, now=self._now())
        return (
            _text(resolved.get("effective_playback_status")) == "playing"
            and str(resolved.get("playback_status_source") or "") in {
                "fresh-metadata-event",
                "newer-session-start",
            }
        )

    def reconcile_once(self) -> str:
        runtime = self._runtime_airplay()
        if runtime.get("phase") == "action_failed":
            completed = self._finish_airplay_session(
                str(runtime.get("last_reason") or "retry-hold-completion"),
                success_phase="disconnected",
            )
            return "retry-completed" if completed else "retry-failed"
        if runtime.get("phase") != "holding":
            return "idle"

        config = self._load_config()
        stored = self._load_state(config)
        stored_airplay = _dict(stored.get("airplay"))
        remote = _safe_status(self._airplay_status, "AirPlay")

        if remote.get("available") is False:
            self._record_event(
                "airplay",
                "disconnected",
                {"origin": "coordinator-hold-monitor"},
                kind="coordinator",
            )
            self._finish_airplay_session(
                "sender-disconnected-during-hold",
                success_phase="disconnected",
            )
            return "disconnected"

        if self._fresh_playing_transition_after_hold(stored_airplay, remote):
            self._record_event(
                "airplay",
                "playing",
                {"origin": "coordinator-fresh-resume"},
                kind="coordinator",
            )
            return "resumed"

        hold_until = _parse_time(runtime.get("hold_until"))
        if hold_until is not None and self._now() >= hold_until:
            self._record_event(
                "airplay",
                "hold_expired",
                {"origin": "playback-coordinator", "hold_seconds": self._airplay_hold_seconds},
                kind="coordinator",
            )
            self._finish_airplay_session(
                "pause-hold-expired",
                success_phase="expired",
            )
            return "expired"

        return "holding"

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.reconcile_once()
            except Exception as exc:
                runtime = self._runtime_airplay()
                self._save_airplay_runtime(
                    phase=str(runtime.get("phase") or "unknown"),
                    hold_started_at=runtime.get("hold_started_at"),
                    hold_until=runtime.get("hold_until"),
                    reason="reconcile-error",
                    error=str(exc),
                )
            self._wake_event.wait(self._reconcile_seconds)
            self._wake_event.clear()

    def _hold_snapshot(self) -> dict[str, Any]:
        runtime = self._runtime_airplay()
        hold_until = _parse_time(runtime.get("hold_until"))
        remaining: int | None = None
        if hold_until is not None:
            remaining = max(0, math.ceil((hold_until - self._now()).total_seconds()))
        return {
            "owner": "playback-coordinator",
            "phase": runtime.get("phase"),
            "active": runtime.get("phase") in {"holding", "action_failed"},
            "started_at": runtime.get("hold_started_at"),
            "until": runtime.get("hold_until"),
            "remaining_seconds": remaining,
            "last_reason": runtime.get("last_reason"),
            "last_error": runtime.get("last_error"),
        }

    def snapshot(self) -> dict[str, Any]:
        config = self._load_config()
        stored = self._load_state(config)

        plexamp_raw = _safe_status(self._plexamp_status, "Plexamp")
        airplay_remote = _safe_status(self._airplay_status, "AirPlay")
        alarm = _safe_status(self._alarm_status, "Alarm scheduler")
        alarm_audio = _safe_status(self._alarm_audio_status, "Alarm audio")

        stored_airplay = _dict(stored.get("airplay"))
        resolved_airplay = resolve_airplay_remote(stored_airplay, airplay_remote, now=self._now())
        observer_connected = stored_airplay.get("active") is True
        observer_state = _text(resolved_airplay.get("effective_playback_status"), "connected")
        observer_source = str(resolved_airplay.get("playback_status_source") or "observer")
        latest_airplay = self._events.latest("airplay")
        runtime_airplay = self._runtime_airplay()

        airplay_connected = observer_connected
        airplay_state = observer_state if observer_connected else "disconnected"
        airplay_state_source = observer_source if observer_connected else "stored-session"

        if runtime_airplay.get("phase") in {"holding", "action_failed"}:
            airplay_connected = True
            airplay_state = "paused"
            airplay_state_source = "playback-coordinator-hold"
        elif observer_source in {"fresh-metadata-event", "newer-session-start"}:
            pass
        elif latest_airplay and latest_airplay.get("kind") in {"explicit", "coordinator"}:
            applied = _apply_airplay_event(latest_airplay)
            if applied is not None:
                airplay_connected, airplay_state = applied
                airplay_state_source = f"coordinator-{latest_airplay.get('kind')}-event"
        elif not observer_connected:
            airplay_connected = False
            airplay_state = "disconnected"
            airplay_state_source = "stored-session"
        elif latest_airplay and latest_airplay.get("event") == "paused":
            airplay_connected = True
            airplay_state = "paused"
            airplay_state_source = "coordinator-event-journal"

        plexamp_state = _text(plexamp_raw.get("playback_state"))
        if plexamp_raw.get("available") is False and plexamp_state == "unknown":
            plexamp_state = "unavailable"
        explicit_plexamp = self._events.latest_explicit("plexamp")
        if _event_is_fresh(explicit_plexamp, now=self._now()):
            plexamp_state = str(explicit_plexamp.get("event"))

        alarm_screen_required = alarm.get("screen_required") is True
        alarm_playing = alarm_audio.get("playback_active") is True
        alarm_active = alarm_screen_required or alarm_playing
        explicit_alarm = self._events.latest_explicit("alarm")
        if _event_is_fresh(explicit_alarm, now=self._now()):
            alarm_active = explicit_alarm.get("event") == "active"

        if alarm_active:
            active_source = "alarm"
            decision_reason = "alarm-active"
        elif airplay_connected:
            active_source = "airplay"
            decision_reason = (
                "airplay-pause-hold"
                if runtime_airplay.get("phase") in {"holding", "action_failed"}
                else "airplay-session-connected"
            )
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
            "authority": "airplay-hold-owner",
            "commands_enabled": False,
            "command_capabilities": {
                "source_control": False,
                "screen_return_on_hold_end": True,
            },
            "active_source": active_source,
            "decision_reason": decision_reason,
            "current_screen": current_screen,
            "recommended_screen": recommended_screen,
            "screen_in_sync": current_screen == recommended_screen,
            "worker": self.worker_status(),
            "policy": {
                "priority": ["alarm", "newest-explicit-source", "held-airplay", "idle"],
                "airplay_pause_hold_seconds": self._airplay_hold_seconds,
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
                    "hold": self._hold_snapshot(),
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
