from __future__ import annotations

import math
import wave
from array import array
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    from . import alarm_audio_core as _core
except ImportError:  # Supports direct execution imports.
    import alarm_audio_core as _core

DEFAULT_AUDIO_SETTINGS = _core.DEFAULT_AUDIO_SETTINGS
MAX_TEST_SECONDS = _core.MAX_TEST_SECONDS
MAX_TEST_VOLUME_PERCENT = _core.MAX_TEST_VOLUME_PERCENT
SAMPLE_RATE = 44100
CHANNELS = 2
SAMPLE_WIDTH_BYTES = 2

normalise_audio_settings = _core.normalise_audio_settings


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
# upgraded renderer here keeps all proven ownership and safety behaviour intact.
_core.render_tone_wav = render_tone_wav
_core.SAMPLE_RATE = SAMPLE_RATE


class AlarmAudioManager(_core.AlarmAudioManager):
    def diagnostics(self) -> dict[str, Any]:
        payload = deepcopy(super().diagnostics())
        player = payload.setdefault("player", {})
        player["format"] = {
            "sample_rate_hz": SAMPLE_RATE,
            "channels": CHANNELS,
            "sample_width_bits": SAMPLE_WIDTH_BYTES * 8,
            "channel_layout": "dual-mono stereo",
        }
        return payload
