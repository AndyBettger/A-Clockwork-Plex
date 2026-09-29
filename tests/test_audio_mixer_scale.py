from __future__ import annotations

import importlib.util
import sys
import tempfile
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
    def test_managed_split_bus_metadata_overrides_legacy_rate_and_dac(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "a-clockwork-plex-audio"
            managed = root / "a-clockwork-plex-split-bus"
            legacy.write_text(
                "ALSA_CARD=Legacy\n"
                "ALSA_DEVICE=9\n"
                "SAMPLE_RATE=44100\n"
                "CHANNELS=2\n",
                encoding="utf-8",
            )
            managed.write_text(
                "DAC_CARD=Pro\n"
                "DAC_DEVICE=0\n"
                "SAMPLE_RATE=192000\n",
                encoding="utf-8",
            )

            config = HELPER.load_config(legacy, managed)

        self.assertEqual(config["ALSA_CARD"], "Pro")
        self.assertEqual(config["ALSA_DEVICE"], "0")
        self.assertEqual(config["SAMPLE_RATE"], "192000")
        self.assertEqual(config["CHANNELS"], "2")

    def test_managed_metadata_absence_preserves_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "a-clockwork-plex-audio"
            legacy.write_text(
                "ALSA_CARD=Pro\n"
                "ALSA_DEVICE=0\n"
                "SAMPLE_RATE=44100\n"
                "CHANNELS=2\n",
                encoding="utf-8",
            )

            config = HELPER.load_config(legacy, root / "missing-managed")

        self.assertEqual(config["SAMPLE_RATE"], "44100")


    def test_active_processing_status_follows_selected_route_not_split_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            split = root / "split.conf"
            direct = root / "direct.conf"
            split.write_text(
                'pcm.acp_dmix {\n'
                '    type dmix\n'
                '    slave {\n'
                '        pcm "hw:CARD=ACP_Loopback,DEV=0"\n'
                '        format S32_LE\n'
                '        rate 192000\n'
                '        channels 4\n'
                '        period_size 4096\n'
                '        buffer_size 32768\n'
                '    }\n'
                '}\n'
                'pcm.acp_master { type plug }\n',
                encoding="utf-8",
            )
            direct.write_text(
                'pcm.acp_dmix {\n'
                '    type dmix\n'
                '    slave {\n'
                '        pcm "hw:CARD=Pro,DEV=0"\n'
                '        format S16_LE\n'
                '        rate 44100\n'
                '        channels 2\n'
                '        period_size 1024\n'
                '        buffer_size 8192\n'
                '    }\n'
                '}\n'
                'pcm.acp_master { type plug }\n',
                encoding="utf-8",
            )

            split_status = HELPER.active_processing_status(split)
            direct_status = HELPER.active_processing_status(direct)

        self.assertTrue(split_status["available"])
        self.assertEqual(split_status["format"], "S32_LE")
        self.assertEqual(split_status["rate_hz"], 192000)
        self.assertEqual(split_status["channels"], 4)
        self.assertTrue(direct_status["available"])
        self.assertEqual(direct_status["format"], "S16_LE")
        self.assertEqual(direct_status["rate_hz"], 44100)
        self.assertEqual(direct_status["channels"], 2)

    def test_dac_playback_status_reports_open_hw_params_and_closed_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hw = root / "hw_params"
            hw.write_text(
                "access: RW_INTERLEAVED\n"
                "format: S32_LE\n"
                "subformat: STD\n"
                "channels: 2\n"
                "rate: 192000 (192000/1)\n"
                "period_size: 2048\n"
                "buffer_size: 16384\n",
                encoding="utf-8",
            )
            opened = HELPER.dac_playback_status("Pro", "0", path=hw)
            hw.write_text("closed\n", encoding="utf-8")
            closed = HELPER.dac_playback_status("Pro", "0", path=hw)

        self.assertTrue(opened["available"])
        self.assertTrue(opened["open"])
        self.assertEqual(opened["format"], "S32_LE")
        self.assertEqual(opened["rate_hz"], 192000)
        self.assertEqual(opened["period_size"], 2048)
        self.assertEqual(opened["buffer_size"], 16384)
        self.assertTrue(closed["available"])
        self.assertFalse(closed["open"])
        self.assertIsNone(closed["rate_hz"])

    def test_audio_path_keeps_source_unknown_and_separates_processing_from_dac(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            route = root / "active.conf"
            route.write_text(
                'pcm.acp_dmix {\n'
                '    slave {\n'
                '        format S32_LE\n'
                '        rate 192000\n'
                '        channels 4\n'
                '    }\n'
                '}\n'
                'pcm.acp_master { type plug }\n',
                encoding="utf-8",
            )
            state = root / "route-state.json"
            state.write_text(
                '{"mode":"split-bus-selected"}\n',
                encoding="utf-8",
            )
            hw = root / "hw_params"
            hw.write_text(
                "format: S32_LE\nchannels: 2\nrate: 192000 (192000/1)\n"
                "period_size: 2048\nbuffer_size: 16384\n",
                encoding="utf-8",
            )
            status = HELPER.audio_path_status(
                {"ALSA_CARD": "Pro", "ALSA_DEVICE": "0"},
                active_alsa_path=route,
                route_state_path=state,
                dac_hw_params_path=hw,
            )

        self.assertEqual(status["route_mode"], "split-bus-selected")
        self.assertFalse(status["source"]["available"])
        self.assertIsNone(status["source"]["rate_hz"])
        self.assertEqual(status["processing"]["rate_hz"], 192000)
        self.assertEqual(status["dac"]["rate_hz"], 192000)
        self.assertNotEqual(
            status["source"]["authority"],
            status["processing"]["authority"],
        )

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
