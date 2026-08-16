from __future__ import annotations

import math
import shutil
import subprocess
import time
from array import array
from copy import deepcopy
from typing import Any, Iterator

try:
    from . import alarm_audio_core as _core
except ImportError:  # Supports direct execution imports.
    import alarm_audio_core as _core


SAMPLE_RATE = 44100
CHANNELS = 2
SAMPLE_WIDTH_BYTES = 2
CHUNK_FRAMES = 2048
MAX_STREAM_SECONDS = 600


def iter_tone_pcm_chunks(
    tone: dict[str, Any],
    *,
    duration_seconds: int,
    start_percent: int,
    target_percent: int,
    fade_seconds: int,
    chunk_frames: int = CHUNK_FRAMES,
) -> Iterator[bytes]:
    """Yield the established alarm waveform as bounded stereo PCM chunks."""
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

    seconds = max(1, min(MAX_STREAM_SECONDS, int(duration_seconds)))
    start_gain = max(0, min(100, int(start_percent))) / 100
    target_gain = max(0, min(100, int(target_percent))) / 100
    fade = max(0, min(300, int(fade_seconds)))
    total_frames = seconds * SAMPLE_RATE
    chunk_frames = max(64, int(chunk_frames))
    samples = array("h")
    produced_frames = 0
    phase = 0.0

    def flush_if_full() -> bytes | None:
        if len(samples) < chunk_frames * CHANNELS:
            return None
        payload = samples.tobytes()
        samples.clear()
        return payload

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
                payload = flush_if_full()
                if payload is not None:
                    yield payload

            silent_frames = min(gap, total_frames - produced_frames)
            while silent_frames > 0:
                buffered_frames = len(samples) // CHANNELS
                room = max(1, chunk_frames - buffered_frames)
                count_now = min(silent_frames, room)
                samples.extend([0] * count_now * CHANNELS)
                produced_frames += count_now
                silent_frames -= count_now
                payload = flush_if_full()
                if payload is not None:
                    yield payload
            if produced_frames >= total_frames:
                break

    if samples:
        yield samples.tobytes()


def _stderr_text(process: subprocess.Popen[Any], return_code: int | None) -> str | None:
    if not return_code or not process.stderr:
        return None
    raw = process.stderr.read()
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace").strip() or None
    return str(raw or "").strip() or None


def stream_scheduled_alarm(
    manager: Any,
    occurrence: dict[str, Any],
    settings: dict[str, Any],
) -> None:
    """Stream scheduled alarm PCM to aplay without pre-rendering a whole WAV."""
    source = occurrence.get("source") if isinstance(occurrence.get("source"), dict) else {}
    volume = occurrence.get("volume") if isinstance(occurrence.get("volume"), dict) else {}
    tone_ids: list[str] = []
    for value in (
        source.get("tone_id", "classic-klaxon"),
        source.get("fallback_tone_id", "emergency-buzzer"),
    ):
        if value and str(value) not in tone_ids:
            tone_ids.append(str(value))

    duration = max(
        3,
        min(
            MAX_STREAM_SECONDS,
            _core._integer(occurrence.get("audio_duration_seconds"), settings["test_duration_seconds"]),
        ),
    )
    volume_cap = max(
        1,
        min(
            100,
            _core._integer(settings.get("test_volume_cap_percent"), 100),
        ),
    )
    start_percent = min(volume_cap, max(0, _core._integer(volume.get("start_percent"), 60)))
    target_percent = min(volume_cap, max(0, _core._integer(volume.get("target_percent"), 85)))
    fade_seconds = _core._integer(volume.get("fade_seconds"), 10)
    player = shutil.which("aplay")
    requested_at = time.monotonic()

    with manager.lock:
        manager.state.update(
            {
                "current_occurrence_key": occurrence.get("occurrence_key"),
                "standalone_audio_test": bool(occurrence.get("standalone_audio_test")),
                "last_error": None,
            }
        )
        manager._record(
            "playback-requested",
            occurrence_key=occurrence.get("occurrence_key"),
            duration_seconds=duration,
            start_percent=start_percent,
            target_percent=target_percent,
            volume_cap_percent=volume_cap,
            streaming=True,
        )

    if not player:
        with manager.lock:
            manager.state["last_error"] = "aplay was not found. Install alsa-utils."
            manager._record("playback-failed", error=manager.state["last_error"])
        return

    snapshot = manager._release(settings)
    manager.owner_snapshot = snapshot
    with manager.lock:
        manager.state["owner_snapshot"] = deepcopy(snapshot)
        manager._record(
            "audio-owner-warning" if snapshot.get("error") else "audio-owners-released",
            **snapshot,
        )

    success = False
    error: str | None = None
    try:
        for index, tone_id in enumerate(tone_ids):
            if manager.stop_event.is_set():
                break
            tone = manager._tone(tone_id)
            if not tone:
                error = f"Unknown tone: {tone_id}"
                continue

            process: subprocess.Popen[Any] | None = None
            try:
                command = [
                    player,
                    "-q",
                    "-D",
                    settings["alsa_device"],
                    "-t",
                    "raw",
                    "-f",
                    "S16_LE",
                    "-r",
                    str(SAMPLE_RATE),
                    "-c",
                    str(CHANNELS),
                ]
                process = manager.popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    bufsize=0,
                )
                with manager.lock:
                    manager.process = process
                    manager.state.update(
                        {
                            "playback_active": True,
                            "current_tone_id": tone_id,
                            "current_tone_label": str(tone.get("label", tone_id)),
                            "fallback_used": index > 0,
                        }
                    )
                    manager._record(
                        "playback-started",
                        tone_id=tone_id,
                        fallback_used=index > 0,
                        streaming=True,
                        startup_seconds=round(time.monotonic() - requested_at, 3),
                    )

                if process.stdin is None:
                    raise OSError("aplay did not provide a PCM input pipe.")

                try:
                    for chunk in iter_tone_pcm_chunks(
                        tone,
                        duration_seconds=duration,
                        start_percent=start_percent,
                        target_percent=target_percent,
                        fade_seconds=fade_seconds,
                    ):
                        if manager.stop_event.is_set() or process.poll() is not None:
                            break
                        process.stdin.write(chunk)
                except (BrokenPipeError, OSError) as exc:
                    if process.poll() is None and not manager.stop_event.is_set():
                        raise
                    error = str(exc)
                finally:
                    try:
                        process.stdin.close()
                    except OSError:
                        pass

                if manager.stop_event.is_set() and process.poll() is None:
                    return_code = manager._terminate_process(process)
                else:
                    while process.poll() is None and not manager.stop_event.wait(0.05):
                        pass
                    if manager.stop_event.is_set() and process.poll() is None:
                        return_code = manager._terminate_process(process)
                    else:
                        return_code = process.poll()
                        if return_code is None:
                            return_code = process.wait(timeout=2)

                process_error = _stderr_text(process, return_code)
                if process_error:
                    error = process_error
                success = return_code == 0
                if success or manager.stop_event.is_set():
                    break
            except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
                error = str(exc)
                manager._terminate_process(process)
            finally:
                with manager.lock:
                    manager.process = None
                    manager.state["playback_active"] = False

            if index == 0 and len(tone_ids) > 1:
                with manager.lock:
                    manager._record(
                        "fallback-requested",
                        error=error,
                        fallback_tone_id=tone_ids[1],
                    )
    finally:
        manager._restore(settings, snapshot)
        manager.owner_snapshot = None
        with manager.lock:
            manager.state.update({"playback_active": False, "owner_snapshot": None})
            if not success and error and not manager.stop_event.is_set():
                manager.state["last_error"] = error
                manager._record("playback-failed", error=error)
            else:
                manager._record("playback-finished" if success else "playback-stopped")
