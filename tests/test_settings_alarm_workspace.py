from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALARM_EDITOR = ROOT / "app" / "static" / "js" / "settings-alarms.js"
ALARM_STYLE = ROOT / "app" / "static" / "css" / "settings-alarm-model.css"
ADVANCED = ROOT / "app" / "static" / "js" / "settings-advanced.js"
SETTINGS_CLIENT = ROOT / "app" / "static" / "js" / "settings-ipad.js"
SETTINGS_TEMPLATE = ROOT / "app" / "templates" / "settings.html"
BASE = ROOT / "app" / "templates" / "base.html"


class SettingsAlarmWorkspaceTests(unittest.TestCase):
    def test_alarm_workspace_clients_have_valid_javascript_syntax(self):
        for path in (ALARM_EDITOR, ADVANCED, SETTINGS_CLIENT):
            with self.subTest(path=path.name):
                result = subprocess.run(
                    ["node", "--check", str(path)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_alarm_editor_uses_the_shared_transaction(self):
        text = ALARM_EDITOR.read_text(encoding="utf-8")
        self.assertIn("registerDomain?.('alarms'", text)
        self.assertIn("validatedModel", text)
        self.assertIn("markDirty", text)
        self.assertNotIn("method: 'POST'", text)
        self.assertNotIn("requestSubmit", text)
        self.assertNotIn("HTMLFormElement.prototype.submit", text)

    def test_one_settings_save_owns_alarm_configuration(self):
        template = SETTINGS_TEMPLATE.read_text(encoding="utf-8")
        client = SETTINGS_CLIENT.read_text(encoding="utf-8")
        self.assertEqual(template.count("Save Changes"), 1)
        self.assertIn('id="settings-unified-form"', template)
        self.assertIn("/api/settings", client)
        self.assertIn("revision: snapshot.revision", client)
        self.assertIn("providers.forEach", client)
        self.assertNotIn("data-dedicated-settings-save", template)

    def test_testing_and_runtime_controls_live_under_advanced(self):
        template = SETTINGS_TEMPLATE.read_text(encoding="utf-8")
        advanced = ADVANCED.read_text(encoding="utf-8")
        self.assertIn('data-settings-subpage="advanced:alarm"', template)
        self.assertIn("settings-advanced-alarm-diagnostics", template)
        self.assertIn("Alarm runtime", advanced)
        self.assertIn("Test screen in 10 seconds", advanced)
        self.assertIn("Clear visual test", advanced)
        self.assertIn("/api/alarms/scheduler", advanced)
        self.assertIn("/api/alarms/test", advanced)

    def test_everyday_sound_safety_stays_under_alarms(self):
        template = SETTINGS_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn('data-settings-subpage="alarms:sound"', template)
        self.assertIn('data-setting-path="alarm_audio.master_enabled"', template)
        self.assertIn('data-setting-path="alarm_audio.scheduled_enabled"', template)
        self.assertIn("Master safety key", template)
        self.assertIn("Second key", template)

    def test_enabled_pill_is_the_toggle_not_a_second_checkbox(self):
        text = ALARM_EDITOR.read_text(encoding="utf-8")
        style = ALARM_STYLE.read_text(encoding="utf-8")
        self.assertIn("alarm-enabled-toggle", text)
        self.assertIn("alarm.enabled = !alarm.enabled", text)
        self.assertIn("dataset.alarmEnabledToggle", text)
        self.assertIn("aria-pressed", text)
        self.assertNotIn("enabled.type = 'checkbox'", text)
        self.assertIn(".alarm-enabled-toggle.is-off", style)

    def test_time_picker_tracks_clock_format_without_keyboard_entry(self):
        text = ALARM_EDITOR.read_text(encoding="utf-8")
        style = ALARM_STYLE.read_text(encoding="utf-8")
        self.assertIn("storedTimeFromParts", text)
        self.assertIn("displayTimeParts", text)
        self.assertIn("alarm-period-control", text)
        self.assertIn("acp:clock-format-changed", text)
        self.assertIn("stored safely as 24-hour HH:MM", text)
        self.assertNotIn("dataset.keyboard = 'time'", text)
        self.assertIn(".alarm-time-picker", style)
        self.assertIn(".alarm-period-button.is-selected", style)

    def test_behaviour_and_sound_are_explicit_panels(self):
        text = ALARM_EDITOR.read_text(encoding="utf-8")
        self.assertIn("panel('Behaviour'", text)
        self.assertIn("panel('Sound'", text)
        self.assertIn("Snooze duration", text)
        self.assertIn("Scheduled alarm target volume", text)
        self.assertIn("It never changes preview loudness", text)

    def test_preview_volume_is_fixed_and_separate_from_alarm_target(self):
        text = ALARM_EDITOR.read_text(encoding="utf-8")
        self.assertIn("SAFE_PREVIEW_VOLUME_PERCENT = 15", text)
        self.assertIn("master.gain.value = SAFE_PREVIEW_GAIN", text)
        self.assertIn("previewTone(alarm.source.tone_id, previewToneButton)", text)
        self.assertNotIn("previewTone(alarm.source.tone_id, alarm.volume.target_percent", text)
        self.assertIn("capped independently from the scheduled alarm volume", text)

    def test_retired_workspace_and_autosave_clients_are_not_loaded(self):
        base = BASE.read_text(encoding="utf-8")
        template = SETTINGS_TEMPLATE.read_text(encoding="utf-8")
        self.assertNotIn("js/settings-alarm-workspace.js", base)
        self.assertNotIn("js/settings-autosave.js", base)
        self.assertNotIn("js/settings-alarm-scheduled.js", base)
        self.assertNotIn("js/settings-alarm-scheduler.js", base)
        self.assertIn("js/settings-ipad.js", template)
        self.assertIn("20260802-unified-settings", template)


if __name__ == "__main__":
    unittest.main()
