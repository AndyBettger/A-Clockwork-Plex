from __future__ import annotations

import ast
import unittest
from pathlib import Path

from scripts.stage_c_transaction.production_adapter_contract import (
    AdapterOperation,
    AdapterStatus,
    PackageFingerprint,
    ProductionAdapter,
    SnapshotIdentity,
    TransactionAction,
    TransactionIdentity,
)
from scripts.stage_c_transaction import production_operation_programs as programs
from scripts.stage_c_transaction import production_policy_simulation as simulation


class StageCProductionPolicySimulationSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(__file__).resolve().parents[1]
        self.module = (
            self.repo
            / "scripts"
            / "stage_c_transaction"
            / "production_policy_simulation.py"
        )
        self.source = self.module.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    @staticmethod
    def _operations(
        result: simulation.SimulationResult,
    ) -> tuple[AdapterOperation, ...]:
        return tuple(record.operation for record in result.records)

    def test_simulator_has_no_host_or_entrypoint_imports(self) -> None:
        imported: set[str] = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        forbidden = {
            "argparse",
            "fcntl",
            "os",
            "pathlib",
            "requests",
            "shlex",
            "shutil",
            "socket",
            "subprocess",
            "urllib",
        }
        self.assertTrue(forbidden.isdisjoint(imported))
        for marker in (
            "def main(",
            "if __name__",
            "REQUIRED_CONFIRMATION",
            "--confirm",
            "getattr(",
            "eval(",
            "exec(",
            "shell=True",
        ):
            self.assertNotIn(marker, self.source)

    def test_recording_adapter_conforms_and_dispatch_is_explicit_for_all_operations(self) -> None:
        adapter = simulation.RecordingProductionAdapter()
        self.assertIsInstance(adapter, ProductionAdapter)
        for operation in AdapterOperation:
            marker = f"case AdapterOperation.{operation.name}:"
            self.assertEqual(self.source.count(marker), 1, operation.value)
        self.assertEqual(
            self.source.count("case AdapterOperation."),
            len(AdapterOperation),
        )

    def test_adapter_generated_transaction_and_snapshot_are_bound(self) -> None:
        adapter = simulation.RecordingProductionAdapter()
        package = PackageFingerprint("0" * 64)
        self.assertEqual(adapter.acquire_production_lock().status, AdapterStatus.PASS)
        created = adapter.create_authoritative_transaction(
            TransactionAction.INSTALL,
            package,
        )
        self.assertEqual(created.status, AdapterStatus.PASS)
        self.assertIsNotNone(created.payload)
        authoritative = created.payload
        assert authoritative is not None

        filesystem = adapter.capture_filesystem_state(authoritative.transaction)
        self.assertEqual(filesystem.status, AdapterStatus.PASS)
        self.assertIsNotNone(filesystem.payload)
        assert filesystem.payload is not None
        self.assertEqual(filesystem.payload.identity, authoritative.snapshot)

        substituted = adapter.capture_service_state(
            TransactionIdentity("simulation-substituted")
        )
        self.assertEqual(substituted.status, AdapterStatus.FAIL)
        self.assertIn("substituted transaction", substituted.detail)

        wrong_package = adapter.stage_candidate_files(
            authoritative.transaction,
            PackageFingerprint("1" * 64),
        )
        self.assertEqual(wrong_package.status, AdapterStatus.FAIL)
        self.assertIn("substituted package", wrong_package.detail)

        wrong_snapshot = adapter.restore_exact_snapshot(
            authoritative.transaction,
            SnapshotIdentity("simulation-substituted-snapshot"),
        )
        self.assertEqual(wrong_snapshot.status, AdapterStatus.FAIL)
        self.assertIn("substituted snapshot", wrong_snapshot.detail)

    def test_all_four_success_paths_exactly_match_static_programs(self) -> None:
        for program in programs.PROGRAMS:
            with self.subTest(program=program.name.value):
                result = simulation.simulate_action(program.action)
                self.assertEqual(result.outcome, simulation.SimulationOutcome.COMPLETED)
                self.assertEqual(
                    self._operations(result),
                    tuple(step.operation for step in program.steps),
                )
                self.assertTrue(
                    all(record.status is AdapterStatus.PASS for record in result.records)
                )
                self.assertFalse(result.lock_held)
                self.assertTrue(result.terminal_success)
                self.assertFalse(result.rollback_started)
                self.assertFalse(result.rollback_completed)
                self.assertIsNone(result.failure_operation)
                self.assertIsNone(result.failure_disposition)

    def test_pre_lock_failure_never_attempts_release(self) -> None:
        result = simulation.simulate_action(
            TransactionAction.INSTALL,
            (
                simulation.FailureInjection(
                    AdapterOperation.INSPECT_HOST_CONTRACT
                ),
            ),
        )
        self.assertEqual(
            result.outcome,
            simulation.SimulationOutcome.FAILED_BEFORE_LOCK,
        )
        self.assertEqual(
            self._operations(result),
            (AdapterOperation.INSPECT_HOST_CONTRACT,),
        )
        self.assertNotIn(
            AdapterOperation.RELEASE_PRODUCTION_LOCK,
            self._operations(result),
        )
        self.assertFalse(result.lock_held)
        self.assertFalse(result.rollback_started)
        self.assertIs(
            result.failure_disposition,
            programs.FailureDisposition.ABORT_RELEASE_LOCK,
        )

    def test_pre_mutation_failure_after_lock_releases_without_rollback(self) -> None:
        result = simulation.simulate_action(
            TransactionAction.INSTALL,
            (
                simulation.FailureInjection(
                    AdapterOperation.VALIDATE_CANDIDATE_UNITS
                ),
            ),
        )
        self.assertEqual(result.outcome, simulation.SimulationOutcome.ABORTED)
        operations = self._operations(result)
        self.assertEqual(operations[-2], AdapterOperation.VALIDATE_CANDIDATE_UNITS)
        self.assertEqual(operations[-1], AdapterOperation.RELEASE_PRODUCTION_LOCK)
        self.assertNotIn(
            programs.ProgramName.AUTOMATIC_EXACT_ROLLBACK,
            tuple(record.program for record in result.records),
        )
        self.assertFalse(result.lock_held)
        self.assertFalse(result.rollback_started)
        self.assertFalse(result.terminal_success)

    def test_first_mutation_failure_invokes_exact_rollback_without_reacquiring(self) -> None:
        result = simulation.simulate_action(
            TransactionAction.INSTALL,
            (
                simulation.FailureInjection(
                    AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES,
                    1,
                ),
            ),
        )
        self.assertEqual(result.outcome, simulation.SimulationOutcome.ROLLED_BACK)
        self.assertTrue(result.rollback_started)
        self.assertTrue(result.rollback_completed)
        self.assertFalse(result.lock_held)
        records = result.records
        rollback = tuple(
            record.operation
            for record in records
            if record.program is programs.ProgramName.AUTOMATIC_EXACT_ROLLBACK
        )
        self.assertEqual(
            rollback,
            tuple(
                step.operation
                for step in programs.AUTOMATIC_EXACT_ROLLBACK_PROGRAM.steps
            ),
        )
        self.assertEqual(
            self._operations(result).count(AdapterOperation.ACQUIRE_PRODUCTION_LOCK),
            1,
        )

    def test_commit_failure_is_pre_terminal_and_rolls_back(self) -> None:
        result = simulation.simulate_action(
            TransactionAction.INSTALL,
            (
                simulation.FailureInjection(
                    AdapterOperation.WRITE_COMMIT_MANIFEST
                ),
            ),
        )
        self.assertEqual(result.outcome, simulation.SimulationOutcome.ROLLED_BACK)
        self.assertTrue(result.rollback_started)
        self.assertTrue(result.rollback_completed)
        self.assertFalse(result.terminal_success)
        self.assertFalse(result.lock_held)
        self.assertIn(
            programs.ProgramName.AUTOMATIC_EXACT_ROLLBACK,
            tuple(record.program for record in result.records),
        )

    def test_release_failure_after_commit_never_rolls_back(self) -> None:
        result = simulation.simulate_action(
            TransactionAction.INSTALL,
            (
                simulation.FailureInjection(
                    AdapterOperation.RELEASE_PRODUCTION_LOCK
                ),
            ),
        )
        self.assertEqual(result.outcome, simulation.SimulationOutcome.FAIL_CLOSED)
        self.assertTrue(result.terminal_success)
        self.assertTrue(result.lock_held)
        self.assertFalse(result.rollback_started)
        self.assertFalse(result.rollback_completed)
        self.assertIs(
            result.failure_operation,
            AdapterOperation.RELEASE_PRODUCTION_LOCK,
        )
        self.assertIs(
            result.failure_disposition,
            programs.FailureDisposition.FAIL_CLOSED_RETAIN_LOCK,
        )
        self.assertNotIn(
            programs.ProgramName.AUTOMATIC_EXACT_ROLLBACK,
            tuple(record.program for record in result.records),
        )

    def test_failure_during_automatic_rollback_retains_lock_without_nesting(self) -> None:
        result = simulation.simulate_action(
            TransactionAction.INSTALL,
            (
                simulation.FailureInjection(
                    AdapterOperation.INSTALL_MANAGED_FILES
                ),
                simulation.FailureInjection(
                    AdapterOperation.RESTORE_EXACT_SNAPSHOT
                ),
            ),
        )
        self.assertEqual(result.outcome, simulation.SimulationOutcome.FAIL_CLOSED)
        self.assertTrue(result.rollback_started)
        self.assertFalse(result.rollback_completed)
        self.assertTrue(result.lock_held)
        self.assertIs(
            result.failure_operation,
            AdapterOperation.RESTORE_EXACT_SNAPSHOT,
        )
        rollback_records = tuple(
            record
            for record in result.records
            if record.program is programs.ProgramName.AUTOMATIC_EXACT_ROLLBACK
        )
        self.assertEqual(
            tuple(record.operation for record in rollback_records),
            (
                AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES,
                AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES,
                AdapterOperation.VERIFY_DAC_RELEASED,
                AdapterOperation.RESTORE_EXACT_SNAPSHOT,
            ),
        )
        self.assertEqual(
            tuple(record.program for record in result.records).count(
                programs.ProgramName.AUTOMATIC_EXACT_ROLLBACK
            ),
            len(rollback_records),
        )
        self.assertEqual(
            self._operations(result).count(AdapterOperation.ACQUIRE_PRODUCTION_LOCK),
            1,
        )

    def test_standalone_rollback_uses_held_lock_and_exact_sequence(self) -> None:
        result = simulation.simulate_action(TransactionAction.EXACT_ROLLBACK)
        self.assertEqual(result.outcome, simulation.SimulationOutcome.COMPLETED)
        self.assertEqual(
            self._operations(result),
            tuple(
                step.operation
                for step in programs.AUTOMATIC_EXACT_ROLLBACK_PROGRAM.steps
            ),
        )
        self.assertNotIn(
            AdapterOperation.ACQUIRE_PRODUCTION_LOCK,
            self._operations(result),
        )
        self.assertFalse(result.lock_held)
        self.assertTrue(result.terminal_success)

    def test_second_health_occurrence_can_fail_and_trigger_rollback(self) -> None:
        result = simulation.simulate_action(
            TransactionAction.INSTALL,
            (
                simulation.FailureInjection(
                    AdapterOperation.VERIFY_SPLIT_BUS_HEALTH,
                    2,
                ),
            ),
        )
        self.assertEqual(result.outcome, simulation.SimulationOutcome.ROLLED_BACK)
        health_records = tuple(
            record
            for record in result.records
            if record.operation is AdapterOperation.VERIFY_SPLIT_BUS_HEALTH
        )
        self.assertEqual(len(health_records), 2)
        self.assertIs(health_records[0].status, AdapterStatus.PASS)
        self.assertIs(health_records[1].status, AdapterStatus.FAIL)
        self.assertTrue(result.rollback_completed)

    def test_failback_and_uninstall_post_mutation_fail_closed_without_install_rollback(self) -> None:
        cases = (
            (
                TransactionAction.RUNTIME_FAILBACK,
                AdapterOperation.SELECT_DIRECT_FAILBACK_ROUTE,
            ),
            (
                TransactionAction.EXPLICIT_UNINSTALL,
                AdapterOperation.RESTORE_EXACT_SNAPSHOT,
            ),
        )
        for action, failure in cases:
            with self.subTest(action=action.value):
                result = simulation.simulate_action(
                    action,
                    (simulation.FailureInjection(failure),),
                )
                self.assertEqual(
                    result.outcome,
                    simulation.SimulationOutcome.FAIL_CLOSED,
                )
                self.assertTrue(result.lock_held)
                self.assertFalse(result.rollback_started)
                self.assertFalse(result.rollback_completed)
                self.assertIs(
                    result.failure_disposition,
                    programs.FailureDisposition.FAIL_CLOSED_RETAIN_LOCK,
                )
                self.assertNotIn(
                    programs.ProgramName.AUTOMATIC_EXACT_ROLLBACK,
                    tuple(record.program for record in result.records),
                )

    def test_duplicate_failure_injection_is_rejected(self) -> None:
        failure = simulation.FailureInjection(
            AdapterOperation.VERIFY_DAC_RELEASED,
            1,
        )
        with self.assertRaises(ValueError):
            simulation.RecordingProductionAdapter((failure, failure))


if __name__ == "__main__":
    unittest.main()
