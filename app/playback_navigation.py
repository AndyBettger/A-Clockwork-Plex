from __future__ import annotations

import threading
from copy import deepcopy
from typing import Any

try:
    from .playback_coordinator import _safe_status, _text
    from .playback_transport import TransportPlaybackCoordinator
except ImportError:  # Supports direct execution imports.
    from playback_coordinator import _safe_status, _text
    from playback_transport import TransportPlaybackCoordinator


NAVIGATION_ACTIONS = {"previous", "next"}


class NavigationTransportPlaybackCoordinator(TransportPlaybackCoordinator):
    """Add explicit AirPlay Previous/Next commands without inventing state confirmation."""

    authority = "airplay-transport-owner"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._navigation_lock = threading.RLock()
        self._navigation_sequence = 0
        self._navigation_runtime: dict[str, Any] = {
            "sequence": 0,
            "source": None,
            "action": None,
            "status": "idle",
            "requested_at": None,
            "accepted_at": None,
            "completed_at": None,
            "completion_policy": "adapter-acceptance",
            "observed_source": None,
            "last_error": None,
        }

    def navigation_snapshot(self) -> dict[str, Any]:
        with self._navigation_lock:
            return deepcopy(self._navigation_runtime)

    def _new_navigation_command(self, action: str) -> dict[str, Any]:
        with self._navigation_lock:
            self._navigation_sequence += 1
            self._navigation_runtime = {
                "sequence": self._navigation_sequence,
                "source": "airplay",
                "action": action,
                "status": "requested",
                "requested_at": self._timestamp(),
                "accepted_at": None,
                "completed_at": None,
                "completion_policy": "adapter-acceptance",
                "observed_source": None,
                "last_error": None,
            }
            return deepcopy(self._navigation_runtime)

    def _update_navigation_command(self, **updates: Any) -> dict[str, Any]:
        with self._navigation_lock:
            self._navigation_runtime.update(updates)
            return deepcopy(self._navigation_runtime)

    def command(self, source: Any, action: Any) -> dict[str, Any]:
        source_key = _text(source, "")
        action_key = _text(action, "")
        if action_key not in NAVIGATION_ACTIONS:
            return super().command(source_key, action_key)
        if source_key != "airplay":
            raise ValueError("Only AirPlay transport is promoted to PlaybackCoordinator.")

        playback = super().snapshot()
        current = playback.get("sources", {}).get("airplay", {})
        live_remote = _safe_status(self._airplay_status, "AirPlay")
        if current.get("connected") is not True or live_remote.get("available") is not True:
            raise ValueError("AirPlay navigation is available only while a sender is connected.")
        if live_remote.get("can_control") is False:
            raise ValueError("The connected AirPlay sender does not currently expose transport control.")

        command = self._new_navigation_command(action_key)
        self._update_navigation_command(status="executing")
        ok, error = self._airplay_command(action_key)
        if not ok:
            command = self._update_navigation_command(
                status="failed",
                completed_at=self._timestamp(),
                observed_source="mpris-adapter",
                last_error=error or f"AirPlay {action_key} command failed.",
            )
            raise RuntimeError(str(command.get("last_error")))

        command = self._update_navigation_command(
            status="accepted",
            accepted_at=self._timestamp(),
            completed_at=self._timestamp(),
            observed_source="mpris-adapter",
            last_error=None,
        )
        return {"ok": True, "command": command, "playback": self.snapshot()}

    def snapshot(self) -> dict[str, Any]:
        payload = super().snapshot()
        capabilities = payload.setdefault("command_capabilities", {})
        capabilities["airplay_navigation"] = True
        capabilities["airplay_actions"] = ["play", "pause", "previous", "next"]
        commands = payload.setdefault("commands", {})
        commands["airplay_navigation"] = self.navigation_snapshot()
        return payload


def promote_airplay_navigation(hub: Any, dashboard: Any) -> NavigationTransportPlaybackCoordinator:
    """Promote the existing AirPlay transport coordinator with Previous/Next commands."""

    existing = hub.service("playback")
    if isinstance(existing, NavigationTransportPlaybackCoordinator):
        return existing
    if not isinstance(existing, TransportPlaybackCoordinator):
        raise RuntimeError("AirPlay transport coordinator is unavailable for navigation promotion.")

    methods = {
        "play": "Play",
        "pause": "Pause",
        "previous": "Previous",
        "next": "Next",
    }

    def airplay_command(action: str) -> tuple[bool, str | None]:
        method = methods.get(action)
        if method is None:
            return False, f"Unsupported AirPlay transport action: {action}"
        return dashboard.mpris_call(method)

    promoted = NavigationTransportPlaybackCoordinator(
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
        airplay_command=airplay_command,
        command_verify_seconds=existing._command_verify_seconds,
    )
    hub.register_service("playback", promoted)
    hub.register_provider("playback", promoted.snapshot)
    return promoted
