from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VOLUME_CLIENT = ROOT / "app" / "static" / "js" / "airplay-volume-v2.js"
AUDIO_POLISH = ROOT / "app" / "static" / "js" / "audio-polish.js"
NAV_DRAWER = ROOT / "app" / "static" / "js" / "nav-drawer.js"
APPLICATION_STATE = ROOT / "app" / "application_state.py"
AUDIO_MIXER = ROOT / "app" / "audio_mixer.py"
MIXER_CONTROLLER = ROOT / "app" / "mixer_controller.py"
SHAIRPORT_SESSION = ROOT / "app" / "shairport_session.py"


class AirPlayVolumeAuthorityTests(unittest.TestCase):
    def test_visible_slider_uses_compact_receiver_mixer_endpoint(self):
        text = VOLUME_CLIENT.read_text(encoding="utf-8")
        self.assertIn("/api/audio/state", text)
        self.assertIn("effective_percent", text)
        self.assertIn("touchscreen-preview", text)
        self.assertIn("channel: 'airplay'", text)
        self.assertNotIn("SetVolume", text)
        self.assertNotIn("SetAirplayVolume", text)

    def test_visible_slider_polling_suspends_with_hidden_airplay_surface(self):
        text = VOLUME_CLIENT.read_text(encoding="utf-8")
        self.assertIn("window.ACPAirPlaySurfaceLifecycle", text)
        self.assertIn("surfaceLifecycle.isVisible()", text)
        self.assertIn("surfaceLifecycle?.subscribe?.", text)
        self.assertIn("function stopPolling()", text)
        self.assertNotIn("setInterval(refresh", text)

    def test_audio_polish_no_longer_remaps_local_percent_to_sender_scale(self):
        text = AUDIO_POLISH.read_text(encoding="utf-8")
        self.assertNotIn("ACPAirPlayVolumeScale", text)
        self.assertNotIn("uiToSenderPercent", text)
        self.assertNotIn("senderToUiPercent", text)
        self.assertNotIn("/api/audio/defaults", text)
        self.assertNotIn("pending-airplay-defaults", text)

    def test_drawer_has_no_starting_volume_control(self):
        text = NAV_DRAWER.read_text(encoding="utf-8")
        self.assertNotIn("nav-start-airplay", text)
        self.assertNotIn("START ", text)
        self.assertNotIn("DEFAULTS_ENDPOINT", text)
        self.assertNotIn("data-nav-start-knob", text)

    def test_mixer_controller_owns_airplay_live_alsa_stage(self):
        text = MIXER_CONTROLLER.read_text(encoding="utf-8")
        self.assertIn('AIRPLAY_LIVE_MIXER_CHANNEL = "airplay_live"', text)
        self.assertIn('"receiver-local-alsa"', text)
        self.assertIn('"airplay_receiver_volume": True', text)
        self.assertIn('"airplay_sender_volume": False', text)
        self.assertIn('"airplay_starting_volume": False', text)
        self.assertNotIn("_set_airplay_volume", text)

    def test_sender_volume_writer_is_retired(self):
        state = APPLICATION_STATE.read_text(encoding="utf-8")
        session = SHAIRPORT_SESSION.read_text(encoding="utf-8")
        mixer = AUDIO_MIXER.read_text(encoding="utf-8")

        self.assertNotIn("set_sender_airplay_volume", state)
        self.assertNotIn("set_sender_airplay_volume", session)
        self.assertNotIn("SetAirplayVolume", session)
        self.assertNotIn('/api/audio/defaults', mixer)
        self.assertIn('"airplay_live"', mixer)

    def test_real_runner_binds_compatibility_routes_to_same_controller(self):
        code = (
            "from app.runner import app, application_state_hub; "
            "from app import audio_mixer; "
            "routes={rule.rule for rule in app.url_map.iter_rules()}; "
            "mixer=application_state_hub.service('mixer'); "
            "assert '/api/audio/state' in routes, sorted(routes); "
            "assert '/api/audio/live' in routes, sorted(routes); "
            "assert '/api/audio/mixer' in routes, sorted(routes); "
            "assert '/api/audio/defaults' not in routes, sorted(routes); "
            "assert audio_mixer.mixer_controller is mixer; "
            "assert audio_mixer.live_audio_status()['authority'] == 'mixer-controller'"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
