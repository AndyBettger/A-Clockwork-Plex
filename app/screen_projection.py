from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import Any, Callable

from flask import jsonify, request

try:
    from .input_activity import LinuxInputActivityMonitor
    from .playback_coordinator import PlaybackCoordinator, _text
except ImportError:  # Supports direct execution imports.
    from input_activity import LinuxInputActivityMonitor
    from playback_coordinator import PlaybackCoordinator, _text


NowProvider = Callable[[], datetime]
StateProvider = Callable[[dict[str, Any]], dict[str, Any]]
ConfigProvider = Callable[[], dict[str, Any]]
ModeSetter = Callable[[str], Any]
InputActivityProvider = Callable[[], dict[str, Any]]

VALID_SCREENS = {"clock", "weather", "airplay", "plexamp", "settings", "alarm"}
MANUAL_LEASE_SCREENS = VALID_SCREENS - {"alarm"}
IDLE_RETURN_SCREENS = {"clock", "weather", "airplay", "plexamp"}
DEFAULT_IDLE_TIMEOUT_SECONDS = 180
MIN_IDLE_TIMEOUT_SECONDS = 5
MAX_IDLE_TIMEOUT_SECONDS = 86400


def _default_now() -> datetime:
    return datetime.now().astimezone()


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed


class ScreenProjectionController:
    """Own screen recommendation while browser and local input report interaction."""

    authority = "screen-projection-owner"

    def __init__(
        self,
        *,
        load_config: ConfigProvider,
        load_state: StateProvider,
        playback: PlaybackCoordinator,
        set_mode: ModeSetter,
        input_activity: InputActivityProvider | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._load_config = load_config
        self._load_state = load_state
        self._playback = playback
        self._set_mode = set_mode
        self._input_activity = input_activity
        self._now = now_provider or _default_now
        self._lock = threading.RLock()
        now = self._now()
        self._sequence = 0
        self._last_activity_at = now
        self._manual_surface: str | None = None
        self._lease_started_at: datetime | None = None
        self._lease_until: datetime | None = None
        self._last_interaction_source: str | None = "controller-start"
        self._idle_return_mode: str | None = None
        self._last_applied_at: datetime | None = None
        self._last_applied_screen: str | None = None
        self._last_error: str | None = None
        self._last_input_sequence = 0
        initial_input = self._read_input_activity()
        try:
            self._last_input_sequence = int(initial_input.get("sequence") or 0)
        except (TypeError, ValueError):
            self._last_input_sequence = 0

    def _timeout_seconds(self) -> int:
        config = self._load_config()
        dashboard = config.get("dashboard") if isinstance(config.get("dashboard"), dict) else {}
        try:
            seconds = int(dashboard.get("idle_timeout_seconds", DEFAULT_IDLE_TIMEOUT_SECONDS))
        except (TypeError, ValueError):
            seconds = DEFAULT_IDLE_TIMEOUT_SECONDS
        return max(MIN_IDLE_TIMEOUT_SECONDS, min(MAX_IDLE_TIMEOUT_SECONDS, seconds))

    @staticmethod
    def _normalise_screen(value: Any, fallback: str = "clock") -> str:
        screen = _text(value, fallback)
        return screen if screen in VALID_SCREENS else fallback

    @staticmethod
    def _normalise_idle_mode(value: Any, fallback: str = "clock") -> str:
        mode = _text(value, fallback)
        return mode if mode in IDLE_RETURN_SCREENS else fallback

    def _configured_idle_mode(self) -> str:
        config = self._load_config()
        dashboard = config.get("dashboard") if isinstance(config.get("dashboard"), dict) else {}
        return self._normalise_idle_mode(dashboard.get("default_mode"), "clock")

    def _clear_manual_lease(self) -> None:
        self._manual_surface = None
        self._lease_started_at = None
        self._lease_until = None

    def _read_input_activity(self) -> dict[str, Any]:
        if not callable(self._input_activity):
            return {
                "authority": "linux-input-activity-monitor",
                "running": False,
                "available": False,
                "sequence": 0,
                "last_activity_at": None,
                "last_event": None,
                "last_error": "Local input monitor is not registered.",
            }
        try:
            payload = self._input_activity()
        except Exception as exc:
            return {
                "authority": "linux-input-activity-monitor",
                "running": False,
                "available": False,
                "sequence": self._last_input_sequence,
                "last_activity_at": None,
                "last_event": None,
                "last_error": str(exc),
            }
        return payload if isinstance(payload, dict) else {}

    def _adopt_input_activity(self, current_screen: str) -> dict[str, Any]:
        activity = self._read_input_activity()
        try:
            sequence = int(activity.get("sequence") or 0)
        except (TypeError, ValueError):
            sequence = 0
        occurred_at = _parse_datetime(activity.get("last_activity_at"))
        with self._lock:
            if sequence <= self._last_input_sequence:
                return activity
            self._last_input_sequence = sequence
            if occurred_at is None or occurred_at < self._last_activity_at:
                return activity

            event = activity.get("last_event") if isinstance(activity.get("last_event"), dict) else {}
            device = str(event.get("device") or "local-input")
            kind = str(event.get("kind") or "event")
            self._sequence += 1
            self._last_activity_at = occurred_at
            self._last_interaction_source = f"linux-input:{kind}:{device}"
            if self._manual_surface == current_screen:
                self._lease_until = occurred_at + timedelta(seconds=self._timeout_seconds())
        return activity

    def set_idle_return_mode(self, mode: Any) -> dict[str, Any]:
        with self._lock:
            self._idle_return_mode = self._normalise_idle_mode(mode, self._configured_idle_mode())
        return self.snapshot()

    def interaction(self, surface: Any, *, source: Any = "browser-interaction", manual: bool = False) -> dict[str, Any]:
        screen = self._normalise_screen(surface, "clock")
        now = self._now()
        timeout = self._timeout_seconds()
        ignored = False
        with self._lock:
            if not manual and self._manual_surface is not None and screen != self._manual_surface:
                ignored = True
            else:
                self._sequence += 1
                self._last_activity_at = now
                self._last_interaction_source = str(source or "browser-interaction")
                if manual and screen in MANUAL_LEASE_SCREENS:
                    self._manual_surface = screen
                    self._lease_started_at = now
                    self._lease_until = now + timedelta(seconds=timeout)
                elif self._manual_surface == screen:
                    self._lease_until = now + timedelta(seconds=timeout)
        if ignored:
            return self.snapshot()
        return self.snapshot()

    def release(self, *, reason: Any = "browser-release") -> dict[str, Any]:
        with self._lock:
            self._sequence += 1
            self._clear_manual_lease()
            self._last_interaction_source = str(reason or "browser-release")
        return self.snapshot()

    def _lease_snapshot(self, current_screen: str) -> dict[str, Any]:
        now = self._now()
        with self._lock:
            manual_surface = self._manual_surface
            started_at = self._lease_started_at
            until = self._lease_until
            last_activity = self._last_activity_at
            source = self._last_interaction_source
            sequence = self._sequence
            if until is not None and now >= until:
                self._clear_manual_lease()
                manual_surface = None
                started_at = None
                until = None
        active = bool(
            manual_surface in MANUAL_LEASE_SCREENS
            and until is not None
            and now < until
        )
        remaining = None if until is None else max(0, int((until - now).total_seconds() + 0.999))
        idle_remaining = max(
            0,
            int((last_activity + timedelta(seconds=self._timeout_seconds()) - now).total_seconds() + 0.999),
        )
        return {
            "sequence": sequence,
            "manual_surface": manual_surface,
            "active": active,
            "surface_in_sync": manual_surface is None or manual_surface == current_screen,
            "started_at": started_at.isoformat(timespec="milliseconds") if started_at else None,
            "until": until.isoformat(timespec="milliseconds") if until else None,
            "remaining_seconds": remaining,
            "last_activity_at": last_activity.isoformat(timespec="milliseconds"),
            "idle_remaining_seconds": idle_remaining,
            "last_interaction_source": source,
        }

    def snapshot(self) -> dict[str, Any]:
        config = self._load_config()
        stored = self._load_state(config)
        playback = self._playback.snapshot()
        current_screen = self._normalise_screen(playback.get("current_screen") or stored.get("mode"), "clock")
        input_activity = self._adopt_input_activity(current_screen)
        active_source = _text(playback.get("active_source"), "none")
        sources = playback.get("sources") if isinstance(playback.get("sources"), dict) else {}
        alarm = sources.get("alarm") if isinstance(sources.get("alarm"), dict) else {}
        alarm_active = alarm.get("active") is True
        lease = self._lease_snapshot(current_screen)
        now = self._now()

        with self._lock:
            idle_mode = self._idle_return_mode or self._configured_idle_mode()
            last_activity = self._last_activity_at
            last_applied_at = self._last_applied_at
            last_applied_screen = self._last_applied_screen
            last_error = self._last_error

        idle_elapsed = (now - last_activity).total_seconds() >= self._timeout_seconds()
        if alarm_active:
            recommended_screen = "alarm"
            reason = "alarm-active"
        elif lease.get("active"):
            recommended_screen = str(lease.get("manual_surface") or current_screen)
            reason = f"manual-{recommended_screen}-lease"
        elif active_source == "plexamp":
            recommended_screen = "plexamp"
            reason = "plexamp-owns-audio"
        elif active_source == "airplay":
            recommended_screen = "airplay"
            reason = "airplay-owns-audio"
        elif not idle_elapsed:
            recommended_screen = current_screen
            reason = "recent-browser-activity"
        else:
            recommended_screen = self._normalise_idle_mode(idle_mode, self._configured_idle_mode())
            reason = "configured-idle-return"

        should_apply = recommended_screen != current_screen
        return {
            "authority": self.authority,
            "available": True,
            "screen_projection": True,
            "current_screen": current_screen,
            "recommended_screen": recommended_screen,
            "decision_reason": reason,
            "screen_in_sync": not should_apply,
            "should_apply": should_apply,
            "active_source": active_source,
            "idle_timeout_seconds": self._timeout_seconds(),
            "idle_return_mode": self._normalise_idle_mode(idle_mode, self._configured_idle_mode()),
            "lease": lease,
            "input_activity": input_activity,
            "last_applied_at": last_applied_at.isoformat(timespec="milliseconds") if last_applied_at else None,
            "last_applied_screen": last_applied_screen,
            "last_error": last_error,
        }

    def apply(self) -> dict[str, Any]:
        before = self.snapshot()
        target = str(before.get("recommended_screen") or "clock")
        if not before.get("should_apply"):
            return before
        try:
            self._set_mode(target)
        except Exception as exc:
            with self._lock:
                self._last_error = str(exc)
            failed = self.snapshot()
            failed["apply_failed"] = True
            return failed

        with self._lock:
            self._last_applied_at = self._now()
            self._last_applied_screen = target
            self._last_error = None
            if self._manual_surface is not None and target != self._manual_surface:
                self._clear_manual_lease()
        applied = self.snapshot()
        applied["applied_screen"] = target
        return applied


def register_screen_projection(app: Any, hub: Any, dashboard: Any) -> ScreenProjectionController:
    """Register screen projection after playback promotion and before API registration."""

    existing = hub.service("screen")
    if isinstance(existing, ScreenProjectionController):
        return existing

    playback = hub.service("playback")
    if not isinstance(playback, PlaybackCoordinator):
        raise RuntimeError("PlaybackCoordinator is unavailable for screen projection.")

    input_monitor = LinuxInputActivityMonitor()
    controller = ScreenProjectionController(
        load_config=dashboard.load_config,
        load_state=dashboard.load_state,
        playback=playback,
        set_mode=dashboard.set_mode,
        input_activity=input_monitor.snapshot,
    )
    setattr(playback, "_screen_projection_enabled", True)
    hub.register_service("input_activity", input_monitor)
    hub.register_provider("input_activity", input_monitor.snapshot)
    hub.register_service("screen", controller)
    hub.register_provider("screen", controller.snapshot)

    if "api_screen_projection" not in app.view_functions:
        @app.route("/api/screen/state", methods=["GET", "POST"])
        def api_screen_projection():
            if request.method == "GET":
                return jsonify({"ok": True, "screen": controller.snapshot()})

            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                return jsonify({"ok": False, "error": "Screen request must be a JSON object."}), 400
            if "idle_return_mode" in payload:
                controller.set_idle_return_mode(payload.get("idle_return_mode"))
            action = _text(payload.get("action"), "state")
            if action == "state" or action == "preferences":
                state = controller.snapshot()
            elif action == "open":
                state = controller.interaction(
                    payload.get("surface", "plexamp"),
                    source=payload.get("source", "manual-screen-open"),
                    manual=True,
                )
            elif action == "interaction":
                state = controller.interaction(
                    payload.get("surface", "clock"),
                    source=payload.get("source", "browser-interaction"),
                )
            elif action == "release":
                state = controller.release(reason=payload.get("source", "browser-release"))
            elif action == "apply":
                state = controller.apply()
            else:
                return jsonify({"ok": False, "error": f"Unsupported screen action: {action}"}), 400
            return jsonify({"ok": True, "screen": state})

    return controller
