from __future__ import annotations

import unittest
from pathlib import Path


class SettingsAudioLevelCardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mixer = Path("app/audio_mixer.py").read_text(encoding="utf-8")
        self.css = Path("app/static/css/settings-physical-followup.css").read_text(encoding="utf-8")

    def test_music_master_metadata_matches_the_split_bus_contract(self):
        self.assertIn('"label": "Music master"', self.mixer)
        self.assertIn(
            '"description": "Shared persistent level for Plexamp and AirPlay. Scheduled alarms bypass this control."',
            self.mixer,
        )
        self.assertNotIn(
            'Persistent final output level applied to Plexamp, AirPlay and alarm audio.',
            self.mixer,
        )

    def test_alarm_metadata_remains_a_global_ceiling(self):
        self.assertIn('"label": "Maximum alarm volume"', self.mixer)
        self.assertIn(
            '"description": "Global ceiling after each alarm\'s target and fade."',
            self.mixer,
        )

    def test_four_level_cards_use_short_glanceable_headings(self):
        for position, label in enumerate(("Music", "Plexamp", "AirPlay", "Alarms"), start=1):
            selector = f".settings-live-trim:nth-child({position}) header strong::after"
            self.assertIn(selector, self.css)
            self.assertIn(f'content: "{label}"', self.css)

    def test_value_pills_and_fader_headers_share_one_fixed_baseline(self):
        self.assertIn("grid-template-rows: 27px 33px", self.css)
        self.assertIn("min-height: 66px", self.css)
        self.assertIn("border-radius: 999px", self.css)
        self.assertIn("min-width: 62px", self.css)
        self.assertIn("min-height: 31px", self.css)


if __name__ == "__main__":
    unittest.main()
