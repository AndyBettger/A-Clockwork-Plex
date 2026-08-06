from __future__ import annotations

import ast
import errno
import fcntl
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
PUBLISHER_MODULE = (
    ROOT
    / "scripts/stage_c_transaction/disposable_temporary_approval_publisher_v7.py"
)
ROOT_MODULE = ROOT / "scripts/stage_c_transaction/disposable_approval_root_v7.py"

from scripts.stage_c_transaction.approval_authority_binding_v7 import (
    ApprovalAuthorityBindingV7,
    ApprovalHardwareContractV7,
)
from scripts.stage_c_transaction.approval_record_plan_v7 import (
    ApprovalObservedStateV7,
    plan_committed_approval_v7,
    plan_temporary_approval_v7,
)
from scripts.stage_c_transaction.disposable_approval_root_v7 import (
    APPROVAL_MODE,
    APPROVAL_NAME,
    DisposableApprovalObservationResultV7,
    DisposableApprovalRootFailure,
    DisposableApprovalRootV7,
)
from scripts.stage_c_transaction.disposable_c20_lock_owner_v7 import (
    DisposableC20LockOwnerV7,
)
from scripts.stage_c_transaction.disposable_canonical_lease_binder_v7 import (
    DisposableCanonicalLeaseBinderV7,
)
from scripts.stage_c_transaction.disposable_temporary_approval_publisher_v7 import (
    PRIVATE_PREFIX,
    DisposableTemporaryApprovalPublisherV7,
    DisposableTemporaryPublicationDispositionV7,
)
from scripts.stage_c_transaction.production_adapter_contract import (
    AUTHORITATIVE_TRANSACTION_ROOT,
    AdapterStatus,
    PackageFingerprint,
    SnapshotIdentity,
    TransactionIdentity,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v7 import (
    ALL_OPERATIONS_V7,
    BlockedProductionAdapterV7,
    ProductionActivationApprovalAdapterBlocked,
)
from scripts.stage_c_transaction.snapshot_core import CURRENT_ALSA_DESTINATION


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
HASH_E = "e" * 64
HASH_F = "f" * 64


class OneShotFault:
    def __init__(self, point: str) -> None:
        self.point = point
        self.triggered = False

    def __call__(self, observed: str) -> None:
        if observed == self.point and not self.triggered:
            self.triggered = True
            raise RuntimeError(f"injected fault at {observed}")


class StageCDisposableTemporaryApprovalPublicationV7Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.publisher_source = PUBLISHER_MODULE.read_text(encoding="utf-8")
        self.root_source = ROOT_MODULE.read_text(encoding="utf-8")
        self.publisher_tree = ast.parse(self.publisher_source)
        self.root_tree = ast.parse(self.root_source)

    @contextmanager
    def _stack(self, *, fault_hook=None, lease_id: str | None = None):
        with tempfile.TemporaryDirectory() as directory:
            laboratory = Path(directory)
            laboratory.chmod(0o700)
            owner = DisposableC20LockOwnerV7(laboratory)
            approval_root = None
            try:
                binding_result = DisposableCanonicalLeaseBinderV7(owner).bind()
                self.assertIs(binding_result.status, AdapterStatus.PASS)
                owner_observation = owner.observe()
                self.assertIs(owner_observation.status, AdapterStatus.PASS)
                assert owner_observation.payload is not None

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
                transaction = TransactionIdentity("stage-c21-disposable-publication")
                binding = ApprovalAuthorityBindingV7(
                    transaction=transaction,
                    snapshot=SnapshotIdentity(
                        "stage-c21-disposable-publication-snapshot"
                    ),
                    package=package,
                    production_lock_path=str(owner.lock_path),
                    lock_lease_id=lease_id or owner.lease_id,
                    lock_device=owner_observation.payload.device,
                    lock_inode=owner_observation.payload.inode,
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
                    created_at="2026-08-06T00:30:00Z",
                )
                committed = plan_committed_approval_v7(
                    temporary,
                    commit_manifest_sha256=HASH_F,
                    committed_at="2026-08-06T00:31:00Z",
                )
                approval_root = DisposableApprovalRootV7(owner)
                publisher = DisposableTemporaryApprovalPublisherV7(
                    owner,
                    approval_root,
                    temporary,
                    committed,
                    fault_hook=fault_hook,
                )
                yield (
                    laboratory,
                    owner,
                    approval_root,
                    publisher,
                    temporary,
                    committed,
                )
            finally:
                if approval_root is not None and not approval_root.closed:
                    approval_root.close()
                if owner.lock_held:
                    owner.close_owner()

    def _assert_independent_lock_blocked(
        self,
        owner: DisposableC20LockOwnerV7,
    ) -> None:
        second = os.open(
            owner.lock_path,
            os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        try:
            with self.assertRaises(OSError) as raised:
                fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertIn(raised.exception.errno, (errno.EACCES, errno.EAGAIN))
        finally:
            os.close(second)

    def _private_names(self, approval_root: DisposableApprovalRootV7) -> list[str]:
        return sorted(
            item.name
            for item in approval_root.path.iterdir()
            if item.name.startswith(PRIVATE_PREFIX)
        )

    def test_success_publishes_exact_bytes_without_replacement(self) -> None:
        with self._stack() as stack:
            _laboratory, owner, approval_root, publisher, temporary, _committed = stack
            result = publisher.publish()
            self.assertIs(result.status, AdapterStatus.PASS)
            self.assertIs(
                result.disposition,
                DisposableTemporaryPublicationDispositionV7.TEMPORARY_PUBLISHED,
            )
            self.assertIs(result.observed_state, ApprovalObservedStateV7.EXACT_TEMPORARY)
            self.assertFalse(result.reconciled_after_exception)
            self.assertTrue(result.private_name_absent)
            observed = approval_root.observe_public()
            self.assertIs(observed.status, AdapterStatus.PASS)
            assert observed.payload is not None
            self.assertTrue(observed.payload.present)
            self.assertEqual(observed.payload.raw_content, temporary.encoded_bytes)
            self.assertEqual(self._private_names(approval_root), [])
            self._assert_independent_lock_blocked(owner)

    def test_exact_temporary_is_idempotent_without_another_candidate(self) -> None:
        with self._stack() as stack:
            _laboratory, owner, approval_root, publisher, temporary, committed = stack
            self.assertIs(publisher.publish().status, AdapterStatus.PASS)
            points: list[str] = []

            def forbid_mutation(point: str) -> None:
                points.append(point)
                raise AssertionError(f"idempotent publication attempted mutation: {point}")

            second = DisposableTemporaryApprovalPublisherV7(
                owner,
                approval_root,
                temporary,
                committed,
                fault_hook=forbid_mutation,
            )
            result = second.publish()
            self.assertIs(result.status, AdapterStatus.PASS)
            self.assertEqual(points, [])
            self.assertEqual(self._private_names(approval_root), [])
            self._assert_independent_lock_blocked(owner)

    def test_failures_before_public_link_remove_only_tracked_private_candidate(self) -> None:
        points = (
            "before-candidate-create",
            "after-candidate-create",
            "after-candidate-write",
            "after-candidate-exact-truncate",
            "after-candidate-fsync",
            "before-public-link",
        )
        for point in points:
            with self.subTest(point=point), self._stack(
                fault_hook=OneShotFault(point)
            ) as stack:
                _laboratory, owner, approval_root, publisher, _temporary, _committed = stack
                result = publisher.publish()
                self.assertIs(result.status, AdapterStatus.FAIL)
                self.assertIs(
                    result.disposition,
                    DisposableTemporaryPublicationDispositionV7.APPROVAL_ABSENT_ROLLBACK,
                )
                self.assertIs(result.observed_state, ApprovalObservedStateV7.ABSENT)
                self.assertTrue(result.ordinary_rollback_permitted)
                self.assertEqual(self._private_names(approval_root), [])
                observed = approval_root.observe_public()
                assert observed.payload is not None
                self.assertFalse(observed.payload.present)
                self._assert_independent_lock_blocked(owner)

    def test_failures_after_public_link_reconcile_exact_temporary_without_retry(self) -> None:
        points = (
            "after-public-link",
            "after-publication-directory-fsync",
            "before-private-unlink",
            "after-private-unlink",
            "after-cleanup-directory-fsync",
        )
        for point in points:
            with self.subTest(point=point), self._stack(
                fault_hook=OneShotFault(point)
            ) as stack:
                _laboratory, owner, approval_root, publisher, temporary, _committed = stack
                result = publisher.publish()
                self.assertIs(result.status, AdapterStatus.PASS)
                self.assertTrue(result.reconciled_after_exception)
                self.assertIs(
                    result.disposition,
                    DisposableTemporaryPublicationDispositionV7.TEMPORARY_PUBLISHED,
                )
                observed = approval_root.observe_public()
                assert observed.payload is not None
                self.assertEqual(observed.payload.raw_content, temporary.encoded_bytes)
                self.assertEqual(self._private_names(approval_root), [])
                self._assert_independent_lock_blocked(owner)

    def test_partial_write_is_removed_while_public_name_remains_absent(self) -> None:
        with self._stack() as stack:
            _laboratory, owner, approval_root, publisher, _temporary, _committed = stack
            real_pwrite = os.pwrite
            calls = 0

            def partial_then_fail(fd: int, payload, offset: int) -> int:
                nonlocal calls
                calls += 1
                if calls == 1:
                    partial = bytes(payload[: max(1, len(payload) // 2)])
                    return real_pwrite(fd, partial, offset)
                raise OSError("injected partial pwrite failure")

            with patch(
                "scripts.stage_c_transaction.disposable_temporary_approval_publisher_v7.os.pwrite",
                side_effect=partial_then_fail,
            ):
                result = publisher.publish()
            self.assertIs(
                result.disposition,
                DisposableTemporaryPublicationDispositionV7.APPROVAL_ABSENT_ROLLBACK,
            )
            self.assertEqual(self._private_names(approval_root), [])
            observed = approval_root.observe_public()
            assert observed.payload is not None
            self.assertFalse(observed.payload.present)
            self._assert_independent_lock_blocked(owner)

    def test_preexisting_mismatched_or_committed_approval_is_never_replaced(self) -> None:
        for committed_record in (False, True):
            with self.subTest(committed=committed_record), self._stack() as stack:
                _laboratory, owner, approval_root, publisher, temporary, committed = stack
                payload = committed.encoded_bytes if committed_record else b"different\n"
                approval_root.approval_path.write_bytes(payload)
                approval_root.approval_path.chmod(APPROVAL_MODE)
                before = approval_root.approval_path.stat()
                result = publisher.publish()
                self.assertIs(result.status, AdapterStatus.FAIL)
                self.assertIs(
                    result.disposition,
                    DisposableTemporaryPublicationDispositionV7.MANUAL_RECONCILIATION,
                )
                self.assertEqual(approval_root.approval_path.read_bytes(), payload)
                after = approval_root.approval_path.stat()
                self.assertEqual((before.st_dev, before.st_ino), (after.st_dev, after.st_ino))
                self.assertEqual(self._private_names(approval_root), [])
                if committed_record:
                    self.assertIs(result.observed_state, ApprovalObservedStateV7.EXACT_COMMITTED)
                else:
                    self.assertIs(result.observed_state, ApprovalObservedStateV7.MISMATCHED)
                self._assert_independent_lock_blocked(owner)
                self.assertNotEqual(payload, temporary.encoded_bytes)

    def test_unavailable_public_observation_after_link_requires_manual_reconciliation(self) -> None:
        with self._stack() as stack:
            _laboratory, owner, approval_root, publisher, _temporary, _committed = stack
            real_observe = approval_root.observe_public
            calls = 0

            def fail_after_preflight():
                nonlocal calls
                calls += 1
                if calls == 1:
                    return real_observe()
                return DisposableApprovalObservationResultV7(
                    status=AdapterStatus.FAIL,
                    detail="injected public observation failure",
                )

            with patch.object(approval_root, "observe_public", side_effect=fail_after_preflight):
                result = publisher.publish()
            self.assertIs(
                result.disposition,
                DisposableTemporaryPublicationDispositionV7.MANUAL_RECONCILIATION,
            )
            self.assertIs(result.observed_state, ApprovalObservedStateV7.OBSERVATION_FAILURE)
            self.assertTrue(owner.lock_held)
            self._assert_independent_lock_blocked(owner)

    def test_substituted_private_candidate_is_not_unlinked_automatically(self) -> None:
        with self._stack() as stack:
            _laboratory, owner, approval_root, _publisher, temporary, committed = stack
            triggered = False

            def substitute(point: str) -> None:
                nonlocal triggered
                if point != "after-candidate-create" or triggered:
                    return
                triggered = True
                private = next(
                    item
                    for item in approval_root.path.iterdir()
                    if item.name.startswith(PRIVATE_PREFIX)
                )
                private.unlink()
                private.symlink_to(owner.lock_path)
                raise RuntimeError("injected private substitution")

            publisher = DisposableTemporaryApprovalPublisherV7(
                owner,
                approval_root,
                temporary,
                committed,
                fault_hook=substitute,
            )
            result = publisher.publish()
            self.assertIs(
                result.disposition,
                DisposableTemporaryPublicationDispositionV7.MANUAL_RECONCILIATION,
            )
            self.assertFalse(result.private_name_absent)
            private = next(
                item
                for item in approval_root.path.iterdir()
                if item.name.startswith(PRIVATE_PREFIX)
            )
            self.assertTrue(private.is_symlink())
            self.assertTrue(owner.lock_held)
            self._assert_independent_lock_blocked(owner)
            private.unlink()

    def test_root_rejects_symlink_wrong_mode_and_closed_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            laboratory = Path(directory)
            laboratory.chmod(0o700)
            owner = DisposableC20LockOwnerV7(laboratory)
            try:
                (laboratory / "var").symlink_to(laboratory / "run")
                with self.assertRaises(OSError):
                    DisposableApprovalRootV7(owner)
                (laboratory / "var").unlink()
                (laboratory / "var").mkdir(mode=0o755)
                with self.assertRaises(DisposableApprovalRootFailure):
                    DisposableApprovalRootV7(owner)
            finally:
                owner.close_owner()

        with tempfile.TemporaryDirectory() as directory:
            laboratory = Path(directory)
            laboratory.chmod(0o700)
            owner = DisposableC20LockOwnerV7(laboratory)
            owner.close_owner()
            with self.assertRaises(DisposableApprovalRootFailure):
                DisposableApprovalRootV7(owner)

    def test_publisher_rejects_wrong_lease_and_different_authority_root(self) -> None:
        with self.assertRaises(ValueError), self._stack(lease_id="wrong-lease"):
            pass

        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_root = Path(first)
            second_root = Path(second)
            first_root.chmod(0o700)
            second_root.chmod(0o700)
            first_owner = DisposableC20LockOwnerV7(first_root)
            second_owner = DisposableC20LockOwnerV7(second_root)
            first_approval = second_approval = None
            try:
                self.assertIs(
                    DisposableCanonicalLeaseBinderV7(first_owner).bind().status,
                    AdapterStatus.PASS,
                )
                self.assertIs(
                    DisposableCanonicalLeaseBinderV7(second_owner).bind().status,
                    AdapterStatus.PASS,
                )
                first_approval = DisposableApprovalRootV7(first_owner)
                second_approval = DisposableApprovalRootV7(second_owner)
                observation = first_owner.observe()
                assert observation.payload is not None
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
                transaction = TransactionIdentity("different-root")
                binding = ApprovalAuthorityBindingV7(
                    transaction=transaction,
                    snapshot=SnapshotIdentity("different-root-snapshot"),
                    package=package,
                    production_lock_path=str(first_owner.lock_path),
                    lock_lease_id=first_owner.lease_id,
                    lock_device=observation.payload.device,
                    lock_inode=observation.payload.inode,
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
                    created_at="2026-08-06T00:30:00Z",
                )
                committed = plan_committed_approval_v7(
                    temporary,
                    commit_manifest_sha256=HASH_F,
                    committed_at="2026-08-06T00:31:00Z",
                )
                with self.assertRaises(ValueError):
                    DisposableTemporaryApprovalPublisherV7(
                        first_owner,
                        second_approval,
                        temporary,
                        committed,
                    )
            finally:
                if first_approval is not None and not first_approval.closed:
                    first_approval.close()
                if second_approval is not None and not second_approval.closed:
                    second_approval.close()
                if first_owner.lock_held:
                    first_owner.close_owner()
                if second_owner.lock_held:
                    second_owner.close_owner()

    def test_modules_have_no_production_command_audio_or_replacement_boundary(self) -> None:
        for source, tree in (
            (self.publisher_source, self.publisher_tree),
            (self.root_source, self.root_tree),
        ):
            imported = {
                alias.name.split(".")[0]
                for node in tree.body
                if isinstance(node, (ast.Import, ast.ImportFrom))
                for alias in node.names
            }
            self.assertTrue(
                imported.isdisjoint(
                    {"argparse", "ctypes", "socket", "subprocess", "sys"}
                )
            )
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.assertNotIn("dispatch", node.name.lower())
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    self.assertNotIn(
                        node.func.attr,
                        {
                            "flock",
                            "rename",
                            "replace",
                            "renameat2",
                            "dup",
                            "dup2",
                            "system",
                            "run",
                            "popen",
                        },
                    )
            for forbidden in (
                "/run/lock",
                "/var/lib",
                "/etc",
                "systemctl",
                "aplay",
                "amixer",
                "/dev/snd",
                "shell=True",
                "RENAME_EXCHANGE",
            ):
                self.assertNotIn(forbidden, source)

        self.assertEqual(len(ALL_OPERATIONS_V7), 42)
        blocked = BlockedProductionAdapterV7()
        with self.assertRaises(ProductionActivationApprovalAdapterBlocked):
            blocked.publish_temporary_activation_approval(
                TransactionIdentity("still-blocked")
            )


if __name__ == "__main__":
    unittest.main()
