from __future__ import annotations

import subprocess
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import test_unified_settings as unified_fixtures
from app.audio_devices import discover_audio_devices
from app.configuration_restore import (
    ConfigurationRestoreExecutor,
    ConfigurationRestorePlanner,
    RestoreConflict,
    RestoreExecutionError,
)
from app.settings_unified_scheduled import UnifiedSettingsService


class SettingsPhysicalFollowupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path("app/templates/base.html").read_text(encoding="utf-8")
        self.settings_template = Path("app/templates/settings.html").read_text(encoding="utf-8")
        self.client = Path("app/static/js/settings-physical-followup.js").read_text(encoding="utf-8")
        self.settings_ipad = Path("app/static/js/settings-ipad.js").read_text(encoding="utf-8")
        self.audio_mixer = Path("app/audio_mixer.py").read_text(encoding="utf-8")
        self.css = Path("app/static/css/settings-physical-followup.css").read_text(encoding="utf-8")
        self.pass_a_css = Path("app/static/css/settings-pass-a.css").read_text(encoding="utf-8")
        self.restore_css = Path("app/static/css/settings-backup-restore.css").read_text(encoding="utf-8")

    def test_promoted_unified_settings_preserves_scheduled_alarm_switch(self):
        fixture = unified_fixtures.UnifiedSettingsTests()
        with patch.object(unified_fixtures, "UnifiedSettingsService", UnifiedSettingsService):
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

    def test_output_trim_pills_share_header_row_and_equal_fader_length(self):
        self.assertIn("grid-template-columns: minmax(0, 1fr) auto", self.pass_a_css)
        self.assertIn("justify-content: stretch", self.pass_a_css)
        self.assertIn("justify-self: start", self.pass_a_css)
        self.assertIn("justify-self: end", self.pass_a_css)
        self.assertIn("grid-template-rows: 34px minmax(271px, 1fr) 58px", self.pass_a_css)
        self.assertIn("grid-template-rows: 32px minmax(234px, 1fr) 52px", self.pass_a_css)
        self.assertIn("heading is vertically centred on the pill", self.pass_a_css)
        self.assertIn("equal-length calibrated faders", self.pass_a_css)

    def test_backup_restore_polish_centres_actions_and_spaces_blocks(self):
        self.assertIn("settings-backup-restore.css", self.base)
        self.assertIn("20260831-home-restore-feedback-v2", self.base)
        self.assertIn('[data-settings-subpage="advanced:backup"] .settings-action-row', self.restore_css)
        self.assertIn("align-items: center", self.restore_css)
        self.assertIn('[data-configuration-restore-preview]:not([hidden])', self.restore_css)
        self.assertIn('[data-configuration-restore-apply-zone]:not([hidden])', self.restore_css)
        self.assertIn("gap: 14px", self.restore_css)
        self.assertIn("min-height: 39px", self.restore_css)

    def test_audio_output_copy_distinguishes_source_trims_from_alarm_ceiling(self):
        self.assertIn("Levels and equaliser", self.settings_template)
        self.assertIn("Output levels", self.settings_template)
        self.assertIn("Persistent output levels", self.settings_template)
        self.assertIn('"label": "Maximum alarm volume"', self.audio_mixer)
        self.assertIn('"description": "Global ceiling after each alarm\'s target and fade."', self.audio_mixer)
        self.assertIn('"label": "Plexamp trim"', self.audio_mixer)
        self.assertIn('"label": "AirPlay trim"', self.audio_mixer)
        self.assertNotIn('"label": "Alarm trim"', self.audio_mixer)
        self.assertIn("const label = data.label || channel", self.settings_ipad)
        self.assertIn("data.error || data.description || data.pcm", self.settings_ipad)
        self.assertIn('<option value="in">in</option>', self.settings_template)

    def test_equaliser_uses_full_width_stacked_live_rows_with_button_spacing(self):
        self.assertIn('[data-settings-subpage="audio:eq"] .acp-eq-settings-grid', self.css)
        self.assertIn('[data-settings-subpage="audio:eq"] .acp-eq-settings-band', self.css)
        self.assertIn("grid-template-columns: 1fr !important", self.css)
        self.assertIn("86px minmax(0, 1fr) 74px", self.css)
        self.assertIn('[data-settings-subpage="audio:eq"] .acp-eq-settings-actions', self.css)
        self.assertIn("margin-top: 19px", self.css)
        self.assertIn("#acp-eq-settings-card", self.css)
        compact = "".join(self.css.split())
        self.assertNotIn("#acp-eq-settings-card{display:none!important;}", compact)

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


class RestoreHarness:
    def __init__(self) -> None:
        self.revision = 1
        self.state = {
            "schema_version": 1,
            "source": {"app_version": "0.4.0"},
            "a_clockwork_plex": {
                "settings": {
                    "dashboard": {
                        "startup_mode": "clock",
                        "idle_return_mode": "clock",
                        "idle_timeout_seconds": 180,
                    },
                },
                "audio": {
                    "eq": {
                        "enabled": True,
                        "bands": {"bass": 0.0, "mid": 0.0, "treble": 0.0},
                    },
                    "mixer": {
                        "master": 80,
                        "plexamp": 100,
                        "airplay": 100,
                        "alarm": 85,
                    },
                },
            },
            "plexamp": {
                "source_version": "4.13.2",
                "headless_preferences": {},
            },
            "export_report": {"warnings": [], "omitted": []},
        }
        self.calls: list[tuple] = []
        self.fail_mixer_once = False
        self.planner = ConfigurationRestorePlanner(current_backup=self.current_backup)
        self.executor = ConfigurationRestoreExecutor(
            planner=self.planner,
            current_backup=self.current_backup,
            settings_snapshot=self.settings_snapshot,
            settings_apply=self.settings_apply,
            eq_status=self.eq_status,
            eq_set_band=self.eq_set_band,
            eq_set_bypass=self.eq_set_bypass,
            mixer_status=self.mixer_status,
            mixer_set_volumes=self.mixer_set_volumes,
        )

    def current_backup(self):
        return deepcopy(self.state)

    def settings_snapshot(self):
        return {
            "ok": True,
            "revision": str(self.revision),
            "settings": deepcopy(self.state["a_clockwork_plex"]["settings"]),
        }

    def settings_apply(self, payload):
        if str(payload.get("revision")) != str(self.revision):
            raise RuntimeError("stale settings revision")
        self.calls.append(("settings",))
        self.state["a_clockwork_plex"]["settings"] = deepcopy(payload["settings"])
        self.revision += 1
        return self.settings_snapshot()

    def eq_status(self):
        eq = self.state["a_clockwork_plex"]["audio"]["eq"]
        return {
            "available": True,
            "bypassed": not eq["enabled"],
            "bands": {
                band: {"db": value, "stored_db": value}
                for band, value in eq["bands"].items()
            },
        }

    def eq_set_band(self, band, value):
        self.calls.append(("eq-band", str(band), float(value)))
        self.state["a_clockwork_plex"]["audio"]["eq"]["bands"][str(band)] = float(value)
        return self.eq_status()

    def eq_set_bypass(self, enabled):
        self.calls.append(("eq-bypass", bool(enabled)))
        self.state["a_clockwork_plex"]["audio"]["eq"]["enabled"] = not bool(enabled)
        return self.eq_status()

    def mixer_status(self):
        return {
            "available": True,
            "configured": True,
            "channels": {
                channel: {"percent": value, "available": True}
                for channel, value in self.state["a_clockwork_plex"]["audio"]["mixer"].items()
            },
        }

    def mixer_set_volumes(self, values):
        self.calls.append(("mixer", deepcopy(values)))
        self.state["a_clockwork_plex"]["audio"]["mixer"] = deepcopy(values)
        if self.fail_mixer_once:
            self.fail_mixer_once = False
            raise RuntimeError("injected mixer failure")
        return self.mixer_status()

    def candidate(self):
        backup = self.current_backup()
        backup["a_clockwork_plex"]["settings"]["dashboard"]["idle_timeout_seconds"] = 240
        backup["a_clockwork_plex"]["audio"]["eq"]["bands"]["bass"] = 1.0
        backup["a_clockwork_plex"]["audio"]["mixer"]["master"] = 75
        return backup


class PlexampRestoreHarness(RestoreHarness):
    def __init__(self) -> None:
        super().__init__()
        self.state["plexamp"]["headless_preferences"] = {
            "audioConversionBitrate": 256,
            "autoPlayEnabled": False,
            "cacheSize": 32768,
            "cachingWiFi": 10,
            "loudnessLeveling": False,
            "precacheNetworkSpeed": 0,
            "sampleRateConversionQuality": 4,
            "sampleRateMatching": 2,
        }
        self.plexamp_version = "4.13.2"
        self.plexamp_ready = True
        self.fail_headless_once = False
        self.planner = ConfigurationRestorePlanner(
            current_backup=self.current_backup,
            plexamp_preference_status=self.plexamp_status,
        )
        self.executor = ConfigurationRestoreExecutor(
            planner=self.planner,
            current_backup=self.current_backup,
            settings_snapshot=self.settings_snapshot,
            settings_apply=self.settings_apply,
            eq_status=self.eq_status,
            eq_set_band=self.eq_set_band,
            eq_set_bypass=self.eq_set_bypass,
            mixer_status=self.mixer_status,
            mixer_set_volumes=self.mixer_set_volumes,
            plexamp_preference_status=self.plexamp_status,
            plexamp_preference_apply=self.plexamp_apply,
        )

    def plexamp_status(self):
        return {
            "available": self.plexamp_ready,
            "restore_ready": self.plexamp_ready,
            "installed_version": self.plexamp_version,
        }

    def plexamp_apply(self, values, *, source_version):
        self.calls.append(("plexamp", str(source_version), deepcopy(values)))
        if str(source_version) != self.plexamp_version:
            raise RuntimeError("Plexamp version mismatch")
        if self.fail_headless_once:
            self.fail_headless_once = False
            raise RuntimeError("injected Plexamp preference failure")
        self.state["plexamp"]["headless_preferences"].update(deepcopy(values))
        return {
            "ok": True,
            "verified": True,
            "installed_version": self.plexamp_version,
            "changed_count": len(values),
        }

    def headless_candidate(self):
        backup = self.current_backup()
        backup["plexamp"]["headless_preferences"]["autoPlayEnabled"] = True
        return backup


class ConfigurationRestoreTransactionTests(unittest.TestCase):
    def test_preview_remains_read_only_while_separate_restore_is_available(self):
        harness = RestoreHarness()
        plan = harness.planner.plan(harness.candidate())

        self.assertTrue(plan["read_only"])
        self.assertFalse(plan["apply_enabled"])
        self.assertTrue(plan["restore_available"])
        self.assertTrue(plan["server_restore_available"])
        self.assertEqual(plan["apply_change_count"], 3)
        self.assertRegex(plan["preview_token"], r"^[a-f0-9]{32}$")
        self.assertEqual(harness.calls, [])

    def test_executor_applies_settings_eq_and_mixer_then_verifies(self):
        harness = RestoreHarness()
        candidate = harness.candidate()
        plan = harness.planner.plan(candidate)

        result = harness.executor.apply(
            candidate,
            preview_token=plan["preview_token"],
            confirm_restore=True,
            confirmations=[],
        )

        self.assertTrue(result["restored"])
        self.assertEqual(result["applied_change_count"], 3)
        self.assertEqual(
            harness.state["a_clockwork_plex"]["settings"]["dashboard"]["idle_timeout_seconds"],
            240,
        )
        self.assertEqual(
            harness.state["a_clockwork_plex"]["audio"]["eq"]["bands"]["bass"],
            1.0,
        )
        self.assertEqual(
            harness.state["a_clockwork_plex"]["audio"]["mixer"]["master"],
            75,
        )
        after = harness.planner.plan(candidate)
        self.assertEqual(after["apply_change_count"], 0)
        self.assertFalse(after["restore_available"])
        self.assertFalse(after["server_restore_available"])

    def test_executor_rejects_stale_preview_without_new_mutation(self):
        harness = RestoreHarness()
        candidate = harness.candidate()
        plan = harness.planner.plan(candidate)

        harness.state["a_clockwork_plex"]["settings"]["dashboard"]["idle_timeout_seconds"] = 181
        calls_before = deepcopy(harness.calls)

        with self.assertRaises(RestoreConflict):
            harness.executor.apply(
                candidate,
                preview_token=plan["preview_token"],
                confirm_restore=True,
                confirmations=[],
            )

        self.assertEqual(harness.calls, calls_before)
        self.assertEqual(
            harness.state["a_clockwork_plex"]["settings"]["dashboard"]["idle_timeout_seconds"],
            181,
        )

    def test_late_mixer_failure_rolls_back_all_touched_owners(self):
        harness = RestoreHarness()
        before = harness.current_backup()
        candidate = harness.candidate()
        plan = harness.planner.plan(candidate)
        harness.fail_mixer_once = True

        with self.assertRaises(RestoreExecutionError) as context:
            harness.executor.apply(
                candidate,
                preview_token=plan["preview_token"],
                confirm_restore=True,
                confirmations=[],
            )

        self.assertEqual(context.exception.stage, "persistent mixer")
        self.assertEqual(context.exception.rollback_failures, [])
        self.assertEqual(
            harness.state["a_clockwork_plex"],
            before["a_clockwork_plex"],
        )
        self.assertGreaterEqual(
            sum(1 for call in harness.calls if call[0] == "settings"),
            2,
        )
        self.assertGreaterEqual(
            sum(1 for call in harness.calls if call[0] == "mixer"),
            2,
        )

    def test_exact_version_headless_preview_and_apply_are_first_class(self):
        harness = PlexampRestoreHarness()
        candidate = harness.headless_candidate()
        plan = harness.planner.plan(candidate)

        self.assertTrue(plan["restore_available"])
        self.assertFalse(plan["server_restore_available"])
        self.assertTrue(plan["plexamp_headless_restore_available"])
        self.assertEqual(plan["apply_change_count"], 1)
        self.assertEqual(plan["plexamp_headless_change_count"], 1)
        self.assertEqual(plan["plexamp_headless"]["restorable_items"], 1)
        self.assertEqual(plan["plexamp_headless"]["deferred_items"], 0)

        result = harness.executor.apply(
            candidate,
            preview_token=plan["preview_token"],
            confirm_restore=True,
            confirmations=[],
        )

        self.assertTrue(result["restored"])
        self.assertEqual(result["server_applied_change_count"], 0)
        self.assertEqual(result["plexamp_headless_applied_change_count"], 1)
        self.assertTrue(harness.state["plexamp"]["headless_preferences"]["autoPlayEnabled"])
        self.assertEqual(
            [call for call in harness.calls if call[0] == "plexamp"],
            [("plexamp", "4.13.2", {"autoPlayEnabled": True})],
        )
        self.assertFalse(harness.planner.plan(candidate)["restore_available"])

    def test_headless_version_mismatch_is_deferred_without_owner_call(self):
        harness = PlexampRestoreHarness()
        candidate = harness.headless_candidate()
        candidate["plexamp"]["source_version"] = "4.14.0"

        plan = harness.planner.plan(candidate)

        self.assertFalse(plan["restore_available"])
        self.assertFalse(plan["plexamp_headless_restore_available"])
        self.assertEqual(plan["plexamp_headless_detected_change_count"], 1)
        self.assertEqual(plan["plexamp_headless_change_count"], 0)
        self.assertEqual(plan["deferred_change_count"], 1)
        self.assertIn("not an exact known match", " ".join(plan["warnings"]))
        self.assertEqual(harness.calls, [])

    def test_sample_rate_preferences_defer_across_application_audio_generation(self):
        harness = PlexampRestoreHarness()
        candidate = harness.headless_candidate()
        candidate["source"]["app_version"] = "0.5.0"
        candidate["plexamp"]["headless_preferences"]["sampleRateMatching"] = 1

        plan = harness.planner.plan(candidate)

        self.assertTrue(plan["restore_available"])
        self.assertEqual(plan["plexamp_headless_detected_change_count"], 2)
        self.assertEqual(plan["plexamp_headless_change_count"], 1)
        self.assertEqual(plan["deferred_change_count"], 1)
        self.assertIn(
            "plexamp.headless_preferences.sampleRateMatching",
            plan["deferred_changed_paths"],
        )
        self.assertIn("audio generation differs", " ".join(plan["warnings"]))

        result = harness.executor.apply(
            candidate,
            preview_token=plan["preview_token"],
            confirm_restore=True,
            confirmations=[],
        )
        self.assertEqual(result["plexamp_headless_applied_change_count"], 1)
        self.assertEqual(result["deferred_change_count"], 1)
        self.assertTrue(harness.state["plexamp"]["headless_preferences"]["autoPlayEnabled"])
        self.assertEqual(harness.state["plexamp"]["headless_preferences"]["sampleRateMatching"], 2)

    def test_changed_headless_capability_invalidates_preview_before_mutation(self):
        harness = PlexampRestoreHarness()
        candidate = harness.headless_candidate()
        plan = harness.planner.plan(candidate)
        harness.plexamp_version = "4.13.3"

        with self.assertRaises(RestoreConflict):
            harness.executor.apply(
                candidate,
                preview_token=plan["preview_token"],
                confirm_restore=True,
                confirmations=[],
            )

        self.assertEqual(harness.calls, [])
        self.assertFalse(harness.state["plexamp"]["headless_preferences"]["autoPlayEnabled"])

    def test_headless_owner_failure_rolls_back_earlier_server_owners(self):
        harness = PlexampRestoreHarness()
        before = harness.current_backup()
        candidate = harness.candidate()
        candidate["plexamp"]["headless_preferences"]["autoPlayEnabled"] = True
        plan = harness.planner.plan(candidate)
        harness.fail_headless_once = True

        with self.assertRaises(RestoreExecutionError) as context:
            harness.executor.apply(
                candidate,
                preview_token=plan["preview_token"],
                confirm_restore=True,
                confirmations=[],
            )

        self.assertEqual(context.exception.stage, "Plexamp Headless preferences")
        self.assertEqual(context.exception.rollback_failures, [])
        self.assertEqual(harness.state["a_clockwork_plex"], before["a_clockwork_plex"])
        self.assertEqual(harness.state["plexamp"], before["plexamp"])
        self.assertGreaterEqual(sum(1 for call in harness.calls if call[0] == "settings"), 2)

    def test_eq_validation_rejects_values_outside_half_db_steps(self):
        harness = RestoreHarness()
        candidate = harness.candidate()
        candidate["a_clockwork_plex"]["audio"]["eq"]["bands"]["bass"] = 0.3

        with self.assertRaises(ValueError) as context:
            harness.planner.plan(candidate)

        self.assertIn("0.5 dB steps", str(context.exception))
        self.assertEqual(harness.calls, [])

    def test_forbidden_key_detection_is_case_insensitive(self):
        harness = RestoreHarness()
        candidate = harness.candidate()
        candidate["a_clockwork_plex"]["settings"]["weather"] = {"API_KEY": "not-a-real-secret"}

        with self.assertRaises(ValueError) as context:
            harness.planner.plan(candidate)

        self.assertIn("credential-owned field", str(context.exception))
        self.assertNotIn("not-a-real-secret", str(context.exception))

    def test_restore_ui_requires_preview_token_explicit_confirmation_and_owner_split(self):
        client = Path("app/static/js/settings-about.js").read_text(encoding="utf-8")
        runner = Path("app/runner.py").read_text(encoding="utf-8")

        self.assertIn("restore_available", client)
        self.assertIn("server_restore_available", client)
        self.assertIn("plexamp_headless_restore_available", client)
        self.assertIn("plan.apply_enabled !== false", client)
        self.assertIn("data-configuration-restore-server-count", client)
        self.assertIn("data-configuration-restore-headless-summary", client)
        self.assertIn("/api/settings/restore/apply", client)
        self.assertIn("preview_token: lastPlan.preview_token", client)
        self.assertIn("confirm_restore: true", client)
        self.assertIn("confirm-configuration-restore", client)
        self.assertIn("Compatible Plexamp Headless preferences", client)
        self.assertNotIn("Plexamp Headless preferences and Home layout remain deferred", client)
        self.assertIn("PlexampPreferenceManager", runner)
        self.assertIn("plexamp_preference_status=plexamp_preferences.status", runner)
        self.assertIn("plexamp_preference_apply=plexamp_preferences.apply", runner)
        self.assertIn("register_configuration_restore_apply_api", runner)


if __name__ == "__main__":
    unittest.main()
