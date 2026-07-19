from __future__ import annotations

import json
import math
import subprocess
import threading
import time
import uuid
import wave
from array import array
from copy import deepcopy
from pathlib import Path
from typing import Any

from flask import jsonify, request

try:
    from . import alarm_audio_core as _core
    from . import dashboard_core as _dashboard_core
    from .audio_mixer import DEFAULT_MIXER_HELPER, SharedAudioMixer
except ImportError:  # Supports direct execution imports.
    import alarm_audio_core as _core
    import dashboard_core as _dashboard_core
    from audio_mixer import DEFAULT_MIXER_HELPER, SharedAudioMixer

DEFAULT_AUDIO_SETTINGS = _core.DEFAULT_AUDIO_SETTINGS
MAX_TEST_SECONDS = _core.MAX_TEST_SECONDS
MAX_TEST_VOLUME_PERCENT = _core.MAX_TEST_VOLUME_PERCENT
SAMPLE_RATE = 44100
CHANNELS = 2
SAMPLE_WIDTH_BYTES = 2
SHARED_ALARM_PCM = "acp_alarm"

shared_audio_mixer = SharedAudioMixer()


def normalise_audio_settings(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    settings = _core.normalise_audio_settings(source)
    shared = bool(source.get("shared_mixer_enabled", False))

    configured_device = str(source.get("alsa_device", "")).strip()
    hardware_device = str(source.get("hardware_device", "")).strip()
    if not hardware_device and configured_device not in {"", "default", SHARED_ALARM_PCM}:
        hardware_device = configured_device
    if not hardware_device:
        hardware_device = "hw:CARD=Pro,DEV=0"

    settings.update(
        {
            "shared_mixer_enabled": shared,
            "hardware_device": hardware_device[:120],
            "mixer_helper_path": (
                str(source.get("mixer_helper_path", DEFAULT_MIXER_HELPER)).strip()[:240]
                or DEFAULT_MIXER_HELPER
            ),
        }
    )
    if shared:
        settings.update(
            {
                "alsa_device": SHARED_ALARM_PCM,
                "release_services": False,
                "restore_services": False,
            }
        )
    return settings


def render_tone_wav(
    tone: dict[str, Any],
    destination: Path,
    *,
    duration_seconds: int,
    start_percent: int,
    target_percent: int,
    fade_seconds: int,
) -> None:
    """Render a 16-bit, 44.1 kHz stereo alarm file.

    The synthesised signal is duplicated into left and right channels so a mono
    alarm pattern is heard equally through both sides of the bedroom system.
    """
    raw_pattern = tone.get("pattern") if isinstance(tone, dict) else None
    if not isinstance(raw_pattern, list) or not raw_pattern:
        raise ValueError("The selected tone has no playable pattern.")

    pattern: list[dict[str, Any]] = []
    for item in raw_pattern:
        if not isinstance(item, dict):
            continue
        start = max(20.0, min(10000.0, float(item.get("frequency", 440) or 440)))
        end = max(20.0, min(10000.0, float(item.get("end_frequency", start) or start)))
        waveform = str(item.get("wave", "sine")).lower()
        if waveform not in {"sine", "square", "triangle", "sawtooth"}:
            waveform = "sine"
        pattern.append(
            {
                "start": start,
                "end": end,
                "duration": max(20, min(3000, _core._integer(item.get("duration_ms"), 200))),
                "gap": max(0, min(3000, _core._integer(item.get("gap_ms"), 0))),
                "gain": max(0.001, min(0.35, float(item.get("gain", 0.15) or 0.15))),
                "wave": waveform,
            }
        )
    if not pattern:
        raise ValueError("The selected tone contains no valid playback steps.")

    seconds = max(1, min(600, int(duration_seconds)))
    start_gain = max(0, min(100, int(start_percent))) / 100
    target_gain = max(0, min(100, int(target_percent))) / 100
    fade = max(0, min(300, int(fade_seconds)))
    total_frames = seconds * SAMPLE_RATE
    samples = array("h")
    produced_frames = 0
    phase = 0.0

    while produced_frames < total_frames:
        for step in pattern:
            count = max(1, round(step["duration"] * SAMPLE_RATE / 1000))
            gap = max(0, round(step["gap"] * SAMPLE_RATE / 1000))
            attack = min(count // 2, max(1, round(0.015 * SAMPLE_RATE)))
            release = min(count // 2, max(1, round(0.025 * SAMPLE_RATE)))
            for index in range(count):
                if produced_frames >= total_frames:
                    break
                progress = index / max(1, count - 1)
                frequency = step["start"] + (step["end"] - step["start"]) * progress
                phase += 2 * math.pi * frequency / SAMPLE_RATE
                envelope = 1.0
                if index < attack:
                    envelope = index / max(1, attack)
                elif index >= count - release:
                    envelope = max(0.0, (count - index - 1) / max(1, release))
                elapsed = produced_frames / SAMPLE_RATE
                volume = (
                    start_gain + (target_gain - start_gain) * min(1, elapsed / fade)
                    if fade
                    else target_gain
                )
                value = _core._oscillator(step["wave"], phase) * step["gain"] * envelope * volume
                sample = int(max(-1.0, min(1.0, value)) * 32767)
                samples.extend((sample, sample))
                produced_frames += 1

            silent_frames = min(gap, total_frames - produced_frames)
            if silent_frames:
                samples.extend([0] * silent_frames * CHANNELS)
                produced_frames += silent_frames
            if produced_frames >= total_frames:
                break

    destination.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destination), "wb") as output:
        output.setnchannels(CHANNELS)
        output.setsampwidth(SAMPLE_WIDTH_BYTES)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(samples.tobytes())


# The established manager lives in the preserved core module. Its playback
# method resolves render_tone_wav from that module at runtime, so installing the
# upgraded renderer here keeps all proven safety behaviour intact.
_core.render_tone_wav = render_tone_wav
_core.SAMPLE_RATE = SAMPLE_RATE


class AlarmAudioManager(_core.AlarmAudioManager):
    """Stereo renderer plus shared-dmix and legacy exclusive audio support."""

    RESTORE_TIMEOUT_SECONDS = 24

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._handover_lock = threading.Lock()
        self._restoring_handover_ids: set[str] = set()
        self._restored_handover_ids: list[str] = []

    def settings(self) -> dict[str, Any]:
        config = self.config_loader()
        return normalise_audio_settings(config.get("alarm_audio") if isinstance(config, dict) else None)

    def _helper_status(self, settings: dict[str, Any]) -> dict[str, Any]:
        if settings.get("shared_mixer_enabled"):
            mixer = SharedAudioMixer(settings.get("mixer_helper_path", DEFAULT_MIXER_HELPER)).status()
            return {
                "available": mixer.get("available") is True,
                "error": mixer.get("error"),
                "mode": "shared-dmix",
                "services_untouched": True,
                "plexamp_active": None,
                "shairport_active": None,
            }
        return super()._helper_status(settings)

    def _release(self, settings: dict[str, Any]) -> dict[str, Any]:
        if settings.get("shared_mixer_enabled"):
            snapshot = self._helper_status(settings)
            snapshot.update(
                {
                    "released": True,
                    "services_untouched": True,
                    "handover_id": uuid.uuid4().hex,
                }
            )
            return snapshot
        snapshot = super()._release(settings)
        snapshot["handover_id"] = uuid.uuid4().hex
        return snapshot

    def _restore(self, settings: dict[str, Any], snapshot: dict[str, Any] | None) -> None:
        if settings.get("shared_mixer_enabled"):
            return
        if not settings.get("restore_services") or not snapshot or not snapshot.get("available"):
            return

        handover_id = str(snapshot.get("handover_id") or f"legacy-{id(snapshot)}")
        with self._handover_lock:
            if handover_id in self._restoring_handover_ids or handover_id in self._restored_handover_ids:
                return
            self._restoring_handover_ids.add(handover_id)

        started = time.monotonic()
        error: str | None = None
        helper_payload: dict[str, Any] = {}
        args = [
            "sudo",
            "-n",
            settings["helper_path"],
            "restore",
            "1" if snapshot.get("plexamp_active") else "0",
            "1" if snapshot.get("shairport_active") else "0",
        ]

        try:
            result = self.runner(
                args,
                capture_output=True,
                text=True,
                timeout=self.RESTORE_TIMEOUT_SECONDS,
                check=False,
            )
            raw_output = (result.stdout or "").strip()
            if raw_output:
                try:
                    parsed = json.loads(raw_output)
                    if isinstance(parsed, dict):
                        helper_payload = parsed
                except json.JSONDecodeError:
                    helper_payload = {"raw_output": raw_output}
            if result.returncode:
                error = (result.stderr or raw_output or "Audio restore failed.").strip()
        except (OSError, subprocess.TimeoutExpired) as exc:
            error = str(exc)
        finally:
            elapsed = round(time.monotonic() - started, 3)
            with self.lock:
                self.state["last_restore_seconds"] = elapsed
                self.state["last_restore_handover_id"] = handover_id
                self.state["last_restore_helper"] = deepcopy(helper_payload)
                if error:
                    self.state["last_error"] = error
                self._record(
                    "audio-restore-failed" if error else "audio-owners-restored",
                    handover_id=handover_id,
                    elapsed_seconds=elapsed,
                    helper=helper_payload,
                    error=error,
                )
            with self._handover_lock:
                self._restoring_handover_ids.discard(handover_id)
                self._restored_handover_ids.append(handover_id)
                self._restored_handover_ids = self._restored_handover_ids[-64:]

    def diagnostics(self) -> dict[str, Any]:
        payload = deepcopy(super().diagnostics())
        settings = self.settings()
        player = payload.setdefault("player", {})
        player["format"] = {
            "sample_rate_hz": SAMPLE_RATE,
            "channels": CHANNELS,
            "sample_width_bits": SAMPLE_WIDTH_BYTES * 8,
            "channel_layout": "dual-mono stereo",
        }
        mixer = SharedAudioMixer(settings.get("mixer_helper_path", DEFAULT_MIXER_HELPER)).status()
        payload["mixer"] = mixer
        payload["shared_mixer_enabled"] = bool(settings.get("shared_mixer_enabled"))
        with self._handover_lock:
            payload.setdefault("runtime", {})["restore_in_progress"] = bool(self._restoring_handover_ids)
        if settings.get("shared_mixer_enabled"):
            payload["safety_message"] = (
                "Only explicit tests may make sound. Plexamp, AirPlay and alarms share dmix; "
                f"tests remain capped at {MAX_TEST_VOLUME_PERCENT}%."
            )
        return payload


def _register_mixer_api() -> None:
    app = _dashboard_core.app
    if "api_shared_audio_mixer" in app.view_functions:
        return

    @app.route("/api/audio/mixer", methods=["GET", "POST"])
    def api_shared_audio_mixer():
        if request.method == "GET":
            return jsonify({"ok": True, "mixer": shared_audio_mixer.status()})

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "Mixer settings must be a JSON object."}), 400
        try:
            if isinstance(payload.get("volumes"), dict):
                status = shared_audio_mixer.set_volumes(payload["volumes"])
            else:
                status = shared_audio_mixer.set_volume(payload.get("channel"), payload.get("percent"))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "mixer": status, "message": "Shared audio mixer updated."})


_register_mixer_api()
