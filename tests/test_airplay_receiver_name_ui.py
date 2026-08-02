from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "app" / "static" / "js" / "airplay-receiver-name.js"
TEMPLATE = ROOT / "app" / "templates" / "airplay.html"


class AirPlayReceiverNameUiTests(unittest.TestCase):
    def test_client_uses_configured_receiver_name_verbatim(self):
        text = CLIENT.read_text(encoding="utf-8")
        self.assertIn("receiverName = configuredName || renderedName", text)
        self.assertIn("replaceOnlyWhenChanged(title, receiverName)", text)
        self.assertNotIn("replace(/\\s+Plexamp$/i", text)

    def test_client_replaces_the_legacy_rendered_alias_in_ready_copy(self):
        text = CLIENT.read_text(encoding="utf-8")
        self.assertIn("renderedName !== receiverName", text)
        self.assertIn("detailText.split(renderedName).join(receiverName)", text)
        self.assertIn("MutationObserver", text)

    def test_template_exposes_both_configured_and_legacy_rendered_names(self):
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
