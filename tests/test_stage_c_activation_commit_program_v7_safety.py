from __future__ import annotations

import ast
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/stage_c_transaction/activation_commit_program_v7.py"

from scripts.stage_c_transaction.activation_commit_program_v7 import (
    ACTIVATION_COMMIT_POLICY_V7,
    ACTIVATION_INSTALL_SUFFIX_V7,
    APPROVAL_ROLLBACK_INSERTION_V7,
    BIND_LOCK_LEASE,
    PROMOTE_COMMITTED_APPROVAL,
    PUBLISH_TEMPORARY_APPROVAL,
    RELEASE_PRODUCTION_LOCK,
    REMOVE_TEMPORARY_APPROVAL,
    RESTORE_PREVIOUS_INSTALLATION,
    STOP_MANAGED_SERVICES,
    WRITE_COMMIT_MANIFEST,
    ActivationCommitPolicySnapshotV7,
    ActivationCommitStepV7,
    FailureDisposition,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v7 import (
    ALL_OPERATIONS_V7,
)


class StageCActivationCommitProgramV7SafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = MODULE.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    def test_install_suffix_is_exactly_ten_fixed_unique_operations(self) -> None:
        self.assertEqual(len(ACTIVATION_INSTALL_SUFFIX_V7), 10)
        self.assertEqual(
            tuple(step.position for step in ACTIVATION_INSTALL_SUFFIX_V7),
            tuple(range(1, 11)),
        )
        operations = tuple(step.operation for step in ACTIVATION_INSTALL_SUFFIX_V7)
        self.assertEqual(len(operations), len(set(operations)))
        self.assertTrue(set(operations).issubset(set(ALL_OPERATIONS_V7)))
        self.assertEqual(
            tuple(operation.value for operation in operations),
            (
                "bind-production-lock-lease",
                "publish-temporary-activation-approval",
                "start-managed-stage-c-services",
                "open-music-probe",
                "open-alarm-probe",
                "verify-post-start-health",
                "restore-application-services",
                "verify-dashboard-health",
                "promote-committed-activation-approval",
                "release-production-lock",
            ),
        )

    def test_temporary_approval_precedes_every_service_or_probe_step(self) -> None:
        values = tuple(step.operation.value for step in ACTIVATION_INSTALL_SUFFIX_V7)
        publish_index = values.index(PUBLISH_TEMPORARY_APPROVAL.value)
        for operation in (
            "start-managed-stage-c-services",
            "open-music-probe",
            "open-alarm-probe",
            "verify-post-start-health",
            "restore-application-services",
            "verify-dashboard-health",
        ):
            self.assertLess(publish_index, values.index(operation))
        self.assertIs(ACTIVATION_INSTALL_SUFFIX_V7[0].operation, BIND_LOCK_LEASE)
        self.assertFalse(ACTIVATION_INSTALL_SUFFIX_V7[0].requires_temporary_approval)
        for step in ACTIVATION_INSTALL_SUFFIX_V7[2:8]:
            self.assertTrue(step.requires_temporary_approval)
            self.assertFalse(step.requires_committed_approval)

    def test_committed_promotion_is_the_only_terminal_publication(self) -> None:
        terminal = tuple(
            step
            for step in ACTIVATION_INSTALL_SUFFIX_V7
            if step.failure_disposition is FailureDisposition.TERMINAL_PUBLICATION
        )
        self.assertEqual(len(terminal), 1)
        self.assertIs(terminal[0].operation, PROMOTE_COMMITTED_APPROVAL)
        self.assertEqual(terminal[0].position, 9)
        self.assertTrue(terminal[0].requires_temporary_approval)
        self.assertFalse(terminal[0].requires_committed_approval)

    def test_all_preterminal_failures_use_exact_rollback(self) -> None:
        for step in ACTIVATION_INSTALL_SUFFIX_V7[:8]:
            with self.subTest(operation=step.operation.value):
                self.assertIs(
                    step.failure_disposition,
                    FailureDisposition.EXACT_ROLLBACK,
                )
        self.assertIs(
            ACTIVATION_INSTALL_SUFFIX_V7[8].failure_disposition,
            FailureDisposition.TERMINAL_PUBLICATION,
        )

    def test_only_lock_release_follows_commit_and_uses_forward_recovery(self) -> None:
        final = ACTIVATION_INSTALL_SUFFIX_V7[-1]
        self.assertIs(final.operation, RELEASE_PRODUCTION_LOCK)
        self.assertIs(
            final.failure_disposition,
            FailureDisposition.FORWARD_RECOVERY,
        )
        self.assertTrue(final.requires_committed_approval)
        self.assertFalse(final.requires_temporary_approval)

    def test_historical_write_commit_manifest_is_absent_from_v7_suffix(self) -> None:
        operations = tuple(step.operation for step in ACTIVATION_INSTALL_SUFFIX_V7)
        self.assertNotIn(WRITE_COMMIT_MANIFEST, operations)
        self.assertFalse(
            ACTIVATION_COMMIT_POLICY_V7.historical_write_commit_manifest_used
        )
        self.assertEqual(
            ACTIVATION_COMMIT_POLICY_V7.terminal_operation,
            "promote-committed-activation-approval",
        )
        self.assertIn("sole commit marker", self.source)
        self.assertIn("durably prepare the commit manifest", self.source)

    def test_rollback_insertion_stops_runtime_then_removes_temp_before_restore(self) -> None:
        self.assertEqual(len(APPROVAL_ROLLBACK_INSERTION_V7), 3)
        self.assertEqual(
            tuple(step.operation for step in APPROVAL_ROLLBACK_INSERTION_V7),
            (
                STOP_MANAGED_SERVICES,
                REMOVE_TEMPORARY_APPROVAL,
                RESTORE_PREVIOUS_INSTALLATION,
            ),
        )
        for step in APPROVAL_ROLLBACK_INSERTION_V7:
            self.assertIs(
                step.failure_disposition,
                FailureDisposition.EXACT_ROLLBACK,
            )
        self.assertTrue(
            APPROVAL_ROLLBACK_INSERTION_V7[1].requires_temporary_approval
        )
        self.assertNotIn(
            PROMOTE_COMMITTED_APPROVAL,
            tuple(step.operation for step in APPROVAL_ROLLBACK_INSERTION_V7),
        )

    def test_policy_snapshot_is_frozen_and_records_one_terminal_rule(self) -> None:
        self.assertIsInstance(
            ACTIVATION_COMMIT_POLICY_V7,
            ActivationCommitPolicySnapshotV7,
        )
        self.assertEqual(ACTIVATION_COMMIT_POLICY_V7.version, 7)
        self.assertEqual(
            ACTIVATION_COMMIT_POLICY_V7.physically_proved_prefix,
            "stage-c20-route-selection-and-exact-rollback",
        )
        self.assertEqual(
            ACTIVATION_COMMIT_POLICY_V7.failure_before_terminal,
            "exact-rollback",
        )
        self.assertEqual(
            ACTIVATION_COMMIT_POLICY_V7.failure_after_terminal,
            "forward-recovery",
        )
        with self.assertRaises(FrozenInstanceError):
            ACTIVATION_COMMIT_POLICY_V7.version = 8  # type: ignore[misc]

    def test_step_validation_rejects_ambiguous_or_wrong_terminal_shapes(self) -> None:
        template = ACTIVATION_INSTALL_SUFFIX_V7[0]
        with self.assertRaises(ValueError):
            ActivationCommitStepV7(
                0,
                template.operation,
                FailureDisposition.EXACT_ROLLBACK,
                False,
                False,
                "bad position",
            )
        with self.assertRaises(ValueError):
            ActivationCommitStepV7(
                1,
                template.operation,
                FailureDisposition.TERMINAL_PUBLICATION,
                False,
                False,
                "wrong terminal",
            )
        with self.assertRaises(ValueError):
            ActivationCommitStepV7(
                1,
                template.operation,
                FailureDisposition.EXACT_ROLLBACK,
                True,
                True,
                "ambiguous phase",
            )
        with self.assertRaises(ValueError):
            ActivationCommitStepV7(
                1,
                template.operation,
                FailureDisposition.FORWARD_RECOVERY,
                False,
                False,
                "uncommitted forward recovery",
            )

    def test_module_is_static_metadata_without_host_cli_or_dispatch_boundary(self) -> None:
        forbidden_imports = {
            "argparse",
            "ctypes",
            "fcntl",
            "json",
            "os",
            "pathlib",
            "socket",
            "subprocess",
            "sys",
        }
        imported = {
            alias.name.split(".")[0]
            for node in self.tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(imported.isdisjoint(forbidden_imports))
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.assertNotIn("dispatch", node.name.lower())
                names = {arg.arg for arg in (*node.args.args, *node.args.kwonlyargs)}
                self.assertTrue(
                    names.isdisjoint(
                        {
                            "command",
                            "path",
                            "unit_name",
                            "transaction_root",
                            "lease_id",
                            "record",
                        }
                    ),
                    (node.name, names),
                )
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"eval", "exec", "open", "getattr"})
                elif isinstance(node.func, ast.Attribute):
                    self.assertNotEqual(node.func.attr, "dispatch")
        for forbidden_text in (
            "systemctl",
            "aplay",
            "amixer",
            "/dev/snd",
            "/etc/alsa",
            "shell=True",
        ):
            self.assertNotIn(forbidden_text, self.source)


if __name__ == "__main__":
    unittest.main()
