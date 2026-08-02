from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
ALARM_GUIDE = ROOT / "docs" / "alarm-audio-testing.md"
ARCHITECTURE = ROOT / "docs" / "application-state-architecture.md"
SETTINGS_REDESIGN = ROOT / "docs" / "post-weather-settings-redesign.md"
ALARM_RUNTIME = ROOT / "app" / "alarm_runtime.py"


class CurrentProjectDocumentationTests(unittest.TestCase):
    def test_readme_describes_completed_scheduled_alarm_audio(self):
        text = README.read_text(encoding="utf-8")
        self.assertIn("real clock-triggered alarm playback", text)
        self.assertIn("Plexamp and AirPlay pause during alarm priority", text)
        self.assertNotIn("Ordinary scheduled alarm audio is still locked", text)
        self.assertNotIn("Ordinary scheduled alarm playback remains locked", text)

    def test_weather_is_completed_as_final_development_stage(self):
        text = README.read_text(encoding="utf-8")
        self.assertIn("Weather-provider work was the **final development stage**", text)
        self.assertIn("built and physically validated", text)
        self.assertIn("cached Open-Meteo forecasts", text)
        self.assertIn("up to 16 forecast days", text)
        self.assertIn("renders every daily item", text)

    def test_post_weather_settings_redesign_is_implemented(self):
        text = SETTINGS_REDESIGN.read_text(encoding="utf-8")
        self.assertIn("iPad-style split view", text)
        self.assertIn("GET  /api/settings", text)
        self.assertIn("one validated transaction", text)
        self.assertIn("Managed AirPlay receiver name", text)
        self.assertIn("Bass", text)
        self.assertIn("Mid", text)
        self.assertIn("Treble", text)
        self.assertIn("settings-tabs.js", text)
        self.assertIn("no longer loads", text)
        self.assertIn("Display dimming", text)
        self.assertIn("ACPTime", text)
        self.assertIn("16-day response produces 16", text)
        self.assertIn("Advanced Audio is diagnostic", text)

    def test_readme_records_validated_appliance_and_eq_next(self):
        text = README.read_text(encoding="utf-8")
        self.assertIn("unified iPad-style Settings", text)
        self.assertIn("Managed AirPlay receiver name", text)
        self.assertIn("Settings-hosted EQ controls", text)
        self.assertIn("scheduled display dimming", text)
        self.assertIn("one dashboard-wide clock-format", text)
        self.assertIn("Do not run: sudo bash scripts/install-master-eq.sh", text)
        self.assertIn("guarded production-EQ", text)

    def test_alarm_guide_documents_real_scheduled_takeover(self):
        text = ALARM_GUIDE.read_text(encoding="utf-8")
        self.assertIn("clock-triggered scheduled playback", text)
        self.assertIn("Plexamp pause during alarm priority", text)
        self.assertIn("AirPlay pause during alarm priority", text)
        self.assertNotIn("permits **explicit local-audio tests only**", text)

    def test_architecture_identifies_final_authorities(self):
        text = ARCHITECTURE.read_text(encoding="utf-8")
        self.assertIn("RetainedBidirectionalHandoffCoordinator", text)
        self.assertIn("scheduled-alarm-audio-manager", text)
        self.assertIn("ACPTime", text)
        self.assertIn("ACPDisplayDimming", text)
        self.assertIn("manual", text)
        self.assertIn("PR #2 remains draft", text)

    def test_scheduler_wording_describes_delegation_not_disabled_audio(self):
        text = ALARM_RUNTIME.read_text(encoding="utf-8")
        self.assertIn("audio delegated to the alarm-audio authority", text)
        self.assertIn("scheduled audio is delegated to the promoted authority", text)
        self.assertNotIn("audio remains disabled", text)
        self.assertNotIn("audio playback is still disabled", text)


if __name__ == "__main__":
    unittest.main()
