from __future__ import annotations

import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

from app.alarm_audio import AlarmAudioManager, normalise_audio_settings, render_tone_wav


class StubbornProcess:
    def __init__(self) -> None:
        self.returncode = None
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True
        self.returncode = -9

    def wait(self, timeout=None):
        if not self.killed:
            raise subprocess.TimeoutExpired("aplay", timeout)
        return self.returncode


class AlarmAudioTests(unittest.TestCase):
    def test_settings_keep_scheduled_playback_locked(self):
        settings = normalise_audio_settings(
            {
                "master_enabled": True,
                "scheduled_enabled": True,
                "test_duration_seconds": 999,
                "test_volume_cap_percent": 100,
                "alsa_device": "  hw:1,0  ",
            }
        )
        self.assertTrue(settings["master_enabled"])
        self.assertFalse(settings["scheduled_enabled"])
        self.assertEqual(settings["test_duration_seconds"], 30)
        self.assertEqual(settings["test_volume_cap_percent"], 25)
        self.assertEqual(settings["alsa_device"], "hw:1,0")

    def test_renderer_creates_valid_stereo_wave_file(self):
        tone = {
            "id": "test-tone",
            "pattern": [
                {
                    "frequency": 440,
                    "end_frequency": 660,
                    "duration_ms": 120,
                    "gap_ms": 40,
                    "wave": "sine",
                    "gain": 0.15,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tone.wav"
            render_tone_wav(
                tone,
                path,
                duration_seconds=1,
                start_percent=20,
                target_percent=80,
                fade_seconds=1,
            )
            with wave.open(str(path), "rb") as audio:
                self.assertEqual(audio.getnchannels(), 2)
                self.assertEqual(audio.getsampwidth(), 2)
                self.assertEqual(audio.getframerate(), 44100)
                self.assertEqual(audio.getnframes(), 44100)
                frames = audio.readframes(256)

            samples = memoryview(frames).cast("h")
            self.assertGreater(len(samples), 2)
            for index in range(0, len(samples) - 1, 2):
                self.assertEqual(samples[index], samples[index + 1])

    def test_master_switch_blocks_test_playback(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = AlarmAudioManager(
                lambda: {"alarm_audio": {"master_enabled": False}},
                lambda: {"tones": []},
                lambda: {},
                Path(directory) / "runtime.json",
            )
            with self.assertRaisesRegex(ValueError, "master safety switch"):
                manager.test_tone({"label": "Blocked test"})

    def test_occurrence_arming_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = AlarmAudioManager(
                lambda: {"alarm_audio": {}},
                lambda: {"tones": []},
                lambda: {},
                Path(directory) / "runtime.json",
            )
            manager.arm_occurrence("test|123")
            self.assertEqual(manager.status()["armed_occurrence_count"], 1)
            manager.disarm_occurrence("test|123")
            self.assertEqual(manager.status()["armed_occurrence_count"], 0)

    def test_diagnostics_report_stereo_format(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = AlarmAudioManager(
                lambda: {"alarm_audio": {"alsa_device": "plughw:CARD=Pro,DEV=0"}},
                lambda: {"tones": []},
                lambda: {},
                Path(directory) / "runtime.json",
            )
            player_format = manager.diagnostics()["player"]["format"]
            self.assertEqual(player_format["sample_rate_hz"], 44100)
            self.assertEqual(player_format["channels"], 2)
            self.assertEqual(player_format["sample_width_bits"], 16)
            self.assertEqual(player_format["channel_layout"], "dual-mono stereo")

    def test_restore_runs_once_for_each_handover(self):
        calls = []

        def runner(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, stdout='{"restored":true}', stderr="")

        with tempfile.TemporaryDirectory() as directory:
            manager = AlarmAudioManager(
                lambda: {"alarm_audio": {}},
                lambda: {"tones": []},
                lambda: {},
                Path(directory) / "runtime.json",
                runner=runner,
            )
            settings = {
                "restore_services": True,
                "helper_path": "/usr/local/bin/a-clockwork-plex-alarm-audio",
            }
            snapshot = {
                "available": True,
                "plexamp_active": True,
                "shairport_active": False,
                "handover_id": "handover-123",
            }

            manager._restore(settings, snapshot)
            manager._restore(settings, dict(snapshot))

            self.assertEqual(len(calls), 1)
            self.assertEqual(manager.status()["last_restore_helper"], {"restored": True})
            self.assertEqual(manager.status()["last_action"]["action"], "audio-owners-restored")

    def test_stubborn_player_is_killed_after_terminate_timeout(self):
        process = StubbornProcess()
        return_code = AlarmAudioManager._terminate_process(process)
        self.assertTrue(process.terminated)
        self.assertTrue(process.killed)
        self.assertEqual(return_code, -9)


if __name__ == "__main__":
    unittest.main()
