from __future__ import annotations

import ast
import errno
import fcntl
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
FACADE_MODULE = ROOT / "scripts/stage_c_transaction/disposable_approval_lifecycle_facade_v7.py"

from scripts.stage_c_transaction import (  # noqa: E402
    disposable_approval_lifecycle_facade_v7 as facade_module,
)
from scripts.stage_c_transaction.approval_authority_binding_v7 import (  # noqa: E402
    ApprovalAuthorityBindingV7,
    ApprovalHardwareContractV7,
)
from scripts.stage_c_transaction.approval_record_plan_v7 import (  # noqa: E402
    ApprovalObservedStateV7,
    plan_committed_approval_v7,
    plan_temporary_approval_v7,
)
from scripts.stage_c_transaction.disposable_approval_lifecycle_facade_v7 import (  # noqa: E402
    DisposableApprovalLifecycleEventV7,
    DisposableApprovalLifecycleFacadeV7,
    DisposableApprovalLifecycleOperationV7,
    DisposableApprovalLifecycleOrderError,
    DisposableApprovalLifecyclePhaseV7,
)
from scripts.stage_c_transaction.disposable_approval_root_v7 import (  # noqa: E402
    DisposableApprovalRootV7,
)
from scripts.stage_c_transaction.disposable_c20_lock_owner_v7 import (  # noqa: E402
    DisposableC20LockOwnerV7,
)
from scripts.stage_c_transaction.disposable_canonical_lease_binder_v7 import (  # noqa: E402
    DisposableCanonicalLeaseBindingResultV7,
    DisposableLeaseBindingDispositionV7,
)
from scripts.stage_c_transaction.disposable_committed_approval_promoter_v7 import (  # noqa: E402
    DisposableCommittedApprovalPromotionResultV7,
    DisposableCommittedPromotionDispositionV7,
)
from scripts.stage_c_transaction.disposable_temporary_approval_publisher_v7 import (  # noqa: E402
    DisposableTemporaryApprovalPublicationResultV7,
    DisposableTemporaryPublicationDispositionV7,
)
from scripts.stage_c_transaction.disposable_temporary_approval_remover_v7 import (  # noqa: E402
    DisposableTemporaryApprovalRemovalResultV7,
    DisposableTemporaryRemovalDispositionV7,
)
from scripts.stage_c_transaction.production_adapter_contract import (  # noqa: E402
    AUTHORITATIVE_TRANSACTION_ROOT,
    AdapterStatus,
    PackageFingerprint,
    SnapshotIdentity,
    TransactionIdentity,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v7 import (  # noqa: E402
    ALL_OPERATIONS_V7,
    BlockedProductionAdapterV7,
    ProductionActivationApprovalAdapterBlocked,
)
from scripts.stage_c_transaction.snapshot_core import CURRENT_ALSA_DESTINATION  # noqa: E402


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
HASH_E = "e" * 64
HASH_F = "f" * 64


class StageCDisposableApprovalLifecycleFacadeV7Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = FACADE_MODULE.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    def _plans(self, owner: DisposableC20LockOwnerV7):
        observed = owner.observe()
        self.assertIs(observed.status, AdapterStatus.PASS)
        assert observed.payload is not None
        package = PackageFingerprint(HASH_A)
        hardware = ApprovalHardwareContractV7(
            package=package,
            split_route_sha256=HASH_B,
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
        )
        transaction = TransactionIdentity("stage-c21-disposable-lifecycle")
        binding = ApprovalAuthorityBindingV7(
            transaction=transaction,
            snapshot=SnapshotIdentity("stage-c21-disposable-lifecycle-snapshot"),
            package=package,
            production_lock_path=str(owner.lock_path),
            lock_lease_id=owner.lease_id,
            lock_device=observed.payload.device,
            lock_inode=observed.payload.inode,
            authoritative_transaction_path=str(
                Path(AUTHORITATIVE_TRANSACTION_ROOT) / transaction.value
            ),
            transaction_device=201,
            transaction_inode=202,
            selected_route_path=CURRENT_ALSA_DESTINATION,
            selected_route_device=301,
            selected_route_inode=302,
            selected_route_sha256=HASH_B,
            hardware=hardware,
            source_snapshot_complete=True,
            source_split_route_selected=True,
            source_exact_lock_owned=True,
            source_exact_transaction_verified=True,
        )
        temporary = plan_temporary_approval_v7(
            binding,
            created_at="2026-08-06T02:20:00Z",
        )
        committed = plan_committed_approval_v7(
            temporary,
            commit_manifest_sha256=HASH_F,
            committed_at="2026-08-06T02:21:00Z",
        )
        return temporary, committed

    @contextmanager
    def _stack(self):
        with tempfile.TemporaryDirectory() as directory:
            laboratory = Path(directory)
            laboratory.chmod(0o700)
            owner = DisposableC20LockOwnerV7(laboratory)
            approval_root = None
            try:
                temporary, committed = self._plans(owner)
                approval_root = DisposableApprovalRootV7(owner)
                facade = DisposableApprovalLifecycleFacadeV7(
                    owner,
                    approval_root,
                    temporary,
                    committed,
                )
                yield owner, approval_root, facade, temporary, committed
            finally:
                if approval_root is not None and not approval_root.closed:
                    approval_root.close()
                if owner.lock_held:
                    owner.close_owner()

    def _assert_lock_blocked(self, owner: DisposableC20LockOwnerV7) -> None:
        second = os.open(owner.lock_path, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            with self.assertRaises(OSError) as raised:
                fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertIn(raised.exception.errno, (errno.EACCES, errno.EAGAIN))
        finally:
            os.close(second)

    @staticmethod
    def _fixed_component(method_name: str, result):
        component = Mock()
        getattr(component, method_name).return_value = result
        return Mock(return_value=component), component

    def _bound(self, facade: DisposableApprovalLifecycleFacadeV7) -> None:
        event = facade.bind_canonical_lease()
        self.assertIs(event.result.status, AdapterStatus.PASS)
        self.assertIs(facade.phase, DisposableApprovalLifecyclePhaseV7.LEASE_BOUND)

    def _published(self, facade: DisposableApprovalLifecycleFacadeV7) -> None:
        self._bound(facade)
        event = facade.publish_temporary()
        self.assertIs(event.result.status, AdapterStatus.PASS)
        self.assertIs(facade.phase, DisposableApprovalLifecyclePhaseV7.TEMPORARY_PUBLISHED)

    def _assert_recovery_terminal(
        self,
        facade: DisposableApprovalLifecycleFacadeV7,
        event: DisposableApprovalLifecycleEventV7,
        result,
    ) -> None:
        self.assertIs(event.result, result)
        self.assertIs(event.phase_after, DisposableApprovalLifecyclePhaseV7.RECOVERY_REQUIRED)
        self.assertIs(facade.phase, DisposableApprovalLifecyclePhaseV7.RECOVERY_REQUIRED)
        self.assertFalse(event.successful_terminal_state)
        for method in (
            facade.bind_canonical_lease,
            facade.publish_temporary,
            facade.remove_temporary,
            facade.promote_committed,
        ):
            with self.assertRaises(DisposableApprovalLifecycleOrderError):
                method()

    def test_bind_publish_remove_success_path(self) -> None:
        with self._stack() as stack:
            owner, root, facade, temporary, committed = stack
            self.assertIs(facade.temporary_plan, temporary)
            self.assertIs(facade.committed_plan, committed)
            bound = facade.bind_canonical_lease()
            self.assertIs(bound.phase_before, DisposableApprovalLifecyclePhaseV7.OWNER_HELD_EMPTY)
            self.assertIs(bound.phase_after, DisposableApprovalLifecyclePhaseV7.LEASE_BOUND)
            published = facade.publish_temporary()
            self.assertIs(published.phase_after, DisposableApprovalLifecyclePhaseV7.TEMPORARY_PUBLISHED)
            self.assertEqual(root.approval_path.read_bytes(), temporary.encoded_bytes)
            removed = facade.remove_temporary()
            self.assertIs(removed.operation, DisposableApprovalLifecycleOperationV7.REMOVE_TEMPORARY)
            self.assertIs(removed.phase_after, DisposableApprovalLifecyclePhaseV7.TEMPORARY_REMOVED)
            self.assertTrue(removed.successful_terminal_state)
            self.assertTrue(removed.owner_lock_remains_held)
            self.assertFalse(root.approval_path.exists())
            self._assert_lock_blocked(owner)

    def test_bind_publish_promote_success_path(self) -> None:
        with self._stack() as stack:
            owner, root, facade, temporary, committed = stack
            self._published(facade)
            promoted = facade.promote_committed()
            self.assertIs(promoted.operation, DisposableApprovalLifecycleOperationV7.PROMOTE_COMMITTED)
            self.assertIs(promoted.phase_after, DisposableApprovalLifecyclePhaseV7.COMMITTED)
            self.assertTrue(promoted.successful_terminal_state)
            self.assertFalse(promoted.reviewed_follow_up_permitted)
            self.assertFalse(promoted.forward_recovery_required)
            self.assertFalse(promoted.manual_reconciliation_required)
            self.assertNotEqual(temporary.encoded_bytes, committed.encoded_bytes)
            self.assertEqual(root.approval_path.read_bytes(), committed.encoded_bytes)
            self._assert_lock_blocked(owner)

    def test_invalid_order_never_constructs_a_component(self) -> None:
        names = (
            "DisposableCanonicalLeaseBinderV7",
            "DisposableTemporaryApprovalPublisherV7",
            "DisposableTemporaryApprovalRemoverV7",
            "DisposableCommittedApprovalPromoterV7",
        )
        with self._stack() as stack:
            _owner, _root, facade, _temporary, _committed = stack
            active = [patch.object(facade_module, name) for name in names]
            mocks = [item.start() for item in active]
            try:
                for method in (facade.publish_temporary, facade.remove_temporary, facade.promote_committed):
                    with self.assertRaises(DisposableApprovalLifecycleOrderError):
                        method()
                for component in mocks:
                    component.assert_not_called()
            finally:
                for item in reversed(active):
                    item.stop()

        for terminal in ("remove_temporary", "promote_committed"):
            with self.subTest(terminal=terminal), self._stack() as stack:
                _owner, _root, facade, _temporary, _committed = stack
                self._published(facade)
                getattr(facade, terminal)()
                for method in (
                    facade.bind_canonical_lease,
                    facade.publish_temporary,
                    facade.remove_temporary,
                    facade.promote_committed,
                ):
                    with self.assertRaises(DisposableApprovalLifecycleOrderError):
                        method()

    def test_binder_failed_dispositions_are_preserved(self) -> None:
        cases = (
            (DisposableLeaseBindingDispositionV7.EMPTY_ROLLBACK_PERMITTED, True, False),
            (DisposableLeaseBindingDispositionV7.MANUAL_RECONCILIATION, False, True),
        )
        for disposition, reviewed, manual in cases:
            with self.subTest(disposition=disposition), self._stack() as stack:
                owner, _root, facade, _temporary, _committed = stack
                result = DisposableCanonicalLeaseBindingResultV7(
                    status=AdapterStatus.FAIL,
                    disposition=disposition,
                    detail="injected binder failure",
                    lease_id=owner.lease_id,
                    canonical_bytes=owner.canonical_lease_bytes,
                    reconciled_after_exception=False,
                    ordinary_rollback_permitted=reviewed,
                    manual_reconciliation_required=manual,
                    owner_lock_remains_held=True,
                )
                factory, component = self._fixed_component("bind", result)
                with patch.object(facade_module, "DisposableCanonicalLeaseBinderV7", factory):
                    event = facade.bind_canonical_lease()
                factory.assert_called_once_with(owner)
                component.bind.assert_called_once_with()
                self._assert_recovery_terminal(facade, event, result)
                self.assertIs(event.reviewed_follow_up_permitted, reviewed)
                self.assertIs(event.manual_reconciliation_required, manual)

    def test_publisher_failed_dispositions_are_preserved(self) -> None:
        cases = (
            (
                DisposableTemporaryPublicationDispositionV7.APPROVAL_ABSENT_ROLLBACK,
                ApprovalObservedStateV7.ABSENT,
                True,
                False,
            ),
            (
                DisposableTemporaryPublicationDispositionV7.MANUAL_RECONCILIATION,
                ApprovalObservedStateV7.MISMATCHED,
                False,
                True,
            ),
        )
        for disposition, observed_state, reviewed, manual in cases:
            with self.subTest(disposition=disposition), self._stack() as stack:
                owner, root, facade, temporary, committed = stack
                self._bound(facade)
                result = DisposableTemporaryApprovalPublicationResultV7(
                    status=AdapterStatus.FAIL,
                    disposition=disposition,
                    observed_state=observed_state,
                    detail="injected publisher failure",
                    temporary_encoded_sha256=temporary.encoded_sha256,
                    reconciled_after_exception=False,
                    ordinary_rollback_permitted=reviewed,
                    manual_reconciliation_required=manual,
                    owner_lock_remains_held=True,
                    private_name_absent=True,
                )
                factory, component = self._fixed_component("publish", result)
                with patch.object(facade_module, "DisposableTemporaryApprovalPublisherV7", factory):
                    event = facade.publish_temporary()
                factory.assert_called_once_with(owner, root, temporary, committed)
                component.publish.assert_called_once_with()
                self._assert_recovery_terminal(facade, event, result)
                self.assertIs(event.reviewed_follow_up_permitted, reviewed)
                self.assertIs(event.manual_reconciliation_required, manual)

    def test_remover_failed_dispositions_are_preserved(self) -> None:
        cases = (
            (
                DisposableTemporaryRemovalDispositionV7.TEMPORARY_RETAINED_RECOVERY,
                ApprovalObservedStateV7.EXACT_TEMPORARY,
                True,
                False,
            ),
            (
                DisposableTemporaryRemovalDispositionV7.MANUAL_RECONCILIATION,
                ApprovalObservedStateV7.MISMATCHED,
                False,
                True,
            ),
        )
        for disposition, observed_state, reviewed, manual in cases:
            with self.subTest(disposition=disposition), self._stack() as stack:
                owner, root, facade, temporary, committed = stack
                self._published(facade)
                result = DisposableTemporaryApprovalRemovalResultV7(
                    status=AdapterStatus.FAIL,
                    disposition=disposition,
                    observed_state=observed_state,
                    detail="injected remover failure",
                    temporary_encoded_sha256=temporary.encoded_sha256,
                    reconciled_after_exception=False,
                    reviewed_recovery_permitted=reviewed,
                    manual_reconciliation_required=manual,
                    owner_lock_remains_held=True,
                    approval_absent=False,
                )
                factory, component = self._fixed_component("remove", result)
                with patch.object(facade_module, "DisposableTemporaryApprovalRemoverV7", factory):
                    event = facade.remove_temporary()
                factory.assert_called_once_with(owner, root, temporary, committed)
                component.remove.assert_called_once_with()
                self._assert_recovery_terminal(facade, event, result)
                self.assertIs(event.reviewed_follow_up_permitted, reviewed)
                self.assertIs(event.manual_reconciliation_required, manual)

    def test_promoter_failed_dispositions_are_preserved(self) -> None:
        cases = (
            (
                DisposableCommittedPromotionDispositionV7.TEMPORARY_RETAINED_RECOVERY,
                ApprovalObservedStateV7.EXACT_TEMPORARY,
                True,
                False,
                False,
                True,
                False,
            ),
            (
                DisposableCommittedPromotionDispositionV7.COMMITTED_FORWARD_RECOVERY_REQUIRED,
                ApprovalObservedStateV7.EXACT_COMMITTED,
                False,
                True,
                True,
                False,
                False,
            ),
            (
                DisposableCommittedPromotionDispositionV7.MANUAL_RECONCILIATION,
                ApprovalObservedStateV7.MISMATCHED,
                False,
                False,
                True,
                False,
                False,
            ),
        )
        for disposition, observed_state, reviewed, forward, manual, public_temp, public_commit in cases:
            with self.subTest(disposition=disposition), self._stack() as stack:
                owner, root, facade, temporary, committed = stack
                self._published(facade)
                result = DisposableCommittedApprovalPromotionResultV7(
                    status=AdapterStatus.FAIL,
                    disposition=disposition,
                    observed_state=observed_state,
                    detail="injected promoter failure",
                    temporary_encoded_sha256=temporary.encoded_sha256,
                    committed_encoded_sha256=committed.encoded_sha256,
                    reconciled_after_exception=False,
                    reviewed_retry_permitted=reviewed,
                    forward_recovery_required=forward,
                    manual_reconciliation_required=manual,
                    owner_lock_remains_held=True,
                    private_name_absent=True,
                    public_temporary_identity_proved=public_temp,
                    public_committed_identity_proved=public_commit,
                )
                factory, component = self._fixed_component("promote", result)
                with patch.object(facade_module, "DisposableCommittedApprovalPromoterV7", factory):
                    event = facade.promote_committed()
                factory.assert_called_once_with(owner, root, temporary, committed)
                component.promote.assert_called_once_with()
                self._assert_recovery_terminal(facade, event, result)
                self.assertIs(event.reviewed_follow_up_permitted, reviewed)
                self.assertIs(event.forward_recovery_required, forward)
                self.assertIs(event.manual_reconciliation_required, manual)

    def test_constructor_rejects_mismatched_or_closed_authority_and_plans(self) -> None:
        with self._stack() as first, self._stack() as second:
            owner1, root1, _facade1, temporary1, committed1 = first
            owner2, root2, _facade2, temporary2, _committed2 = second
            with self.assertRaises(ValueError):
                DisposableApprovalLifecycleFacadeV7(owner1, root2, temporary1, committed1)
            root1.close()
            with self.assertRaises(ValueError):
                DisposableApprovalLifecycleFacadeV7(owner1, root1, temporary1, committed1)
            with self.assertRaises(ValueError):
                DisposableApprovalLifecycleFacadeV7(owner2, root2, temporary1, committed1)
            with self.assertRaises(ValueError):
                DisposableApprovalLifecycleFacadeV7(owner2, root2, temporary2, committed1)

    def test_event_is_frozen_and_rejects_inconsistent_transition(self) -> None:
        with self._stack() as stack:
            _owner, _root, facade, _temporary, _committed = stack
            event = facade.bind_canonical_lease()
            with self.assertRaises(FrozenInstanceError):
                event.phase_after = DisposableApprovalLifecyclePhaseV7.COMMITTED  # type: ignore[misc]
            with self.assertRaises(ValueError):
                DisposableApprovalLifecycleEventV7(
                    operation=event.operation,
                    phase_before=event.phase_before,
                    phase_after=DisposableApprovalLifecyclePhaseV7.COMMITTED,
                    result=event.result,
                    successful_terminal_state=True,
                    reviewed_follow_up_permitted=False,
                    forward_recovery_required=False,
                    manual_reconciliation_required=False,
                    owner_lock_remains_held=True,
                )

    def test_source_has_no_mutation_or_generic_dispatch_and_production_stays_blocked(self) -> None:
        imported = {
            alias.name.split(".")[0]
            for node in self.tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(
            imported.isdisjoint(
                {"argparse", "ctypes", "fcntl", "os", "pathlib", "socket", "subprocess", "sys"}
            )
        )
        methods = {
            node.name: node
            for node in ast.walk(self.tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        expected_calls = {
            "bind_canonical_lease": "bind",
            "publish_temporary": "publish",
            "remove_temporary": "remove",
            "promote_committed": "promote",
        }
        for name, expected in expected_calls.items():
            method = methods[name]
            delegated = [
                node.func.attr
                for node in ast.walk(method)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"bind", "publish", "remove", "promote"}
            ]
            self.assertEqual(delegated, [expected])
            self.assertFalse(any(isinstance(node, (ast.For, ast.AsyncFor, ast.While)) for node in ast.walk(method)))

        forbidden_attributes = {
            "open",
            "close",
            "write",
            "pwrite",
            "truncate",
            "ftruncate",
            "fsync",
            "link",
            "unlink",
            "rename",
            "replace",
            "mkdir",
            "chmod",
            "chown",
            "flock",
            "system",
            "run",
            "popen",
        }
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.assertNotIn("dispatch", node.name.lower())
                self.assertNotIn("factory", node.name.lower())
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, forbidden_attributes)
        for forbidden in (
            "/run/lock",
            "/var/lib",
            "/etc",
            "systemctl",
            "aplay",
            "amixer",
            "/dev/snd",
            "shell=True",
        ):
            self.assertNotIn(forbidden, self.source)

        self.assertEqual(len(ALL_OPERATIONS_V7), 42)
        blocked = BlockedProductionAdapterV7()
        transaction = TransactionIdentity("lifecycle-still-blocked")
        for method_name in (
            "bind_production_lock_lease",
            "publish_temporary_activation_approval",
            "remove_temporary_activation_approval",
            "promote_committed_activation_approval",
        ):
            with self.subTest(method=method_name), self.assertRaises(
                ProductionActivationApprovalAdapterBlocked
            ):
                getattr(blocked, method_name)(transaction)


if __name__ == "__main__":
    unittest.main()
