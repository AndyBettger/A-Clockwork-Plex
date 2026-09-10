from __future__ import annotations

import unittest
from copy import deepcopy

from app.configuration_reset import ConfigurationResetExecutor, ConfigurationResetPlanner
from app.configuration_restore import RestoreExecutionError


class FakeRestorePlanner:
    def __init__(self, current_ref: dict) -> None:
        self.current_ref = current_ref
        self.rollback_mode = False
        self.preview_token = "a" * 32

    def plan(self, target):
        target_settings = target.get("a_clockwork_plex", {}).get("settings", {})
        current_settings = self.current_ref.get("a_clockwork_plex", {}).get("settings", {})
        changed = target_settings != current_settings
        token = "b" * 32 if self.rollback_mode else self.preview_token
        return {
            "server_changed_paths": (
                ["a_clockwork_plex.settings.dashboard.startup_mode"] if changed else []
            ),
            "sections": {"settings.dashboard": 1} if changed else {},
            "warnings": [],
            "confirmations_required": [],
            "preview_token": token,
            "restore_available": changed,
        }


class FakeRestoreExecutor:
    def __init__(self, current_ref: dict, planner: FakeRestorePlanner) -> None:
        self.current_ref = current_ref
        self.planner = planner
        self.calls = []

    def apply(self, target, **kwargs):
        self.calls.append((deepcopy(target), dict(kwargs)))
        self.current_ref.clear()
        self.current_ref.update(deepcopy(target))
        self.planner.rollback_mode = True
        return {
            "applied_change_count": 1,
            "applied_sections": ["settings.dashboard"],
        }


class FakeCommissioning:
    def __init__(self) -> None:
        self.player_changed = True
        self.audio_changed = True
        self.fingerprint = "c" * 32
        self.fail = False
        self.apply_calls = []

    def plan(self):
        count = int(self.player_changed) + int(self.audio_changed)
        return {
            "ok": True,
            "ready": True,
            "baseline_present": True,
            "change_count": count,
            "player_name_changed": self.player_changed,
            "audio_output_changed": self.audio_changed,
            "audio_output_label": "A Clockwork Plex - Plexamp",
            "fingerprint": self.fingerprint,
        }

    def apply(self, *, fingerprint: str):
        self.apply_calls.append(fingerprint)
        if self.fail:
            error = RuntimeError("injected Plexamp commissioning failure")
            error.rolled_back = True
            error.rollback_failures = []
            raise error
        count = int(self.player_changed) + int(self.audio_changed)
        self.player_changed = False
        self.audio_changed = False
        return {"verified": True, "changed_count": count}


def current_model(startup: str = "weather") -> dict:
    return {
        "schema_version": 1,
        "source": {"app_version": "0.4.0"},
        "a_clockwork_plex": {
            "settings": {
                "dashboard": {
                    "startup_mode": startup,
                    "idle_return_mode": "clock",
                    "idle_timeout_seconds": 180,
                },
                "display": {},
                "weather": {},
                "alarms": {},
                "airplay": {},
            },
            "audio": {},
        },
        "plexamp": {},
    }


def default_settings() -> dict:
    return {
        "dashboard": {
            "startup_mode": "clock",
            "idle_return_mode": "clock",
            "idle_timeout_seconds": 180,
        },
        "display": {},
        "weather": {},
        "alarms": {},
        "airplay": {},
    }


class ResetCommissioningTests(unittest.TestCase):
    def build(self, *, include_commissioning: bool = True):
        current = current_model()
        restore_planner = FakeRestorePlanner(current)
        restore_executor = FakeRestoreExecutor(current, restore_planner)
        commissioning = FakeCommissioning()
        planner = ConfigurationResetPlanner(
            restore_planner=restore_planner,
            current_backup=lambda: deepcopy(current),
            default_settings=default_settings,
            eq_status=lambda: {"available": False},
            mixer_status=lambda: {"available": False, "configured": False},
            plexamp_commissioning_plan=(commissioning.plan if include_commissioning else None),
        )
        executor = ConfigurationResetExecutor(
            planner=planner,
            restore_planner=restore_planner,
            restore_executor=restore_executor,
            plexamp_commissioning_apply=(commissioning.apply if include_commissioning else None),
        )
        return current, restore_planner, restore_executor, commissioning, planner, executor

    def test_combined_plan_counts_acp_and_commissioning_without_leaking_values(self) -> None:
        _current, _rp, _re, _commissioning, planner, _executor = self.build()

        result = planner.plan()

        self.assertEqual(result["acp_change_count"], 1)
        self.assertEqual(result["plexamp_commissioning_change_count"], 2)
        self.assertEqual(result["change_count"], 3)
        self.assertIn("plexamp.commissioning.player_name", result["changed_paths"])
        self.assertIn("plexamp.commissioning.audio_output", result["changed_paths"])
        self.assertEqual(result["sections"]["plexamp.commissioning"], 2)
        self.assertNotEqual(result["reset_token"], "a" * 32)
        self.assertEqual(result["restore_preview_token"], "a" * 32)
        self.assertRegex(result["owner_tokens"]["a_clockwork_plex"], r"^[a-f0-9]{32}$")
        self.assertNotEqual(result["owner_tokens"]["a_clockwork_plex"], "a" * 32)
        self.assertEqual(result["owner_tokens"]["plexamp_commissioning"], "c" * 32)

    def test_acp_owner_token_ignores_headless_restore_token_drift_but_tracks_acp_state(self) -> None:
        current, restore_planner, _re, _commissioning, planner, _executor = self.build()
        first = planner.plan()
        first_acp_token = first["owner_tokens"]["a_clockwork_plex"]
        first_reset_token = first["reset_token"]

        current["plexamp"]["headless_preferences"] = {
            "audioConversionBitrate": 128,
            "cacheSize": 512,
        }
        restore_planner.preview_token = "d" * 32
        second = planner.plan()

        self.assertEqual(second["owner_tokens"]["a_clockwork_plex"], first_acp_token)
        self.assertEqual(second["restore_preview_token"], "d" * 32)
        self.assertNotEqual(second["reset_token"], first_reset_token)

        current["a_clockwork_plex"]["settings"]["dashboard"]["startup_mode"] = "radio"
        third = planner.plan()
        self.assertNotEqual(third["owner_tokens"]["a_clockwork_plex"], first_acp_token)

    def test_combined_apply_reports_all_three_verified_changes(self) -> None:
        _current, _rp, restore_executor, commissioning, planner, executor = self.build()
        plan = planner.plan()

        result = executor.apply(
            reset_token=plan["reset_token"],
            confirm_reset=True,
        )

        self.assertEqual(result["applied_change_count"], 3)
        self.assertEqual(result["acp_applied_change_count"], 1)
        self.assertEqual(result["plexamp_commissioning_applied_change_count"], 2)
        self.assertEqual(len(restore_executor.calls), 1)
        self.assertEqual(restore_executor.calls[0][1]["preview_token"], "a" * 32)
        self.assertEqual(commissioning.apply_calls, ["c" * 32])
        self.assertTrue(result["plexamp_auth_preserved"])
        self.assertTrue(result["plexamp_headless_preferences_preserved"])
        self.assertFalse(result["plexamp_home_reset"])

    def test_commissioning_only_reset_does_not_enter_portable_restore(self) -> None:
        current, _rp, restore_executor, _commissioning, planner, executor = self.build()
        current["a_clockwork_plex"]["settings"]["dashboard"]["startup_mode"] = "clock"
        plan = planner.plan()
        self.assertEqual(plan["acp_change_count"], 0)
        self.assertEqual(plan["plexamp_commissioning_change_count"], 2)

        result = executor.apply(
            reset_token=plan["reset_token"],
            confirm_reset=True,
        )

        self.assertEqual(result["applied_change_count"], 2)
        self.assertEqual(restore_executor.calls, [])

    def test_late_commissioning_failure_rolls_acp_back_to_exact_before_backup(self) -> None:
        current, _rp, restore_executor, commissioning, planner, executor = self.build()
        before = deepcopy(current)
        plan = planner.plan()
        commissioning.fail = True

        with self.assertRaises(RestoreExecutionError) as context:
            executor.apply(reset_token=plan["reset_token"], confirm_reset=True)

        self.assertEqual(context.exception.stage, "Plexamp commissioning")
        self.assertEqual(context.exception.rollback_failures, [])
        self.assertEqual(current, before)
        self.assertEqual(len(restore_executor.calls), 2)
        rollback_target, rollback_kwargs = restore_executor.calls[-1]
        self.assertEqual(rollback_target, before)
        self.assertEqual(rollback_kwargs["preview_token"], "b" * 32)
        self.assertTrue(rollback_kwargs["confirm_restore"])

    def test_missing_optional_commissioning_owner_preserves_legacy_reset_token_contract(self) -> None:
        _current, _rp, _re, _commissioning, planner, _executor = self.build(
            include_commissioning=False
        )

        result = planner.plan()

        self.assertEqual(result["acp_change_count"], 1)
        self.assertEqual(result["plexamp_commissioning_change_count"], 0)
        self.assertEqual(result["change_count"], 1)
        self.assertEqual(result["reset_token"], "a" * 32)
        self.assertEqual(result["restore_preview_token"], "a" * 32)
        self.assertFalse(result["plexamp_commissioning"]["ready"])


if __name__ == "__main__":
    unittest.main()
