from __future__ import annotations

import ast
import unittest
from collections import Counter
from dataclasses import FrozenInstanceError, dataclass
from enum import Enum
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/stage_c_transaction/activation_commit_executor_v7.py"

from scripts.stage_c_transaction.activation_commit_executor_v7 import (
    ActivationExecutionContextV7,
    ActivationExecutionOutcomeV7,
    ApprovalKnowledgeV7,
    execute_activation_commit_v7,
)
from scripts.stage_c_transaction.activation_commit_program_v7 import (
    ACTIVATION_EXACT_ROLLBACK_V7,
    ACTIVATION_INSTALL_SUFFIX_V7,
    PROMOTE_COMMITTED_APPROVAL,
    PUBLISH_TEMPORARY_APPROVAL,
    RELEASE_PRODUCTION_LOCK,
    REMOVE_TEMPORARY_APPROVAL,
    RUN_FINITE_MUSIC_PROBE,
    STOP_CAPTURED_APPLICATION_SERVICES,
    VERIFY_DASHBOARD_HEALTH,
)
from scripts.stage_c_transaction.production_adapter_contract import (
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    AuthoritativeTransaction,
    MixerSnapshot,
    PackageFingerprint,
    ServiceActiveState,
    ServiceEnableState,
    ServiceLoadState,
    ServiceSnapshot,
    ServiceState,
    ServiceUnit,
    SnapshotIdentity,
    TransactionAction,
    TransactionIdentity,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v7 import (
    ACTIVATION_APPROVAL_PATH,
    COMMITTED_APPROVAL_PHASE,
    PRODUCTION_LOCK_PATH,
    TEMPORARY_APPROVAL_PHASE,
    ActivationApprovalAdapterResult,
    ActivationApprovalLifecycleOperation,
    ActivationApprovalRemovalReceipt,
    BlockedProductionAdapterV7,
    CommittedActivationApprovalReceipt,
    ProductionLockLeaseBindingReceipt,
    ProductionOperationV7,
    TemporaryActivationApprovalReceipt,
)


class FailureMode(str, Enum):
    FAIL = "fail"
    RAISE = "raise"
    WRONG_OPERATION = "wrong-operation"


@dataclass(frozen=True)
class FailurePoint:
    operation: ProductionOperationV7
    occurrence: int = 1
    mode: FailureMode = FailureMode.FAIL

    def __post_init__(self) -> None:
        if self.occurrence <= 0:
            raise ValueError("failure occurrence must be positive")


def _context() -> ActivationExecutionContextV7:
    package = PackageFingerprint("a" * 64)
    transaction = AuthoritativeTransaction(
        transaction=TransactionIdentity("stage-c21-executor-test"),
        snapshot=SnapshotIdentity("stage-c21-executor-test-snapshot"),
        action=TransactionAction.INSTALL,
        package=package,
    )
    services = ServiceSnapshot(
        tuple(
            ServiceState(
                unit=unit,
                load=ServiceLoadState.LOADED,
                active=ServiceActiveState.ACTIVE,
                enabled=ServiceEnableState.ENABLED,
            )
            for unit in ServiceUnit
        )
    )
    return ActivationExecutionContextV7(
        transaction=transaction,
        services=services,
        mixer=MixerSnapshot(70, 70, 65, 80),
    )


class RecordingTerminalAdapterV7(BlockedProductionAdapterV7):
    def __init__(
        self,
        context: ActivationExecutionContextV7,
        failures: tuple[FailurePoint, ...] = (),
    ) -> None:
        if len({(item.operation, item.occurrence) for item in failures}) != len(failures):
            raise ValueError("duplicate failure point")
        self.context = context
        self.failures = failures
        self.occurrences: Counter[ProductionOperationV7] = Counter()
        self.attempted_operations: list[ProductionOperationV7] = []
        self.lock_held = True
        self.lease_id = "stage-c21-test-lease"
        self.temporary_sha256 = "1" * 64
        self.committed_sha256 = "2" * 64
        self.route_sha256 = "3" * 64
        self.manifest_sha256 = "4" * 64

    def _failure_mode(self, operation: ProductionOperationV7) -> FailureMode | None:
        self.attempted_operations.append(operation)
        self.occurrences[operation] += 1
        occurrence = self.occurrences[operation]
        for failure in self.failures:
            if failure.operation is operation and failure.occurrence == occurrence:
                return failure.mode
        return None

    def _ordinary(self, operation: AdapterOperation) -> AdapterResult[None]:
        mode = self._failure_mode(operation)
        if mode is FailureMode.RAISE:
            raise RuntimeError(f"injected exception: {operation.value}")
        if mode is FailureMode.WRONG_OPERATION:
            return AdapterResult(
                operation=AdapterOperation.VERIFY_DAC_RELEASED,
                status=AdapterStatus.PASS,
                detail="injected wrong operation receipt",
            )
        if mode is FailureMode.FAIL:
            return AdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=f"injected explicit failure: {operation.value}",
            )
        if operation is RELEASE_PRODUCTION_LOCK:
            self.lock_held = False
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail=f"recorded pass: {operation.value}",
        )

    def _approval(
        self,
        operation: ActivationApprovalLifecycleOperation,
    ) -> ActivationApprovalAdapterResult:
        mode = self._failure_mode(operation)
        if mode is FailureMode.RAISE:
            raise RuntimeError(f"injected exception: {operation.value}")
        if mode is FailureMode.FAIL:
            return ActivationApprovalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=f"injected explicit failure: {operation.value}",
            )
        transaction = self.context.transaction.transaction
        package = self.context.transaction.package
        if operation is ActivationApprovalLifecycleOperation.BIND_PRODUCTION_LOCK_LEASE:
            payload = ProductionLockLeaseBindingReceipt(
                transaction=transaction,
                lock_path=PRODUCTION_LOCK_PATH,
                lease_id=self.lease_id,
                lock_device=1,
                lock_inode=2,
                transaction_owns_lock=True,
                canonical_content_written=True,
                exact_inode_verified=True,
                external_observer_ready=True,
            )
        elif operation is ActivationApprovalLifecycleOperation.PUBLISH_TEMPORARY_ACTIVATION_APPROVAL:
            payload = TemporaryActivationApprovalReceipt(
                transaction=transaction,
                approval_path=ACTIVATION_APPROVAL_PATH,
                phase=TEMPORARY_APPROVAL_PHASE,
                package=package,
                lock_lease_id=self.lease_id,
                record_sha256=self.temporary_sha256,
                active_route_sha256=self.route_sha256,
                boot_eligible=False,
                atomically_published=True,
                exact_record_verified=True,
            )
        elif operation is ActivationApprovalLifecycleOperation.REMOVE_TEMPORARY_ACTIVATION_APPROVAL:
            payload = ActivationApprovalRemovalReceipt(
                transaction=transaction,
                approval_path=ACTIVATION_APPROVAL_PATH,
                expected_record_sha256=self.temporary_sha256,
                exact_record_removed=True,
                approval_absent=True,
                rollback_owned=True,
            )
        elif operation is ActivationApprovalLifecycleOperation.PROMOTE_COMMITTED_ACTIVATION_APPROVAL:
            payload = CommittedActivationApprovalReceipt(
                transaction=transaction,
                approval_path=ACTIVATION_APPROVAL_PATH,
                phase=COMMITTED_APPROVAL_PHASE,
                package=package,
                lock_lease_id=self.lease_id,
                temporary_record_sha256=self.temporary_sha256,
                committed_record_sha256=self.committed_sha256,
                commit_manifest_sha256=self.manifest_sha256,
                boot_eligible=True,
                atomically_promoted=True,
                exact_record_verified=True,
            )
        else:
            raise AssertionError(operation)
        return ActivationApprovalAdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail=f"recorded pass: {operation.value}",
            payload=payload,
        )

    def bind_production_lock_lease(self, transaction: TransactionIdentity):
        self.assert_equal_transaction(transaction)
        return self._approval(
            ActivationApprovalLifecycleOperation.BIND_PRODUCTION_LOCK_LEASE
        )

    def publish_temporary_activation_approval(self, transaction: TransactionIdentity):
        self.assert_equal_transaction(transaction)
        return self._approval(
            ActivationApprovalLifecycleOperation.PUBLISH_TEMPORARY_ACTIVATION_APPROVAL
        )

    def remove_temporary_activation_approval(self, transaction: TransactionIdentity):
        self.assert_equal_transaction(transaction)
        return self._approval(
            ActivationApprovalLifecycleOperation.REMOVE_TEMPORARY_ACTIVATION_APPROVAL
        )

    def promote_committed_activation_approval(self, transaction: TransactionIdentity):
        self.assert_equal_transaction(transaction)
        return self._approval(
            ActivationApprovalLifecycleOperation.PROMOTE_COMMITTED_ACTIVATION_APPROVAL
        )

    def assert_equal_transaction(self, transaction: TransactionIdentity) -> None:
        if transaction != self.context.transaction.transaction:
            raise AssertionError("substituted transaction")

    def start_managed_stage_c_services(self, transaction: TransactionIdentity):
        self.assert_equal_transaction(transaction)
        return self._ordinary(AdapterOperation.START_MANAGED_STAGE_C_SERVICES)

    def verify_split_bus_health(self, transaction: TransactionIdentity):
        self.assert_equal_transaction(transaction)
        return self._ordinary(AdapterOperation.VERIFY_SPLIT_BUS_HEALTH)

    def run_finite_music_probe(self, transaction: TransactionIdentity):
        self.assert_equal_transaction(transaction)
        return self._ordinary(AdapterOperation.RUN_FINITE_MUSIC_PROBE)

    def run_finite_alarm_probe(self, transaction: TransactionIdentity):
        self.assert_equal_transaction(transaction)
        return self._ordinary(AdapterOperation.RUN_FINITE_ALARM_PROBE)

    def restore_captured_application_services(
        self,
        transaction: TransactionIdentity,
        services: ServiceSnapshot,
    ):
        self.assert_equal_transaction(transaction)
        if services != self.context.services:
            raise AssertionError("substituted service snapshot")
        return self._ordinary(AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES)

    def verify_dashboard_health(self, transaction: TransactionIdentity):
        self.assert_equal_transaction(transaction)
        return self._ordinary(AdapterOperation.VERIFY_DASHBOARD_HEALTH)

    def stop_captured_application_services(
        self,
        transaction: TransactionIdentity,
        services: ServiceSnapshot,
    ):
        self.assert_equal_transaction(transaction)
        if services != self.context.services:
            raise AssertionError("substituted service snapshot")
        return self._ordinary(AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES)

    def stop_managed_stage_c_services(self, transaction: TransactionIdentity):
        self.assert_equal_transaction(transaction)
        return self._ordinary(AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES)

    def verify_dac_released(self, transaction: TransactionIdentity):
        self.assert_equal_transaction(transaction)
        return self._ordinary(AdapterOperation.VERIFY_DAC_RELEASED)

    def restore_exact_snapshot(
        self,
        transaction: TransactionIdentity,
        snapshot: SnapshotIdentity,
    ):
        self.assert_equal_transaction(transaction)
        if snapshot != self.context.transaction.snapshot:
            raise AssertionError("substituted snapshot")
        return self._ordinary(AdapterOperation.RESTORE_EXACT_SNAPSHOT)

    def reload_systemd(self, transaction: TransactionIdentity):
        self.assert_equal_transaction(transaction)
        return self._ordinary(AdapterOperation.RELOAD_SYSTEMD)

    def restore_mixer_state(
        self,
        transaction: TransactionIdentity,
        mixer: MixerSnapshot,
    ):
        self.assert_equal_transaction(transaction)
        if mixer != self.context.mixer:
            raise AssertionError("substituted mixer snapshot")
        return self._ordinary(AdapterOperation.RESTORE_MIXER_STATE)

    def restore_service_state(
        self,
        transaction: TransactionIdentity,
        services: ServiceSnapshot,
    ):
        self.assert_equal_transaction(transaction)
        if services != self.context.services:
            raise AssertionError("substituted service snapshot")
        return self._ordinary(AdapterOperation.RESTORE_SERVICE_STATE)

    def verify_exact_rollback(
        self,
        transaction: TransactionIdentity,
        snapshot: SnapshotIdentity,
    ):
        self.assert_equal_transaction(transaction)
        if snapshot != self.context.transaction.snapshot:
            raise AssertionError("substituted snapshot")
        return self._ordinary(AdapterOperation.VERIFY_EXACT_ROLLBACK)

    def release_production_lock(self):
        return self._ordinary(AdapterOperation.RELEASE_PRODUCTION_LOCK)


class StageCActivationCommitExecutorV7Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = _context()
        self.source = MODULE.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    @staticmethod
    def _failure_for_step(index: int, mode: FailureMode = FailureMode.FAIL) -> FailurePoint:
        operations = [step.operation for step in ACTIVATION_INSTALL_SUFFIX_V7]
        operation = operations[index]
        occurrence = operations[: index + 1].count(operation)
        return FailurePoint(operation, occurrence, mode)

    def test_success_executes_exact_suffix_and_releases_committed_lock(self) -> None:
        adapter = RecordingTerminalAdapterV7(self.context)
        result = execute_activation_commit_v7(adapter, self.context)
        self.assertIs(result.outcome, ActivationExecutionOutcomeV7.COMMITTED)
        self.assertIs(result.approval, ApprovalKnowledgeV7.COMMITTED)
        self.assertFalse(result.lock_held)
        self.assertFalse(result.exact_rollback_verified)
        self.assertEqual(
            tuple(record.operation for record in result.records),
            tuple(step.operation for step in ACTIVATION_INSTALL_SUFFIX_V7),
        )
        self.assertTrue(all(record.status is AdapterStatus.PASS for record in result.records))

    def test_every_explicit_preterminal_failure_runs_complete_exact_rollback(self) -> None:
        for index, step in enumerate(ACTIVATION_INSTALL_SUFFIX_V7[:-1]):
            with self.subTest(index=index, operation=step.operation.value):
                adapter = RecordingTerminalAdapterV7(
                    self.context,
                    (self._failure_for_step(index),),
                )
                result = execute_activation_commit_v7(adapter, self.context)
                self.assertIs(
                    result.outcome,
                    ActivationExecutionOutcomeV7.EXACTLY_ROLLED_BACK,
                )
                self.assertIs(result.failure_operation, step.operation)
                self.assertIsNone(result.rollback_failure_operation)
                self.assertIs(result.approval, ApprovalKnowledgeV7.ABSENT)
                self.assertTrue(result.exact_rollback_verified)
                self.assertFalse(result.lock_held)
                rollback_operations = tuple(
                    record.operation
                    for record in result.records
                    if record.phase.value == "exact-rollback"
                )
                expected = tuple(
                    rollback_step.operation
                    for rollback_step in ACTIVATION_EXACT_ROLLBACK_V7
                    if not (
                        rollback_step.operation is REMOVE_TEMPORARY_APPROVAL
                        and index <= 1
                    )
                )
                self.assertEqual(rollback_operations, expected)

    def test_postcommit_release_failure_recovers_forward_without_rollback(self) -> None:
        index = len(ACTIVATION_INSTALL_SUFFIX_V7) - 1
        adapter = RecordingTerminalAdapterV7(
            self.context,
            (self._failure_for_step(index),),
        )
        result = execute_activation_commit_v7(adapter, self.context)
        self.assertIs(
            result.outcome,
            ActivationExecutionOutcomeV7.FORWARD_RECOVERY_REQUIRED,
        )
        self.assertIs(result.failure_operation, RELEASE_PRODUCTION_LOCK)
        self.assertIs(result.approval, ApprovalKnowledgeV7.COMMITTED)
        self.assertTrue(result.lock_held)
        self.assertFalse(
            any(record.phase.value == "exact-rollback" for record in result.records)
        )

    def test_temporary_publication_exception_is_indeterminate_and_fails_closed(self) -> None:
        adapter = RecordingTerminalAdapterV7(
            self.context,
            (FailurePoint(PUBLISH_TEMPORARY_APPROVAL, mode=FailureMode.RAISE),),
        )
        result = execute_activation_commit_v7(adapter, self.context)
        self.assertIs(
            result.outcome,
            ActivationExecutionOutcomeV7.FAIL_CLOSED_LOCK_RETAINED,
        )
        self.assertIs(result.approval, ApprovalKnowledgeV7.INDETERMINATE)
        self.assertTrue(result.lock_held)
        self.assertIsNone(result.rollback_failure_operation)
        self.assertFalse(
            any(record.phase.value == "exact-rollback" for record in result.records)
        )

    def test_terminal_publication_exception_never_rolls_back_unknown_commit(self) -> None:
        adapter = RecordingTerminalAdapterV7(
            self.context,
            (FailurePoint(PROMOTE_COMMITTED_APPROVAL, mode=FailureMode.RAISE),),
        )
        result = execute_activation_commit_v7(adapter, self.context)
        self.assertIs(
            result.outcome,
            ActivationExecutionOutcomeV7.FAIL_CLOSED_LOCK_RETAINED,
        )
        self.assertIs(result.approval, ApprovalKnowledgeV7.INDETERMINATE)
        self.assertTrue(result.lock_held)
        self.assertIsNone(result.rollback_failure_operation)
        self.assertFalse(
            any(record.phase.value == "exact-rollback" for record in result.records)
        )

    def test_ordinary_exception_after_temporary_publication_rolls_back(self) -> None:
        adapter = RecordingTerminalAdapterV7(
            self.context,
            (FailurePoint(RUN_FINITE_MUSIC_PROBE, mode=FailureMode.RAISE),),
        )
        result = execute_activation_commit_v7(adapter, self.context)
        self.assertIs(
            result.outcome,
            ActivationExecutionOutcomeV7.EXACTLY_ROLLED_BACK,
        )
        self.assertIs(result.failure_operation, RUN_FINITE_MUSIC_PROBE)
        self.assertTrue(
            any(record.operation is REMOVE_TEMPORARY_APPROVAL for record in result.records)
        )

    def test_wrong_operation_receipt_is_an_adapter_failure_and_rolls_back(self) -> None:
        adapter = RecordingTerminalAdapterV7(
            self.context,
            (FailurePoint(RUN_FINITE_MUSIC_PROBE, mode=FailureMode.WRONG_OPERATION),),
        )
        result = execute_activation_commit_v7(adapter, self.context)
        self.assertIs(
            result.outcome,
            ActivationExecutionOutcomeV7.EXACTLY_ROLLED_BACK,
        )
        failure_record = next(
            record
            for record in result.records
            if record.operation is RUN_FINITE_MUSIC_PROBE
        )
        self.assertEqual(failure_record.exception_type, "ValueError")

    def test_every_rollback_failure_retains_lock_and_never_commits(self) -> None:
        for rollback_step in ACTIVATION_EXACT_ROLLBACK_V7:
            with self.subTest(operation=rollback_step.operation.value):
                adapter = RecordingTerminalAdapterV7(
                    self.context,
                    (
                        FailurePoint(VERIFY_DASHBOARD_HEALTH),
                        FailurePoint(rollback_step.operation),
                    ),
                )
                result = execute_activation_commit_v7(adapter, self.context)
                self.assertIs(
                    result.outcome,
                    ActivationExecutionOutcomeV7.FAIL_CLOSED_LOCK_RETAINED,
                )
                self.assertIs(result.failure_operation, VERIFY_DASHBOARD_HEALTH)
                self.assertIs(
                    result.rollback_failure_operation,
                    rollback_step.operation,
                )
                self.assertTrue(result.lock_held)
                self.assertIsNot(result.approval, ApprovalKnowledgeV7.COMMITTED)

    def test_blocked_adapter_cannot_create_a_hidden_activation_path(self) -> None:
        result = execute_activation_commit_v7(
            BlockedProductionAdapterV7(),
            self.context,
        )
        self.assertIs(
            result.outcome,
            ActivationExecutionOutcomeV7.FAIL_CLOSED_LOCK_RETAINED,
        )
        self.assertIs(result.failure_operation, ACTIVATION_INSTALL_SUFFIX_V7[0].operation)
        self.assertIs(result.rollback_failure_operation, STOP_CAPTURED_APPLICATION_SERVICES)
        self.assertTrue(result.lock_held)

    def test_non_adapter_and_non_install_context_are_rejected(self) -> None:
        with self.assertRaises(TypeError):
            execute_activation_commit_v7(object(), self.context)  # type: ignore[arg-type]
        transaction = AuthoritativeTransaction(
            transaction=TransactionIdentity("not-install"),
            snapshot=SnapshotIdentity("not-install-snapshot"),
            action=TransactionAction.EXACT_ROLLBACK,
            package=PackageFingerprint("b" * 64),
        )
        with self.assertRaises(ValueError):
            ActivationExecutionContextV7(
                transaction=transaction,
                services=self.context.services,
                mixer=self.context.mixer,
            )

    def test_results_and_records_are_frozen(self) -> None:
        result = execute_activation_commit_v7(
            RecordingTerminalAdapterV7(self.context),
            self.context,
        )
        with self.assertRaises(FrozenInstanceError):
            result.lock_held = True  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            result.records[0].detail = "changed"  # type: ignore[misc]

    def test_executor_has_no_host_cli_command_or_generic_lookup_boundary(self) -> None:
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
