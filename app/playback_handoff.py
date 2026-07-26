from __future__ import annotations

import threading
import urllib.error
import urllib.request
from copy import deepcopy
from typing import Any, Callable

try:
    from .playback_coordinator import _safe_status, _text
    from .playback_navigation import NavigationTransportPlaybackCoordinator
except ImportError:  # Supports direct execution imports.
    from playback_coordinator import _safe_status, _text
    from playback_navigation import NavigationTransportPlaybackCoordinator


PlexampPause = Callable[[], tuple[bool, str | None]]


class AirPlayTakeoverPlaybackCoordinator(NavigationTransportPlaybackCoordinator):
    """Own the one-way AirPlay-start takeover of an already-playing Plexamp."""

    authority = "airplay-takeover-owner"

    def __init__(self, *, plexamp_pause: PlexampPause, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._plexamp_pause = plexamp_pause
        self._handoff_lock = threading.RLock()
        self._airplay_playing_latched = False
        self._handoff_sequence = 0
        self._handoff_runtime: dict[str, Any] = {
            "sequence": 0,
            "direction": "airplay-to-plexamp",
            "status": "idle",
            "trigger": None,
            "requested_at": None,
            "accepted_at": None,
            "completed_at": None,
            "plexamp_before": None,
            "plexamp_after": None,
            "command_count": 0,
            "completion_policy": "plexamp-observation",
            "screen_policy": "preserve-open-plexamp-surface",
            "last_error": None,
        }

    def handoff_snapshot(self) -> dict[str, Any]:
        with self._handoff_lock:
            return deepcopy(self._handoff_runtime)

    def _update_handoff(self, **updates: Any) -> dict[str, Any]:
        with self._handoff_lock:
            self._handoff_runtime.update(updates)
            return deepcopy(self._handoff_runtime)

    def _start_handoff(self, *, trigger: str, plexamp_state: str) -> dict[str, Any]:
        with self._handoff_lock:
            self._handoff_sequence += 1
            command_count = int(self._handoff_runtime.get("command_count") or 0)
            self._handoff_runtime = {
                "sequence": self._handoff_sequence,
                "direction": "airplay-to-plexamp",
                "status": "requested",
                "trigger": trigger,
                "requested_at": self._timestamp(),
                "accepted_at": None,
                "completed_at": None,
                "plexamp_before": plexamp_state,
                "plexamp_after": None,
                "command_count": command_count,
                "completion_policy": "plexamp-observation",
                "screen_policy": "preserve-open-plexamp-surface",
                "last_error": None,
            }
            return deepcopy(self._handoff_runtime)

    def _reconcile_airplay_takeover(self, playback: dict[str, Any] | None = None) -> str:
        state = playback if isinstance(playback, dict) else super().snapshot()
        sources = state.get("sources") if isinstance(state.get("sources"), dict) else {}
        airplay = sources.get("airplay") if isinstance(sources.get("airplay"), dict) else {}
        plexamp = sources.get("plexamp") if isinstance(sources.get("plexamp"), dict) else {}
        airplay_playing = airplay.get("connected") is True and _text(airplay.get("state"), "unknown") == "playing"
        plexamp_state = _text(plexamp.get("state"), "unknown")

        with self._handoff_lock:
            if not airplay_playing:
                self._airplay_playing_latched = False
                return "idle"

            if self._airplay_playing_latched:
                if self._handoff_runtime.get("status") == "accepted-awaiting-observation" and plexamp_state != "playing":
                    self._handoff_runtime.update(
                        {
                            "status": "confirmed",
                            "completed_at": self._timestamp(),
                            "plexamp_after": plexamp_state,
                            "last_error": None,
                        }
                    )
                    return "confirmed"
                return "waiting" if self._handoff_runtime.get("status") == "accepted-awaiting-observation" else "idle"

            self._airplay_playing_latched = True

        trigger = str(airplay.get("state_source") or "coordinator-playing-observation")
        self._start_handoff(trigger=trigger, plexamp_state=plexamp_state)

        if plexamp_state != "playing":
            self._update_handoff(
                status="not-needed",
                completed_at=self._timestamp(),
                plexamp_after=plexamp_state,
                last_error=None,
            )
            return "not-needed"

        self._update_handoff(status="executing")
        ok, error = self._plexamp_pause()
        if not ok:
            self._update_handoff(
                status="failed",
                completed_at=self._timestamp(),
                plexamp_after=plexamp_state,
                last_error=error or "Plexamp pause command failed.",
            )
            return "failed"

        with self._handoff_lock:
            self._handoff_runtime["command_count"] = int(self._handoff_runtime.get("command_count") or 0) + 1

        after = _safe_status(self._plexamp_status, "Plexamp")
        after_state = _text(after.get("playback_state"), "unknown")
        confirmed = after_state != "playing"
        self._update_handoff(
            status="confirmed" if confirmed else "accepted-awaiting-observation",
            accepted_at=self._timestamp(),
            completed_at=self._timestamp() if confirmed else None,
            plexamp_after=after_state,
            last_error=None,
        )
        return "confirmed" if confirmed else "accepted"

    def record_event(self, source: str, event: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        item = super().record_event(source, event, details)
        if _text(source, "") == "airplay":
            self._reconcile_airplay_takeover(super().snapshot())
        return item

    def reconcile_once(self) -> str:
        parent_result = super().reconcile_once()
        handoff_result = self._reconcile_airplay_takeover(super().snapshot())
        return parent_result if parent_result != "idle" else handoff_result

    def snapshot(self) -> dict[str, Any]:
        payload = super().snapshot()
        self._reconcile_airplay_takeover(payload)
        payload["authority"] = self.authority
        capabilities = payload.setdefault("command_capabilities", {})
        capabilities.update(
            {
                "airplay_to_plexamp_handoff": True,
                "plexamp_to_airplay_handoff": False,
                "screen_projection": False,
                "preserve_open_plexamp_surface": True,
                "service_restarts": False,
            }
        )
        handoffs = payload.setdefault("handoffs", {})
        handoffs["airplay_to_plexamp"] = self.handoff_snapshot()
        return payload


def _install_screen_preserving_airplay_start(app: Any, dashboard: Any) -> None:
    """Keep an explicitly open Plexamp surface visible when AirPlay starts."""

    current = app.view_functions.get("api_airplay_start")
    if current is None or getattr(current, "_acp_preserves_plexamp_screen", False):
        return

    def airplay_start_preserving_plexamp(*args: Any, **kwargs: Any):
        before = dashboard.load_state(dashboard.load_config())
        preserve_plexamp = _text(before.get("mode"), "clock") == "plexamp"
        response = current(*args, **kwargs)
        if preserve_plexamp:
            dashboard.set_mode("plexamp")
        return response

    airplay_start_preserving_plexamp._acp_preserves_plexamp_screen = True  # type: ignore[attr-defined]
    app.view_functions["api_airplay_start"] = airplay_start_preserving_plexamp


def _remove_page_open_handoff(app: Any, dashboard: Any) -> None:
    """Opening Plexamp is screen intent only and must not arm source arbitration."""

    current = app.view_functions.get("plexamp")
    original = getattr(dashboard, "plexamp", None)
    if current is not None and getattr(current, "_acp_airplay_handoff_wrapped", False) and callable(original):
        app.view_functions["plexamp"] = original


def promote_airplay_takeover(hub: Any, dashboard: Any) -> AirPlayTakeoverPlaybackCoordinator:
    """Promote coordinator-owned AirPlay→Plexamp pause and retire page-open intent."""

    existing = hub.service("playback")
    if isinstance(existing, AirPlayTakeoverPlaybackCoordinator):
        return existing
    if not isinstance(existing, NavigationTransportPlaybackCoordinator):
        raise RuntimeError("AirPlay navigation coordinator is unavailable for handoff promotion.")

    def pause_plexamp() -> tuple[bool, str | None]:
        config = dashboard.load_config()
        plexamp = config.get("plexamp") if isinstance(config.get("plexamp"), dict) else {}
        base_url = str(plexamp.get("url", "http://localhost:32500")).rstrip("/")
        pause_url = str(plexamp.get("pause_url", f"{base_url}/player/playback/pause"))
        request_object = urllib.request.Request(pause_url, headers={"Accept": "*/*"})
        try:
            with urllib.request.urlopen(request_object, timeout=2.0) as response:
                response.read(1)
        except (OSError, TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            return False, str(exc)
        return True, None

    promoted = AirPlayTakeoverPlaybackCoordinator(
        load_config=existing._load_config,
        load_state=existing._load_state,
        plexamp_status=existing._plexamp_status,
        airplay_status=existing._airplay_status,
        alarm_status=existing._alarm_status,
        alarm_audio_status=existing._alarm_audio_status,
        event_journal=existing._events,
        runtime_path=existing._runtime_store.path,
        airplay_hold_seconds=existing._airplay_hold_seconds,
        reconcile_seconds=existing._reconcile_seconds,
        hold_completion=existing._hold_completion,
        now_provider=existing._now,
        airplay_command=existing._airplay_command,
        command_verify_seconds=existing._command_verify_seconds,
        plexamp_pause=pause_plexamp,
    )

    promoted._command_sequence = existing._command_sequence
    promoted._command_runtime = existing.command_snapshot()
    promoted._navigation_sequence = existing._navigation_sequence
    promoted._navigation_runtime = existing.navigation_snapshot()

    _remove_page_open_handoff(dashboard.app, dashboard)
    _install_screen_preserving_airplay_start(dashboard.app, dashboard)
    hub.register_service("playback", promoted)
    hub.register_provider("playback", promoted.snapshot)
    return promoted
