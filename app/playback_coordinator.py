from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable


StatusProvider = Callable[[], dict[str, Any]]
ConfigProvider = Callable[[], dict[str, Any]]
StateProvider = Callable[[dict[str, Any]], dict[str, Any]]


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


class PlaybackCoordinator:
    """Build the authoritative playback snapshot without issuing commands.

    This first stage is deliberately observational. Existing Shairport/Plexamp
    hooks continue to perform handoffs while the coordinator proves that it can
    describe the appliance consistently. Command ownership will be transferred
    only after its state model has passed physical regression tests.
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
    ) -> None:
        self._load_config = load_config
        self._load_state = load_state
        self._plexamp_status = plexamp_status
        self._airplay_status = airplay_status
        self._alarm_status = alarm_status
        self._alarm_audio_status = alarm_audio_status

    def snapshot(self) -> dict[str, Any]:
        config = self._load_config()
        stored = self._load_state(config)

        plexamp_raw = _safe_status(self._plexamp_status, "Plexamp")
        airplay_remote = _safe_status(self._airplay_status, "AirPlay")
        alarm = _safe_status(self._alarm_status, "Alarm scheduler")
        alarm_audio = _safe_status(self._alarm_audio_status, "Alarm audio")

        stored_airplay = _dict(stored.get("airplay"))
        airplay_connected = stored_airplay.get("active") is True
        remote_state = _text(airplay_remote.get("playback_status"))
        if not airplay_connected:
            airplay_state = "disconnected"
        elif remote_state in {"playing", "paused", "stopped"}:
            airplay_state = remote_state
        else:
            airplay_state = "connected"

        plexamp_state = _text(plexamp_raw.get("playback_state"))
        if plexamp_raw.get("available") is False and plexamp_state == "unknown":
            plexamp_state = "unavailable"

        alarm_screen_required = alarm.get("screen_required") is True
        alarm_playing = alarm_audio.get("playback_active") is True
        alarm_active = alarm_screen_required or alarm_playing

        if alarm_active:
            active_source = "alarm"
        elif airplay_connected:
            # A paused-but-connected AirPlay sender owns the deliberate hold.
            active_source = "airplay"
        elif plexamp_state == "playing":
            active_source = "plexamp"
        else:
            active_source = "none"

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

        return {
            "authority": "observer",
            "commands_enabled": False,
            "active_source": active_source,
            "current_screen": current_screen,
            "recommended_screen": recommended_screen,
            "screen_in_sync": current_screen == recommended_screen,
            "policy": {
                "priority": ["alarm", "newest-explicit-source", "held-airplay", "idle"],
                "airplay_pause_hold_seconds": 600,
                "service_restarts_for_handoffs": False,
            },
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
                    "started_at": stored_airplay.get("started_at"),
                    "ended_at": stored_airplay.get("ended_at"),
                    "metadata": _dict(stored_airplay.get("metadata")),
                    "error": airplay_remote.get("error"),
                    "observed": airplay_remote,
                },
                "alarm": {
                    "active": alarm_active,
                    "screen_required": alarm_screen_required,
                    "playback_active": alarm_playing,
                    "scheduler": alarm,
                    "audio": alarm_audio,
                },
            },
        }
