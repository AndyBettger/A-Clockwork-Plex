from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "app" / "static" / "js" / "airplay-receiver-name.js"
TEMPLATE = ROOT / "app" / "templates" / "airplay.html"
LIVE_CLIENT = ROOT / "app" / "static" / "js" / "airplay-live.js"


class AirPlayReceiverNameUiTests(unittest.TestCase):
    def test_compatibility_client_uses_configured_receiver_name_verbatim(self):
        text = CLIENT.read_text(encoding="utf-8")
        self.assertIn("configuredName", text)
        self.assertIn("title.textContent = configuredName", text)
        self.assertNotIn("replace(/\\s+Plexamp$/i", text)

    def test_compatibility_repair_is_one_time_not_a_competing_renderer(self):
        text = CLIENT.read_text(encoding="utf-8")
        self.assertIn("one-time compatibility repair", text)
        self.assertNotIn("MutationObserver", text)
        self.assertNotIn("setInterval", text)
        self.assertNotIn("requestAnimationFrame", text)

    def test_live_renderer_remains_the_ongoing_name_authority(self):
        text = LIVE_CLIENT.read_text(encoding="utf-8")
        self.assertIn("config?.airplay?.display_name", text)
        self.assertIn("setText('title', title || airplayName)", text)
        self.assertIn("Choose ${airplayName} from the AirPlay menu", text)

    def test_template_exposes_configured_and_legacy_ready_names(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("data-configured-receiver-name", text)
        self.assertIn("data-receiver-name", text)
        self.assertIn("airplay-receiver-name.js", text)

    def test_client_has_valid_javascript_syntax(self):
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


if __name__ == "__main__":
    unittest.main()
