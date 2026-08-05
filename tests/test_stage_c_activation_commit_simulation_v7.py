from __future__ import annotations

import ast
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/stage_c_transaction/activation_commit_simulation_v7.py"

from scripts.stage_c_transaction.activation_commit_program_v7 import (
    ACTIVATION_EXACT_ROLLBACK_V7,
    ACTIVATION_INSTALL_SUFFIX_V7,
    PROMOTE_COMMITTED_APPROVAL,
    PUBLISH_TEMPORARY_APPROVAL,
    RELEASE_PRODUCTION_LOCK,
    REMOVE_TEMPORARY_APPROVAL,
    RESTORE_EXACT_SNAPSHOT,
    STOP_MANAGED_SERVICES,
    VERIFY_DAC_RELEASED,
    VERIFY_EXACT_ROLLBACK,
)
from scripts.stage_c_transaction.activation_commit_simulation_v7 import (
    ActivationSimulationResultV7,
    ActivationSimulationStatus,
    simulate_activation_commit_v7,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v7 import (
    ActivationApprovalLifecycleOperation,
)


class StageCActivationCommitSimulationV7Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = MODULE.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    def test_success_executes_exact_suffix_and_ends_committed_unlocked(self) -> None:
        result = simulate_activation_commit_v7()
        self.assertIs(result.status, ActivationSimulationStatus.PASS)
        self.assertEqual(
            result.attempted_operations,
            tuple(step.operation.value for step in ACTIVATION_INSTALL_SUFFIX_V7),
        )
        self.assertEqual(result.rollback_operations, ())
        self.assertIsNone(result.failed_operation)
        state = result.final_state
        self.assertFalse(state.lock_held)
        self.assertTrue(state.lease_bound)
        self.assertFalse(state.temporary_approval_present)
        self.assertTrue(state.managed_runtime_running)
        self.assertTrue(state.applications_restored)
        self.assertTrue(state.split_health_verified)
        self.assertTrue(state.dashboard_health_verified)
        self.assertTrue(state.committed_approval_present)
        self.assertFalse(state.exact_snapshot_restored)
        self.assertFalse(state.mixer_state_restored)
        self.assertFalse(state.service_state_restored)
        self.assertFalse(state.exact_previous_installation_restored)

    def test_every_failure_through_terminal_operation_rolls_back_exactly(self) -> None:
        preterminal = tuple(
            step.operation for step in ACTIVATION_INSTALL_SUFFIX_V7[:-1]
        )
        self.assertIs(preterminal[-1], PROMOTE_COMMITTED_APPROVAL)
        expected_tail = tuple(
            step.operation.value for step in ACTIVATION_EXACT_ROLLBACK_V7[-3:]
        )
        for operation in preterminal:
            with self.subTest(operation=operation.value):
                result = simulate_activation_commit_v7(fail_at=operation)
                self.assertIs(
                    result.status,
                    ActivationSimulationStatus.EXACTLY_ROLLED_BACK,
                )
                self.assertEqual(result.failed_operation, operation.value)
                self.assertIsNone(result.rollback_failed_operation)
                self.assertFalse(result.final_state.lock_held)
                self.assertFalse(result.final_state.temporary_approval_present)
                self.assertFalse(result.final_state.managed_runtime_running)
                self.assertFalse(result.final_state.committed_approval_present)
                self.assertTrue(result.final_state.exact_snapshot_restored)
                self.assertTrue(result.final_state.mixer_state_restored)
                self.assertTrue(result.final_state.service_state_restored)
                self.assertTrue(
                    result.final_state.exact_previous_installation_restored
                )
                self.assertEqual(result.rollback_operations[-3:], expected_tail)

    def test_temporary_removal_runs_only_after_publication_completed(self) -> None:
        before_publish = (
            ACTIVATION_INSTALL_SUFFIX_V7[0].operation,
            PUBLISH_TEMPORARY_APPROVAL,
        )
        for operation in before_publish:
            with self.subTest(operation=operation.value):
                result = simulate_activation_commit_v7(fail_at=operation)
                self.assertNotIn(
                    REMOVE_TEMPORARY_APPROVAL.value,
                    result.rollback_operations,
                )
        for step in ACTIVATION_INSTALL_SUFFIX_V7[2:10]:
            with self.subTest(operation=step.operation.value):
                result = simulate_activation_commit_v7(fail_at=step.operation)
                self.assertIn(
                    REMOVE_TEMPORARY_APPROVAL.value,
                    result.rollback_operations,
                )
                self.assertLess(
                    result.rollback_operations.index(STOP_MANAGED_SERVICES.value),
                    result.rollback_operations.index(
                        REMOVE_TEMPORARY_APPROVAL.value
                    ),
                )
                self.assertLess(
                    result.rollback_operations.index(
                        REMOVE_TEMPORARY_APPROVAL.value
                    ),
                    result.rollback_operations.index(VERIFY_DAC_RELEASED.value),
                )

    def test_postcommit_lock_release_failure_requires_forward_recovery_only(self) -> None:
        result = simulate_activation_commit_v7(
            fail_at=RELEASE_PRODUCTION_LOCK
        )
        self.assertIs(
            result.status,
            ActivationSimulationStatus.FORWARD_RECOVERY_REQUIRED,
        )
        self.assertEqual(
            result.failed_operation,
            RELEASE_PRODUCTION_LOCK.value,
        )
        self.assertEqual(result.rollback_operations, ())
        state = result.final_state
        self.assertTrue(state.lock_held)
        self.assertTrue(state.committed_approval_present)
        self.assertFalse(state.temporary_approval_present)
        self.assertFalse(state.exact_previous_installation_restored)

    def test_each_exact_rollback_failure_retains_lock_and_never_commits(self) -> None:
        rollback_operations = tuple(
            step.operation for step in ACTIVATION_EXACT_ROLLBACK_V7
        )
        for rollback_operation in rollback_operations:
            with self.subTest(operation=rollback_operation.value):
                result = simulate_activation_commit_v7(
                    fail_at=PROMOTE_COMMITTED_APPROVAL,
                    rollback_fail_at=rollback_operation,
                )
                self.assertIs(
                    result.status,
                    ActivationSimulationStatus.ROLLBACK_FAILED_LOCK_RETAINED,
                )
                self.assertEqual(
                    result.rollback_failed_operation,
                    rollback_operation.value,
                )
                self.assertTrue(result.final_state.lock_held)
                self.assertFalse(result.final_state.committed_approval_present)
                self.assertIn(
                    rollback_operation.value,
                    result.rollback_operations,
                )
                self.assertEqual(
                    result.rollback_operations[-1],
                    rollback_operation.value,
                )

    def test_removal_restore_verify_and_release_failures_preserve_exact_phase(self) -> None:
        removal_failure = simulate_activation_commit_v7(
            fail_at=PROMOTE_COMMITTED_APPROVAL,
            rollback_fail_at=REMOVE_TEMPORARY_APPROVAL,
        )
        self.assertTrue(
            removal_failure.final_state.temporary_approval_present
        )
        self.assertFalse(removal_failure.final_state.exact_snapshot_restored)
        self.assertFalse(
            removal_failure.final_state.exact_previous_installation_restored
        )

        restore_failure = simulate_activation_commit_v7(
            fail_at=PROMOTE_COMMITTED_APPROVAL,
            rollback_fail_at=RESTORE_EXACT_SNAPSHOT,
        )
        self.assertFalse(
            restore_failure.final_state.temporary_approval_present
        )
        self.assertFalse(restore_failure.final_state.exact_snapshot_restored)
        self.assertFalse(
            restore_failure.final_state.exact_previous_installation_restored
        )

        verify_failure = simulate_activation_commit_v7(
            fail_at=PROMOTE_COMMITTED_APPROVAL,
            rollback_fail_at=VERIFY_EXACT_ROLLBACK,
        )
        self.assertTrue(verify_failure.final_state.exact_snapshot_restored)
        self.assertTrue(verify_failure.final_state.mixer_state_restored)
        self.assertTrue(verify_failure.final_state.service_state_restored)
        self.assertFalse(
            verify_failure.final_state.exact_previous_installation_restored
        )
        self.assertTrue(verify_failure.final_state.lock_held)

        release_failure = simulate_activation_commit_v7(
            fail_at=PROMOTE_COMMITTED_APPROVAL,
            rollback_fail_at=RELEASE_PRODUCTION_LOCK,
        )
        self.assertTrue(
            release_failure.final_state.exact_previous_installation_restored
        )
        self.assertTrue(release_failure.final_state.lock_held)

    def test_failure_injection_is_typed_and_confined_to_fixed_programs(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside the fixed activation suffix"):
            simulate_activation_commit_v7(
                fail_at=ActivationApprovalLifecycleOperation.
                REMOVE_TEMPORARY_ACTIVATION_APPROVAL
            )
        with self.assertRaisesRegex(ValueError, "outside the fixed exact rollback"):
            simulate_activation_commit_v7(
                fail_at=PROMOTE_COMMITTED_APPROVAL,
                rollback_fail_at=ActivationApprovalLifecycleOperation.
                BIND_PRODUCTION_LOCK_LEASE,
            )
        with self.assertRaisesRegex(ValueError, "requires an install failure"):
            simulate_activation_commit_v7(
                rollback_fail_at=STOP_MANAGED_SERVICES
            )

    def test_results_are_frozen_and_reject_inconsistent_terminal_states(self) -> None:
        result = simulate_activation_commit_v7()
        self.assertIsInstance(result, ActivationSimulationResultV7)
        with self.assertRaises(FrozenInstanceError):
            result.failed_operation = "changed"  # type: ignore[misc]
        with self.assertRaises(ValueError):
            ActivationSimulationResultV7(
                status=ActivationSimulationStatus.FORWARD_RECOVERY_REQUIRED,
                attempted_operations=("release-production-lock",),
                rollback_operations=("restore-exact-snapshot",),
                failed_operation="release-production-lock",
                rollback_failed_operation=None,
                final_state=result.final_state,
            )

    def test_historical_write_commit_manifest_never_appears_in_any_trace(self) -> None:
        results = [simulate_activation_commit_v7()]
        results.extend(
            simulate_activation_commit_v7(fail_at=step.operation)
            for step in ACTIVATION_INSTALL_SUFFIX_V7
        )
        for result in results:
            combined = result.attempted_operations + result.rollback_operations
            self.assertNotIn("write-commit-manifest", combined)
            self.assertLessEqual(
                combined.count(
                    "promote-committed-activation-approval"
                ),
                1,
            )

    def test_simulator_has_no_host_entrypoint_command_or_generic_dispatch(self) -> None:
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
                            "path",
                            "command",
                            "unit_name",
                            "transaction_root",
                            "record",
                            "lease_id",
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
