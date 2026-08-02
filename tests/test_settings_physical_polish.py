from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


class SettingsPhysicalPolishTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path("app/templates/base.html").read_text(encoding="utf-8")
        self.client = Path("app/static/js/settings-physical-polish.js").read_text(encoding="utf-8")
        self.css = Path("app/static/css/settings-physical-polish.css").read_text(encoding="utf-8")

    def test_polish_assets_are_settings_only_and_cache_busted(self):
        self.assertIn("settings-physical-polish.js", self.base)
        self.assertIn("settings-physical-polish.css", self.base)
        self.assertIn("20260802-physical-polish-v2", self.base)
        self.assertIn("active_page | default(state.mode) == 'settings'", self.base)

    def test_output_trims_reuse_the_calibrated_audio_fader(self):
        self.assertIn("nav-live-fader settings-output-fader", self.client)
        self.assertIn("input.dataset.mixerSlider", self.client)
        self.assertIn("nav-fader-scale-label is-top", self.client)
        self.assertIn("data-settings-fader-step", self.client)
        self.assertIn("settings-output-fader", self.css)
        self.assertIn("same calibrated mixer fader", self.css)

    def test_equaliser_uses_full_width_stacked_rows_with_button_spacing(self):
        self.assertIn('[data-settings-subpage="audio:eq"] .settings-eq-grid', self.css)
        self.assertIn("grid-template-columns: 1fr !important", self.css)
        self.assertIn("86px minmax(0, 1fr) 74px", self.css)
        self.assertIn(".settings-eq-grid + .button", self.css)
        self.assertIn("margin-top: 19px", self.css)

    def test_physical_audio_route_is_read_only_not_an_alias_dropdown(self):
        self.assertIn("simplifyAudioHardware", self.client)
        self.assertIn("hideHardwareControl('alarm_audio.hardware_device')", self.client)
        self.assertIn("physical output is intentionally read-only", self.client)
        self.assertNotIn("/api/audio/devices", self.client)
        self.assertNotIn("installAudioDeviceSelector", self.client)

    def test_airplay_receiver_uses_one_fresh_confirmed_transaction(self):
        self.assertIn("installAirplayReceiverOwner", self.client)
        self.assertIn("input.removeAttribute('data-setting-path')", self.client)
        self.assertIn("const latest = await freshSettingsSnapshot()", self.client)
        self.assertIn("confirm_airplay_restart: true", self.client)
        self.assertIn("AirPlay receiver update failed", self.client)
        self.assertIn("window.location.reload()", self.client)

    def test_dirty_state_propagates_to_subpage_and_specific_option(self):
        self.assertIn("settings-subpage-dirty-dot", self.client)
        self.assertIn("settings-option-dirty", self.client)
        self.assertIn("setSubpageDirty", self.client)
        self.assertIn("setCategoryDirty", self.client)
        self.assertIn("settings-subpage-dirty-dot", self.css)
        self.assertIn("settings-option-dirty::after", self.css)

    def test_polish_client_has_valid_javascript_syntax(self):
        result = subprocess.run(
            ["node", "--check", "app/static/js/settings-physical-polish.js"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
