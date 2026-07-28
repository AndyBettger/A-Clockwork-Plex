from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PERSISTENT_PLEXAMP = ROOT / "app" / "static" / "js" / "plexamp-persistent.js"
PLAYBACK_HANDOFF = ROOT / "app" / "playback_handoff.py"


class PlexampUiHandoffRetirementTests(unittest.TestCase):
    def test_persistent_plexamp_never_controls_airplay_transport(self):
        text = PERSISTENT_PLEXAMP.read_text(encoding="utf-8")

        self.assertNotIn("/api/airplay/control", text)
        self.assertNotIn("pauseAirplayWhenPlexampWins", text)
        self.assertNotIn("handoffPauseInFlight", text)
        self.assertNotIn("handoffCooldownUntil", text)
        self.assertNotIn("acp:live-audio-status", text)

    def test_opening_plexamp_is_screen_intent_only(self):
        text = PERSISTENT_PLEXAMP.read_text(encoding="utf-8")

        self.assertIn("function show(options = {})", text)
        self.assertIn("updateServerMode('plexamp')", text)
        self.assertIn("function prepareNavigation()", text)
        self.assertIn("window.ACPPlexamp =", text)
        self.assertNotIn("ACPLiveAudioSnapshot", text)

    def test_reverse_handoff_remains_disabled_until_coordinator_promotion(self):
        text = PLAYBACK_HANDOFF.read_text(encoding="utf-8")

        self.assertIn('"plexamp_to_airplay_handoff": False', text)
        self.assertIn('"screen_projection": False', text)


if __name__ == "__main__":
    unittest.main()
