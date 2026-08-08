from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from flask import jsonify, request

try:
    from . import dashboard_core as _dashboard_core
except ImportError:  # Supports direct execution imports.
    import dashboard_core as _dashboard_core


MIXER_CHANNELS: dict[str, dict[str, Any]] = {
    "master": {
        "label": "Master output",
        "control": "A Clockwork Master",
        "pcm": "acp_master",
        "default_percent": 80,
        "description": "Persistent final output level applied to Plexamp, AirPlay and alarm audio.",
    },
    "plexamp": {
        "label": "Plexamp trim",
        "control": "A Clockwork Plexamp",
        "pcm": "acp_plexamp",
        "default_percent": 100,
        "description": "Persistent downstream calibration after Plexamp's own player volume.",
    },
    "airplay": {
        "label": "AirPlay trim",
        "control": "A Clockwork AirPlay",
        "pcm": "acp_airplay",
        "default_percent": 100,
        "description": "Persistent downstream calibration after the AirPlay sender volume.",
    },
    "alarm": {
        "label": "Maximum alarm volume",
        "control": "A Clockwork Alarm",
        "pcm": "acp_alarm",
        "default_percent": 100,
        "description": "Global ceiling after each alarm's target and fade.",
    },
}

DEFAULT_MIXER_HELPER = "/usr/local/bin/a-clockwork-plex-audio-mixer"
DEFAULT_AIRPLAY_START_PERCENT = 60


def _integer(value: Any, fallback: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return fallback


def _bounded_percent(value: Any, fallback: int = 50) -> int:
    return max(0, min(100, _integer(value, fallback)))


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
                    "raw_percent": None,
                    "db": None,
                    "scale": "perceptual-amplitude",
                    "available": False,
                    "error": None,
                }
                for channel_id, metadata in MIXER_CHANNELS.items()
            },
            "devices": {
                channel_id: metadata["pcm"]
                for channel_id, metadata in MIXER_CHANNELS.items()
            },
            "scale": {
                "name": "perceptual-amplitude",
                "examples": {
                    "50_percent_db": -6.02,
                    "25_percent_db": -12.04,
                    "10_percent_db": -20.0,
                },
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
                "scale": helper.get("scale") or payload["scale"],
                "error": helper.get("error"),
            }
        )
        helper_channels = helper.get("channels") if isinstance(helper.get("channels"), dict) else {}
        for channel_id, channel in payload["channels"].items():
            source = helper_channels.get(channel_id) if isinstance(helper_channels.get(channel_id), dict) else {}
            channel.update(
                {
                    "percent": source.get("percent"),
                    "raw_percent": source.get("raw_percent"),
                    "db": source.get("db"),
                    "scale": source.get("scale", "perceptual-amplitude"),
                    "available": source.get("available") is True,
                    "pcm_available": source.get("pcm_available") is True,
                    "error": source.get("error"),
                }
            )
        return payload

    def set_volume(self, channel: str, percent: Any, *, persist: bool = True) -> dict[str, Any]:
        channel_id = str(channel or "").strip().lower()
        if channel_id not in MIXER_CHANNELS:
            raise ValueError(f"Unknown mixer channel: {channel_id or '-'}")
        level = _integer(percent, -1)
        if not 0 <= level <= 100:
            raise ValueError("Mixer volume must be from 0 to 100 percent.")
        if not self.helper_path.exists():
            raise ValueError("The shared audio mixer helper is not installed.")

        action = "set" if persist else "live"
        return_code, payload, error = self._invoke(action, channel_id, str(level), timeout=8)
        if return_code:
            raise ValueError(error or str(payload.get("error") or "Could not change mixer volume."))
        return self.status()

    def set_volumes(self, values: dict[str, Any], *, persist: bool = True) -> dict[str, Any]:
        if not isinstance(values, dict) or not values:
            raise ValueError("At least one mixer channel is required.")
        for channel, percent in values.items():
            self.set_volume(str(channel), percent, persist=persist)
        return self.status()


class PlexampVolumeController:
    """Read and change Plexamp Headless' own player state and volume."""

    def __init__(self, base_url: str, *, opener: Callable[..., Any] | None = None) -> None:
        self.base_url = str(base_url or "http://localhost:32500").rstrip("/")
        self.opener = opener or urllib.request.urlopen
        self._command_lock = threading.Lock()
        self._command_id = int(time.time() * 1000) % 2_000_000_000

    def _next_command_id(self) -> int:
        with self._command_lock:
            self._command_id = (self._command_id + 1) % 2_000_000_000
            return self._command_id

    def _read(self, path: str, *, timeout: float = 2.0) -> bytes:
        url = f"{self.base_url}{path}"
        request_object = urllib.request.Request(
            url,
            headers={"Accept": "application/xml, application/json, */*"},
        )
        with self.opener(request_object, timeout=timeout) as response:
            return response.read()

    @staticmethod
    def _timeline_snapshot(payload: bytes) -> dict[str, Any]:
        snapshot: dict[str, Any] = {"percent": None, "playback_state": None}
        try:
            root = ET.fromstring(payload)
        except (ET.ParseError, ValueError):
            return snapshot
        for element in root.iter():
            tag = str(element.tag).rsplit("}", 1)[-1]
            if tag != "Timeline" or str(element.attrib.get("type", "")).lower() != "music":
                continue
            value = element.attrib.get("volume")
            if value is not None:
                try:
                    snapshot["percent"] = max(0, min(100, round(float(value))))
                except (TypeError, ValueError):
                    pass
            state = str(element.attrib.get("state", "")).strip().lower()
            snapshot["playback_state"] = state or None
            break
        return snapshot

    @staticmethod
    def _timeline_volume(payload: bytes) -> int | None:
        return PlexampVolumeController._timeline_snapshot(payload).get("percent")

    def status(self) -> dict[str, Any]:
        command_id = self._next_command_id()
        query = urllib.parse.urlencode({"commandID": command_id, "type": "music", "wait": 0})
        try:
            payload = self._read(f"/player/timeline/poll?{query}")
        except (OSError, TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            return {
                "available": False,
                "percent": None,
                "playback_state": None,
                "source": "plexamp-player",
                "error": str(exc),
            }
        snapshot = self._timeline_snapshot(payload)
        percent = snapshot.get("percent")
        return {
            "available": percent is not None,
            "percent": percent,
            "playback_state": snapshot.get("playback_state"),
            "source": "plexamp-player",
            "error": None if percent is not None else "Plexamp timeline did not report a music volume.",
        }

    def set_volume(self, percent: Any) -> dict[str, Any]:
        level = _integer(percent, -1)
        if not 0 <= level <= 100:
            raise ValueError("Plexamp volume must be from 0 to 100 percent.")
        command_id = self._next_command_id()
        query = urllib.parse.urlencode({"volume": level, "type": "music", "commandID": command_id})
        try:
            self._read(f"/player/playback/setParameters?{query}")
        except (OSError, TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            raise ValueError(f"Could not change Plexamp volume: {exc}") from exc
        status = self.status()
        if not status.get("available"):
            status.update({"available": True, "percent": level, "error": None})
        status["requested_percent"] = level
        return status


def airplay_defaults() -> dict[str, Any]:
    config = _dashboard_core.load_config()
    airplay = config.get("airplay") if isinstance(config, dict) and isinstance(config.get("airplay"), dict) else {}
    return {
        "default_volume_percent": _bounded_percent(
            airplay.get("default_volume_percent"),
            DEFAULT_AIRPLAY_START_PERCENT,
        ),
        "apply_default_volume_on_start": airplay.get("apply_default_volume_on_start", True) is not False,
    }


def save_airplay_defaults(payload: dict[str, Any]) -> dict[str, Any]:
    current = airplay_defaults()
    default_percent = _bounded_percent(
        payload.get("default_volume_percent", current["default_volume_percent"]),
        current["default_volume_percent"],
    )
    apply_on_start = payload.get(
        "apply_default_volume_on_start",
        current["apply_default_volume_on_start"],
    )

    raw_config = _dashboard_core.load_json(_dashboard_core.CONFIG_PATH, {})
    airplay = raw_config.get("airplay") if isinstance(raw_config.get("airplay"), dict) else {}
    airplay.update(
        {
            "default_volume_percent": default_percent,
            "apply_default_volume_on_start": bool(apply_on_start),
        }
    )
    raw_config["airplay"] = airplay
    _dashboard_core.save_json(_dashboard_core.CONFIG_PATH, raw_config)
    return airplay_defaults()


def _plexamp_controller() -> PlexampVolumeController:
    config = _dashboard_core.load_config()
    plexamp = config.get("plexamp") if isinstance(config, dict) and isinstance(config.get("plexamp"), dict) else {}
    return PlexampVolumeController(str(plexamp.get("url", "http://localhost:32500")))


def _airplay_session_active() -> bool:
    config = _dashboard_core.load_config()
    state = _dashboard_core.load_state(config)
    airplay = state.get("airplay") if isinstance(state.get("airplay"), dict) else {}
    return bool(airplay.get("active"))


shared_audio_mixer = SharedAudioMixer()
mixer_controller: Any | None = None


def bind_mixer_controller(controller: Any) -> None:
    """Bind compatibility routes to the one application audio authority."""
    global mixer_controller
    mixer_controller = controller


def _controller_unavailable() -> dict[str, Any]:
    return {
        "authority": "mixer-controller-unbound",
        "available": False,
        "mode": "live-player-aware",
        "defaults": airplay_defaults(),
        "airplay_default_application": {
            "status": "controller-unavailable",
            "in_progress": False,
            "last_error": "MixerController has not been bound by app.runner.",
        },
        "channels": {},
        "mixer": shared_audio_mixer.status(),
        "error": "MixerController has not been bound by app.runner.",
    }


def live_audio_status() -> dict[str, Any]:
    if mixer_controller is None:
        return _controller_unavailable()
    return mixer_controller.live_snapshot()


def set_live_audio_volume(channel: Any, percent: Any) -> dict[str, Any]:
    if mixer_controller is None:
        raise ValueError("MixerController has not been bound by app.runner.")
    return mixer_controller.set_live_percent(channel, percent, reason="legacy-live-audio-api")


def _application_status() -> dict[str, Any]:
    if mixer_controller is None:
        return _controller_unavailable()["airplay_default_application"]
    return mixer_controller.application_status()


def _register_audio_api() -> None:
    app = _dashboard_core.app

    if "api_shared_audio_mixer" not in app.view_functions:
        @app.route("/api/audio/mixer", methods=["GET", "POST"])
        def api_shared_audio_mixer():
            if request.method == "GET":
                status = mixer_controller.mixer_snapshot() if mixer_controller is not None else shared_audio_mixer.status()
                return jsonify({"ok": True, "mixer": status, "authority": "mixer-controller"})

            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                return jsonify({"ok": False, "error": "Mixer settings must be a JSON object."}), 400
            persist = payload.get("persist", True) is not False
            try:
                if mixer_controller is not None:
                    if isinstance(payload.get("volumes"), dict):
                        status = mixer_controller.set_trim_volumes(payload["volumes"], persist=persist)
                    else:
                        status = mixer_controller.set_trim_percent(
                            payload.get("channel"),
                            payload.get("percent"),
                            persist=persist,
                        )
                elif isinstance(payload.get("volumes"), dict):
                    status = shared_audio_mixer.set_volumes(payload["volumes"], persist=persist)
                else:
                    status = shared_audio_mixer.set_volume(
                        payload.get("channel"),
                        payload.get("percent"),
                        persist=persist,
                    )
            except ValueError as exc:
                return jsonify({"ok": False, "error": str(exc)}), 400
            message = "Persistent output level saved." if persist else "Audio output level changed."
            return jsonify({"ok": True, "mixer": status, "persisted": persist, "message": message})

    if "api_live_audio" not in app.view_functions:
        @app.route("/api/audio/live", methods=["GET", "POST"])
        def api_live_audio():
            if mixer_controller is None:
                return jsonify({"ok": False, "error": "MixerController is unavailable."}), 503
            if request.method == "GET":
                return jsonify({"ok": True, "live": mixer_controller.live_snapshot()})
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                return jsonify({"ok": False, "error": "Live mixer request must be a JSON object."}), 400
            try:
                status = mixer_controller.set_live_percent(
                    payload.get("channel"),
                    payload.get("percent"),
                    reason="legacy-live-audio-api",
                )
            except ValueError as exc:
                return jsonify({"ok": False, "error": str(exc)}), 409
            return jsonify({"ok": True, "live": status, "message": "Live audio level changed."})

    if "api_audio_defaults" not in app.view_functions:
        @app.route("/api/audio/defaults", methods=["GET", "POST"])
        def api_audio_defaults():
            if request.method == "GET":
                return jsonify(
                    {
                        "ok": True,
                        "defaults": airplay_defaults(),
                        "application": _application_status(),
                    }
                )
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                return jsonify({"ok": False, "error": "Audio defaults must be a JSON object."}), 400
            try:
                defaults = save_airplay_defaults(payload)
            except OSError as exc:
                return jsonify({"ok": False, "error": f"Could not save audio defaults: {exc}"}), 500
            if mixer_controller is not None:
                mixer_controller.refresh_defaults("settings-save")
            return jsonify(
                {
                    "ok": True,
                    "defaults": defaults,
                    "application": _application_status(),
                    "message": "AirPlay starting volume saved.",
                }
            )

    original_airplay_start = app.view_functions.get("api_airplay_start")
    if original_airplay_start and not getattr(original_airplay_start, "_acp_audio_defaults_wrapped", False):
        def api_airplay_start_with_audio_default():
            response = original_airplay_start()
            if mixer_controller is not None:
                mixer_controller.start_airplay_session("session-start")
            return response

        api_airplay_start_with_audio_default._acp_audio_defaults_wrapped = True  # type: ignore[attr-defined]
        app.view_functions["api_airplay_start"] = api_airplay_start_with_audio_default


_register_audio_api()
