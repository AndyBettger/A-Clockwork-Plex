from __future__ import annotations

from datetime import timedelta
from typing import Any

from flask import jsonify, request

try:
    from .input_activity import LinuxInputActivityMonitor
    from .playback_coordinator import PlaybackCoordinator, _text
    from .screen_projection import (
        IDLE_RETURN_SCREENS,
        MANUAL_LEASE_SCREENS,
        PLAYBACK_SOURCES,
        ScreenProjectionController,
    )
except ImportError:  # Supports direct execution imports.
    from input_activity import LinuxInputActivityMonitor
    from playback_coordinator import PlaybackCoordinator, _text
    from screen_projection import (
        IDLE_RETURN_SCREENS,
        MANUAL_LEASE_SCREENS,
        PLAYBACK_SOURCES,
        ScreenProjectionController,
    )


class ActivityAwareScreenProjectionController(ScreenProjectionController):
    """Let fresh playback activity interrupt a lease without duplicating policy.

    A lease survives an already-active source. It yields when a different source
    becomes active or when the same source begins a new playback generation, such
    as an NFC-created Plexamp queue or an AirPlay pause/resume transition.
    """

    authority = "screen-projection-owner"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._lease_activity_token: str | None = None

    @staticmethod
    def _source_activity_token(playback: dict[str, Any], active_source: str) -> str | None:
        activity = playback.get("playback_activity")
        if isinstance(activity, dict) and str(activity.get("source") or "none") == active_source:
            token = str(activity.get("token") or "").strip()
            if token:
                return token

        sources = playback.get("sources") if isinstance(playback.get("sources"), dict) else {}
        source = sources.get(active_source) if isinstance(sources.get(active_source), dict) else {}
        token = str(source.get("activity_token") or "").strip()
        return token or None

    def _clear_manual_lease(self, reason: str | None = None) -> None:
        super()._clear_manual_lease(reason)
        self._lease_activity_token = None

    def set_idle_return_mode(self, mode: Any) -> str:
        with self._lock:
            self._idle_return_mode = self._normalise_idle_mode(mode, self._configured_idle_mode())
            return self._idle_return_mode

    def interaction(
        self,
        surface: Any,
        *,
        source: Any = "browser-interaction",
        manual: bool = False,
        visible_surface: Any = None,
    ) -> dict[str, Any]:
        screen = self._normalise_screen(surface, "clock")
        now = self._now()
        timeout = self._timeout_seconds()
        playback = self._playback_snapshot()
        active_source = self._normalise_audio_source(playback.get("active_source"))
        activity_token = self._source_activity_token(playback, active_source)

        with self._lock:
            ignored = not manual and self._manual_surface is not None and screen != self._manual_surface
            if not ignored:
                self._sequence += 1
                self._last_activity_at = now
                self._last_interaction_source = str(source or "browser-interaction")
                if manual and screen in MANUAL_LEASE_SCREENS:
                    self._manual_surface = screen
                    self._lease_started_at = now
                    self._lease_until = now + timedelta(seconds=timeout)
                    self._lease_audio_source = active_source
                    self._lease_activity_token = activity_token
                    self._last_lease_end_reason = None
                elif self._manual_surface == screen:
                    self._lease_until = now + timedelta(seconds=timeout)

        return self.snapshot(visible_surface, playback_snapshot=playback)

    def _lease_snapshot(
        self,
        current_screen: str,
        active_source: str,
        activity_token: str | None,
    ) -> dict[str, Any]:
        now = self._now()
        with self._lock:
            manual_surface = self._manual_surface
            started_at = self._lease_started_at
            until = self._lease_until
            audio_source_at_start = self._lease_audio_source
            activity_token_at_start = self._lease_activity_token
            last_activity = self._last_activity_at
            source = self._last_interaction_source
            sequence = self._sequence

            if until is not None and now >= until:
                self._clear_manual_lease("timeout")
            elif (
                manual_surface is not None
                and active_source in PLAYBACK_SOURCES
                and active_source != audio_source_at_start
            ):
                previous = audio_source_at_start or "none"
                self._clear_manual_lease(f"audio-source-changed:{previous}->{active_source}")
            elif (
                manual_surface is not None
                and active_source in PLAYBACK_SOURCES
                and active_source == audio_source_at_start
                and activity_token_at_start
                and activity_token
                and activity_token != activity_token_at_start
            ):
                self._clear_manual_lease(f"playback-activity-changed:{active_source}")

            manual_surface = self._manual_surface
            started_at = self._lease_started_at
            until = self._lease_until
            audio_source_at_start = self._lease_audio_source
            activity_token_at_start = self._lease_activity_token
            last_end_reason = self._last_lease_end_reason

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
            "audio_source_at_start": audio_source_at_start,
            "activity_token_at_start": activity_token_at_start,
            "current_activity_token": activity_token,
            "last_end_reason": last_end_reason,
            "started_at": started_at.isoformat(timespec="milliseconds") if started_at else None,
            "until": until.isoformat(timespec="milliseconds") if until else None,
            "remaining_seconds": remaining,
            "last_activity_at": last_activity.isoformat(timespec="milliseconds"),
            "idle_remaining_seconds": idle_remaining,
            "last_interaction_source": source,
        }

    def snapshot(
        self,
        visible_surface: Any = None,
        *,
        playback_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        config = self._load_config()
        stored = self._load_state(config)
        playback = playback_snapshot if isinstance(playback_snapshot, dict) else self._playback_snapshot()
        current_screen = self._normalise_screen(playback.get("current_screen") or stored.get("mode"), "clock")
        visible_screen = self._normalise_screen(visible_surface, current_screen)
        input_activity = self._adopt_input_activity(current_screen)
        active_source = self._normalise_audio_source(playback.get("active_source"))
        activity_token = self._source_activity_token(playback, active_source)
        sources = playback.get("sources") if isinstance(playback.get("sources"), dict) else {}
        alarm = sources.get("alarm") if isinstance(sources.get("alarm"), dict) else {}
        alarm_screen_required = alarm.get("screen_required") is True
        lease = self._lease_snapshot(current_screen, active_source, activity_token)
        now = self._now()

        with self._lock:
            idle_mode = self._idle_return_mode or self._configured_idle_mode()
            last_activity = self._last_activity_at
            last_applied_at = self._last_applied_at
            last_applied_screen = self._last_applied_screen
            last_error = self._last_error

        idle_elapsed = (now - last_activity).total_seconds() >= self._timeout_seconds()
        if alarm_screen_required:
            recommended_screen = "alarm"
            reason = "alarm-screen-required"
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
        should_present = recommended_screen != visible_screen
        return {
            "authority": self.authority,
            "available": True,
            "screen_projection": True,
            "current_screen": current_screen,
            "visible_surface": visible_screen,
            "recommended_screen": recommended_screen,
            "decision_reason": reason,
            "logical_screen_in_sync": not should_apply,
            "presentation_in_sync": not should_present,
            "screen_in_sync": not should_apply and not should_present,
            "should_apply": should_apply,
            "should_present": should_present,
            "active_source": active_source,
            "playback_activity_token": activity_token,
            "idle_timeout_seconds": self._timeout_seconds(),
            "idle_return_mode": self._normalise_idle_mode(idle_mode, self._configured_idle_mode()),
            "lease": lease,
            "input_activity": input_activity,
            "last_applied_at": last_applied_at.isoformat(timespec="milliseconds") if last_applied_at else None,
            "last_applied_screen": last_applied_screen,
            "last_error": last_error,
        }


def register_activity_screen_projection(app: Any, hub: Any, dashboard: Any) -> ActivityAwareScreenProjectionController:
    """Register the final activity-aware screen authority and its compact API."""
    existing = hub.service("screen")
    if isinstance(existing, ActivityAwareScreenProjectionController):
        return existing

    playback = hub.service("playback")
    if not isinstance(playback, PlaybackCoordinator):
        raise RuntimeError("PlaybackCoordinator is unavailable for screen projection.")

    input_monitor = LinuxInputActivityMonitor()
    controller = ActivityAwareScreenProjectionController(
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
                return jsonify({
                    "ok": True,
                    "screen": controller.snapshot(request.args.get("visible_surface")),
                })

            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                return jsonify({"ok": False, "error": "Screen request must be a JSON object."}), 400
            if "idle_return_mode" in payload:
                controller.set_idle_return_mode(payload.get("idle_return_mode"))
            visible_surface = payload.get("visible_surface")
            action = _text(payload.get("action"), "state")
            if action in {"state", "preferences"}:
                state = controller.snapshot(visible_surface)
            elif action == "open":
                state = controller.interaction(
                    payload.get("surface", "plexamp"),
                    source=payload.get("source", "manual-screen-open"),
                    manual=True,
                    visible_surface=visible_surface,
                )
            elif action == "interaction":
                state = controller.interaction(
                    payload.get("surface", "clock"),
                    source=payload.get("source", "browser-interaction"),
                    visible_surface=visible_surface,
                )
            elif action == "release":
                state = controller.release(reason=payload.get("source", "browser-release"))
            elif action == "apply":
                state = controller.apply(visible_surface)
            else:
                return jsonify({"ok": False, "error": f"Unsupported screen action: {action}"}), 400
            return jsonify({"ok": True, "screen": state})

    return controller
