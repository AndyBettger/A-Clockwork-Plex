from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from app.alarm_audio import (
    MAX_PREVIEW_SECONDS,
    SAFE_PREVIEW_VOLUME_PERCENT,
    AlarmAudioManager,
)


MANIFEST = {
    "preview_seconds": 10,
    "fallback_tone_id": "emergency-buzzer",
    "tones": [
        {
            "id": "classic-klaxon",
            "label": "Classic Klaxon",
            "pattern": [
                {
                    "frequency": 640,
                    "duration_ms": 360,
                    "gap_ms": 55,
                    "wave": "square",
                    "gain": 0.22,
                }
            ],
        },
        {
            "id": "emergency-buzzer",
            "label": "Emergency Buzzer",
            "pattern": [
                {
                    "frequency": 980,
                    "duration_ms": 280,
                    "gap_ms": 70,
                    "wave": "square",
                    "gain": 0.24,
                }
            ],
        },
    ],
}


class CapturingAlarmAudioManager(AlarmAudioManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.captured: tuple[dict, str] | None = None

    def _start(self, occurrence, cycle):
        self.captured = (deepcopy(occurrence), str(cycle))


class AlarmAudioPreviewTests(unittest.TestCase):
    def build_manager(self, root: Path, *, master_enabled: bool = True) -> CapturingAlarmAudioManager:
        return CapturingAlarmAudioManager(
            lambda: {"alarm_audio": {"master_enabled": master_enabled}},
            lambda: deepcopy(MANIFEST),
            lambda: {},
            root / "alarm-audio-runtime.json",
        )

    def test_preview_is_fixed_low_volume_standalone_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self.build_manager(Path(directory))
            status = manager.preview_tone("classic-klaxon")

        self.assertIsNotNone(manager.captured)
        occurrence, cycle = manager.captured
        self.assertTrue(occurrence["audio_test"])
        self.assertTrue(occurrence["standalone_audio_test"])
        self.assertEqual(occurrence["audio_duration_seconds"], MAX_PREVIEW_SECONDS)
        self.assertEqual(occurrence["volume"]["start_percent"], SAFE_PREVIEW_VOLUME_PERCENT)
        self.assertEqual(occurrence["volume"]["target_percent"], SAFE_PREVIEW_VOLUME_PERCENT)
        self.assertEqual(occurrence["volume"]["fade_seconds"], 0)
        self.assertEqual(occurrence["source"]["tone_id"], "classic-klaxon")
        self.assertEqual(occurrence["source"]["fallback_tone_id"], "emergency-buzzer")
        self.assertTrue(cycle.startswith("preview|audio-preview|"))
        self.assertEqual(status["preview_duration_seconds"], MAX_PREVIEW_SECONDS)
        self.assertEqual(status["preview_volume_percent"], SAFE_PREVIEW_VOLUME_PERCENT)

    def test_preview_still_requires_master_audio_safety_switch(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self.build_manager(Path(directory), master_enabled=False)
            with self.assertRaisesRegex(ValueError, "locked"):
                manager.preview_tone("classic-klaxon")

    def test_unknown_preview_tone_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self.build_manager(Path(directory))
            with self.assertRaisesRegex(ValueError, "Unknown tone"):
                manager.preview_tone("not-a-tone")


if __name__ == "__main__":
    unittest.main()
