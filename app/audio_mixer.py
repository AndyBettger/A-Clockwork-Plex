from __future__ import annotations

import json
import os
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

MIXER_CHANNELS: dict[str, dict[str, Any]] = {
    "master": {
        "label": "Master output",
        "control": "A Clockwork Master",
        "pcm": "acp_master",
        "default_percent": 80,
        "description": "Final level applied to Plexamp, AirPlay and alarm audio.",
    },
    "plexamp": {
        "label": "Plexamp",
        "control": "A Clockwork Plexamp",
        "pcm": "acp_plexamp",
        "default_percent": 100,
        "description": "Additional gain stage after Plexamp's own player volume.",
    },
    "airplay": {
        "label": "AirPlay",
        "control": "A Clockwork AirPlay",
        "pcm": "acp_airplay",
        "default_percent": 100,
        "description": "Shared with Shairport Sync and the sender's volume control.",
    },
    "alarm": {
        "label": "Alarm",
        "control": "A Clockwork Alarm",
        "pcm": "acp_alarm",
        "default_percent": 100,
        "description": "Output ceiling after each alarm's own fade and target volume.",
    },
}

DEFAULT_MIXER_HELPER = "/usr/local/bin/a-clockwork-plex-audio-mixer"


def _integer(value: Any, fallback: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return fallback


class SharedAudioMixer:
    """Read and update the restricted ALSA shared-mixer helper."""

    def __init__(
        self,
        helper_path: str | Path = DEFAULT_MIXER_HELPER,
        *,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self.helper_path = Path(helper_path)
        self.runner = runner or subprocess.run

    def _base_payload(self) -> dict[str, Any]:
        return {
            "available": False,
            "installed": self.helper_path.exists() and os.access(self.helper_path, os.X_OK),
            "configured": False,
            "mode": "shared-dmix",
            "helper_path": str(self.helper_path),
            "channels": {
                channel_id: {
                    "id": channel_id,
                    **deepcopy(metadata),
                    "percent": None,
                    "available": False,
                    "error": None,
                }
                for channel_id, metadata in MIXER_CHANNELS.items()
            },
            "devices": {
                channel_id: metadata["pcm"]
                for channel_id, metadata in MIXER_CHANNELS.items()
            },
            "error": None,
        }

    def _invoke(self, *arguments: str, timeout: int = 6) -> tuple[int, dict[str, Any], str]:
        command = ["sudo", "-n", str(self.helper_path), *arguments]
        try:
            result = self.runner(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return 1, {}, str(exc)

        output = (result.stdout or "").strip()
        error = (result.stderr or "").strip()
        try:
            payload = json.loads(output or "{}")
        except json.JSONDecodeError:
            payload = {}
            if not error:
                error = output or "The audio mixer helper returned invalid JSON."
        if result.returncode and not error:
            error = str(payload.get("error") or output or "The audio mixer helper failed.")
        return result.returncode, payload if isinstance(payload, dict) else {}, error

    def status(self) -> dict[str, Any]:
        payload = self._base_payload()
        if not payload["installed"]:
            payload["error"] = (
                "The shared audio mixer is not installed. Run "
                "sudo bash scripts/install-shared-audio.sh."
            )
            return payload

        return_code, helper, error = self._invoke("status")
        if error:
            payload["error"] = error
        if return_code:
            return payload

        payload.update(
            {
                "available": helper.get("available") is True,
                "configured": helper.get("configured") is True,
                "card": helper.get("card"),
                "hardware_pcm": helper.get("hardware_pcm"),
                "sample_rate_hz": helper.get("sample_rate_hz", 44100),
                "channels_count": helper.get("channels_count", 2),
                "error": helper.get("error"),
            }
        )
        helper_channels = helper.get("channels") if isinstance(helper.get("channels"), dict) else {}
        for channel_id, channel in payload["channels"].items():
            source = helper_channels.get(channel_id) if isinstance(helper_channels.get(channel_id), dict) else {}
            channel.update(
                {
                    "percent": source.get("percent"),
                    "available": source.get("available") is True,
                    "pcm_available": source.get("pcm_available") is True,
                    "error": source.get("error"),
                }
            )
        return payload

    def set_volume(self, channel: str, percent: Any) -> dict[str, Any]:
        channel_id = str(channel or "").strip().lower()
        if channel_id not in MIXER_CHANNELS:
            raise ValueError(f"Unknown mixer channel: {channel_id or '-'}")
        level = _integer(percent, -1)
        if not 0 <= level <= 100:
            raise ValueError("Mixer volume must be from 0 to 100 percent.")
        if not self.helper_path.exists():
            raise ValueError("The shared audio mixer helper is not installed.")

        return_code, payload, error = self._invoke("set", channel_id, str(level), timeout=8)
        if return_code:
            raise ValueError(error or str(payload.get("error") or "Could not change mixer volume."))
        return self.status()

    def set_volumes(self, values: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(values, dict) or not values:
            raise ValueError("At least one mixer channel is required.")
        for channel, percent in values.items():
            self.set_volume(str(channel), percent)
        return self.status()
