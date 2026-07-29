from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VOLUME_CLIENT = ROOT / "app" / "static" / "js" / "airplay-volume-v2.js"
AUDIO_POLISH = ROOT / "app" / "static" / "js" / "audio-polish.js"
APPLICATION_STATE = ROOT / "app" / "application_state.py"
AUDIO_MIXER = ROOT / "app" / "audio_mixer.py"
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

    def test_audio_state_endpoint_uses_same_perceptual_scale_as_audio_drawer(self):
        text = AUDIO_POLISH.read_text(encoding="utf-8")

        self.assertIn("const audioStateEndpoint = '/api/audio/state';", text)
        self.assertIn("[liveEndpoint, audioStateEndpoint].includes(url.pathname)", text)
        self.assertIn("transformAirplayChannel(payload.audio?.channels?.airplay)", text)
        self.assertIn("percent: uiToSenderPercent(submitted.percent)", text)
        self.assertIn("'effective_percent'", text)
        self.assertIn("'observed_percent'", text)

    def test_perceptual_scale_matches_physical_regression_values(self):
        harness = f"""
const fs = require('fs');
global.window = {{
  fetch: async () => new Response('{{}}', {{ headers: {{ 'Content-Type': 'application/json' }} }}),
  location: {{ href: 'http://localhost:8088/clock', origin: 'http://localhost:8088' }},
  localStorage: {{ getItem: () => null, setItem: () => {{}}, removeItem: () => {{}} }},
  setInterval: () => 0,
  setTimeout: () => 0,
  requestAnimationFrame: (callback) => callback(),
}};
global.document = {{ getElementById: () => null, addEventListener: () => {{}} }};
global.MutationObserver = class {{ observe() {{}} }};
eval(fs.readFileSync({json.dumps(str(AUDIO_POLISH))}, 'utf8'));
console.log(JSON.stringify({{
  sender68: window.ACPAirPlayVolumeScale.senderToUiPercent(68),
  ui75: window.ACPAirPlayVolumeScale.uiToSenderPercent(75),
}}));
"""
        result = subprocess.run(
            ["node", "-e", harness],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        values = json.loads(result.stdout.strip())
        self.assertEqual(values["sender68"], 33)
        self.assertEqual(values["ui75"], 92)

    def test_visible_strip_owns_its_css_percentage_locally(self):
        text = VOLUME_CLIENT.read_text(encoding="utf-8")
        self.assertIn("strip.style.setProperty('--airplay-volume-percent'", text)
        self.assertIn("strip.dataset.volumeStateSource", text)
        self.assertNotIn("document.body.style.setProperty('--airplay-volume-percent'", text)

    def test_slider_sends_only_final_explicit_value(self):
        text = VOLUME_CLIENT.read_text(encoding="utf-8")
        self.assertIn("queueFinalSend", text)
        self.assertIn("pointerup", text)
        self.assertIn("body: JSON.stringify({ channel: 'airplay', percent: clamp(percent) })", text)
        self.assertNotIn("slider.addEventListener('input', () => queue", text)

    def test_state_hub_registers_one_complete_mixer_service(self):
        text = APPLICATION_STATE.read_text(encoding="utf-8")
        self.assertIn('hub.register_service("mixer", mixer_controller)', text)
        self.assertIn('hub.register_provider("audio", mixer_controller.snapshot)', text)
        self.assertIn('@app.route("/api/audio/state", methods=["GET", "POST"])', text)
        self.assertIn("audio_mixer.bind_mixer_controller(mixer_controller)", text)
        self.assertIn("set_mixer_volume=set_mixer_volume", text)
        self.assertIn("set_plexamp_volume=set_plexamp_volume", text)
        self.assertNotIn("_install_mixer_controller_bridge", text)

    def test_starting_volume_policy_is_one_write_per_session(self):
        text = MIXER_CONTROLLER.read_text(encoding="utf-8")
        legacy = AUDIO_MIXER.read_text(encoding="utf-8")
        self.assertIn('"airplay_starting_volume_write_limit": 1', text)
        self.assertIn('return "already-active"', text)
        self.assertNotIn("for _ in range(80)", legacy)
        self.assertNotIn("stable_reads", legacy)
        self.assertNotIn("airplay-default-volume", legacy)
        self.assertNotIn("_schedule_airplay_default", legacy)
        self.assertNotIn("_airplay_default_status", legacy)

    def test_real_runner_binds_compatibility_routes_to_same_controller(self):
        code = (
            "from app.runner import app, application_state_hub; "
            "from app import audio_mixer; "
            "routes={rule.rule for rule in app.url_map.iter_rules()}; "
            "mixer=application_state_hub.service('mixer'); "
            "assert '/api/audio/state' in routes, sorted(routes); "
            "assert '/api/audio/live' in routes, sorted(routes); "
            "assert '/api/audio/mixer' in routes, sorted(routes); "
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
