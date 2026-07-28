from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PERSISTENT_PLEXAMP = ROOT / "app" / "static" / "js" / "plexamp-persistent.js"
PLAYBACK_HANDOFF = ROOT / "app" / "playback_handoff.py"
RUNNER = ROOT / "app" / "runner.py"
SCREEN_PROJECTION = ROOT / "app" / "screen_projection.py"


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

    def test_reverse_handoff_is_coordinator_owned_after_promotion(self):
        handoff = PLAYBACK_HANDOFF.read_text(encoding="utf-8")
        runner = RUNNER.read_text(encoding="utf-8")

        self.assertIn('class BidirectionalHandoffPlaybackCoordinator', handoff)
        self.assertIn('"plexamp_to_airplay_handoff": True', handoff)
        self.assertIn('promote_bidirectional_handoff(application_state_hub)', runner)
        self.assertNotIn("/api/airplay/control", PERSISTENT_PLEXAMP.read_text(encoding="utf-8"))

    def test_screen_projection_is_separate_from_playback_handoff(self):
        projection = SCREEN_PROJECTION.read_text(encoding="utf-8")
        runner = RUNNER.read_text(encoding="utf-8")

        self.assertIn("class ScreenProjectionController", projection)
        self.assertIn('authority = "screen-projection-owner"', projection)
        self.assertIn("register_screen_projection(app, application_state_hub, dashboard)", runner)
        self.assertNotIn("/api/airplay/control", projection)


if __name__ == "__main__":
    unittest.main()
