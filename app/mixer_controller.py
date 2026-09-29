from __future__ import annotations

import threading
from copy import deepcopy
from typing import Any, Callable


StatusProvider = Callable[[], dict[str, Any]]
PlexampVolumeCommand = Callable[[int], dict[str, Any]]
MixerVolumeCommand = Callable[[str, int, bool], dict[str, Any]]

MIXER_CHANNELS = {"master", "plexamp", "airplay", "alarm"}
LIVE_CHANNELS = {"master", "plexamp", "airplay", "alarm"}
AIRPLAY_LIVE_MIXER_CHANNEL = "airplay_live"


def _validated_percent(value: Any, *, label: str) -> int:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be from 0 to 100 percent.") from None
    if not 0 <= numeric <= 100:
        raise ValueError(f"{label} must be from 0 to 100 percent.")
    return max(0, min(100, int(round(numeric))))


def _safe_status(provider: StatusProvider | None, label: str) -> dict[str, Any]:
    if provider is None:
        return {"available": False, "error": f"{label} provider is unavailable."}
    try:
        value = provider()
    except Exception as exc:
        return {"available": False, "error": str(exc)}
    return deepcopy(value) if isinstance(value, dict) else {
        "available": False,
        "error": f"{label} provider returned a non-object value.",
    }


def _channel(mixer: dict[str, Any], channel: str) -> dict[str, Any]:
    channels = mixer.get("channels") if isinstance(mixer.get("channels"), dict) else {}
    value = channels.get(channel)
    return deepcopy(value) if isinstance(value, dict) else {}


class MixerController:
    """Own the interface-facing audio control model.

    Plexamp retains its native player volume. AirPlay is deliberately receiver
    owned: Shairport ignores source attenuation and the ACP live fader controls
    a dedicated runtime ALSA softvol upstream of the persistent AirPlay trim.
    """

    authority = "mixer-controller"

    def __init__(
        self,
        *,
        airplay_status: StatusProvider,
        plexamp_status: StatusProvider | None = None,
        set_plexamp_volume: PlexampVolumeCommand | None = None,
        mixer_status: StatusProvider | None = None,
        set_mixer_volume: MixerVolumeCommand | None = None,
    ) -> None:
        self._airplay_status = airplay_status
        self._plexamp_status = plexamp_status
        self._set_plexamp_volume = set_plexamp_volume
        self._mixer_status = mixer_status
        self._set_mixer_volume = set_mixer_volume
        self._lock = threading.RLock()
        self._session_active = False

    def mixer_snapshot(self) -> dict[str, Any]:
        return _safe_status(self._mixer_status, "Shared ALSA mixer")

    def plexamp_snapshot(self, mixer: dict[str, Any] | None = None) -> dict[str, Any]:
        player = _safe_status(self._plexamp_status, "Plexamp volume")
        trim = _channel(mixer if isinstance(mixer, dict) else self.mixer_snapshot(), "plexamp")
        return {
            "id": "plexamp",
            "label": "Plexamp",
            **player,
            "source": player.get("source") or "plexamp-player",
            "detail": "Plexamp player volume; its Now Playing control should follow.",
            "trim": trim,
        }

    def airplay_snapshot(self, mixer: dict[str, Any] | None = None) -> dict[str, Any]:
        current_mixer = mixer if isinstance(mixer, dict) else self.mixer_snapshot()
        live = _channel(current_mixer, AIRPLAY_LIVE_MIXER_CHANNEL)
        trim = _channel(current_mixer, "airplay")
        remote = _safe_status(self._airplay_status, "AirPlay")
        sender_connected = remote.get("available") is True
        local_ready = live.get("available") is True and live.get("pcm_available") is True
        with self._lock:
            session_active = self._session_active
        percent = live.get("percent") if local_ready else None
        return {
            "id": "airplay",
            "label": "AirPlay",
            "available": bool(local_ready and (sender_connected or session_active)),
            "percent": percent,
            "effective_percent": percent,
            "state_source": "receiver-local-alsa" if local_ready else "receiver-local-unavailable",
            "source": "alsa-airplay-live",
            "detail": "Receiver-side AirPlay volume. Shairport source attenuation is ignored.",
            "sender_volume_ignored": True,
            "sender_connected": sender_connected,
            "sender_volume_percent": remote.get("volume_percent"),
            "sender_volume_db": remote.get("airplay_volume_db"),
            "remote": remote,
            "trim": trim,
            "live": live,
            "error": live.get("error") if not local_ready else None,
        }

    @staticmethod
    def _alsa_live_channel(channel: str, label: str, status: dict[str, Any], detail: str) -> dict[str, Any]:
        return {
            "id": channel,
            "label": label,
            "available": status.get("available") is True,
            "percent": status.get("percent"),
            "source": f"alsa-live-{channel}",
            "detail": detail,
            "trim": status,
            "error": status.get("error"),
        }

    def application_status(self, channel: dict[str, Any] | None = None) -> dict[str, Any]:
        airplay = channel if isinstance(channel, dict) else self.airplay_snapshot()
        with self._lock:
            active = self._session_active
        return {
            "status": "receiver-owned",
            "in_progress": False,
            "session_active": active,
            "effective_percent": airplay.get("effective_percent"),
            "state_source": airplay.get("state_source"),
            "last_error": airplay.get("error"),
        }

    def live_snapshot(self) -> dict[str, Any]:
        mixer = self.mixer_snapshot()
        master = _channel(mixer, "master")
        alarm = _channel(mixer, "alarm")
        plexamp = self.plexamp_snapshot(mixer)
        airplay = self.airplay_snapshot(mixer)
        return {
            "authority": self.authority,
            "available": mixer.get("available") is True,
            "mode": "receiver-owned-airplay",
            "channels": {
                "master": self._alsa_live_channel(
                    "master",
                    "Master",
                    master,
                    "Immediate output level; Settings stores the persistent default.",
                ),
                "plexamp": plexamp,
                "airplay": airplay,
                "alarm": self._alsa_live_channel(
                    "alarm",
                    "Alarm",
                    alarm,
                    "Immediate alarm ceiling; Settings stores the persistent default.",
                ),
            },
            "mixer": mixer,
            "error": mixer.get("error"),
        }

    def snapshot(self) -> dict[str, Any]:
        live = self.live_snapshot()
        return {
            **live,
            "commands_enabled": True,
            "command_capabilities": {
                "live_player_volume": ["plexamp"],
                "live_alsa_volume": ["master", "airplay", "alarm"],
                "alsa_trims": sorted(MIXER_CHANNELS),
                "airplay_receiver_volume": True,
                "airplay_sender_volume": False,
                "airplay_starting_volume": False,
                "service_restarts": False,
            },
        }

    def set_trim_percent(self, channel: Any, percent: Any, *, persist: bool = True) -> dict[str, Any]:
        channel_id = str(channel or "").strip().lower()
        if channel_id not in MIXER_CHANNELS:
            raise ValueError(f"Unknown mixer channel: {channel_id or '-'}")
        level = _validated_percent(percent, label="Mixer volume")
        if self._set_mixer_volume is None:
            raise ValueError("The shared ALSA mixer command is unavailable.")
        self._set_mixer_volume(channel_id, level, bool(persist))
        return self.mixer_snapshot()

    def set_trim_volumes(self, values: dict[str, Any], *, persist: bool = True) -> dict[str, Any]:
        if not isinstance(values, dict) or not values:
            raise ValueError("At least one mixer channel is required.")
        for channel, percent in values.items():
            self.set_trim_percent(channel, percent, persist=persist)
        return self.mixer_snapshot()

    def set_live_percent(self, channel: Any, percent: Any, *, reason: str = "pi-slider") -> dict[str, Any]:
        _ = reason
        channel_id = str(channel or "").strip().lower()
        if channel_id not in LIVE_CHANNELS:
            raise ValueError(f"Unknown live audio channel: {channel_id or '-'}")
        level = _validated_percent(percent, label="Live audio volume")

        if channel_id in {"master", "alarm"}:
            if self._set_mixer_volume is None:
                raise ValueError("The shared ALSA mixer command is unavailable.")
            self._set_mixer_volume(channel_id, level, False)
        elif channel_id == "plexamp":
            if self._set_plexamp_volume is None:
                raise ValueError("Plexamp volume control is unavailable.")
            self._set_plexamp_volume(level)
        else:
            if self._set_mixer_volume is None:
                raise ValueError("The shared ALSA mixer command is unavailable.")
            self._set_mixer_volume(AIRPLAY_LIVE_MIXER_CHANNEL, level, False)
        return self.live_snapshot()

    def start_airplay_session(self, reason: str = "session-start", *, background: bool = True) -> str:
        _ = reason, background
        with self._lock:
            if self._session_active:
                return "already-active"
            self._session_active = True
        return "receiver-owned"

    def refresh_defaults(self, reason: str = "settings-save", *, background: bool = True) -> str:
        _ = reason, background
        return "retired"

    def end_airplay_session(self, reason: str = "session-ended") -> None:
        _ = reason
        with self._lock:
            self._session_active = False
