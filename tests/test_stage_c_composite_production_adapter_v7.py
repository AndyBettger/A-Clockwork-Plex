from __future__ import annotations

import ast
import fcntl
import os
import stat
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/stage_c_transaction/composite_production_adapter_v7.py"

from scripts.stage_c_runtime_authority.approval_store import ApprovalStore
from scripts.stage_c_runtime_authority.model import (
    ActivationApprovalRecord,
    ApprovalPhase,
    RuntimeAuthorityError,
)
from scripts.stage_c_transaction.activation_commit_executor_v7 import (
    ActivationExecutionContextV7,
    ActivationExecutionOutcomeV7,
    execute_activation_commit_v7,
)
from scripts.stage_c_transaction.composite_production_adapter_v7 import (
    CompositeProductionAdapterV7,
)
from scripts.stage_c_transaction.disposable_activation_approval_adapter import (
    DisposableActivationApprovalLifecycleAdapter,
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
from scripts.stage_c_transaction.production_adapter_lifecycle_v6 import (
    BlockedProductionAdapterV6,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v7 import (
    ALL_OPERATIONS_V7,
    BlockedProductionAdapterV7,
    ProductionAdapterV7,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
HASH_E = "e" * 64
HASH_F = "f" * 64


def temporary_record(
    transaction: TransactionIdentity,
    package: PackageFingerprint,
) -> ActivationApprovalRecord:
    return ActivationApprovalRecord(
        schema_version=1,
        phase=ApprovalPhase.TEMPORARY,
        transaction_id=transaction.value,
        lock_lease_id="stage-c21-disposable-lease",
        package_fingerprint=package.sha256,
        commit_manifest_sha256=None,
        active_route_sha256=HASH_B,
        direct_route_sha256=HASH_C,
        camilladsp_config_sha256=HASH_D,
        camilladsp_binary_version="4.1.3",
        camilladsp_binary_sha256=HASH_E,
        loopback_index=7,
        loopback_id="ACP_Loopback",
        loopback_pcm_substreams=2,
        loopback_pcm_notify=1,
        dac_card="Pro",
        dac_device=0,
        sample_rate=44100,
        sample_format="S16_LE",
        period_size=1024,
        buffer_size=8192,
        created_at="2026-08-05T22:00:00Z",
        committed_at=None,
    )


def execution_context(
    transaction: TransactionIdentity,
    package: PackageFingerprint,
) -> ActivationExecutionContextV7:
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
        transaction=AuthoritativeTransaction(
            transaction=transaction,
            snapshot=SnapshotIdentity("stage-c21-composite-snapshot"),
            action=TransactionAction.INSTALL,
            package=package,
        ),
        services=services,
        mixer=MixerSnapshot(70, 70, 65, 80),
    )


class RecordingOrdinaryAdapterV6(BlockedProductionAdapterV6):
    """Receipt-only v1-v6 laboratory adapter for terminal-executor proof."""

    def __init__(
        self,
        context: ActivationExecutionContextV7,
        approval: DisposableActivationApprovalLifecycleAdapter,
        *,
        fail_at: AdapterOperation | None = None,
    ) -> None:
        self.context = context
        self.approval = approval
        self.fail_at = fail_at
        self.attempted_operations: list[AdapterOperation] = []
        self._failed = False

    def _require_transaction(self, transaction: TransactionIdentity) -> None:
        if transaction != self.context.transaction.transaction:
            raise AssertionError("ordinary adapter received a substituted transaction")

    def _result(self, operation: AdapterOperation) -> AdapterResult[None]:
        self.attempted_operations.append(operation)
        if operation is self.fail_at and not self._failed:
            self._failed = True
            return AdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=f"injected ordinary failure: {operation.value}",
            )
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail=f"recorded ordinary pass: {operation.value}",
        )

    def start_managed_stage_c_services(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        self._require_transaction(transaction)
        return self._result(AdapterOperation.START_MANAGED_STAGE_C_SERVICES)

    def verify_split_bus_health(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        self._require_transaction(transaction)
        return self._result(AdapterOperation.VERIFY_SPLIT_BUS_HEALTH)

    def run_finite_music_probe(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        self._require_transaction(transaction)
        return self._result(AdapterOperation.RUN_FINITE_MUSIC_PROBE)

    def run_finite_alarm_probe(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        self._require_transaction(transaction)
        return self._result(AdapterOperation.RUN_FINITE_ALARM_PROBE)

    def restore_captured_application_services(
        self,
        transaction: TransactionIdentity,
        services: ServiceSnapshot,
    ) -> AdapterResult[None]:
        self._require_transaction(transaction)
        if services != self.context.services:
            raise AssertionError("ordinary adapter received substituted services")
        return self._result(
            AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES
        )

    def verify_dashboard_health(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        self._require_transaction(transaction)
        result = self._result(AdapterOperation.VERIFY_DASHBOARD_HEALTH)
        if result.status is AdapterStatus.PASS:
            self.approval.record_commit_manifest_for_rehearsal(
                transaction,
                HASH_F,
            )
        return result

    def stop_captured_application_services(
        self,
        transaction: TransactionIdentity,
        services: ServiceSnapshot,
    ) -> AdapterResult[None]:
        self._require_transaction(transaction)
        if services != self.context.services:
            raise AssertionError("ordinary adapter received substituted services")
        return self._result(AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES)

    def stop_managed_stage_c_services(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        self._require_transaction(transaction)
        return self._result(AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES)

    def verify_dac_released(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        self._require_transaction(transaction)
        return self._result(AdapterOperation.VERIFY_DAC_RELEASED)

    def restore_exact_snapshot(
        self,
        transaction: TransactionIdentity,
        snapshot: SnapshotIdentity,
    ) -> AdapterResult[None]:
        self._require_transaction(transaction)
        if snapshot != self.context.transaction.snapshot:
            raise AssertionError("ordinary adapter received a substituted snapshot")
        return self._result(AdapterOperation.RESTORE_EXACT_SNAPSHOT)

    def reload_systemd(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        self._require_transaction(transaction)
        return self._result(AdapterOperation.RELOAD_SYSTEMD)

    def restore_mixer_state(
        self,
        transaction: TransactionIdentity,
        mixer: MixerSnapshot,
    ) -> AdapterResult[None]:
        self._require_transaction(transaction)
        if mixer != self.context.mixer:
            raise AssertionError("ordinary adapter received substituted mixer state")
        return self._result(AdapterOperation.RESTORE_MIXER_STATE)

    def restore_service_state(
        self,
        transaction: TransactionIdentity,
        services: ServiceSnapshot,
    ) -> AdapterResult[None]:
        self._require_transaction(transaction)
        if services != self.context.services:
            raise AssertionError("ordinary adapter received substituted services")
        return self._result(AdapterOperation.RESTORE_SERVICE_STATE)

    def verify_exact_rollback(
        self,
        transaction: TransactionIdentity,
        snapshot: SnapshotIdentity,
    ) -> AdapterResult[None]:
        self._require_transaction(transaction)
        if snapshot != self.context.transaction.snapshot:
            raise AssertionError("ordinary adapter received a substituted snapshot")
        return self._result(AdapterOperation.VERIFY_EXACT_ROLLBACK)

    def release_production_lock(self) -> AdapterResult[None]:
        self.attempted_operations.append(AdapterOperation.RELEASE_PRODUCTION_LOCK)
        self.approval.close_disposable_transaction()
        return AdapterResult(
            operation=AdapterOperation.RELEASE_PRODUCTION_LOCK,
            status=AdapterStatus.PASS,
            detail="exact disposable transaction lock released",
        )


class StageCCompositeProductionAdapterV7Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = MODULE.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)
        self.transaction = TransactionIdentity("stage-c21-composite-transaction")
        self.package = PackageFingerprint(HASH_A)
        self.context = execution_context(self.transaction, self.package)

    def _new_approval(
        self,
    ) -> DisposableActivationApprovalLifecycleAdapter:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        root.chmod(0o700)
        self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
        approval = DisposableActivationApprovalLifecycleAdapter(
            root,
            transaction=self.transaction,
            package=self.package,
            temporary_approval=temporary_record(
                self.transaction,
                self.package,
            ),
            timestamp_factory=lambda: "2026-08-05T22:01:00Z",
        )
        self.addCleanup(self._force_cleanup, approval)
        return approval

    @staticmethod
    def _force_cleanup(
        approval: DisposableActivationApprovalLifecycleAdapter,
    ) -> None:
        if approval.closed:
            return
        approval_path = approval.state_root / "activation-approved"
        try:
            approval_path.unlink()
        except FileNotFoundError:
            pass
        try:
            approval.close_disposable_transaction()
            return
        except BaseException:
            pass
        try:
            descriptor = os.fstat(approval._lock_fd)
            path_info = approval.lock_path.lstat()
            if (
                descriptor.st_dev == path_info.st_dev
                and descriptor.st_ino == path_info.st_ino
            ):
                approval.lock_path.unlink()
        except OSError:
            pass
        try:
            fcntl.flock(approval._lock_fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(approval._lock_fd)
        except OSError:
            pass
        approval._closed = True

    def test_composite_exposes_the_exact_forty_two_method_surface(self) -> None:
        expected = {
            operation.value.replace("-", "_")
            for operation in ALL_OPERATIONS_V7
        }
        observed = {
            name
            for name, value in CompositeProductionAdapterV7.__dict__.items()
            if not name.startswith("_") and callable(value)
        }
        self.assertEqual(len(expected), 42)
        self.assertEqual(observed, expected)

    def test_delegates_are_runtime_checked_and_composite_satisfies_v7(self) -> None:
        approval = self._new_approval()
        ordinary = RecordingOrdinaryAdapterV6(self.context, approval)
        composite = CompositeProductionAdapterV7(ordinary, approval)
        self.assertIsInstance(composite, ProductionAdapterV7)
        with self.assertRaises(TypeError):
            CompositeProductionAdapterV7(object(), approval)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            CompositeProductionAdapterV7(ordinary, object())  # type: ignore[arg-type]

    def test_ordinary_and_approval_operations_have_separate_authorities(self) -> None:
        approval = self._new_approval()
        ordinary = RecordingOrdinaryAdapterV6(self.context, approval)
        composite = CompositeProductionAdapterV7(ordinary, approval)

        ordinary_result = composite.start_managed_stage_c_services(self.transaction)
        self.assertIs(
            ordinary_result.operation,
            AdapterOperation.START_MANAGED_STAGE_C_SERVICES,
        )
        self.assertEqual(
            ordinary.attempted_operations,
            [AdapterOperation.START_MANAGED_STAGE_C_SERVICES],
        )
        self.assertFalse(approval.lease_bound)

        approval_result = composite.bind_production_lock_lease(self.transaction)
        self.assertEqual(
            approval_result.operation.value,
            "bind-production-lock-lease",
        )
        self.assertTrue(approval.lease_bound)
        self.assertEqual(
            ordinary.attempted_operations,
            [AdapterOperation.START_MANAGED_STAGE_C_SERVICES],
        )
        approval.close_disposable_transaction()

    def test_full_executor_commits_real_disposable_approval_and_exact_lock(self) -> None:
        approval = self._new_approval()
        ordinary = RecordingOrdinaryAdapterV6(self.context, approval)
        composite = CompositeProductionAdapterV7(ordinary, approval)
        lock_path = approval.lock_path

        result = execute_activation_commit_v7(composite, self.context)

        self.assertIs(result.outcome, ActivationExecutionOutcomeV7.COMMITTED)
        self.assertFalse(result.lock_held)
        self.assertTrue(approval.closed)
        self.assertFalse(lock_path.exists())
        committed = ApprovalStore(approval.state_root).read()
        self.assertIs(committed.phase, ApprovalPhase.COMMITTED)
        self.assertEqual(committed.transaction_id, self.transaction.value)
        self.assertEqual(committed.package_fingerprint, self.package.sha256)
        self.assertEqual(committed.commit_manifest_sha256, HASH_F)
        self.assertEqual(committed.committed_at, "2026-08-05T22:01:00Z")
        self.assertNotIn(AdapterOperation.WRITE_COMMIT_MANIFEST, ordinary.attempted_operations)

    def test_full_executor_removes_temporary_approval_and_unlocks_on_failure(self) -> None:
        approval = self._new_approval()
        ordinary = RecordingOrdinaryAdapterV6(
            self.context,
            approval,
            fail_at=AdapterOperation.RUN_FINITE_MUSIC_PROBE,
        )
        composite = CompositeProductionAdapterV7(ordinary, approval)
        lock_path = approval.lock_path

        result = execute_activation_commit_v7(composite, self.context)

        self.assertIs(
            result.outcome,
            ActivationExecutionOutcomeV7.EXACTLY_ROLLED_BACK,
        )
        self.assertFalse(result.lock_held)
        self.assertTrue(result.exact_rollback_verified)
        self.assertTrue(approval.closed)
        self.assertFalse(lock_path.exists())
        with self.assertRaisesRegex(RuntimeAuthorityError, "absent"):
            ApprovalStore(approval.state_root).read()
        self.assertIn(
            AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES,
            ordinary.attempted_operations,
        )
        self.assertIn(
            AdapterOperation.VERIFY_EXACT_ROLLBACK,
            ordinary.attempted_operations,
        )
        self.assertIs(
            ordinary.attempted_operations[-1],
            AdapterOperation.RELEASE_PRODUCTION_LOCK,
        )

    def test_blocked_approval_delegate_cannot_create_a_hidden_v7_path(self) -> None:
        real_approval = self._new_approval()
        ordinary = RecordingOrdinaryAdapterV6(self.context, real_approval)
        composite = CompositeProductionAdapterV7(
            ordinary,
            BlockedProductionAdapterV7(),
        )

        result = execute_activation_commit_v7(composite, self.context)

        self.assertIs(
            result.outcome,
            ActivationExecutionOutcomeV7.EXACTLY_ROLLED_BACK,
        )
        self.assertEqual(result.failure_operation.value, "bind-production-lock-lease")
        self.assertTrue(real_approval.closed)
        self.assertFalse(real_approval.lock_path.exists())

    def test_composite_is_frozen(self) -> None:
        approval = self._new_approval()
        ordinary = RecordingOrdinaryAdapterV6(self.context, approval)
        composite = CompositeProductionAdapterV7(ordinary, approval)
        with self.assertRaises(FrozenInstanceError):
            composite.ordinary = object()  # type: ignore[misc]

    def test_module_has_no_host_cli_reflection_or_generic_dispatch_boundary(self) -> None:
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
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    self.assertNotIn(
                        node.func.id,
                        {"eval", "exec", "getattr", "setattr"},
                    )
                elif isinstance(node.func, ast.Attribute):
                    self.assertNotIn(
                        node.func.attr,
                        {"dispatch", "__getattr__", "__getattribute__"},
                    )
        for forbidden_text in (
            "systemctl",
            "aplay",
            "amixer",
            "/dev/snd",
            "/etc/alsa",
            "shell=True",
            "__getattr__",
        ):
            self.assertNotIn(forbidden_text, self.source)


if __name__ == "__main__":
    unittest.main()
