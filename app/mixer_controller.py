from __future__ import annotations

import threading
import time
from copy import deepcopy
from datetime import datetime
from typing import Any, Callable


ConfigProvider = Callable[[], dict[str, Any]]
StatusProvider = Callable[[], dict[str, Any]]
VolumeCommand = Callable[[int], tuple[bool, str | None]]
NowProvider = Callable[[], datetime]
SleepProvider = Callable[[float], None]

DEFAULT_AIRPLAY_START_PERCENT = 60
DEFAULT_SENDER_WAIT_ATTEMPTS = 40
DEFAULT_SENDER_WAIT_SECONDS = 0.25


def _bounded_percent(value: Any, fallback: int = 50) -> int:
    try:
        parsed = int(round(float(value)))
    except (TypeError, ValueError):
        parsed = fallback
    return max(0, min(100, parsed))


def _reported_percent(remote: dict[str, Any]) -> int | None:
    value = remote.get("volume_percent")
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(100, round(numeric)))


def _default_now() -> datetime:
    return datetime.now().astimezone()


def _safe_status(provider: StatusProvider) -> dict[str, Any]:
    try:
        value = provider()
    except Exception as exc:
        return {"available": False, "error": str(exc)}
    return deepcopy(value) if isinstance(value, dict) else {
        "available": False,
        "error": "AirPlay status provider returned a non-object value.",
    }


class MixerController:
    """Own player-aware volume intent without changing the production audio graph.

    The first promoted responsibility is AirPlay sender volume. Starting volume is
    written at most once per sender session. The requested value remains effective
    while MPRIS is still reporting the pre-command baseline; a genuinely newer
    sender value supersedes it.
    """

    authority = "mixer-controller"

    def __init__(
        self,
        *,
        load_config: ConfigProvider,
        airplay_status: StatusProvider,
        set_airplay_volume: VolumeCommand,
        now_provider: NowProvider | None = None,
        sleep_provider: SleepProvider | None = None,
        sender_wait_attempts: int = DEFAULT_SENDER_WAIT_ATTEMPTS,
        sender_wait_seconds: float = DEFAULT_SENDER_WAIT_SECONDS,
    ) -> None:
        self._load_config = load_config
        self._airplay_status = airplay_status
        self._set_airplay_volume = set_airplay_volume
        self._now = now_provider or _default_now
        self._sleep = sleep_provider or time.sleep
        self._sender_wait_attempts = max(1, int(sender_wait_attempts))
        self._sender_wait_seconds = max(0.01, float(sender_wait_seconds))
        self._lock = threading.RLock()
        self._generation = 0
        self._session_active = False
        self._runtime: dict[str, Any] = {
            "status": "waiting-for-session",
            "in_progress": False,
            "session_active": False,
            "target_percent": None,
            "requested_percent": None,
            "observed_percent": None,
            "effective_percent": None,
            "state_source": "unavailable",
            "request_active": False,
            "baseline_percent": None,
            "command_count": 0,
            "last_attempt_at": None,
            "last_applied_at": None,
            "last_confirmed_at": None,
            "last_error": None,
            "reason": None,
        }

    def _timestamp(self) -> str:
        return self._now().isoformat(timespec="milliseconds")

    def defaults(self) -> dict[str, Any]:
        config = self._load_config()
        airplay = config.get("airplay") if isinstance(config.get("airplay"), dict) else {}
        return {
            "default_volume_percent": _bounded_percent(
                airplay.get("default_volume_percent"),
                DEFAULT_AIRPLAY_START_PERCENT,
            ),
            "apply_default_volume_on_start": airplay.get("apply_default_volume_on_start", True) is not False,
        }

    def _update(self, **updates: Any) -> None:
        with self._lock:
            self._runtime.update(updates)

    def _current_generation(self) -> int:
        with self._lock:
            return self._generation

    def _new_generation(self) -> int:
        with self._lock:
            self._generation += 1
            return self._generation

    def _resolve_remote(self, remote: dict[str, Any]) -> dict[str, Any]:
        observed = _reported_percent(remote)
        available = remote.get("available") is True
        now = self._timestamp()

        with self._lock:
            runtime = self._runtime
            runtime["observed_percent"] = observed
            runtime["session_active"] = self._session_active
            requested = runtime.get("requested_percent")
            baseline = runtime.get("baseline_percent")
            request_active = runtime.get("request_active") is True

            if not available:
                effective = None
                source = "sender-unavailable"
            elif request_active and isinstance(requested, int):
                if observed is not None and abs(observed - requested) <= 1:
                    runtime["request_active"] = False
                    runtime["status"] = "confirmed"
                    runtime["in_progress"] = False
                    runtime["last_confirmed_at"] = runtime.get("last_confirmed_at") or now
                    runtime["last_error"] = None
                    effective = observed
                    source = "sender-confirmed"
                elif (
                    observed is not None
                    and isinstance(baseline, int)
                    and abs(observed - baseline) > 1
                ):
                    runtime["request_active"] = False
                    runtime["status"] = "sender-overrode"
                    runtime["in_progress"] = False
                    effective = observed
                    source = "sender-observed-newer"
                else:
                    effective = requested
                    source = "controller-request"
            else:
                effective = observed
                source = "sender-observed" if observed is not None else "sender-unreported"

            runtime["effective_percent"] = effective
            runtime["state_source"] = source
            snapshot = deepcopy(runtime)

        return {
            "id": "airplay",
            "label": "AirPlay",
            "available": available,
            "percent": effective,
            "effective_percent": effective,
            "observed_percent": observed,
            "requested_percent": snapshot.get("requested_percent"),
            "state_source": source,
            "command_status": snapshot.get("status"),
            "request_active": snapshot.get("request_active") is True,
            "target_percent": snapshot.get("target_percent"),
            "baseline_percent": snapshot.get("baseline_percent"),
            "command_count": snapshot.get("command_count", 0),
            "last_attempt_at": snapshot.get("last_attempt_at"),
            "last_applied_at": snapshot.get("last_applied_at"),
            "last_confirmed_at": snapshot.get("last_confirmed_at"),
            "last_error": snapshot.get("last_error"),
            "reason": snapshot.get("reason"),
            "remote": remote,
        }

    def airplay_snapshot(self) -> dict[str, Any]:
        return self._resolve_remote(_safe_status(self._airplay_status))

    def snapshot(self) -> dict[str, Any]:
        return {
            "authority": self.authority,
            "commands_enabled": True,
            "command_capabilities": {
                "airplay_sender_volume": True,
                "airplay_starting_volume_write_limit": 1,
                "service_restarts": False,
            },
            "defaults": self.defaults(),
            "channels": {
                "airplay": self.airplay_snapshot(),
            },
        }

    def application_status(self) -> dict[str, Any]:
        channel = self.airplay_snapshot()
        with self._lock:
            runtime = deepcopy(self._runtime)
        runtime.update(
            {
                "observed_percent": channel.get("observed_percent"),
                "effective_percent": channel.get("effective_percent"),
                "state_source": channel.get("state_source"),
                "session_active": self._session_active,
            }
        )
        return runtime

    def _apply_starting_volume(self, generation: int, reason: str) -> str:
        defaults = self.defaults()
        target = defaults["default_volume_percent"]

        for _attempt in range(self._sender_wait_attempts):
            if generation != self._current_generation():
                return "cancelled"

            remote = _safe_status(self._airplay_status)
            if remote.get("available") is True:
                baseline = _reported_percent(remote)
                self._update(
                    status="applying",
                    in_progress=True,
                    target_percent=target,
                    observed_percent=baseline,
                    baseline_percent=baseline,
                    last_attempt_at=self._timestamp(),
                    last_error=None,
                    reason=reason,
                )
                ok, error = self._set_airplay_volume(target)
                if generation != self._current_generation():
                    return "cancelled"
                with self._lock:
                    self._runtime["command_count"] = int(self._runtime.get("command_count") or 0) + 1
                    self._runtime.update(
                        {
                            "status": "requested" if ok else "failed",
                            "in_progress": False,
                            "requested_percent": target if ok else None,
                            "request_active": bool(ok),
                            "last_applied_at": self._timestamp() if ok else None,
                            "last_error": error,
                        }
                    )
                return "requested" if ok else "failed"

            self._update(status="waiting-for-remote", in_progress=True, last_error=remote.get("error"))
            self._sleep(self._sender_wait_seconds)

        self._update(
            status="timed-out",
            in_progress=False,
            last_error="The AirPlay sender did not become available for one starting-volume command.",
        )
        return "timed-out"

    def start_airplay_session(self, reason: str = "session-start", *, background: bool = True) -> str:
        defaults = self.defaults()
        force = reason == "settings-save"
        with self._lock:
            if self._session_active and not force:
                self._runtime.update(
                    {
                        "status": self._runtime.get("status") or "observing",
                        "reason": "session-resume-no-volume-reset",
                    }
                )
                return "already-active"
            self._session_active = True
            generation = self._new_generation()
            self._runtime.update(
                {
                    "status": "waiting-for-remote" if defaults["apply_default_volume_on_start"] else "disabled",
                    "in_progress": defaults["apply_default_volume_on_start"],
                    "session_active": True,
                    "target_percent": defaults["default_volume_percent"],
                    "requested_percent": None,
                    "request_active": False,
                    "baseline_percent": None,
                    "command_count": 0,
                    "last_attempt_at": None,
                    "last_applied_at": None,
                    "last_confirmed_at": None,
                    "last_error": None,
                    "reason": reason,
                }
            )

        if not defaults["apply_default_volume_on_start"]:
            return "disabled"
        if not background:
            return self._apply_starting_volume(generation, reason)

        threading.Thread(
            target=self._apply_starting_volume,
            args=(generation, reason),
            name="mixer-controller-airplay-start",
            daemon=True,
        ).start()
        return "scheduled"

    def end_airplay_session(self, reason: str = "session-ended") -> None:
        self._new_generation()
        defaults = self.defaults()
        with self._lock:
            self._session_active = False
            self._runtime.update(
                {
                    "status": "waiting-for-session" if defaults["apply_default_volume_on_start"] else "disabled",
                    "in_progress": False,
                    "session_active": False,
                    "target_percent": defaults["default_volume_percent"],
                    "requested_percent": None,
                    "request_active": False,
                    "baseline_percent": None,
                    "last_error": None,
                    "reason": reason,
                }
            )

    def set_airplay_percent(self, percent: Any, *, reason: str = "pi-slider") -> dict[str, Any]:
        level = _bounded_percent(percent, -1)
        try:
            numeric = float(percent)
        except (TypeError, ValueError):
            raise ValueError("AirPlay volume must be from 0 to 100 percent.") from None
        if not 0 <= numeric <= 100:
            raise ValueError("AirPlay volume must be from 0 to 100 percent.")

        remote = _safe_status(self._airplay_status)
        if remote.get("available") is not True:
            raise ValueError("AirPlay volume is available only while a sender is connected.")

        generation = self._new_generation()
        baseline = _reported_percent(remote)
        self._update(
            status="applying",
            in_progress=True,
            session_active=True,
            target_percent=level,
            observed_percent=baseline,
            baseline_percent=baseline,
            requested_percent=None,
            request_active=False,
            last_attempt_at=self._timestamp(),
            last_error=None,
            reason=reason,
        )
        ok, error = self._set_airplay_volume(level)
        if generation != self._current_generation():
            raise ValueError("AirPlay volume command was superseded by a newer request.")
        with self._lock:
            self._session_active = True
            self._runtime["command_count"] = int(self._runtime.get("command_count") or 0) + 1
            self._runtime.update(
                {
                    "status": "requested" if ok else "failed",
                    "in_progress": False,
                    "requested_percent": level if ok else None,
                    "request_active": bool(ok),
                    "last_applied_at": self._timestamp() if ok else None,
                    "last_error": error,
                }
            )
        if not ok:
            raise ValueError(error or "Could not change AirPlay volume.")
        return self.airplay_snapshot()
