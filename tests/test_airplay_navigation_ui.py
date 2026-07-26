from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "app" / "static" / "js" / "airplay-navigation-state.js"
CLASSIFIER = ROOT / "app" / "static" / "js" / "airplay-extra-controls.js"
TEMPLATE = ROOT / "app" / "templates" / "airplay.html"


class AirPlayNavigationUiTests(unittest.TestCase):
    def test_navigation_client_has_valid_javascript_syntax(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is not installed.")
        result = subprocess.run(
            [node, "--check", str(CLIENT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_visible_navigation_is_cloned_after_adaptive_classifier(self):
        template = TEMPLATE.read_text(encoding="utf-8")
        client = CLIENT.read_text(encoding="utf-8")
        self.assertLess(
            template.index("airplay-extra-controls.js"),
            template.index("airplay-navigation-state.js"),
        )
        self.assertIn("legacyBack.cloneNode(true)", client)
        self.assertIn("legacyForward.cloneNode(true)", client)
        self.assertIn("legacyBack.replaceWith(backButton)", client)
        self.assertIn("legacyForward.replaceWith(forwardButton)", client)

    def test_navigation_uses_coordinator_and_never_legacy_control_route(self):
        client = CLIENT.read_text(encoding="utf-8")
        self.assertIn("/api/playback/state", client)
        self.assertIn("/api/playback/command", client)
        self.assertIn("JSON.stringify({ source: 'airplay', action })", client)
        self.assertIn("action !== 'previous' && action !== 'next'", client)
        self.assertIn("capabilities.airplay_navigation === true", client)
        self.assertNotIn("/api/airplay/control", client)
        self.assertNotIn("play_pause", client)

    def test_existing_spoken_audio_classifier_is_preserved_as_presentation_only(self):
        classifier = CLASSIFIER.read_text(encoding="utf-8")
        client = CLIENT.read_text(encoding="utf-8")
        self.assertIn("spokenAppPattern", classifier)
        self.assertIn("explicitMusicApp", classifier)
        self.assertIn("LONG_SPOKEN_SECONDS", classifier)
        self.assertIn("VERY_LONG_SPOKEN_SECONDS", classifier)
        self.assertIn("setButtonMode", classifier)
        self.assertIn("copyPresentation", client)
        self.assertIn("data-airplay-skip-mode", client)
        self.assertNotIn("spokenAppPattern", client)

    def test_navigation_disables_when_coordinator_has_no_connected_sender(self):
        client = CLIENT.read_text(encoding="utf-8")
        self.assertIn("connected = source.connected === true", client)
        self.assertIn("button.hidden = !connected", client)
        self.assertIn("button.disabled = commandPending || !connected || !canNavigate", client)


if __name__ == "__main__":
    unittest.main()
