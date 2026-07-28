from __future__ import annotations

import urllib.error
import urllib.request
from typing import Any

try:
    from .playback_coordinator import PlaybackCoordinator
    from .playback_handoff import _install_screen_preserving_airplay_start
    from .playback_handoff_retention import RetainedBidirectionalHandoffCoordinator
except ImportError:  # Supports direct execution imports.
    from playback_coordinator import PlaybackCoordinator
    from playback_handoff import _install_screen_preserving_airplay_start
    from playback_handoff_retention import RetainedBidirectionalHandoffCoordinator


AIRPLAY_METHODS = {
    "play": "Play",
    "pause": "Pause",
    "previous": "Previous",
    "next": "Next",
}


def promote_playback_authority(hub: Any, dashboard: Any) -> RetainedBidirectionalHandoffCoordinator:
    """Replace the observational coordinator with the final production authority once."""

    existing = hub.service("playback")
    if isinstance(existing, RetainedBidirectionalHandoffCoordinator):
        return existing
    if not isinstance(existing, PlaybackCoordinator):
        raise RuntimeError("PlaybackCoordinator is unavailable for authority promotion.")

    def airplay_command(action: str) -> tuple[bool, str | None]:
        method = AIRPLAY_METHODS.get(str(action or "").strip().lower())
        if method is None:
            return False, f"Unsupported AirPlay transport action: {action}"
        return dashboard.mpris_call(method)

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

    authority = RetainedBidirectionalHandoffCoordinator(
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
        command_verify_seconds=20,
        plexamp_pause=pause_plexamp,
    )

    _install_screen_preserving_airplay_start(dashboard.app, dashboard)
    hub.register_service("playback", authority)
    hub.register_provider("playback", authority.snapshot)
    return authority
