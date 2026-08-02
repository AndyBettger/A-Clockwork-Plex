from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import test_unified_settings as unified_fixtures
from app.audio_devices import discover_audio_devices
from app.settings_unified_scheduled import UnifiedSettingsService


class SettingsPhysicalFollowupTests(unittest.TestCase):
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

    def test_audio_device_discovery_keeps_current_and_parses_pcm_names(self):
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

    def test_followup_uses_one_autosave_owner_and_no_fixed_save_controls(self):
        base = Path("app/templates/base.html").read_text(encoding="utf-8")
        client = Path("app/static/js/settings-physical-followup.js").read_text(encoding="utf-8")
        css = Path("app/static/css/settings-physical-followup.css").read_text(encoding="utf-8")

        self.assertIn("settings-physical-followup.js", base)
        self.assertIn("settings-physical-followup.css", base)
        self.assertIn("form.requestSubmit()", client)
        self.assertIn("authority.markDirty =", client)
        self.assertIn("keyboard-open", client)
        self.assertIn("settings-save-actions", css)
        self.assertIn("display: none !important", css)
        self.assertIn("writing-mode: vertical-lr", css)
        self.assertIn("#acp-eq-settings-card", css)

    def test_hardware_configuration_and_status_are_reorganised_once(self):
        client = Path("app/static/js/settings-physical-followup.js").read_text(encoding="utf-8")
        runner = Path("app/runner.py").read_text(encoding="utf-8")

        self.assertIn("arrangeAudioHardware", client)
        self.assertIn("alarm_audio.hardware_device", client)
        self.assertIn("/api/audio/devices", client)
        self.assertIn("settings-audio-hardware-status", client)
        self.assertIn("register_audio_devices_api", runner)
        self.assertIn("settings_unified_scheduled", runner)

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
