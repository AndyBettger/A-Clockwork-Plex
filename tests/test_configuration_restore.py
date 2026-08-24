from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path

from app.configuration_restore import (
    ConfigurationRestoreExecutor,
    ConfigurationRestorePlanner,
    RestoreConflict,
    RestoreExecutionError,
)


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


class ConfigurationRestoreTests(unittest.TestCase):
    def test_preview_remains_read_only_while_separate_restore_is_available(self):
        harness = RestoreHarness()
        plan = harness.planner.plan(harness.candidate())

        self.assertTrue(plan["read_only"])
        self.assertFalse(plan["apply_enabled"])
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

    def test_restore_ui_requires_preview_token_and_explicit_confirmation(self):
        client = Path("app/static/js/settings-about.js").read_text(encoding="utf-8")
        runner = Path("app/runner.py").read_text(encoding="utf-8")

        self.assertIn("server_restore_available", client)
        self.assertIn("plan.apply_enabled !== false", client)
        self.assertIn("/api/settings/restore/apply", client)
        self.assertIn("preview_token: lastPlan.preview_token", client)
        self.assertIn("confirm_restore: true", client)
        self.assertIn("confirm-configuration-restore", client)
        self.assertIn("Plexamp Headless preferences and Home layout remain deferred", client)
        self.assertIn("register_configuration_restore_apply_api", runner)


if __name__ == "__main__":
    unittest.main()
