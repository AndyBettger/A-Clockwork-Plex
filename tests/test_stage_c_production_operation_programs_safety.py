from __future__ import annotations

import ast
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from scripts.stage_c_transaction.production_adapter_contract import (
    AdapterOperation,
    TransactionAction,
)
from scripts.stage_c_transaction import production_operation_programs as programs


class StageCProductionOperationProgramsSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(__file__).resolve().parents[1]
        self.module = (
            self.repo
            / "scripts"
            / "stage_c_transaction"
            / "production_operation_programs.py"
        )
        self.source = self.module.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    @staticmethod
    def _operations(program: programs.OperationProgram) -> tuple[AdapterOperation, ...]:
        return tuple(step.operation for step in program.steps)

    def test_module_is_static_metadata_without_execution_boundary(self) -> None:
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
            "ProductionAdapter",
            "BlockedProductionAdapter",
            "ProductionAdapterBlocked",
            "getattr(",
            "callable(",
            "def main(",
            "if __name__",
            "REQUIRED_CONFIRMATION",
            "--confirm",
        ):
            self.assertNotIn(marker, self.source)

    def test_exactly_four_immutable_programs_map_each_action_once(self) -> None:
        expected_mapping = (
            (programs.ProgramName.INSTALL, TransactionAction.INSTALL),
            (
                programs.ProgramName.AUTOMATIC_EXACT_ROLLBACK,
                TransactionAction.EXACT_ROLLBACK,
            ),
            (
                programs.ProgramName.RUNTIME_DIRECT_FAILBACK,
                TransactionAction.RUNTIME_FAILBACK,
            ),
            (
                programs.ProgramName.EXPLICIT_UNINSTALL,
                TransactionAction.EXPLICIT_UNINSTALL,
            ),
        )
        self.assertEqual(len(programs.PROGRAMS), 4)
        self.assertEqual(
            tuple((program.name, program.action) for program in programs.PROGRAMS),
            expected_mapping,
        )
        self.assertEqual(
            {program.action for program in programs.PROGRAMS},
            set(TransactionAction),
        )
        for program in programs.PROGRAMS:
            self.assertIs(programs.program_for_action(program.action), program)
            with self.assertRaises(FrozenInstanceError):
                program.name = programs.ProgramName.INSTALL  # type: ignore[misc]
            with self.assertRaises(FrozenInstanceError):
                program.steps[0].detail = "changed"  # type: ignore[misc]

    def test_every_step_uses_only_the_stage_c10_operation_enum(self) -> None:
        for program in programs.PROGRAMS:
            with self.subTest(program=program.name.value):
                self.assertTrue(program.steps)
                self.assertTrue(
                    all(isinstance(step.operation, AdapterOperation) for step in program.steps)
                )
                self.assertEqual(
                    tuple(step.order for step in program.steps),
                    tuple(range(10, 10 * (len(program.steps) + 1), 10)),
                )
                self.assertIs(
                    program.steps[-1].operation,
                    AdapterOperation.RELEASE_PRODUCTION_LOCK,
                )
                self.assertIs(
                    program.steps[-2].operation,
                    program.terminal_success_operation,
                )
                self.assertIs(
                    program.after_terminal_success_failure,
                    programs.FailureDisposition.FAIL_CLOSED_RETAIN_LOCK,
                )
        self.assertFalse(hasattr(AdapterOperation, "EXPLICIT_UNINSTALL"))

    def test_unheld_programs_acquire_before_every_lock_bound_step(self) -> None:
        for program in (
            programs.INSTALL_PROGRAM,
            programs.RUNTIME_DIRECT_FAILBACK_PROGRAM,
            programs.EXPLICIT_UNINSTALL_PROGRAM,
        ):
            with self.subTest(program=program.name.value):
                self.assertIs(program.entry_lock_state, programs.EntryLockState.UNHELD)
                operations = self._operations(program)
                acquire = operations.index(AdapterOperation.ACQUIRE_PRODUCTION_LOCK)
                self.assertEqual(operations.count(AdapterOperation.ACQUIRE_PRODUCTION_LOCK), 1)
                self.assertTrue(
                    all(not step.lock_required for step in program.steps[: acquire + 1])
                )
                self.assertTrue(
                    all(step.lock_required for step in program.steps[acquire + 1 :])
                )
                self.assertLess(
                    acquire,
                    operations.index(AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION),
                )

    def test_install_program_matches_reviewed_order_and_failure_boundary(self) -> None:
        program = programs.INSTALL_PROGRAM
        expected = (
            AdapterOperation.INSPECT_HOST_CONTRACT,
            AdapterOperation.INSPECT_PRODUCTION_LOCK,
            AdapterOperation.ACQUIRE_PRODUCTION_LOCK,
            AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION,
            AdapterOperation.CAPTURE_FILESYSTEM_STATE,
            AdapterOperation.CAPTURE_SERVICE_STATE,
            AdapterOperation.CAPTURE_MIXER_STATE,
            AdapterOperation.CAPTURE_LOOPBACK_STATE,
            AdapterOperation.CAPTURE_DAC_STATE,
            AdapterOperation.STAGE_CANDIDATE_FILES,
            AdapterOperation.VALIDATE_CANDIDATE_ALSA,
            AdapterOperation.VALIDATE_CANDIDATE_SUDOERS,
            AdapterOperation.VALIDATE_CANDIDATE_UNITS,
            AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP,
            AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES,
            AdapterOperation.VERIFY_DAC_RELEASED,
            AdapterOperation.INSTALL_MANAGED_FILES,
            AdapterOperation.RELOAD_SYSTEMD,
            AdapterOperation.SELECT_SPLIT_BUS_ROUTE,
            AdapterOperation.START_MANAGED_STAGE_C_SERVICES,
            AdapterOperation.VERIFY_SPLIT_BUS_HEALTH,
            AdapterOperation.RUN_FINITE_MUSIC_PROBE,
            AdapterOperation.RUN_FINITE_ALARM_PROBE,
            AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES,
            AdapterOperation.VERIFY_SPLIT_BUS_HEALTH,
            AdapterOperation.VERIFY_DASHBOARD_HEALTH,
            AdapterOperation.WRITE_COMMIT_MANIFEST,
            AdapterOperation.RELEASE_PRODUCTION_LOCK,
        )
        self.assertEqual(self._operations(program), expected)
        first_change = next(
            index
            for index, step in enumerate(program.steps)
            if step.changes_managed_audio_state
        )
        self.assertIs(
            program.steps[first_change].operation,
            AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES,
        )
        self.assertTrue(
            all(not step.changes_managed_audio_state for step in program.steps[:first_change])
        )
        self.assertIs(
            program.before_mutation_failure,
            programs.FailureDisposition.ABORT_RELEASE_LOCK,
        )
        self.assertIs(
            program.after_mutation_failure,
            programs.FailureDisposition.AUTOMATIC_EXACT_ROLLBACK,
        )
        self.assertIs(
            program.terminal_success_operation,
            AdapterOperation.WRITE_COMMIT_MANIFEST,
        )
        self.assertIs(
            program.after_terminal_success_failure,
            programs.FailureDisposition.FAIL_CLOSED_RETAIN_LOCK,
        )
        self.assertIs(
            program.snapshot_source,
            programs.SnapshotSource.FRESH_AUTHORITATIVE,
        )

    def test_install_commits_only_after_post_start_and_dashboard_health(self) -> None:
        operations = self._operations(programs.INSTALL_PROGRAM)
        restore_apps = operations.index(AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES)
        post_start_health = operations.index(AdapterOperation.VERIFY_SPLIT_BUS_HEALTH, restore_apps)
        dashboard = operations.index(AdapterOperation.VERIFY_DASHBOARD_HEALTH)
        commit = operations.index(AdapterOperation.WRITE_COMMIT_MANIFEST)
        release = operations.index(AdapterOperation.RELEASE_PRODUCTION_LOCK)
        self.assertLess(restore_apps, post_start_health)
        self.assertLess(post_start_health, dashboard)
        self.assertLess(dashboard, commit)
        self.assertLess(commit, release)
        self.assertEqual(operations.count(AdapterOperation.VERIFY_SPLIT_BUS_HEALTH), 2)

    def test_automatic_rollback_retains_existing_lock_and_verifies_before_release(self) -> None:
        program = programs.AUTOMATIC_EXACT_ROLLBACK_PROGRAM
        expected = (
            AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES,
            AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES,
            AdapterOperation.VERIFY_DAC_RELEASED,
            AdapterOperation.RESTORE_EXACT_SNAPSHOT,
            AdapterOperation.RELOAD_SYSTEMD,
            AdapterOperation.RESTORE_MIXER_STATE,
            AdapterOperation.RESTORE_SERVICE_STATE,
            AdapterOperation.VERIFY_EXACT_ROLLBACK,
            AdapterOperation.RELEASE_PRODUCTION_LOCK,
        )
        self.assertEqual(self._operations(program), expected)
        self.assertIs(program.entry_lock_state, programs.EntryLockState.HELD)
        self.assertNotIn(AdapterOperation.ACQUIRE_PRODUCTION_LOCK, expected)
        self.assertTrue(all(step.lock_required for step in program.steps))
        self.assertIs(
            program.before_mutation_failure,
            programs.FailureDisposition.FAIL_CLOSED_RETAIN_LOCK,
        )
        self.assertIs(
            program.after_mutation_failure,
            programs.FailureDisposition.FAIL_CLOSED_RETAIN_LOCK,
        )
        self.assertIs(
            program.terminal_success_operation,
            AdapterOperation.VERIFY_EXACT_ROLLBACK,
        )
        self.assertIs(
            program.after_terminal_success_failure,
            programs.FailureDisposition.FAIL_CLOSED_RETAIN_LOCK,
        )
        self.assertIs(
            program.snapshot_source,
            programs.SnapshotSource.ACTIVE_TRANSACTION_AUTHORITATIVE,
        )

    def test_runtime_failback_is_alarm_safe_and_never_performs_uninstall_restore(self) -> None:
        program = programs.RUNTIME_DIRECT_FAILBACK_PROGRAM
        operations = self._operations(program)
        expected = (
            AdapterOperation.INSPECT_HOST_CONTRACT,
            AdapterOperation.INSPECT_PRODUCTION_LOCK,
            AdapterOperation.ACQUIRE_PRODUCTION_LOCK,
            AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION,
            AdapterOperation.CAPTURE_SERVICE_STATE,
            AdapterOperation.CAPTURE_MIXER_STATE,
            AdapterOperation.CAPTURE_DAC_STATE,
            AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES,
            AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES,
            AdapterOperation.VERIFY_DAC_RELEASED,
            AdapterOperation.SELECT_DIRECT_FAILBACK_ROUTE,
            AdapterOperation.RESTORE_MIXER_STATE,
            AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES,
            AdapterOperation.RUN_FINITE_MUSIC_PROBE,
            AdapterOperation.RUN_FINITE_ALARM_PROBE,
            AdapterOperation.VERIFY_DASHBOARD_HEALTH,
            AdapterOperation.WRITE_COMMIT_MANIFEST,
            AdapterOperation.RELEASE_PRODUCTION_LOCK,
        )
        self.assertEqual(operations, expected)
        self.assertNotIn(AdapterOperation.RESTORE_EXACT_SNAPSHOT, operations)
        self.assertNotIn(AdapterOperation.SELECT_SPLIT_BUS_ROUTE, operations)
        self.assertLess(
            operations.index(AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES),
            operations.index(AdapterOperation.SELECT_DIRECT_FAILBACK_ROUTE),
        )
        self.assertLess(
            operations.index(AdapterOperation.SELECT_DIRECT_FAILBACK_ROUTE),
            operations.index(AdapterOperation.RUN_FINITE_ALARM_PROBE),
        )
        self.assertIs(
            program.terminal_success_operation,
            AdapterOperation.WRITE_COMMIT_MANIFEST,
        )
        self.assertIs(
            program.snapshot_source,
            programs.SnapshotSource.COMMITTED_INSTALLATION_PLUS_LIVE,
        )

    def test_explicit_uninstall_is_composed_policy_not_adapter_shortcut(self) -> None:
        program = programs.EXPLICIT_UNINSTALL_PROGRAM
        operations = self._operations(program)
        expected = (
            AdapterOperation.INSPECT_HOST_CONTRACT,
            AdapterOperation.INSPECT_PRODUCTION_LOCK,
            AdapterOperation.ACQUIRE_PRODUCTION_LOCK,
            AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION,
            AdapterOperation.CAPTURE_SERVICE_STATE,
            AdapterOperation.CAPTURE_MIXER_STATE,
            AdapterOperation.CAPTURE_DAC_STATE,
            AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES,
            AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES,
            AdapterOperation.VERIFY_DAC_RELEASED,
            AdapterOperation.RESTORE_EXACT_SNAPSHOT,
            AdapterOperation.RELOAD_SYSTEMD,
            AdapterOperation.RESTORE_MIXER_STATE,
            AdapterOperation.RESTORE_SERVICE_STATE,
            AdapterOperation.VERIFY_EXACT_ROLLBACK,
            AdapterOperation.WRITE_COMMIT_MANIFEST,
            AdapterOperation.RELEASE_PRODUCTION_LOCK,
        )
        self.assertEqual(operations, expected)
        self.assertIs(program.action, TransactionAction.EXPLICIT_UNINSTALL)
        self.assertIs(
            program.snapshot_source,
            programs.SnapshotSource.COMMITTED_INSTALLATION_AUTHORITATIVE,
        )
        self.assertIs(
            program.terminal_success_operation,
            AdapterOperation.WRITE_COMMIT_MANIFEST,
        )
        self.assertFalse(hasattr(AdapterOperation, "EXPLICIT_UNINSTALL"))
        self.assertNotIn(AdapterOperation.SELECT_DIRECT_FAILBACK_ROUTE, operations)
        self.assertNotIn(AdapterOperation.SELECT_SPLIT_BUS_ROUTE, operations)
        self.assertLess(
            operations.index(AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES),
            operations.index(AdapterOperation.RESTORE_EXACT_SNAPSHOT),
        )
        self.assertLess(
            operations.index(AdapterOperation.VERIFY_EXACT_ROLLBACK),
            operations.index(AdapterOperation.WRITE_COMMIT_MANIFEST),
        )

    def test_program_snapshot_is_static_and_complete(self) -> None:
        snapshot = programs.program_snapshot()
        self.assertEqual(len(snapshot), 4)
        self.assertEqual(
            tuple(row[0] for row in snapshot),
            tuple(name.value for name in programs.ProgramName),
        )
        for row, program in zip(snapshot, programs.PROGRAMS, strict=True):
            self.assertEqual(row[1], program.action.value)
            self.assertEqual(row[2], program.entry_lock_state.value)
            self.assertEqual(row[3], program.terminal_success_operation.value)
            self.assertEqual(
                row[4].split(","),
                [step.operation.value for step in program.steps],
            )

    def test_structural_guards_reject_unsafe_program_shapes(self) -> None:
        release = programs.OperationStep(
            order=10,
            phase=programs.ProgramPhase.COMPLETION,
            operation=AdapterOperation.RELEASE_PRODUCTION_LOCK,
            changes_managed_audio_state=False,
            lock_required=True,
            detail="release",
        )
        common = {
            "name": programs.ProgramName.INSTALL,
            "action": TransactionAction.INSTALL,
            "entry_lock_state": programs.EntryLockState.UNHELD,
            "snapshot_source": programs.SnapshotSource.FRESH_AUTHORITATIVE,
            "before_mutation_failure": programs.FailureDisposition.ABORT_RELEASE_LOCK,
            "after_mutation_failure": programs.FailureDisposition.AUTOMATIC_EXACT_ROLLBACK,
            "terminal_success_operation": AdapterOperation.WRITE_COMMIT_MANIFEST,
            "after_terminal_success_failure": programs.FailureDisposition.FAIL_CLOSED_RETAIN_LOCK,
        }
        with self.assertRaises(ValueError):
            programs.OperationProgram(steps=(release,), **common)

        acquire = programs.OperationStep(
            order=10,
            phase=programs.ProgramPhase.LOCK,
            operation=AdapterOperation.ACQUIRE_PRODUCTION_LOCK,
            changes_managed_audio_state=False,
            lock_required=False,
            detail="acquire",
        )
        terminal = programs.OperationStep(
            order=20,
            phase=programs.ProgramPhase.VALIDATION,
            operation=AdapterOperation.VERIFY_EXACT_ROLLBACK,
            changes_managed_audio_state=False,
            lock_required=True,
            detail="verify",
        )
        release_30 = programs.OperationStep(
            order=30,
            phase=programs.ProgramPhase.COMPLETION,
            operation=AdapterOperation.RELEASE_PRODUCTION_LOCK,
            changes_managed_audio_state=False,
            lock_required=True,
            detail="release",
        )
        with self.assertRaises(ValueError):
            programs.OperationProgram(
                name=programs.ProgramName.AUTOMATIC_EXACT_ROLLBACK,
                action=TransactionAction.EXACT_ROLLBACK,
                entry_lock_state=programs.EntryLockState.HELD,
                snapshot_source=programs.SnapshotSource.ACTIVE_TRANSACTION_AUTHORITATIVE,
                before_mutation_failure=programs.FailureDisposition.FAIL_CLOSED_RETAIN_LOCK,
                after_mutation_failure=programs.FailureDisposition.FAIL_CLOSED_RETAIN_LOCK,
                terminal_success_operation=AdapterOperation.VERIFY_EXACT_ROLLBACK,
                after_terminal_success_failure=programs.FailureDisposition.FAIL_CLOSED_RETAIN_LOCK,
                steps=(acquire, terminal, release_30),
            )

        late_terminal = programs.OperationStep(
            order=20,
            phase=programs.ProgramPhase.COMMIT,
            operation=AdapterOperation.WRITE_COMMIT_MANIFEST,
            changes_managed_audio_state=True,
            lock_required=True,
            detail="commit",
        )
        extra = programs.OperationStep(
            order=30,
            phase=programs.ProgramPhase.VALIDATION,
            operation=AdapterOperation.VERIFY_DASHBOARD_HEALTH,
            changes_managed_audio_state=False,
            lock_required=True,
            detail="too late",
        )
        release_40 = programs.OperationStep(
            order=40,
            phase=programs.ProgramPhase.COMPLETION,
            operation=AdapterOperation.RELEASE_PRODUCTION_LOCK,
            changes_managed_audio_state=False,
            lock_required=True,
            detail="release",
        )
        with self.assertRaises(ValueError):
            programs.OperationProgram(
                steps=(acquire, late_terminal, extra, release_40),
                **common,
            )


if __name__ == "__main__":
    unittest.main()
