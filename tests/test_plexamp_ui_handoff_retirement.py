from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIO_MIXER = ROOT / "app" / "audio_mixer.py"
PERSISTENT_PLEXAMP = ROOT / "app" / "static" / "js" / "plexamp-persistent.js"
PLAYBACK_AUTHORITY = ROOT / "app" / "playback_authority.py"
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

    def test_legacy_server_workers_and_route_wrapper_are_removed(self):
        mixer = AUDIO_MIXER.read_text(encoding="utf-8")

        self.assertNotIn("_arm_plexamp_handoff", mixer)
        self.assertNotIn("_plexamp_handoff_runtime", mixer)
        self.assertNotIn("_plexamp_handoff_generation", mixer)
        self.assertNotIn("plexamp-airplay-handoff", mixer)
        self.assertNotIn("_acp_airplay_handoff_wrapped", mixer)
        self.assertNotIn('"plexamp_handoff"', mixer)
        self.assertNotIn("_schedule_airplay_default", mixer)
        self.assertNotIn("airplay-default-volume", mixer)
        self.assertIn("bind_mixer_controller", mixer)
        self.assertIn("mixer_controller.start_airplay_session", mixer)
        self.assertIn("_acp_audio_defaults_wrapped", mixer)

    def test_reverse_handoff_is_owned_by_final_production_authority(self):
        authority = PLAYBACK_AUTHORITY.read_text(encoding="utf-8")
        handoff = PLAYBACK_HANDOFF.read_text(encoding="utf-8")
        runner = RUNNER.read_text(encoding="utf-8")

        self.assertIn("RetainedBidirectionalHandoffCoordinator", authority)
        self.assertIn("class BidirectionalHandoffPlaybackCoordinator", handoff)
        self.assertIn('"plexamp_to_airplay_handoff": True', handoff)
        self.assertIn("promote_playback_authority(application_state_hub, dashboard)", runner)
        self.assertNotIn("promote_bidirectional_handoff(application_state_hub)", runner)
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
