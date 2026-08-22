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
        self.assertIn("real clock-triggered playback", text)
        self.assertIn("automatic takeover from Plexamp/AirPlay while the alarm owns priority", text)
        self.assertIn("scheduled alarms **bypass Music Master and music EQ**", text)
        self.assertNotIn("Ordinary scheduled alarm audio is still locked", text)
        self.assertNotIn("Ordinary scheduled alarm playback remains locked", text)

    def test_readme_describes_current_weather_stack_without_stale_stage_claims(self):
        text = README.read_text(encoding="utf-8")
        self.assertIn("**Open-Meteo** supplies cached forecast data", text)
        self.assertIn("**Ecowitt Push** or **Weather Underground PWS**", text)
        self.assertIn("cached historical rainfall and Rainy Day Fund totals", text)
        self.assertIn("fresh supplementary indoor temperature/humidity", text)
        self.assertIn("rolling Hourly rain, Event rain", text)
        self.assertNotIn("Weather-provider work was the **final development stage**", text)

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

    def test_readme_records_current_settings_and_managed_eq(self):
        text = README.read_text(encoding="utf-8")
        self.assertIn("The touchscreen Settings workspace covers", text)
        self.assertIn("AirPlay receiver naming", text)
        self.assertIn("Music Master, source trims, Maximum Alarm Volume and EQ", text)
        self.assertIn("scheduled night dimming", text)
        self.assertIn("CamillaDSP is pinned to the accepted 4.1.3 build", text)
        self.assertIn("a-clockwork-plex-camilladsp.service", text)
        self.assertIn("obsolete bare `scripts/install-master-eq.sh` laboratory-era path", text)
        self.assertIn("pre-production audio rehearsal harnesses have been retired", text)

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
