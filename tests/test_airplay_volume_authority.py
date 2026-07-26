from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VOLUME_CLIENT = ROOT / "app" / "static" / "js" / "airplay-volume-v2.js"
APPLICATION_STATE = ROOT / "app" / "application_state.py"
MIXER_CONTROLLER = ROOT / "app" / "mixer_controller.py"


class AirPlayVolumeAuthorityTests(unittest.TestCase):
    def test_visible_slider_uses_compact_mixer_state_endpoint(self):
        text = VOLUME_CLIENT.read_text(encoding="utf-8")
        self.assertIn("/api/audio/state", text)
        self.assertIn("effective_percent", text)
        self.assertIn("touchscreen-preview", text)
        self.assertNotIn("/api/audio/live", text)
        self.assertNotIn("reassertTimer", text)
        self.assertNotIn("SetVolume", text)

    def test_slider_sends_only_final_explicit_value(self):
        text = VOLUME_CLIENT.read_text(encoding="utf-8")
        self.assertIn("queueFinalSend", text)
        self.assertIn("pointerup", text)
        self.assertIn("body: JSON.stringify({ channel: 'airplay', percent: clamp(percent) })", text)
        self.assertNotIn("slider.addEventListener('input', () => queue", text)

    def test_state_hub_registers_mixer_service_and_audio_provider(self):
        text = APPLICATION_STATE.read_text(encoding="utf-8")
        self.assertIn('hub.register_service("mixer", mixer_controller)', text)
        self.assertIn('hub.register_provider("audio", mixer_controller.snapshot)', text)
        self.assertIn('@app.route("/api/audio/state", methods=["GET", "POST"])', text)
        self.assertIn("_install_mixer_controller_bridge", text)

    def test_starting_volume_policy_is_one_write_per_session(self):
        text = MIXER_CONTROLLER.read_text(encoding="utf-8")
        self.assertIn('"airplay_starting_volume_write_limit": 1', text)
        self.assertIn('return "already-active"', text)
        self.assertNotIn("for _ in range(80)", text)
        self.assertNotIn("stable_reads", text)

    def test_real_runner_exposes_audio_state_and_binds_legacy_symbol_to_controller(self):
        code = (
            "from app.runner import app, application_state_hub; "
            "from app import audio_mixer; "
            "routes={rule.rule for rule in app.url_map.iter_rules()}; "
            "mixer=application_state_hub.service('mixer'); "
            "assert '/api/audio/state' in routes, sorted(routes); "
            "assert audio_mixer._schedule_airplay_default.__self__ is mixer; "
            "assert audio_mixer._airplay_default_status.__self__ is mixer"
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
