from __future__ import annotations

import ast
import errno
import fcntl
import json
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
REMOVER_MODULE = (
    ROOT
    / "scripts/stage_c_transaction/disposable_temporary_approval_remover_v7.py"
)

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
    DisposableApprovalObservationResultV7,
    DisposableApprovalRootV7,
)
from scripts.stage_c_transaction.disposable_c20_lock_owner_v7 import (
    DisposableC20LockOwnerV7,
)
from scripts.stage_c_transaction.disposable_canonical_lease_binder_v7 import (
    DisposableCanonicalLeaseBinderV7,
)
from scripts.stage_c_transaction.disposable_temporary_approval_publisher_v7 import (
    DisposableTemporaryApprovalPublisherV7,
)
from scripts.stage_c_transaction.disposable_temporary_approval_remover_v7 import (
    DisposableTemporaryApprovalRemovalResultV7,
    DisposableTemporaryApprovalRemoverV7,
    DisposableTemporaryRemovalDispositionV7,
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


class StageCDisposableTemporaryApprovalRemovalV7Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = REMOVER_MODULE.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    @contextmanager
    def _stack(
        self,
        *,
        fault_hook=None,
        publish: bool = True,
        lease_id: str | None = None,
    ):
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
                transaction = TransactionIdentity("stage-c21-disposable-removal")
                binding = ApprovalAuthorityBindingV7(
                    transaction=transaction,
                    snapshot=SnapshotIdentity(
                        "stage-c21-disposable-removal-snapshot"
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
                    created_at="2026-08-06T01:35:00Z",
                )
                committed = plan_committed_approval_v7(
                    temporary,
                    commit_manifest_sha256=HASH_F,
                    committed_at="2026-08-06T01:36:00Z",
                )
                approval_root = DisposableApprovalRootV7(owner)
                if publish:
                    publication = DisposableTemporaryApprovalPublisherV7(
                        owner,
                        approval_root,
                        temporary,
                        committed,
                    ).publish()
                    self.assertIs(publication.status, AdapterStatus.PASS)
                remover = DisposableTemporaryApprovalRemoverV7(
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
                    remover,
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

    def test_success_removes_the_exact_opened_temporary_inode(self) -> None:
        opened: list[tuple[int, int]] = []
        unlinked: list[tuple[int, int]] = []

        with self._stack() as stack:
            _laboratory, owner, approval_root, remover, _temporary, _committed = stack
            before = approval_root.approval_path.stat()
            real_unlink = os.unlink

            def record_unlink(path, *args, **kwargs):
                current = os.stat(
                    path,
                    dir_fd=kwargs.get("dir_fd"),
                    follow_symlinks=False,
                )
                unlinked.append((current.st_dev, current.st_ino))
                return real_unlink(path, *args, **kwargs)

            original_open = remover._open_exact_temporary

            def record_open():
                proof = original_open()
                opened.append((proof.device, proof.inode))
                return proof

            with patch.object(remover, "_open_exact_temporary", side_effect=record_open), patch(
                "scripts.stage_c_transaction.disposable_temporary_approval_remover_v7.os.unlink",
                side_effect=record_unlink,
            ):
                result = remover.remove()
            self.assertIs(result.status, AdapterStatus.PASS)
            self.assertIs(
                result.disposition,
                DisposableTemporaryRemovalDispositionV7.TEMPORARY_REMOVED,
            )
            self.assertIs(result.observed_state, ApprovalObservedStateV7.ABSENT)
            self.assertFalse(result.reconciled_after_exception)
            self.assertTrue(result.approval_absent)
            self.assertEqual(opened, [(before.st_dev, before.st_ino)])
            self.assertEqual(unlinked, opened)
            observed = approval_root.observe_public()
            assert observed.payload is not None
            self.assertFalse(observed.payload.present)
            self._assert_independent_lock_blocked(owner)

    def test_absent_precondition_is_refused_not_idempotently_accepted(self) -> None:
        with self._stack(publish=False) as stack:
            _laboratory, owner, approval_root, remover, _temporary, _committed = stack
            result = remover.remove()
            self.assertIs(result.status, AdapterStatus.FAIL)
            self.assertIs(
                result.disposition,
                DisposableTemporaryRemovalDispositionV7.MANUAL_RECONCILIATION,
            )
            self.assertIs(result.observed_state, ApprovalObservedStateV7.ABSENT)
            self.assertTrue(result.approval_absent)
            self.assertFalse(result.reviewed_recovery_permitted)
            observed = approval_root.observe_public()
            assert observed.payload is not None
            self.assertFalse(observed.payload.present)
            self._assert_independent_lock_blocked(owner)

    def test_failures_before_unlink_leave_same_inode_for_reviewed_recovery(self) -> None:
        points = (
            "before-public-open",
            "after-public-open",
            "after-public-read",
            "before-final-name-recheck",
        )
        for point in points:
            with self.subTest(point=point), self._stack(
                fault_hook=OneShotFault(point)
            ) as stack:
                _laboratory, owner, approval_root, remover, temporary, _committed = stack
                before = approval_root.approval_path.stat()
                result = remover.remove()
                self.assertIs(result.status, AdapterStatus.FAIL)
                self.assertIs(
                    result.disposition,
                    DisposableTemporaryRemovalDispositionV7.TEMPORARY_RETAINED_RECOVERY,
                )
                self.assertIs(result.observed_state, ApprovalObservedStateV7.EXACT_TEMPORARY)
                self.assertTrue(result.reviewed_recovery_permitted)
                self.assertFalse(result.approval_absent)
                after = approval_root.approval_path.stat()
                self.assertEqual((before.st_dev, before.st_ino), (after.st_dev, after.st_ino))
                self.assertEqual(approval_root.approval_path.read_bytes(), temporary.encoded_bytes)
                self._assert_independent_lock_blocked(owner)

    def test_failures_after_unlink_reconcile_durable_exact_absence(self) -> None:
        points = (
            "after-public-unlink",
            "after-unlinked-descriptor-verification",
            "before-removal-directory-fsync",
            "after-removal-directory-fsync",
            "before-absence-observation",
            "after-absence-observation",
            "before-final-owner-verification",
            "after-final-owner-verification",
        )
        for point in points:
            with self.subTest(point=point), self._stack(
                fault_hook=OneShotFault(point)
            ) as stack:
                _laboratory, owner, approval_root, remover, _temporary, _committed = stack
                result = remover.remove()
                self.assertIs(result.status, AdapterStatus.PASS)
                self.assertIs(
                    result.disposition,
                    DisposableTemporaryRemovalDispositionV7.TEMPORARY_REMOVED,
                )
                self.assertTrue(result.reconciled_after_exception)
                self.assertTrue(result.approval_absent)
                observed = approval_root.observe_public()
                assert observed.payload is not None
                self.assertFalse(observed.payload.present)
                self._assert_independent_lock_blocked(owner)

    def test_directory_fsync_failure_is_repaired_before_success(self) -> None:
        with self._stack() as stack:
            _laboratory, owner, approval_root, remover, _temporary, _committed = stack
            real_fsync = os.fsync
            calls = 0

            def fail_once(fd: int) -> None:
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise OSError("injected directory fsync failure")
                real_fsync(fd)

            with patch(
                "scripts.stage_c_transaction.disposable_temporary_approval_remover_v7.os.fsync",
                side_effect=fail_once,
            ):
                result = remover.remove()
            self.assertIs(result.status, AdapterStatus.PASS)
            self.assertTrue(result.reconciled_after_exception)
            self.assertGreaterEqual(calls, 2)
            self.assertFalse(approval_root.approval_path.exists())
            self._assert_independent_lock_blocked(owner)

    def test_committed_mismatched_noncanonical_wrong_mode_and_symlink_are_never_removed(self) -> None:
        cases = ("committed", "mismatched", "noncanonical", "wrong-mode", "symlink")
        for case in cases:
            with self.subTest(case=case), self._stack() as stack:
                _laboratory, owner, approval_root, remover, temporary, committed = stack
                approval_root.approval_path.unlink()
                if case == "committed":
                    approval_root.approval_path.write_bytes(committed.encoded_bytes)
                    expected_state = ApprovalObservedStateV7.EXACT_COMMITTED
                elif case == "mismatched":
                    approval_root.approval_path.write_bytes(b"different\n")
                    expected_state = ApprovalObservedStateV7.MISMATCHED
                elif case == "noncanonical":
                    envelope = json.loads(temporary.encoded_bytes.decode("utf-8"))
                    approval_root.approval_path.write_bytes(
                        json.dumps(envelope, indent=2).encode("utf-8") + b"\n"
                    )
                    expected_state = ApprovalObservedStateV7.MISMATCHED
                elif case == "wrong-mode":
                    approval_root.approval_path.write_bytes(temporary.encoded_bytes)
                    approval_root.approval_path.chmod(0o644)
                    expected_state = ApprovalObservedStateV7.OBSERVATION_FAILURE
                else:
                    approval_root.approval_path.symlink_to(owner.lock_path)
                    expected_state = ApprovalObservedStateV7.OBSERVATION_FAILURE
                if case not in {"wrong-mode", "symlink"}:
                    approval_root.approval_path.chmod(APPROVAL_MODE)
                before = approval_root.approval_path.lstat()
                result = remover.remove()
                self.assertIs(result.status, AdapterStatus.FAIL)
                self.assertIs(
                    result.disposition,
                    DisposableTemporaryRemovalDispositionV7.MANUAL_RECONCILIATION,
                )
                self.assertIs(result.observed_state, expected_state)
                after = approval_root.approval_path.lstat()
                self.assertEqual((before.st_dev, before.st_ino), (after.st_dev, after.st_ino))
                self._assert_independent_lock_blocked(owner)
                approval_root.approval_path.unlink()

    def test_public_substitution_at_last_boundary_is_detected_not_unlinked(self) -> None:
        with self._stack() as stack:
            _laboratory, owner, approval_root, _remover, temporary, committed = stack
            replacement: list[tuple[int, int]] = []

            def substitute(point: str) -> None:
                if point != "before-final-name-recheck" or replacement:
                    return
                approval_root.approval_path.unlink()
                approval_root.approval_path.symlink_to(owner.lock_path)
                info = approval_root.approval_path.lstat()
                replacement.append((info.st_dev, info.st_ino))

            remover = DisposableTemporaryApprovalRemoverV7(
                owner,
                approval_root,
                temporary,
                committed,
                fault_hook=substitute,
            )
            result = remover.remove()
            self.assertIs(
                result.disposition,
                DisposableTemporaryRemovalDispositionV7.MANUAL_RECONCILIATION,
            )
            self.assertTrue(approval_root.approval_path.is_symlink())
            after = approval_root.approval_path.lstat()
            self.assertEqual(replacement, [(after.st_dev, after.st_ino)])
            self._assert_independent_lock_blocked(owner)
            approval_root.approval_path.unlink()

    def test_recreated_exact_bytes_on_different_inode_do_not_gain_retry_permission(self) -> None:
        with self._stack() as stack:
            _laboratory, owner, approval_root, _remover, temporary, committed = stack
            original = approval_root.approval_path.stat()
            replaced = False

            def replace_and_raise(point: str) -> None:
                nonlocal replaced
                if point != "before-final-name-recheck" or replaced:
                    return
                replaced = True
                approval_root.approval_path.unlink()
                approval_root.approval_path.write_bytes(temporary.encoded_bytes)
                approval_root.approval_path.chmod(APPROVAL_MODE)
                raise RuntimeError("injected exact-byte inode replacement")

            remover = DisposableTemporaryApprovalRemoverV7(
                owner,
                approval_root,
                temporary,
                committed,
                fault_hook=replace_and_raise,
            )
            result = remover.remove()
            current = approval_root.approval_path.stat()
            self.assertNotEqual((original.st_dev, original.st_ino), (current.st_dev, current.st_ino))
            self.assertIs(result.observed_state, ApprovalObservedStateV7.EXACT_TEMPORARY)
            self.assertIs(
                result.disposition,
                DisposableTemporaryRemovalDispositionV7.MANUAL_RECONCILIATION,
            )
            self.assertFalse(result.reviewed_recovery_permitted)
            self.assertEqual(approval_root.approval_path.read_bytes(), temporary.encoded_bytes)
            self._assert_independent_lock_blocked(owner)

    def test_unavailable_observation_after_unlink_retains_manual_authority(self) -> None:
        with self._stack() as stack:
            _laboratory, owner, approval_root, remover, _temporary, _committed = stack
            real_observe = approval_root.observe_public
            calls = 0

            def fail_after_preflight():
                nonlocal calls
                calls += 1
                if calls == 1:
                    return real_observe()
                return DisposableApprovalObservationResultV7(
                    status=AdapterStatus.FAIL,
                    detail="injected post-unlink observation failure",
                )

            with patch.object(approval_root, "observe_public", side_effect=fail_after_preflight):
                result = remover.remove()
            self.assertIs(
                result.disposition,
                DisposableTemporaryRemovalDispositionV7.MANUAL_RECONCILIATION,
            )
            self.assertIs(result.observed_state, ApprovalObservedStateV7.OBSERVATION_FAILURE)
            self.assertTrue(owner.lock_held)
            self._assert_independent_lock_blocked(owner)

    def test_lost_owner_authority_blocks_removal(self) -> None:
        with self._stack() as stack:
            _laboratory, owner, approval_root, remover, temporary, _committed = stack
            owner.lock_path.write_bytes(b"wrong-lease\n")
            result = remover.remove()
            self.assertIs(
                result.disposition,
                DisposableTemporaryRemovalDispositionV7.MANUAL_RECONCILIATION,
            )
            self.assertEqual(approval_root.approval_path.read_bytes(), temporary.encoded_bytes)
            self.assertTrue(owner.lock_held)
            owner.lock_path.write_bytes(owner.canonical_lease_bytes)
            self._assert_independent_lock_blocked(owner)

    def test_wrong_lease_and_different_root_authorities_are_rejected(self) -> None:
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
                transaction = TransactionIdentity("different-removal-root")
                binding = ApprovalAuthorityBindingV7(
                    transaction=transaction,
                    snapshot=SnapshotIdentity("different-removal-root-snapshot"),
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
                    created_at="2026-08-06T01:35:00Z",
                )
                committed = plan_committed_approval_v7(
                    temporary,
                    commit_manifest_sha256=HASH_F,
                    committed_at="2026-08-06T01:36:00Z",
                )
                with self.assertRaises(ValueError):
                    DisposableTemporaryApprovalRemoverV7(
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

    def test_result_is_frozen_and_rejects_inconsistent_permissions(self) -> None:
        with self._stack() as stack:
            _laboratory, _owner, _approval_root, remover, _temporary, _committed = stack
            result = remover.remove()
            with self.assertRaises(FrozenInstanceError):
                result.approval_absent = False  # type: ignore[misc]
        with self.assertRaises(ValueError):
            DisposableTemporaryApprovalRemovalResultV7(
                status=AdapterStatus.PASS,
                disposition=DisposableTemporaryRemovalDispositionV7.TEMPORARY_REMOVED,
                observed_state=ApprovalObservedStateV7.EXACT_TEMPORARY,
                detail="invalid",
                temporary_encoded_sha256=HASH_A,
                reconciled_after_exception=False,
                reviewed_recovery_permitted=False,
                manual_reconciliation_required=False,
                owner_lock_remains_held=True,
                approval_absent=True,
            )

    def test_module_has_only_exact_unlink_and_no_production_or_promotion_boundary(self) -> None:
        imported = {
            alias.name.split(".")[0]
            for node in self.tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(
            imported.isdisjoint(
                {"argparse", "ctypes", "socket", "subprocess", "sys"}
            )
        )
        unlink_calls = 0
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.assertNotIn("dispatch", node.name.lower())
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "unlink":
                    unlink_calls += 1
                self.assertNotIn(
                    node.func.attr,
                    {
                        "flock",
                        "link",
                        "rename",
                        "replace",
                        "renameat2",
                        "dup",
                        "dup2",
                        "pwrite",
                        "write",
                        "ftruncate",
                        "truncate",
                        "fchmod",
                        "chmod",
                        "fchown",
                        "chown",
                        "mkdir",
                        "system",
                        "run",
                        "popen",
                    },
                )
        self.assertEqual(unlink_calls, 1)
        self.assertNotIn("O_CREAT", self.source)
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
            "committed promotion",
        ):
            self.assertNotIn(forbidden, self.source)

        self.assertEqual(len(ALL_OPERATIONS_V7), 42)
        blocked = BlockedProductionAdapterV7()
        with self.assertRaises(ProductionActivationApprovalAdapterBlocked):
            blocked.remove_temporary_activation_approval(
                TransactionIdentity("still-blocked-removal")
            )


if __name__ == "__main__":
    unittest.main()
