from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "app" / "static" / "js" / "airplay-playback-state.js"
TEMPLATE = ROOT / "app" / "templates" / "airplay.html"


class AirPlayPlaybackStateUiTests(unittest.TestCase):
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

    def test_visible_transport_is_replaced_after_legacy_metadata_setup(self):
        template = TEMPLATE.read_text(encoding="utf-8")
        client = CLIENT.read_text(encoding="utf-8")
        self.assertIn("airplay-playback-state.js", template)
        self.assertLess(template.index("airplay-live.js"), template.index("airplay-playback-state.js"))
        self.assertIn("cloneNode(true)", client)
        self.assertIn("originalButton.replaceWith(button)", client)

    def test_transport_renders_only_from_playback_coordinator(self):
        client = CLIENT.read_text(encoding="utf-8")
        self.assertIn("/api/playback/state", client)
        self.assertIn("playback?.sources?.airplay", client)
        self.assertIn("playback?.commands?.airplay", client)
        self.assertIn("source.connected === true", client)
        self.assertNotIn("/api/status", client)
        self.assertNotIn("MutationObserver", client)

    def test_button_sends_explicit_idempotent_commands_to_coordinator(self):
        client = CLIENT.read_text(encoding="utf-8")
        self.assertIn("/api/playback/command", client)
        self.assertIn("state === 'playing' ? 'pause' : 'play'", client)
        self.assertIn("JSON.stringify({ source: 'airplay', action })", client)
        self.assertNotIn("/api/airplay/control", client)
        self.assertNotIn("play_pause", client)
        self.assertNotIn("playpause", client)
        self.assertNotIn("'toggle'", client)

    def test_client_has_no_optimistic_transport_state(self):
        client = CLIENT.read_text(encoding="utf-8")
        self.assertNotIn("optimisticState", client)
        self.assertNotIn("OPTIMISTIC_MS", client)
        self.assertIn("render(payload?.playback || {})", client)

    def test_client_never_manages_audio_services(self):
        client = CLIENT.read_text(encoding="utf-8")
        self.assertNotIn("systemctl", client)
        self.assertNotIn("shairport-sync.service", client)
        self.assertNotIn("plexamp.service", client)


if __name__ == "__main__":
    unittest.main()
