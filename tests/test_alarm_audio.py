from __future__ import annotations

import tempfile
import unittest
import wave
from pathlib import Path

from app.alarm_audio import AlarmAudioManager, normalise_audio_settings, render_tone_wav


class AlarmAudioTests(unittest.TestCase):
    def test_settings_keep_scheduled_playback_locked(self):
        settings = normalise_audio_settings(
            {
                "master_enabled": True,
                "scheduled_enabled": True,
                "test_duration_seconds": 999,
                "alsa_device": "  hw:1,0  ",
            }
        )
        self.assertTrue(settings["master_enabled"])
        self.assertFalse(settings["scheduled_enabled"])
        self.assertEqual(settings["test_duration_seconds"], 30)
        self.assertEqual(settings["alsa_device"], "hw:1,0")

    def test_renderer_creates_valid_mono_wave_file(self):
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
                self.assertEqual(audio.getnchannels(), 1)
                self.assertEqual(audio.getsampwidth(), 2)
                self.assertEqual(audio.getframerate(), 22050)
                self.assertEqual(audio.getnframes(), 22050)

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


if __name__ == "__main__":
    unittest.main()
