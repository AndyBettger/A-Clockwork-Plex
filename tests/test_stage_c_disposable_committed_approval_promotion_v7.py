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
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
PROMOTER_MODULE = (
    ROOT
    / "scripts/stage_c_transaction/disposable_committed_approval_promoter_v7.py"
)

from scripts.stage_c_transaction import (  # noqa: E402
    disposable_committed_approval_promoter_v7 as promoter_module,
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
from scripts.stage_c_transaction.disposable_approval_root_v7 import (  # noqa: E402
    APPROVAL_MODE,
    APPROVAL_NAME,
    DisposableApprovalObservationResultV7,
    DisposableApprovalRootV7,
)
from scripts.stage_c_transaction.disposable_c20_lock_owner_v7 import (  # noqa: E402
    DisposableC20LockOwnerV7,
)
from scripts.stage_c_transaction.disposable_canonical_lease_binder_v7 import (  # noqa: E402
    DisposableCanonicalLeaseBinderV7,
)
from scripts.stage_c_transaction.disposable_committed_approval_promoter_v7 import (  # noqa: E402
    PRIVATE_PREFIX,
    DisposableCommittedApprovalPromoterV7,
    DisposableCommittedPromotionDispositionV7,
)
from scripts.stage_c_transaction.disposable_temporary_approval_publisher_v7 import (  # noqa: E402
    DisposableTemporaryApprovalPublisherV7,
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


class OneShotFault:
    def __init__(self, point: str) -> None:
        self.point = point
        self.triggered = False

    def __call__(self, observed: str) -> None:
        if observed == self.point and not self.triggered:
            self.triggered = True
            raise RuntimeError(f"injected fault at {observed}")


class StageCDisposableCommittedApprovalPromotionV7Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = PROMOTER_MODULE.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    @contextmanager
    def _stack(self, *, fault_hook=None, seed_temporary: bool = True):
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
                transaction = TransactionIdentity("stage-c21-disposable-promotion")
                binding = ApprovalAuthorityBindingV7(
                    transaction=transaction,
                    snapshot=SnapshotIdentity(
                        "stage-c21-disposable-promotion-snapshot"
                    ),
                    package=package,
                    production_lock_path=str(owner.lock_path),
                    lock_lease_id=owner.lease_id,
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
                    created_at="2026-08-06T01:20:00Z",
                )
                committed = plan_committed_approval_v7(
                    temporary,
                    commit_manifest_sha256=HASH_F,
                    committed_at="2026-08-06T01:21:00Z",
                )
                approval_root = DisposableApprovalRootV7(owner)
                if seed_temporary:
                    published = DisposableTemporaryApprovalPublisherV7(
                        owner,
                        approval_root,
                        temporary,
                        committed,
                    ).publish()
                    self.assertIs(published.status, AdapterStatus.PASS)
                promoter = DisposableCommittedApprovalPromoterV7(
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
                    promoter,
                    temporary,
                    committed,
                )
            finally:
                if approval_root is not None and not approval_root.closed:
                    approval_root.close()
                if owner.lock_held:
                    owner.close_owner()

    @staticmethod
    def _private_names(approval_root: DisposableApprovalRootV7) -> list[Path]:
        return sorted(
            (
                item
                for item in approval_root.path.iterdir()
                if item.name.startswith(PRIVATE_PREFIX)
            ),
            key=lambda item: item.name,
        )

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

    def test_success_exchanges_exact_inodes_and_removes_parked_temporary(self) -> None:
        identities: dict[str, tuple[int, int]] = {}

        def record(point: str) -> None:
            if point == "after-candidate-fsync":
                private = self._private_names(approval_root)[0]
                info = private.stat()
                identities["candidate"] = (info.st_dev, info.st_ino)
            elif point == "after-exchange":
                public = approval_root.approval_path.stat()
                private = self._private_names(approval_root)[0].stat()
                identities["exchanged-public"] = (public.st_dev, public.st_ino)
                identities["parked-temporary"] = (private.st_dev, private.st_ino)

        with self._stack(fault_hook=record) as stack:
            _laboratory, owner, approval_root, promoter, temporary, committed = stack
            original = approval_root.approval_path.stat()
            original_identity = (original.st_dev, original.st_ino)
            result = promoter.promote()
            self.assertIs(result.status, AdapterStatus.PASS)
            self.assertIs(
                result.disposition,
                DisposableCommittedPromotionDispositionV7.COMMITTED_PROMOTED,
            )
            self.assertIs(result.observed_state, ApprovalObservedStateV7.EXACT_COMMITTED)
            self.assertFalse(result.reconciled_after_exception)
            self.assertTrue(result.public_committed_identity_proved)
            self.assertTrue(result.private_name_absent)
            observed = approval_root.observe_public()
            self.assertIs(observed.status, AdapterStatus.PASS)
            assert observed.payload is not None
            self.assertEqual(observed.payload.raw_content, committed.encoded_bytes)
            self.assertEqual(
                (observed.payload.device, observed.payload.inode),
                identities["candidate"],
            )
            self.assertEqual(
                identities["exchanged-public"],
                identities["candidate"],
            )
            self.assertEqual(identities["parked-temporary"], original_identity)
            self.assertNotEqual(temporary.encoded_bytes, committed.encoded_bytes)
            self.assertEqual(self._private_names(approval_root), [])
            self._assert_independent_lock_blocked(owner)

    def test_every_preexchange_fault_retains_original_temporary_and_cleans_candidate(self) -> None:
        points = (
            "before-public-temporary-open",
            "after-public-temporary-open",
            "after-public-temporary-read",
            "before-candidate-create",
            "after-candidate-create",
            "after-candidate-write",
            "after-candidate-truncate",
            "after-candidate-fsync",
            "before-final-exchange-name-recheck",
        )
        for point in points:
            with self.subTest(point=point), self._stack(
                fault_hook=OneShotFault(point)
            ) as stack:
                _laboratory, owner, approval_root, promoter, temporary, _committed = stack
                before = approval_root.approval_path.stat()
                result = promoter.promote()
                self.assertIs(result.status, AdapterStatus.FAIL)
                self.assertIs(
                    result.disposition,
                    DisposableCommittedPromotionDispositionV7.TEMPORARY_RETAINED_RECOVERY,
                )
                self.assertTrue(result.reviewed_retry_permitted)
                self.assertTrue(result.public_temporary_identity_proved)
                after = approval_root.approval_path.stat()
                self.assertEqual((before.st_dev, before.st_ino), (after.st_dev, after.st_ino))
                self.assertEqual(approval_root.approval_path.read_bytes(), temporary.encoded_bytes)
                self.assertEqual(self._private_names(approval_root), [])
                self._assert_independent_lock_blocked(owner)

    def test_partial_candidate_write_is_removed_by_tracked_inode(self) -> None:
        with self._stack() as stack:
            _laboratory, owner, approval_root, promoter, temporary, _committed = stack
            real_pwrite = os.pwrite
            calls = 0

            def partial_then_fail(fd: int, payload, offset: int) -> int:
                nonlocal calls
                calls += 1
                if calls == 1:
                    partial = bytes(payload[: max(1, len(payload) // 3)])
                    return real_pwrite(fd, partial, offset)
                raise OSError("injected partial committed candidate write")

            with patch.object(promoter_module.os, "pwrite", side_effect=partial_then_fail):
                result = promoter.promote()
            self.assertIs(
                result.disposition,
                DisposableCommittedPromotionDispositionV7.TEMPORARY_RETAINED_RECOVERY,
            )
            self.assertEqual(approval_root.approval_path.read_bytes(), temporary.encoded_bytes)
            self.assertEqual(self._private_names(approval_root), [])
            self._assert_independent_lock_blocked(owner)

    def test_every_postexchange_fault_reconciles_forward_without_second_exchange(self) -> None:
        points = (
            "after-exchange",
            "before-exchange-directory-fsync",
            "after-exchange-directory-fsync",
            "before-committed-observation",
            "after-committed-observation",
            "before-parked-temporary-unlink",
            "after-parked-temporary-unlink",
            "before-cleanup-directory-fsync",
            "after-cleanup-directory-fsync",
            "before-final-committed-observation",
            "after-final-committed-observation",
            "before-final-owner-verification",
            "after-final-owner-verification",
        )
        for point in points:
            with self.subTest(point=point), self._stack(
                fault_hook=OneShotFault(point)
            ) as stack:
                _laboratory, owner, approval_root, promoter, _temporary, committed = stack
                real_exchange = promoter_module._rename_exchange
                exchanges = 0

                def counted_exchange(dir_fd: int, private_name: str) -> None:
                    nonlocal exchanges
                    exchanges += 1
                    real_exchange(dir_fd, private_name)

                with patch.object(
                    promoter_module,
                    "_rename_exchange",
                    side_effect=counted_exchange,
                ):
                    result = promoter.promote()
                self.assertIs(result.status, AdapterStatus.PASS)
                self.assertIs(
                    result.disposition,
                    DisposableCommittedPromotionDispositionV7.COMMITTED_PROMOTED,
                )
                self.assertTrue(result.reconciled_after_exception)
                self.assertEqual(exchanges, 1)
                self.assertEqual(approval_root.approval_path.read_bytes(), committed.encoded_bytes)
                self.assertEqual(self._private_names(approval_root), [])
                self._assert_independent_lock_blocked(owner)

    def test_exchange_then_raise_is_classified_and_reconciled_forward(self) -> None:
        with self._stack() as stack:
            _laboratory, owner, approval_root, promoter, _temporary, committed = stack
            real_exchange = promoter_module._rename_exchange
            exchanges = 0

            def exchange_then_raise(dir_fd: int, private_name: str) -> None:
                nonlocal exchanges
                exchanges += 1
                real_exchange(dir_fd, private_name)
                raise RuntimeError("injected exception after successful syscall")

            with patch.object(
                promoter_module,
                "_rename_exchange",
                side_effect=exchange_then_raise,
            ):
                result = promoter.promote()
            self.assertIs(result.status, AdapterStatus.PASS)
            self.assertTrue(result.reconciled_after_exception)
            self.assertEqual(exchanges, 1)
            self.assertEqual(approval_root.approval_path.read_bytes(), committed.encoded_bytes)
            self.assertEqual(self._private_names(approval_root), [])
            self._assert_independent_lock_blocked(owner)

    def test_failed_first_directory_fsync_is_repaired_before_success(self) -> None:
        with self._stack() as stack:
            _laboratory, owner, approval_root, promoter, _temporary, committed = stack
            real_fsync = os.fsync
            directory_fd = approval_root._borrow_directory_descriptor_for_publisher()
            failed = False

            def fail_first_directory_fsync(fd: int) -> None:
                nonlocal failed
                if fd == directory_fd and not failed:
                    failed = True
                    raise OSError("injected first directory fsync failure")
                real_fsync(fd)

            with patch.object(
                promoter_module.os,
                "fsync",
                side_effect=fail_first_directory_fsync,
            ):
                result = promoter.promote()
            self.assertTrue(failed)
            self.assertIs(result.status, AdapterStatus.PASS)
            self.assertTrue(result.reconciled_after_exception)
            self.assertEqual(approval_root.approval_path.read_bytes(), committed.encoded_bytes)
            self.assertEqual(self._private_names(approval_root), [])
            self._assert_independent_lock_blocked(owner)

    def test_transient_observation_failure_after_exchange_recovers_forward(self) -> None:
        with self._stack() as stack:
            _laboratory, owner, approval_root, promoter, _temporary, committed = stack
            real_observe = approval_root.observe_public
            calls = 0

            def fail_committed_observation_once():
                nonlocal calls
                calls += 1
                if calls == 2:
                    return DisposableApprovalObservationResultV7(
                        status=AdapterStatus.FAIL,
                        detail="injected committed observation failure",
                    )
                return real_observe()

            with patch.object(
                approval_root,
                "observe_public",
                side_effect=fail_committed_observation_once,
            ):
                result = promoter.promote()
            self.assertIs(result.status, AdapterStatus.PASS)
            self.assertTrue(result.reconciled_after_exception)
            self.assertEqual(approval_root.approval_path.read_bytes(), committed.encoded_bytes)
            self.assertEqual(self._private_names(approval_root), [])
            self._assert_independent_lock_blocked(owner)

    def test_exact_committed_at_entry_is_refused_not_idempotently_accepted(self) -> None:
        with self._stack() as stack:
            _laboratory, owner, approval_root, promoter, temporary, committed = stack
            self.assertIs(promoter.promote().status, AdapterStatus.PASS)
            before = approval_root.approval_path.stat()
            second = DisposableCommittedApprovalPromoterV7(
                owner,
                approval_root,
                temporary,
                committed,
            )
            result = second.promote()
            self.assertIs(result.status, AdapterStatus.FAIL)
            self.assertIs(
                result.disposition,
                DisposableCommittedPromotionDispositionV7.MANUAL_RECONCILIATION,
            )
            self.assertIs(result.observed_state, ApprovalObservedStateV7.EXACT_COMMITTED)
            after = approval_root.approval_path.stat()
            self.assertEqual((before.st_dev, before.st_ino), (after.st_dev, after.st_ino))
            self.assertEqual(approval_root.approval_path.read_bytes(), committed.encoded_bytes)
            self.assertEqual(self._private_names(approval_root), [])
            self._assert_independent_lock_blocked(owner)

    def test_absent_committed_mismatched_noncanonical_wrong_mode_and_symlink_are_untouched(self) -> None:
        cases = ("absent", "committed", "mismatched", "noncanonical", "wrong-mode", "symlink")
        for case in cases:
            with self.subTest(case=case), self._stack(seed_temporary=False) as stack:
                _laboratory, owner, approval_root, promoter, temporary, committed = stack
                path = approval_root.approval_path
                expected_bytes = None
                expected_identity = None
                if case == "committed":
                    path.write_bytes(committed.encoded_bytes)
                    path.chmod(APPROVAL_MODE)
                elif case == "mismatched":
                    path.write_bytes(b"different\n")
                    path.chmod(APPROVAL_MODE)
                elif case == "noncanonical":
                    path.write_bytes(temporary.encoded_bytes.rstrip(b"\n") + b" \n")
                    path.chmod(APPROVAL_MODE)
                elif case == "wrong-mode":
                    path.write_bytes(temporary.encoded_bytes)
                    path.chmod(0o644)
                elif case == "symlink":
                    path.symlink_to(owner.lock_path)
                if path.exists() or path.is_symlink():
                    info = path.lstat()
                    expected_identity = (info.st_dev, info.st_ino)
                    if not path.is_symlink():
                        expected_bytes = path.read_bytes()
                result = promoter.promote()
                self.assertIs(result.status, AdapterStatus.FAIL)
                self.assertIs(
                    result.disposition,
                    DisposableCommittedPromotionDispositionV7.MANUAL_RECONCILIATION,
                )
                self.assertEqual(self._private_names(approval_root), [])
                if case == "absent":
                    self.assertFalse(path.exists())
                else:
                    info = path.lstat()
                    self.assertEqual((info.st_dev, info.st_ino), expected_identity)
                    if case == "symlink":
                        self.assertTrue(path.is_symlink())
                    else:
                        self.assertEqual(path.read_bytes(), expected_bytes)
                self._assert_independent_lock_blocked(owner)

    def test_public_substitution_before_exchange_is_detected_and_not_unlinked(self) -> None:
        replacement_identity = None

        def substitute(point: str) -> None:
            nonlocal replacement_identity
            if point != "before-final-exchange-name-recheck":
                return
            approval_root.approval_path.unlink()
            approval_root.approval_path.write_bytes(temporary.encoded_bytes)
            approval_root.approval_path.chmod(APPROVAL_MODE)
            info = approval_root.approval_path.stat()
            replacement_identity = (info.st_dev, info.st_ino)
            raise RuntimeError("injected public temporary substitution")

        with self._stack(fault_hook=substitute) as stack:
            _laboratory, owner, approval_root, promoter, temporary, _committed = stack
            result = promoter.promote()
            self.assertIs(
                result.disposition,
                DisposableCommittedPromotionDispositionV7.MANUAL_RECONCILIATION,
            )
            info = approval_root.approval_path.stat()
            self.assertEqual((info.st_dev, info.st_ino), replacement_identity)
            self.assertEqual(approval_root.approval_path.read_bytes(), temporary.encoded_bytes)
            self.assertGreaterEqual(len(self._private_names(approval_root)), 1)
            self._assert_independent_lock_blocked(owner)

    def test_private_substitution_before_exchange_is_detected_and_not_unlinked(self) -> None:
        replacement_identity = None

        def substitute(point: str) -> None:
            nonlocal replacement_identity
            if point != "before-final-exchange-name-recheck":
                return
            private = self._private_names(approval_root)[0]
            private.unlink()
            private.write_bytes(committed.encoded_bytes)
            private.chmod(APPROVAL_MODE)
            info = private.stat()
            replacement_identity = (info.st_dev, info.st_ino)
            raise RuntimeError("injected private candidate substitution")

        with self._stack(fault_hook=substitute) as stack:
            _laboratory, owner, approval_root, promoter, temporary, committed = stack
            result = promoter.promote()
            self.assertIs(
                result.disposition,
                DisposableCommittedPromotionDispositionV7.MANUAL_RECONCILIATION,
            )
            private = self._private_names(approval_root)[0]
            info = private.stat()
            self.assertEqual((info.st_dev, info.st_ino), replacement_identity)
            self.assertEqual(private.read_bytes(), committed.encoded_bytes)
            self.assertEqual(approval_root.approval_path.read_bytes(), temporary.encoded_bytes)
            self._assert_independent_lock_blocked(owner)

    def test_exact_committed_bytes_on_different_inode_require_forward_recovery(self) -> None:
        replacement_identity = None

        def substitute(point: str) -> None:
            nonlocal replacement_identity
            if point != "after-exchange":
                return
            approval_root.approval_path.unlink()
            approval_root.approval_path.write_bytes(committed.encoded_bytes)
            approval_root.approval_path.chmod(APPROVAL_MODE)
            info = approval_root.approval_path.stat()
            replacement_identity = (info.st_dev, info.st_ino)
            raise RuntimeError("injected committed public substitution")

        with self._stack(fault_hook=substitute) as stack:
            _laboratory, owner, approval_root, promoter, _temporary, committed = stack
            result = promoter.promote()
            self.assertIs(
                result.disposition,
                DisposableCommittedPromotionDispositionV7.COMMITTED_FORWARD_RECOVERY_REQUIRED,
            )
            self.assertTrue(result.forward_recovery_required)
            self.assertFalse(result.public_committed_identity_proved)
            info = approval_root.approval_path.stat()
            self.assertEqual((info.st_dev, info.st_ino), replacement_identity)
            self.assertEqual(approval_root.approval_path.read_bytes(), committed.encoded_bytes)
            self.assertGreaterEqual(len(self._private_names(approval_root)), 1)
            self._assert_independent_lock_blocked(owner)

    def test_lost_owner_authority_blocks_promotion(self) -> None:
        with self._stack() as stack:
            _laboratory, owner, approval_root, promoter, temporary, _committed = stack
            before = approval_root.approval_path.stat()
            owner.close_owner()
            result = promoter.promote()
            self.assertIs(result.status, AdapterStatus.FAIL)
            self.assertIs(
                result.disposition,
                DisposableCommittedPromotionDispositionV7.MANUAL_RECONCILIATION,
            )
            after = approval_root.approval_path.stat()
            self.assertEqual((before.st_dev, before.st_ino), (after.st_dev, after.st_ino))
            self.assertEqual(approval_root.approval_path.read_bytes(), temporary.encoded_bytes)
            self.assertEqual(self._private_names(approval_root), [])

    def test_result_is_frozen_and_rejects_inconsistent_authority_flags(self) -> None:
        with self._stack() as stack:
            _laboratory, _owner, _approval_root, promoter, _temporary, _committed = stack
            result = promoter.promote()
            with self.assertRaises(FrozenInstanceError):
                result.detail = "changed"  # type: ignore[misc]
            with self.assertRaises(ValueError):
                promoter_module.DisposableCommittedApprovalPromotionResultV7(
                    status=AdapterStatus.PASS,
                    disposition=(
                        DisposableCommittedPromotionDispositionV7.COMMITTED_PROMOTED
                    ),
                    observed_state=ApprovalObservedStateV7.EXACT_COMMITTED,
                    detail="invalid",
                    temporary_encoded_sha256=HASH_A,
                    committed_encoded_sha256=HASH_B,
                    reconciled_after_exception=False,
                    reviewed_retry_permitted=False,
                    forward_recovery_required=False,
                    manual_reconciliation_required=False,
                    owner_lock_remains_held=True,
                    private_name_absent=False,
                    public_temporary_identity_proved=False,
                    public_committed_identity_proved=True,
                )

    def test_module_has_one_forward_exchange_and_no_production_or_reverse_boundary(self) -> None:
        imported = {
            alias.name.split(".")[0]
            for node in self.tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(
            imported.isdisjoint(
                {"argparse", "socket", "subprocess", "sys"}
            )
        )
        exchange_calls = 0
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.assertNotIn("dispatch", node.name.lower())
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "_rename_exchange":
                    exchange_calls += 1
                if isinstance(node.func, ast.Attribute):
                    self.assertNotIn(
                        node.func.attr,
                        {
                            "flock",
                            "rename",
                            "replace",
                            "link",
                            "dup",
                            "dup2",
                            "system",
                            "run",
                            "popen",
                        },
                    )
                    if node.func.attr == "unlink" and node.args:
                        self.assertFalse(
                            isinstance(node.args[0], ast.Name)
                            and node.args[0].id == "APPROVAL_NAME"
                        )
        self.assertEqual(exchange_calls, 1)
        self.assertNotIn("replace_exact", self.source)
        self.assertNotIn("exchange back", self.source.lower())
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
        transaction = TransactionIdentity("still-blocked")
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
