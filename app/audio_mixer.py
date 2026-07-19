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
        "description": "Persistent final trim applied to Plexamp, AirPlay and alarm audio.",
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
        "label": "Alarm trim",
        "control": "A Clockwork Alarm",
        "pcm": "acp_alarm",
        "default_percent": 100,
        "description": "Persistent output ceiling after each alarm's own fade and target volume.",
    },
}

DEFAULT_MIXER_HELPER = "/usr/local/bin/a-clockwork-plex-audio-mixer"
DEFAULT_AIRPLAY_START_PERCENT = 60
LIVE_CHANNELS = {"master", "plexamp", "airplay", "alarm"}


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
                "examples": {"50_percent_db": -6.02, "25_percent_db": -12.04, "10_percent_db": -20.0},
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
        request_object = urllib.request.Request(url, headers={"Accept": "application/xml, application/json, */*"})
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
    apply_on_start = payload.get("apply_default_volume_on_start", current["apply_default_volume_on_start"])

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
_airplay_default_lock = threading.Lock()
_airplay_default_generation = 0
_airplay_default_runtime: dict[str, Any] = {
    "status": "waiting-for-session",
    "in_progress": False,
    "target_percent": None,
    "last_attempt_at": None,
    "last_applied_at": None,
    "last_confirmed_percent": None,
    "last_error": None,
    "reason": None,
}
_plexamp_handoff_lock = threading.Lock()
_plexamp_handoff_generation = 0
_plexamp_handoff_runtime: dict[str, Any] = {
    "status": "idle",
    "armed_at": None,
    "completed_at": None,
    "method": None,
    "last_error": None,
}


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _airplay_default_status() -> dict[str, Any]:
    with _airplay_default_lock:
        return deepcopy(_airplay_default_runtime)


def _update_airplay_default_runtime(**updates: Any) -> None:
    with _airplay_default_lock:
        _airplay_default_runtime.update(updates)


def _plexamp_handoff_status() -> dict[str, Any]:
    with _plexamp_handoff_lock:
        return deepcopy(_plexamp_handoff_runtime)


def _update_plexamp_handoff_runtime(**updates: Any) -> None:
    with _plexamp_handoff_lock:
        _plexamp_handoff_runtime.update(updates)


def _schedule_airplay_default(reason: str = "session-start") -> None:
    global _airplay_default_generation
    defaults = airplay_defaults()
    target = defaults["default_volume_percent"]
    if not defaults["apply_default_volume_on_start"]:
        _update_airplay_default_runtime(
            status="disabled",
            in_progress=False,
            target_percent=target,
            last_error=None,
            reason=reason,
        )
        return

    with _airplay_default_lock:
        _airplay_default_generation += 1
        generation = _airplay_default_generation
        _airplay_default_runtime.update(
            {
                "status": "waiting-for-remote",
                "in_progress": True,
                "target_percent": target,
                "last_attempt_at": _iso_now(),
                "last_error": None,
                "reason": reason,
            }
        )

    def worker() -> None:
        stable_reads = 0
        last_error: str | None = None
        for _ in range(80):
            with _airplay_default_lock:
                if generation != _airplay_default_generation:
                    return

            remote = _dashboard_core.mpris_remote_status()
            playback = str(remote.get("playback_status") or "").strip().lower()
            current = remote.get("volume_percent")
            if remote.get("available") and playback in {"playing", "paused"}:
                if isinstance(current, (int, float)) and abs(float(current) - target) <= 1:
                    stable_reads += 1
                    _update_airplay_default_runtime(
                        status="verifying",
                        last_confirmed_percent=round(float(current)),
                        last_error=None,
                    )
                    if stable_reads >= 3:
                        _update_airplay_default_runtime(
                            status="applied",
                            in_progress=False,
                            last_applied_at=_iso_now(),
                            last_confirmed_percent=round(float(current)),
                            last_error=None,
                        )
                        return
                else:
                    stable_reads = 0
                    ok, error = _dashboard_core.mpris_call("SetVolume", "d", f"{target / 100:.4f}")
                    last_error = error
                    _update_airplay_default_runtime(
                        status="applying" if ok else "retrying",
                        last_attempt_at=_iso_now(),
                        last_error=error,
                    )
            else:
                stable_reads = 0
                _update_airplay_default_runtime(status="waiting-for-remote")
            time.sleep(0.25)

        _update_airplay_default_runtime(
            status="timed-out",
            in_progress=False,
            last_error=last_error or "The AirPlay sender did not retain the requested starting volume.",
        )

    threading.Thread(target=worker, name="airplay-default-volume", daemon=True).start()


def _arm_plexamp_handoff() -> None:
    """Wait for Plexamp to start playing, then pause/stop an active AirPlay sender."""
    global _plexamp_handoff_generation
    remote = _dashboard_core.mpris_remote_status()
    if not remote.get("available") or str(remote.get("playback_status") or "").lower() != "playing":
        _update_plexamp_handoff_runtime(status="not-needed", last_error=None)
        return

    with _plexamp_handoff_lock:
        _plexamp_handoff_generation += 1
        generation = _plexamp_handoff_generation
        _plexamp_handoff_runtime.update(
            {
                "status": "armed",
                "armed_at": _iso_now(),
                "completed_at": None,
                "method": None,
                "last_error": None,
            }
        )

    def worker() -> None:
        for _ in range(160):
            with _plexamp_handoff_lock:
                if generation != _plexamp_handoff_generation:
                    return

            remote_now = _dashboard_core.mpris_remote_status()
            remote_playback = str(remote_now.get("playback_status") or "").lower()
            if not remote_now.get("available") or remote_playback != "playing":
                _update_plexamp_handoff_runtime(
                    status="airplay-already-quiet",
                    completed_at=_iso_now(),
                    last_error=None,
                )
                return

            plexamp = _plexamp_controller().status()
            if str(plexamp.get("playback_state") or "").lower() == "playing":
                ok, error = _dashboard_core.mpris_call("Pause")
                method = "Pause"
                time.sleep(0.2)
                after = _dashboard_core.mpris_remote_status()
                if not ok or str(after.get("playback_status") or "").lower() == "playing":
                    ok, error = _dashboard_core.mpris_call("Stop")
                    method = "Stop"
                _update_plexamp_handoff_runtime(
                    status="completed" if ok else "failed",
                    completed_at=_iso_now(),
                    method=method,
                    last_error=error,
                )
                return
            time.sleep(0.25)

        _update_plexamp_handoff_runtime(
            status="timed-out",
            completed_at=_iso_now(),
            last_error="Plexamp did not begin playing before the AirPlay handoff window expired.",
        )

    threading.Thread(target=worker, name="plexamp-airplay-handoff", daemon=True).start()


def live_audio_status() -> dict[str, Any]:
    mixer = shared_audio_mixer.status()
    mixer_channels = mixer.get("channels") if isinstance(mixer.get("channels"), dict) else {}
    plexamp = _plexamp_controller().status()
    airplay = _dashboard_core.mpris_remote_status()
    defaults = airplay_defaults()

    def trim(channel_id: str) -> dict[str, Any]:
        value = mixer_channels.get(channel_id)
        return deepcopy(value) if isinstance(value, dict) else {}

    return {
        "available": mixer.get("available") is True,
        "mode": "live-player-aware",
        "defaults": defaults,
        "airplay_default_application": _airplay_default_status(),
        "plexamp_handoff": _plexamp_handoff_status(),
        "channels": {
            "master": {
                "id": "master",
                "label": "Master",
                "available": trim("master").get("available") is True,
                "percent": trim("master").get("percent"),
                "source": "alsa-live-master",
                "detail": "Immediate output level; Settings stores the persistent default.",
                "trim": trim("master"),
                "error": trim("master").get("error"),
            },
            "plexamp": {
                "id": "plexamp",
                "label": "Plexamp",
                **plexamp,
                "detail": "Plexamp player volume; its Now Playing control should follow.",
                "trim": trim("plexamp"),
            },
            "airplay": {
                "id": "airplay",
                "label": "AirPlay",
                "available": airplay.get("available") is True,
                "percent": airplay.get("volume_percent"),
                "source": "airplay-sender",
                "detail": "AirPlay sender volume; available while a remote session is connected.",
                "remote": airplay,
                "trim": trim("airplay"),
                "error": airplay.get("error"),
            },
            "alarm": {
                "id": "alarm",
                "label": "Alarm",
                "available": trim("alarm").get("available") is True,
                "percent": trim("alarm").get("percent"),
                "source": "alsa-live-alarm",
                "detail": "Immediate alarm ceiling; Settings stores the persistent default.",
                "trim": trim("alarm"),
                "error": trim("alarm").get("error"),
            },
        },
        "mixer": mixer,
        "error": mixer.get("error"),
    }


def set_live_audio_volume(channel: Any, percent: Any) -> dict[str, Any]:
    channel_id = str(channel or "").strip().lower()
    if channel_id not in LIVE_CHANNELS:
        raise ValueError(f"Unknown live audio channel: {channel_id or '-'}")
    level = _integer(percent, -1)
    if not 0 <= level <= 100:
        raise ValueError("Live audio volume must be from 0 to 100 percent.")

    if channel_id in {"master", "alarm"}:
        shared_audio_mixer.set_volume(channel_id, level, persist=False)
    elif channel_id == "plexamp":
        _plexamp_controller().set_volume(level)
    else:
        remote = _dashboard_core.mpris_remote_status()
        if not remote.get("available"):
            raise ValueError("AirPlay volume is available only while a sender is connected.")
        ok, error = _dashboard_core.mpris_call("SetVolume", "d", f"{level / 100:.4f}")
        if not ok:
            raise ValueError(error or "Could not change AirPlay volume.")

    return live_audio_status()


def _register_audio_api() -> None:
    app = _dashboard_core.app

    if "api_shared_audio_mixer" not in app.view_functions:
        @app.route("/api/audio/mixer", methods=["GET", "POST"])
        def api_shared_audio_mixer():
            if request.method == "GET":
                return jsonify({"ok": True, "mixer": shared_audio_mixer.status()})

            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                return jsonify({"ok": False, "error": "Mixer settings must be a JSON object."}), 400
            persist = payload.get("persist", True) is not False
            try:
                if isinstance(payload.get("volumes"), dict):
                    status = shared_audio_mixer.set_volumes(payload["volumes"], persist=persist)
                else:
                    status = shared_audio_mixer.set_volume(
                        payload.get("channel"),
                        payload.get("percent"),
                        persist=persist,
                    )
            except ValueError as exc:
                return jsonify({"ok": False, "error": str(exc)}), 400
            message = "Persistent audio trim saved." if persist else "Audio trim changed."
            return jsonify({"ok": True, "mixer": status, "persisted": persist, "message": message})

    if "api_live_audio" not in app.view_functions:
        @app.route("/api/audio/live", methods=["GET", "POST"])
        def api_live_audio():
            if request.method == "GET":
                return jsonify({"ok": True, "live": live_audio_status()})
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                return jsonify({"ok": False, "error": "Live mixer request must be a JSON object."}), 400
            try:
                status = set_live_audio_volume(payload.get("channel"), payload.get("percent"))
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
                        "application": _airplay_default_status(),
                    }
                )
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                return jsonify({"ok": False, "error": "Audio defaults must be a JSON object."}), 400
            try:
                defaults = save_airplay_defaults(payload)
            except OSError as exc:
                return jsonify({"ok": False, "error": f"Could not save audio defaults: {exc}"}), 500
            if defaults["apply_default_volume_on_start"] and _airplay_session_active():
                _schedule_airplay_default("settings-save")
            else:
                _update_airplay_default_runtime(
                    status="waiting-for-session" if defaults["apply_default_volume_on_start"] else "disabled",
                    in_progress=False,
                    target_percent=defaults["default_volume_percent"],
                    last_error=None,
                    reason="settings-save",
                )
            return jsonify(
                {
                    "ok": True,
                    "defaults": defaults,
                    "application": _airplay_default_status(),
                    "message": "AirPlay starting volume saved.",
                }
            )

    original_airplay_start = app.view_functions.get("api_airplay_start")
    if original_airplay_start and not getattr(original_airplay_start, "_acp_audio_defaults_wrapped", False):
        def api_airplay_start_with_audio_default():
            response = original_airplay_start()
            _schedule_airplay_default("session-start")
            return response

        api_airplay_start_with_audio_default._acp_audio_defaults_wrapped = True  # type: ignore[attr-defined]
        app.view_functions["api_airplay_start"] = api_airplay_start_with_audio_default

    original_plexamp_page = app.view_functions.get("plexamp")
    if original_plexamp_page and not getattr(original_plexamp_page, "_acp_airplay_handoff_wrapped", False):
        def plexamp_page_with_airplay_handoff():
            _arm_plexamp_handoff()
            return original_plexamp_page()

        plexamp_page_with_airplay_handoff._acp_airplay_handoff_wrapped = True  # type: ignore[attr-defined]
        app.view_functions["plexamp"] = plexamp_page_with_airplay_handoff


_register_audio_api()
