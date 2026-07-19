from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
import threading
import uuid
import wave
from array import array
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

DEFAULT_AUDIO_SETTINGS = {
    "master_enabled": False,
    "scheduled_enabled": False,
    "release_services": True,
    "restore_services": True,
    "backend": "aplay",
    "alsa_device": "default",
    "test_duration_seconds": 12,
    "helper_path": "/usr/local/bin/a-clockwork-plex-alarm-audio",
}
SAMPLE_RATE = 22050
MAX_TEST_SECONDS = 30


def _integer(value: Any, fallback: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return fallback


def normalise_audio_settings(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    return {
        "master_enabled": bool(source.get("master_enabled", False)),
        # Scheduled alarms remain hard-locked during the controlled test pass.
        "scheduled_enabled": False,
        "release_services": bool(source.get("release_services", True)),
        "restore_services": bool(source.get("restore_services", True)),
        "backend": "aplay",
        "alsa_device": str(source.get("alsa_device", "default")).strip()[:120] or "default",
        "test_duration_seconds": max(3, min(MAX_TEST_SECONDS, _integer(source.get("test_duration_seconds"), 12))),
        "helper_path": str(source.get("helper_path", DEFAULT_AUDIO_SETTINGS["helper_path"])).strip()[:240]
        or DEFAULT_AUDIO_SETTINGS["helper_path"],
    }


def _oscillator(waveform: str, phase: float) -> float:
    cycle = phase % (2 * math.pi)
    if waveform == "square":
        return 1.0 if math.sin(cycle) >= 0 else -1.0
    if waveform == "triangle":
        return (2 / math.pi) * math.asin(math.sin(cycle))
    if waveform == "sawtooth":
        return cycle / math.pi - 1
    return math.sin(cycle)


def render_tone_wav(
    tone: dict[str, Any],
    destination: Path,
    *,
    duration_seconds: int,
    start_percent: int,
    target_percent: int,
    fade_seconds: int,
) -> None:
    raw_pattern = tone.get("pattern") if isinstance(tone, dict) else None
    if not isinstance(raw_pattern, list) or not raw_pattern:
        raise ValueError("The selected tone has no playable pattern.")

    pattern = []
    for item in raw_pattern:
        if not isinstance(item, dict):
            continue
        start = max(20.0, min(5000.0, float(item.get("frequency", 440) or 440)))
        end = max(20.0, min(5000.0, float(item.get("end_frequency", start) or start)))
        waveform = str(item.get("wave", "sine")).lower()
        if waveform not in {"sine", "square", "triangle", "sawtooth"}:
            waveform = "sine"
        pattern.append(
            {
                "start": start,
                "end": end,
                "duration": max(20, min(3000, _integer(item.get("duration_ms"), 200))),
                "gap": max(0, min(3000, _integer(item.get("gap_ms"), 0))),
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
    total = seconds * SAMPLE_RATE
    samples = array("h")
    produced = 0
    phase = 0.0

    while produced < total:
        for step in pattern:
            count = max(1, round(step["duration"] * SAMPLE_RATE / 1000))
            gap = max(0, round(step["gap"] * SAMPLE_RATE / 1000))
            attack = min(count // 2, max(1, round(0.015 * SAMPLE_RATE)))
            release = min(count // 2, max(1, round(0.025 * SAMPLE_RATE)))
            for index in range(count):
                if produced >= total:
                    break
                progress = index / max(1, count - 1)
                frequency = step["start"] + (step["end"] - step["start"]) * progress
                phase += 2 * math.pi * frequency / SAMPLE_RATE
                envelope = 1.0
                if index < attack:
                    envelope = index / max(1, attack)
                elif index >= count - release:
                    envelope = max(0.0, (count - index - 1) / max(1, release))
                elapsed = produced / SAMPLE_RATE
                volume = start_gain + (target_gain - start_gain) * min(1, elapsed / fade) if fade else target_gain
                value = _oscillator(step["wave"], phase) * step["gain"] * envelope * volume
                samples.append(int(max(-1.0, min(1.0, value)) * 32767))
                produced += 1
            silence = min(gap, total - produced)
            samples.extend([0] * silence)
            produced += silence
            if produced >= total:
                break

    destination.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destination), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(samples.tobytes())


class AlarmAudioManager:
    """Explicit-test-only local playback and DAC ownership coordinator."""

    def __init__(
        self,
        config_loader: Callable[[], dict[str, Any]],
        manifest_loader: Callable[[], dict[str, Any]],
        scheduler_status: Callable[[], dict[str, Any]],
        runtime_path: Path,
        *,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        popen: Callable[..., subprocess.Popen[Any]] | None = None,
    ) -> None:
        self.config_loader = config_loader
        self.manifest_loader = manifest_loader
        self.scheduler_status = scheduler_status
        self.runtime_path = Path(runtime_path)
        self.runner = runner or subprocess.run
        self.popen = popen or subprocess.Popen
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.monitor_stop = threading.Event()
        self.monitor_thread: threading.Thread | None = None
        self.worker_thread: threading.Thread | None = None
        self.process: subprocess.Popen[Any] | None = None
        self.owner_snapshot: dict[str, Any] | None = None
        self.armed: set[str] = set()
        self.played_cycles: set[str] = set()
        self.state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        state = {
            "manager_running": False,
            "playback_active": False,
            "current_occurrence_key": None,
            "current_tone_id": None,
            "current_tone_label": None,
            "fallback_used": False,
            "last_error": None,
            "last_action": None,
            "history": [],
        }
        try:
            loaded = json.loads(self.runtime_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state.update(loaded)
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            pass
        state.update({"manager_running": False, "playback_active": False, "owner_snapshot": None})
        return state

    def _save(self) -> None:
        self.runtime_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.runtime_path.with_suffix(self.runtime_path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(self.state, handle, indent=2, sort_keys=True)
            handle.write("\n")
        temporary.replace(self.runtime_path)

    def _record(self, action: str, **details: Any) -> None:
        event = {"action": action, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **details}
        self.state["last_action"] = event
        history = [item for item in self.state.get("history", []) if isinstance(item, dict)]
        self.state["history"] = (history + [event])[-64:]
        try:
            self._save()
        except OSError as exc:
            self.state["last_error"] = f"Could not save audio runtime state: {exc}"

    def settings(self) -> dict[str, Any]:
        config = self.config_loader()
        return normalise_audio_settings(config.get("alarm_audio") if isinstance(config, dict) else None)

    def _tone(self, tone_id: Any) -> dict[str, Any] | None:
        wanted = str(tone_id or "").lower()
        for tone in self.manifest_loader().get("tones", []):
            if isinstance(tone, dict) and str(tone.get("id", "")).lower() == wanted:
                return deepcopy(tone)
        return None

    def _helper_status(self, settings: dict[str, Any]) -> dict[str, Any]:
        helper = Path(settings["helper_path"])
        if not helper.exists() or not os.access(helper, os.X_OK):
            return {"available": False, "error": "Alarm audio helper is not installed."}
        try:
            result = self.runner([str(helper), "status"], capture_output=True, text=True, timeout=4, check=False)
            payload = json.loads(result.stdout or "{}") if result.returncode == 0 else {}
            return {
                "available": True,
                "plexamp_active": payload.get("plexamp_active") is True,
                "shairport_active": payload.get("shairport_active") is True,
                "error": None if result.returncode == 0 else (result.stderr or result.stdout).strip(),
            }
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            return {"available": True, "error": str(exc)}

    def _release(self, settings: dict[str, Any]) -> dict[str, Any]:
        snapshot = self._helper_status(settings)
        if not settings["release_services"] or not snapshot.get("available"):
            return snapshot
        try:
            result = self.runner(
                ["sudo", "-n", settings["helper_path"], "release"],
                capture_output=True,
                text=True,
                timeout=12,
                check=False,
            )
            if result.returncode:
                snapshot["error"] = (result.stderr or result.stdout or "Audio release failed.").strip()
        except (OSError, subprocess.TimeoutExpired) as exc:
            snapshot["error"] = str(exc)
        return snapshot

    def _restore(self, settings: dict[str, Any], snapshot: dict[str, Any] | None) -> None:
        if not settings["restore_services"] or not snapshot or not snapshot.get("available"):
            return
        args = [
            "sudo", "-n", settings["helper_path"], "restore",
            "1" if snapshot.get("plexamp_active") else "0",
            "1" if snapshot.get("shairport_active") else "0",
        ]
        try:
            result = self.runner(args, capture_output=True, text=True, timeout=15, check=False)
            if result.returncode:
                self.state["last_error"] = (result.stderr or result.stdout or "Audio restore failed.").strip()
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.state["last_error"] = str(exc)

    def diagnostics(self) -> dict[str, Any]:
        settings = self.settings()
        player = shutil.which("aplay")
        helper = self._helper_status(settings)
        return {
            "settings": settings,
            "runtime": self.status(),
            "helper": helper,
            "player": {
                "available": bool(player),
                "command": [player, "-q", "-D", settings["alsa_device"]] if player else None,
                "error": None if player else "aplay was not found. Install alsa-utils.",
            },
            "scheduled_playback_enabled": False,
            "safety_message": "Only explicit tests may make sound. Scheduled alarms remain locked.",
        }

    def start(self) -> None:
        with self.lock:
            if self.monitor_thread and self.monitor_thread.is_alive():
                return
            self.monitor_stop.clear()
            self.state["manager_running"] = True
            self._record("manager-started")
        self.monitor_thread = threading.Thread(target=self._monitor, name="alarm-audio-monitor", daemon=True)
        self.monitor_thread.start()

    def shutdown(self) -> None:
        self.monitor_stop.set()
        self.stop_playback(reason="manager-shutdown")
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=3)
        with self.lock:
            self.state["manager_running"] = False
            self._record("manager-stopped")

    def arm_occurrence(self, key: str) -> None:
        if not str(key).strip():
            raise ValueError("Cannot arm audio without an occurrence key.")
        with self.lock:
            self.armed.add(str(key))
            self._record("occurrence-armed", occurrence_key=str(key))

    def disarm_occurrence(self, key: str | None = None) -> None:
        with self.lock:
            self.armed.discard(str(key)) if key else self.armed.clear()
            self._record("occurrence-disarmed", occurrence_key=key)

    def test_tone(self, occurrence: dict[str, Any]) -> dict[str, Any]:
        settings = self.settings()
        if not settings["master_enabled"]:
            raise ValueError("Alarm audio is locked. Enable the master safety switch first.")
        payload = deepcopy(occurrence)
        payload.update(
            {
                "occurrence_key": str(payload.get("occurrence_key") or f"audio-test|{uuid.uuid4().hex}"),
                "audio_test": True,
                "standalone_audio_test": True,
                "audio_duration_seconds": settings["test_duration_seconds"],
            }
        )
        self._start(payload, f"direct|{payload['occurrence_key']}")
        return self.status()

    def _start(self, occurrence: dict[str, Any], cycle: str) -> None:
        settings = self.settings()
        if not settings["master_enabled"]:
            raise ValueError("Alarm audio is locked by the master switch.")
        if not occurrence.get("audio_test"):
            raise ValueError("Scheduled alarm playback is still locked in this pass.")
        with self.lock:
            if cycle in self.played_cycles:
                return
        self.stop_playback(reason="replaced-by-new-test")
        with self.lock:
            self.played_cycles.add(cycle)
            self.stop_event.clear()
            self.worker_thread = threading.Thread(
                target=self._play,
                args=(deepcopy(occurrence), settings),
                name="alarm-audio-player",
                daemon=True,
            )
            self.worker_thread.start()

    def _play(self, occurrence: dict[str, Any], settings: dict[str, Any]) -> None:
        source = occurrence.get("source") if isinstance(occurrence.get("source"), dict) else {}
        volume = occurrence.get("volume") if isinstance(occurrence.get("volume"), dict) else {}
        tone_ids = []
        for value in (source.get("tone_id", "classic-klaxon"), source.get("fallback_tone_id", "emergency-buzzer")):
            if value and str(value) not in tone_ids:
                tone_ids.append(str(value))
        duration = max(3, min(MAX_TEST_SECONDS, _integer(occurrence.get("audio_duration_seconds"), settings["test_duration_seconds"])))
        player = shutil.which("aplay")
        with self.lock:
            self.state.update(
                {
                    "current_occurrence_key": occurrence.get("occurrence_key"),
                    "standalone_audio_test": bool(occurrence.get("standalone_audio_test")),
                    "last_error": None,
                }
            )
            self._record("playback-requested", occurrence_key=occurrence.get("occurrence_key"), duration_seconds=duration)
        if not player:
            with self.lock:
                self.state["last_error"] = "aplay was not found. Install alsa-utils."
                self._record("playback-failed", error=self.state["last_error"])
            return

        snapshot = self._release(settings)
        self.owner_snapshot = snapshot
        with self.lock:
            self.state["owner_snapshot"] = deepcopy(snapshot)
            self._record("audio-owner-warning" if snapshot.get("error") else "audio-owners-released", **snapshot)

        success = False
        error = None
        for index, tone_id in enumerate(tone_ids):
            if self.stop_event.is_set():
                break
            tone = self._tone(tone_id)
            if not tone:
                error = f"Unknown tone: {tone_id}"
                continue
            wav_path = Path(tempfile.gettempdir()) / f"a-clockwork-plex-{uuid.uuid4().hex}.wav"
            try:
                render_tone_wav(
                    tone,
                    wav_path,
                    duration_seconds=duration,
                    start_percent=_integer(volume.get("start_percent"), 60),
                    target_percent=_integer(volume.get("target_percent"), 85),
                    fade_seconds=_integer(volume.get("fade_seconds"), 10),
                )
                command = [player, "-q", "-D", settings["alsa_device"], str(wav_path)]
                process = self.popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                with self.lock:
                    self.process = process
                    self.state.update(
                        {
                            "playback_active": True,
                            "current_tone_id": tone_id,
                            "current_tone_label": str(tone.get("label", tone_id)),
                            "fallback_used": index > 0,
                        }
                    )
                    self._record("playback-started", tone_id=tone_id, fallback_used=index > 0)
                while process.poll() is None and not self.stop_event.wait(0.1):
                    pass
                if self.stop_event.is_set() and process.poll() is None:
                    process.terminate()
                return_code = process.wait(timeout=2)
                error = process.stderr.read().strip() if return_code and process.stderr else None
                success = return_code == 0
                if success or self.stop_event.is_set():
                    break
            except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
                error = str(exc)
            finally:
                wav_path.unlink(missing_ok=True)
                with self.lock:
                    self.process = None
                    self.state["playback_active"] = False
            if index == 0 and len(tone_ids) > 1:
                with self.lock:
                    self._record("fallback-requested", error=error, fallback_tone_id=tone_ids[1])

        self._restore(settings, snapshot)
        self.owner_snapshot = None
        with self.lock:
            self.state.update({"playback_active": False, "owner_snapshot": None})
            if not success and error and not self.stop_event.is_set():
                self.state["last_error"] = error
                self._record("playback-failed", error=error)
            else:
                self._record("playback-finished" if success else "playback-stopped")

    def stop_playback(self, *, reason: str = "stopped", restore: bool = True) -> dict[str, Any]:
        settings = self.settings()
        with self.lock:
            self.stop_event.set()
            process = self.process
            snapshot = deepcopy(self.owner_snapshot)
            if process and process.poll() is None:
                process.terminate()
        if self.worker_thread and self.worker_thread.is_alive() and self.worker_thread is not threading.current_thread():
            self.worker_thread.join(timeout=3)
        if restore and snapshot and self.owner_snapshot is not None:
            self._restore(settings, snapshot)
        with self.lock:
            self.process = None
            self.owner_snapshot = None
            self.state.update({"playback_active": False, "owner_snapshot": None})
            self._record("playback-stop-requested", reason=reason)
        return self.status()

    def _monitor(self) -> None:
        while not self.monitor_stop.wait(0.25):
            try:
                scheduler = self.scheduler_status()
            except Exception as exc:
                with self.lock:
                    self.state["last_error"] = f"Could not read scheduler state: {exc}"
                continue
            active = scheduler.get("active_occurrence") if isinstance(scheduler, dict) else None
            completed = {str(value) for value in scheduler.get("completed_occurrence_keys", []) if value}
            with self.lock:
                self.armed.difference_update(completed)
            key = str(active.get("occurrence_key", "")) if isinstance(active, dict) else ""
            phase = active.get("phase") if isinstance(active, dict) else None
            cycle = f"{key}|{active.get('ring_cycle_started_at', '')}" if isinstance(active, dict) else ""
            with self.lock:
                armed = key in self.armed
                playing = bool(self.state.get("playback_active"))
                current = str(self.state.get("current_occurrence_key") or "")
                standalone = bool(self.state.get("standalone_audio_test"))
            if armed and phase == "ringing" and key:
                occurrence = deepcopy(active)
                occurrence["audio_test"] = True
                try:
                    self._start(occurrence, cycle)
                except ValueError as exc:
                    with self.lock:
                        self.state["last_error"] = str(exc)
                continue
            if playing and not standalone and (not active or phase != "ringing" or current != key):
                self.stop_playback(reason="alarm-left-ringing-state")

    def status(self) -> dict[str, Any]:
        with self.lock:
            state = deepcopy(self.state)
            state["manager_running"] = bool(self.monitor_thread and self.monitor_thread.is_alive())
            state["worker_alive"] = bool(self.worker_thread and self.worker_thread.is_alive())
            state["armed_occurrence_count"] = len(self.armed)
            return state
