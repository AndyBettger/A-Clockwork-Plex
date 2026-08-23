from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "app" / "static" / "js" / "settings-completion.js"
STYLE = ROOT / "app" / "static" / "css" / "settings-completion.css"
BASE = ROOT / "app" / "templates" / "base.html"
ABOUT = ROOT / "app" / "static" / "app-version.json"
ABOUT_CLIENT = ROOT / "app" / "static" / "js" / "settings-about.js"
ADVANCED = ROOT / "app" / "static" / "js" / "settings-advanced.js"


class SettingsCompletionTests(unittest.TestCase):
    def test_client_has_valid_javascript_syntax(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is not installed.")
        for path in (CLIENT, ABOUT_CLIENT):
            result = subprocess.run(
                [node, "--check", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"{path}: {result.stderr}")

    def test_completion_assets_are_settings_only(self):
        text = BASE.read_text(encoding="utf-8")
        self.assertIn("settings-completion.css", text)
        self.assertIn("settings-completion.js", text)
        self.assertIn("20260823-about-release-metadata-v1", text)
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

    def test_about_metadata_is_durable_release_identity(self):
        metadata = json.loads(ABOUT.read_text(encoding="utf-8"))
        self.assertEqual(
            set(metadata),
            {
                "name",
                "version",
                "tag",
                "release_name",
                "repository",
                "companion_repository",
            },
        )
        self.assertEqual(metadata["name"], "A Clockwork Plex")
        self.assertEqual(metadata["version"], "0.4.0")
        self.assertRegex(metadata["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(metadata["tag"], f"v{metadata['version']}")
        self.assertEqual(metadata["release_name"], "Unified Bedside Appliance")

        durable_values = " ".join(str(value) for value in metadata.values()).lower()
        for stale in ("feature/alarm-engine", "-dev", "next phase", "rollout next"):
            with self.subTest(stale=stale):
                self.assertNotIn(stale, durable_values)

        client = CLIENT.read_text(encoding="utf-8")
        self.assertIn("Appliance capabilities", client)
        self.assertIn("Managed EQ", client)
        self.assertIn("Guarded setup", client)
        self.assertNotIn("Next phase", client)
        self.assertNotIn("Production EQ", client)
        self.assertNotIn("old bare installer remains blocked", client)

        about_client = ABOUT_CLIENT.read_text(encoding="utf-8")
        self.assertIn("metadata.version", about_client)
        self.assertIn("metadata.release_name", about_client)
        self.assertIn("metadata.tag", about_client)
        self.assertNotIn("metadata.phase", about_client)

    def test_advanced_alarm_poll_is_slow_and_visibility_scoped(self):
        text = ADVANCED.read_text(encoding="utf-8")
        self.assertIn("PASSIVE_REFRESH_MS = 30000", text)
        self.assertIn("pageVisible()", text)
        self.assertNotIn("5000", text)


if __name__ == "__main__":
    unittest.main()
