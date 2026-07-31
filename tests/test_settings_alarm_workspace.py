from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "app" / "static" / "js" / "settings-alarm-workspace.js"
AUTOSAVE = ROOT / "app" / "static" / "js" / "settings-autosave.js"
BASE = ROOT / "app" / "templates" / "base.html"


class SettingsAlarmWorkspaceTests(unittest.TestCase):
    def test_workspace_client_has_valid_javascript_syntax(self):
        result = subprocess.run(
            ["node", "--check", str(WORKSPACE)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_alarm_editor_has_a_visible_dedicated_save(self):
        text = WORKSPACE.read_text(encoding="utf-8")
        self.assertIn('id="alarm-workspace-save"', text)
        self.assertIn('type="submit"', text)
        self.assertIn('data-dedicated-settings-save="alarms"', text)
        self.assertIn("Unsaved alarm changes.", text)
        self.assertIn("validated and saved together as one schedule", text)

    def test_general_autosave_does_not_swallow_dedicated_alarm_save(self):
        text = AUTOSAVE.read_text(encoding="utf-8")
        self.assertIn("function dedicatedSubmit(event)", text)
        self.assertIn("[data-dedicated-settings-save]", text)
        self.assertIn("if (dedicatedSubmit(event)) return;", text)

    def test_workspace_owns_final_alarm_intro_truth(self):
        text = WORKSPACE.read_text(encoding="utf-8")
        self.assertIn("function updateAlarmIntro()", text)
        self.assertIn("Scheduled alarms", text)
        self.assertIn("timing, screen takeover, sound, Snooze and Dismiss", text)
        self.assertNotIn("The scheduler remains disabled during this pass", text)

    def test_testing_and_runtime_controls_move_to_advanced(self):
        text = WORKSPACE.read_text(encoding="utf-8")
        self.assertIn("alarm-advanced-workspace", text)
        self.assertIn("alarm-scheduler-status-card", text)
        self.assertIn("alarm-audio-advanced-card", text)
        self.assertIn("Alarm testing and audio diagnostics", text)
        self.assertIn("alarm-audio-test-panel", text)
        self.assertIn("alarm-audio-readings", text)

    def test_everyday_sound_safety_stays_in_alarm_workspace(self):
        text = WORKSPACE.read_text(encoding="utf-8")
        self.assertIn("Alarm sound safety", text)
        self.assertIn("alarm-audio-master", text)
        self.assertIn("alarm-audio-scheduled-toggle", text)
        self.assertIn("Master safety key for scheduled alarms", text)

    def test_template_loads_cache_busted_workspace_client(self):
        text = BASE.read_text(encoding="utf-8")
        self.assertIn("js/settings-alarm-workspace.js", text)
        self.assertIn("20260731-alarm-workspace-truth", text)


if __name__ == "__main__":
    unittest.main()
