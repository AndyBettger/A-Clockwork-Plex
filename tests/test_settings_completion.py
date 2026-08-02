from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "app" / "static" / "js" / "settings-completion.js"
STYLE = ROOT / "app" / "static" / "css" / "settings-completion.css"
BASE = ROOT / "app" / "templates" / "base.html"
ABOUT = ROOT / "app" / "static" / "app-version.json"
ADVANCED = ROOT / "app" / "static" / "js" / "settings-advanced.js"


class SettingsCompletionTests(unittest.TestCase):
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

    def test_completion_assets_are_settings_only(self):
        text = BASE.read_text(encoding="utf-8")
        self.assertIn("settings-completion.css", text)
        self.assertIn("settings-completion.js", text)
        self.assertIn("active_page | default(state.mode) == 'settings'", text)
        self.assertTrue(STYLE.exists())

    def test_advanced_route_controls_are_removed_from_diagnostics(self):
        text = CLIENT.read_text(encoding="utf-8")
        for path in (
            "alarm_audio.shared_mixer_enabled",
            "alarm_audio.hardware_device",
            "alarm_audio.alsa_device",
        ):
            self.assertIn(path, text)
        self.assertIn("closest('label')?.remove()", text)
        self.assertIn("Read-only audio route", text)
        self.assertIn("test_duration_seconds", text)

    def test_false_advanced_dirty_markers_are_cleared_at_all_levels(self):
        text = CLIENT.read_text(encoding="utf-8")
        self.assertIn("settings-subpage-dirty-dot", text)
        self.assertIn("settings-option-dirty", text)
        self.assertIn("data-settings-section-target=\"advanced\"", text)
        self.assertIn("dot.hidden = true", text)

    def test_about_metadata_describes_current_release_phase(self):
        text = ABOUT.read_text(encoding="utf-8")
        self.assertIn("Unified Dashboard, Weather, Alarms and Managed AirPlay", text)
        self.assertIn("Production EQ guarded rollout next", text)
        client = CLIENT.read_text(encoding="utf-8")
        self.assertIn("Current appliance", client)
        self.assertIn("old bare installer remains blocked", client)

    def test_advanced_alarm_poll_is_slow_and_visibility_scoped(self):
        text = ADVANCED.read_text(encoding="utf-8")
        self.assertIn("PASSIVE_REFRESH_MS = 30000", text)
        self.assertIn("pageVisible()", text)
        self.assertNotIn("5000", text)


if __name__ == "__main__":
    unittest.main()
