from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import configuration_reset


SCRIPT_PATH = ROOT / "scripts" / "a-clockwork-plex-audio-mixer.py"
SPEC = importlib.util.spec_from_file_location("a_clockwork_plex_audio_mixer_helper", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load mixer helper from {SCRIPT_PATH}")
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)


class AudioMixerScaleTests(unittest.TestCase):
    def test_human_percentages_map_to_expected_decibels(self):
        self.assertAlmostEqual(HELPER.loudness_percent_to_db(100), 0.0, places=2)
        self.assertAlmostEqual(HELPER.loudness_percent_to_db(50), -6.02, places=2)
        self.assertAlmostEqual(HELPER.loudness_percent_to_db(25), -12.04, places=2)
        self.assertAlmostEqual(HELPER.loudness_percent_to_db(10), -20.0, places=2)
        self.assertIsNone(HELPER.loudness_percent_to_db(0))

    def test_decibels_round_trip_to_human_percentages(self):
        for percent in (10, 25, 50, 75, 100):
            db_value = HELPER.loudness_percent_to_db(percent)
            self.assertIsNotNone(db_value)
            self.assertAlmostEqual(HELPER.db_to_loudness_percent(db_value), percent, delta=1)

    def test_floor_maps_to_zero(self):
        self.assertEqual(HELPER.db_to_loudness_percent(-51.0), 0)
        self.assertEqual(HELPER.db_to_loudness_percent(-80.0), 0)

    def test_decibels_convert_to_positive_raw_alsa_percentages(self):
        self.assertEqual(HELPER.db_to_raw_percent(None), 0)
        self.assertEqual(HELPER.db_to_raw_percent(-51.0), 0)
        self.assertEqual(HELPER.db_to_raw_percent(0.0), 100)
        self.assertAlmostEqual(HELPER.db_to_raw_percent(-6.02), 88, delta=1)
        self.assertAlmostEqual(HELPER.db_to_raw_percent(-12.04), 76, delta=1)
        self.assertAlmostEqual(HELPER.db_to_raw_percent(-20.0), 61, delta=1)

    def test_reset_defaults_use_the_helpers_observable_quantized_percentages(self):
        self.assertEqual(configuration_reset.MIXER_MIN_DB, HELPER.MIN_DB)
        self.assertEqual(configuration_reset.MIXER_MAX_DB, HELPER.MAX_DB)
        defaults = configuration_reset._default_mixer()
        self.assertEqual(defaults["master"], 100)
        self.assertEqual(defaults["plexamp"], 100)
        self.assertEqual(defaults["airplay"], 100)
        self.assertEqual(defaults["alarm"], 100)

        for channel, requested in {
            key: int(metadata["default_percent"])
            for key, metadata in configuration_reset.MIXER_CHANNELS.items()
        }.items():
            db_value = HELPER.loudness_percent_to_db(requested)
            raw_percent = HELPER.db_to_raw_percent(db_value)
            represented_db = HELPER.MIN_DB + (
                (HELPER.MAX_DB - HELPER.MIN_DB) * raw_percent / 100.0
            )
            observed = HELPER.db_to_loudness_percent(represented_db)
            self.assertEqual(defaults[channel], observed)


if __name__ == "__main__":
    unittest.main()
