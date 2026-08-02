from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import test_unified_settings as unified_fixtures
from app.audio_devices import discover_audio_devices
from app.settings_unified_scheduled import UnifiedSettingsService


class SettingsPhysicalFollowupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path("app/templates/base.html").read_text(encoding="utf-8")
        self.client = Path("app/static/js/settings-physical-followup.js").read_text(encoding="utf-8")
        self.css = Path("app/static/css/settings-physical-followup.css").read_text(encoding="utf-8")

    def test_promoted_unified_settings_preserves_scheduled_alarm_switch(self):
        fixture = unified_fixtures.UnifiedSettingsTests()
        service, stored, saves, *_rest = fixture.build()
        self.assertIsInstance(service, UnifiedSettingsService)

        snapshot = service.snapshot()
        self.assertTrue(snapshot["settings"]["alarm_audio"]["master_enabled"])
        self.assertTrue(snapshot["settings"]["alarm_audio"]["scheduled_enabled"])

        settings = snapshot["settings"]
        settings["weather"]["station_name"] = "Autosaved station"
        result = service.apply({"revision": snapshot["revision"], "settings": settings})

        self.assertEqual(len(saves), 1)
        self.assertTrue(stored["alarm_audio"]["scheduled_enabled"])
        self.assertTrue(result["settings"]["alarm_audio"]["scheduled_enabled"])

    def test_audio_device_discovery_remains_read_only_backend_diagnostics(self):
        output = """null
    Discard all samples
hw:CARD=Pro,DEV=0
    HiFiBerry DAC, direct hardware device
plughw:CARD=Pro,DEV=0
    HiFiBerry DAC with conversions
default
    Default ALSA Output
"""

        def runner(*_args, **_kwargs):
            return subprocess.CompletedProcess(["aplay", "-L"], 0, output, "")

        with patch("app.audio_devices.shutil.which", return_value="/usr/bin/aplay"):
            payload = discover_audio_devices(
                runner=runner,
                current_device="hw:CARD=Pro,DEV=0",
            )

        ids = [item["id"] for item in payload["devices"]]
        self.assertTrue(payload["available"])
        self.assertEqual(ids.count("hw:CARD=Pro,DEV=0"), 1)
        self.assertIn("plughw:CARD=Pro,DEV=0", ids)
        self.assertIn("default", ids)
        self.assertIn("null", ids)

    def test_one_consolidated_autosave_owner_replaces_fixed_save_controls(self):
        self.assertEqual(self.base.count("settings-physical-followup.js"), 1)
        self.assertEqual(self.base.count("settings-physical-followup.css"), 1)
        self.assertNotIn("settings-physical-polish.js", self.base)
        self.assertNotIn("settings-physical-polish.css", self.base)
        self.assertIn("20260802-physical-followup-v2", self.base)
        self.assertIn("form.requestSubmit()", self.client)
        self.assertIn("authority.markDirty =", self.client)
        self.assertIn("keyboard-open", self.client)
        self.assertIn("settings-save-actions", self.css)
        self.assertIn("display: none !important", self.css)

    def test_output_trims_reuse_the_calibrated_audio_fader(self):
        self.assertIn("nav-live-fader settings-output-fader", self.client)
        self.assertIn("input.dataset.mixerSlider", self.client)
        self.assertIn("nav-fader-scale-label is-top", self.client)
        self.assertIn("data-settings-fader-step", self.client)
        self.assertIn("settings-output-fader", self.css)
        self.assertIn("calibrated Audio-drawer fader", self.css)

    def test_equaliser_uses_full_width_stacked_rows_with_button_spacing(self):
        self.assertIn('[data-settings-subpage="audio:eq"] .settings-eq-grid', self.css)
        self.assertIn("grid-template-columns: 1fr !important", self.css)
        self.assertIn("86px minmax(0, 1fr) 74px", self.css)
        self.assertIn(".settings-eq-grid + .button", self.css)
        self.assertIn("margin-top: 19px", self.css)
        self.assertIn("#acp-eq-settings-card", self.css)

    def test_physical_audio_route_is_read_only_not_an_alias_dropdown(self):
        self.assertIn("arrangeAudioHardware", self.client)
        self.assertIn("hideConfigurationField('alarm_audio.hardware_device')", self.client)
        self.assertIn("physical output is intentionally read-only", self.client)
        self.assertNotIn("/api/audio/devices", self.client)
        self.assertNotIn("installAudioDeviceSelector", self.client)
        self.assertIn("settings-audio-hardware-status", self.client)

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
        self.assertIn("setSectionDirty", self.client)
        self.assertIn("settings-subpage-dirty-dot", self.css)
        self.assertIn("settings-option-dirty::after", self.css)

    def test_followup_client_has_valid_javascript_syntax(self):
        result = subprocess.run(
            ["node", "--check", "app/static/js/settings-physical-followup.js"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
