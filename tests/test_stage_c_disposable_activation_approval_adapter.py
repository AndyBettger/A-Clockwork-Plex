from __future__ import annotations

import fcntl
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from stage_c_runtime_authority.approval_store import ApprovalStore
from stage_c_runtime_authority.model import (
    ActivationApprovalRecord,
    ApprovalPhase,
    RuntimeAuthorityError,
)
from stage_c_transaction.disposable_activation_approval_adapter import (
    DisposableActivationApprovalLifecycleAdapter,
    create_disposable_root,
)
from stage_c_transaction.production_adapter_contract import (
    PackageFingerprint,
    ProductionAdapterBlocked,
    TransactionIdentity,
)
from stage_c_transaction.production_adapter_lifecycle_v7 import (
    ActivationApprovalLifecycleOperation,
    BlockedProductionAdapterV7,
    ProductionAdapterV7,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
HASH_E = "e" * 64
HASH_F = "f" * 64


class InjectedFault(RuntimeError):
    pass


class OneShotFault:
    def __init__(self, target: str):
        self.target = target
        self.points: list[str] = []
        self.fired = False

    def __call__(self, point: str) -> None:
        self.points.append(point)
        if point == self.target and not self.fired:
            self.fired = True
            raise InjectedFault(point)


def temporary_record(
    transaction: TransactionIdentity,
    package: PackageFingerprint,
    *,
    lease_id: str = "stage-c21-disposable-lease",
) -> ActivationApprovalRecord:
    return ActivationApprovalRecord(
        schema_version=1,
        phase=ApprovalPhase.TEMPORARY,
        transaction_id=transaction.value,
        lock_lease_id=lease_id,
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
        created_at="2026-08-05T20:00:00Z",
        committed_at=None,
    )


class StageCDisposableActivationApprovalAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transaction = TransactionIdentity("stage-c21-disposable-transaction")
        self.package = PackageFingerprint(HASH_A)

    def _new_adapter(
        self,
        *,
        fault_hook=None,
        timestamp: str = "2026-08-05T20:01:00Z",
        transaction: TransactionIdentity | None = None,
        package: PackageFingerprint | None = None,
        record: ActivationApprovalRecord | None = None,
    ) -> DisposableActivationApprovalLifecycleAdapter:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        root.chmod(0o700)
        selected_transaction = transaction or self.transaction
        selected_package = package or self.package
        selected_record = record or temporary_record(
            selected_transaction,
            selected_package,
        )
        adapter = DisposableActivationApprovalLifecycleAdapter(
            root,
            transaction=selected_transaction,
            package=selected_package,
            temporary_approval=selected_record,
            fault_hook=fault_hook,
            timestamp_factory=lambda: timestamp,
        )
        self.addCleanup(self._force_cleanup, adapter)
        return adapter

    @staticmethod
    def _force_cleanup(
        adapter: DisposableActivationApprovalLifecycleAdapter,
    ) -> None:
        if adapter.closed:
            return
        approval = adapter.state_root / "activation-approved"
        try:
            approval.unlink()
        except FileNotFoundError:
            pass
        parked = adapter.lock_path.with_name(adapter.lock_path.name + ".parked-test")
        if parked.exists():
            try:
                adapter.lock_path.unlink()
            except FileNotFoundError:
                pass
            parked.rename(adapter.lock_path)
        try:
            adapter.close_disposable_transaction()
            return
        except BaseException:
            pass
        try:
            descriptor = os.fstat(adapter._lock_fd)
            path_info = adapter.lock_path.lstat()
            if (
                descriptor.st_dev == path_info.st_dev
                and descriptor.st_ino == path_info.st_ino
            ):
                adapter.lock_path.unlink()
        except OSError:
            pass
        try:
            fcntl.flock(adapter._lock_fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(adapter._lock_fd)
        except OSError:
            pass
        adapter._closed = True

    def _bind_and_publish(
        self,
        adapter: DisposableActivationApprovalLifecycleAdapter,
    ) -> None:
        adapter.bind_production_lock_lease(self.transaction)
        adapter.publish_temporary_activation_approval(self.transaction)

    def test_root_must_be_existing_real_empty_owned_0700_absolute(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "root"
            root.mkdir(mode=0o700)
            record = temporary_record(self.transaction, self.package)

            with self.assertRaisesRegex(RuntimeAuthorityError, "absolute"):
                DisposableActivationApprovalLifecycleAdapter(
                    Path("relative-root"),
                    transaction=self.transaction,
                    package=self.package,
                    temporary_approval=record,
                )

            root.chmod(0o755)
            with self.assertRaisesRegex(RuntimeAuthorityError, "mode 0700"):
                DisposableActivationApprovalLifecycleAdapter(
                    root,
                    transaction=self.transaction,
                    package=self.package,
                    temporary_approval=record,
                )

            root.chmod(0o700)
            (root / "occupied").write_text("x", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeAuthorityError, "must be empty"):
                DisposableActivationApprovalLifecycleAdapter(
                    root,
                    transaction=self.transaction,
                    package=self.package,
                    temporary_approval=record,
                )

            target = parent / "target"
            target.mkdir(mode=0o700)
            symlink = parent / "symlink"
            symlink.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(RuntimeAuthorityError, "real directory"):
                DisposableActivationApprovalLifecycleAdapter(
                    symlink,
                    transaction=self.transaction,
                    package=self.package,
                    temporary_approval=record,
                )

    def test_helper_creates_one_fresh_0700_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = create_disposable_root(parent)
            self.assertEqual(root.parent, parent)
            self.assertTrue(root.is_dir())
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            self.assertEqual(list(root.iterdir()), [])

    def test_constructor_creates_empty_held_0600_lock_only_under_root(self) -> None:
        adapter = self._new_adapter()
        self.assertTrue(adapter.lock_path.is_relative_to(adapter.root))
        self.assertTrue(adapter.state_root.is_relative_to(adapter.root))
        self.assertEqual(adapter.lock_path.read_bytes(), b"")
        self.assertEqual(stat.S_IMODE(adapter.lock_path.stat().st_mode), 0o600)
        second = os.open(adapter.lock_path, os.O_RDWR | os.O_NOFOLLOW)
        try:
            with self.assertRaises(BlockingIOError):
                fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(second)

    def test_only_four_v7_operations_are_overridden_and_v1_v6_stay_blocked(self) -> None:
        adapter = self._new_adapter()
        self.assertIsInstance(adapter, BlockedProductionAdapterV7)
        self.assertIsInstance(adapter, ProductionAdapterV7)
        for name in (
            "bind_production_lock_lease",
            "publish_temporary_activation_approval",
            "remove_temporary_activation_approval",
            "promote_committed_activation_approval",
        ):
            self.assertIn(name, DisposableActivationApprovalLifecycleAdapter.__dict__)
        with self.assertRaises(ProductionAdapterBlocked):
            adapter.capture_filesystem_state(self.transaction)
        with self.assertRaises(ProductionAdapterBlocked):
            adapter.select_split_bus_route(self.transaction)
        with self.assertRaises(ProductionAdapterBlocked):
            adapter.write_commit_manifest(self.transaction)

    def test_bind_writes_canonical_lease_without_changing_inode(self) -> None:
        adapter = self._new_adapter()
        before = adapter.lock_path.stat()
        result = adapter.bind_production_lock_lease(self.transaction)
        after = adapter.lock_path.stat()
        self.assertIs(
            result.operation,
            ActivationApprovalLifecycleOperation.BIND_PRODUCTION_LOCK_LEASE,
        )
        self.assertEqual(
            adapter.lock_path.read_bytes(),
            b"stage-c21-disposable-lease\n",
        )
        self.assertEqual((before.st_dev, before.st_ino), (after.st_dev, after.st_ino))
        self.assertEqual(result.payload.lock_inode, before.st_ino)
        self.assertTrue(adapter.lease_bound)
        reconciled = adapter.bind_production_lock_lease(self.transaction)
        self.assertIn("reconciled", reconciled.detail)

    def test_wrong_transaction_or_substituted_lock_is_refused(self) -> None:
        adapter = self._new_adapter()
        wrong = TransactionIdentity("wrong-transaction")
        with self.assertRaisesRegex(RuntimeAuthorityError, "transaction identity"):
            adapter.bind_production_lock_lease(wrong)

        adapter.bind_production_lock_lease(self.transaction)
        parked = adapter.lock_path.with_name(adapter.lock_path.name + ".parked-test")
        adapter.lock_path.rename(parked)
        adapter.lock_path.write_text("replacement\n", encoding="ascii")
        adapter.lock_path.chmod(0o600)
        with self.assertRaisesRegex(RuntimeAuthorityError, "substituted"):
            adapter.publish_temporary_activation_approval(self.transaction)
        self.assertEqual(adapter.lock_path.read_text(encoding="ascii"), "replacement\n")

    def test_temporary_publish_is_exact_non_bootable_and_idempotent(self) -> None:
        adapter = self._new_adapter()
        adapter.bind_production_lock_lease(self.transaction)
        first = adapter.publish_temporary_activation_approval(self.transaction)
        self.assertIs(
            first.operation,
            ActivationApprovalLifecycleOperation.PUBLISH_TEMPORARY_ACTIVATION_APPROVAL,
        )
        self.assertFalse(first.payload.boot_eligible)
        self.assertEqual(first.payload.record_sha256, temporary_record(self.transaction, self.package).record_sha256)
        stored = ApprovalStore(adapter.state_root).read()
        self.assertIs(stored.phase, ApprovalPhase.TEMPORARY)
        second = adapter.publish_temporary_activation_approval(self.transaction)
        self.assertIn("reconciled", second.detail)
        self.assertEqual(ApprovalStore(adapter.state_root).read(), stored)

    def test_publish_fault_before_link_leaves_absence_and_retry_succeeds(self) -> None:
        fault = OneShotFault("new-temp-fsynced")
        adapter = self._new_adapter(fault_hook=fault)
        adapter.bind_production_lock_lease(self.transaction)
        with self.assertRaises(InjectedFault):
            adapter.publish_temporary_activation_approval(self.transaction)
        with self.assertRaisesRegex(RuntimeAuthorityError, "absent"):
            ApprovalStore(adapter.state_root).read()
        result = adapter.publish_temporary_activation_approval(self.transaction)
        self.assertTrue(result.payload.atomically_published)
        self.assertEqual(
            [path.name for path in adapter.state_root.iterdir()],
            ["activation-approved"],
        )

    def test_publish_fault_after_public_link_reconciles_same_call(self) -> None:
        fault = OneShotFault("new-linked")
        adapter = self._new_adapter(fault_hook=fault)
        adapter.bind_production_lock_lease(self.transaction)
        result = adapter.publish_temporary_activation_approval(self.transaction)
        self.assertIn("interrupted", result.detail)
        self.assertEqual(
            ApprovalStore(adapter.state_root).read(),
            temporary_record(self.transaction, self.package),
        )
        self.assertEqual(
            [path.name for path in adapter.state_root.iterdir()],
            ["activation-approved"],
        )

    def test_removal_fault_before_unlink_preserves_record_and_retry_succeeds(self) -> None:
        fault = OneShotFault("before-temporary-removal")
        adapter = self._new_adapter(fault_hook=fault)
        self._bind_and_publish(adapter)
        with self.assertRaises(InjectedFault):
            adapter.remove_temporary_activation_approval(self.transaction)
        self.assertIs(ApprovalStore(adapter.state_root).read().phase, ApprovalPhase.TEMPORARY)
        result = adapter.remove_temporary_activation_approval(self.transaction)
        self.assertTrue(result.payload.approval_absent)

    def test_removal_fault_after_unlink_reconciles_exact_absence(self) -> None:
        fault = OneShotFault("after-temporary-removal")
        adapter = self._new_adapter(fault_hook=fault)
        self._bind_and_publish(adapter)
        result = adapter.remove_temporary_activation_approval(self.transaction)
        self.assertIn("interrupted", result.detail)
        self.assertTrue(result.payload.exact_record_removed)
        with self.assertRaisesRegex(RuntimeAuthorityError, "absent"):
            ApprovalStore(adapter.state_root).read()

    def test_removal_refuses_tampered_or_already_absent_record(self) -> None:
        adapter = self._new_adapter()
        self._bind_and_publish(adapter)
        approval_path = adapter.state_root / "activation-approved"
        approval_path.write_text("{}\n", encoding="utf-8")
        with self.assertRaises(RuntimeAuthorityError):
            adapter.remove_temporary_activation_approval(self.transaction)
        approval_path.unlink()
        with self.assertRaisesRegex(RuntimeAuthorityError, "already absent"):
            adapter.remove_temporary_activation_approval(self.transaction)

    def test_promotion_requires_immutable_commit_digest_and_changes_record_identity(self) -> None:
        adapter = self._new_adapter()
        self._bind_and_publish(adapter)
        with self.assertRaisesRegex(RuntimeAuthorityError, "recorded commit manifest"):
            adapter.promote_committed_activation_approval(self.transaction)
        with self.assertRaisesRegex(RuntimeAuthorityError, "lowercase SHA-256"):
            adapter.record_commit_manifest_for_rehearsal(self.transaction, "bad")
        adapter.record_commit_manifest_for_rehearsal(self.transaction, HASH_F)
        adapter.record_commit_manifest_for_rehearsal(self.transaction, HASH_F)
        with self.assertRaisesRegex(RuntimeAuthorityError, "cannot be replaced"):
            adapter.record_commit_manifest_for_rehearsal(self.transaction, HASH_A)
        result = adapter.promote_committed_activation_approval(self.transaction)
        committed = ApprovalStore(adapter.state_root).read()
        self.assertIs(committed.phase, ApprovalPhase.COMMITTED)
        self.assertEqual(committed.commit_manifest_sha256, HASH_F)
        self.assertEqual(committed.committed_at, "2026-08-05T20:01:00Z")
        self.assertNotEqual(
            result.payload.temporary_record_sha256,
            result.payload.committed_record_sha256,
        )
        self.assertTrue(result.payload.boot_eligible)

    def test_promotion_faults_restore_exact_temporary_record_then_retry(self) -> None:
        for point in ("replacement-temp-fsynced", "replacement-exchanged"):
            with self.subTest(point=point):
                fault = OneShotFault(point)
                adapter = self._new_adapter(fault_hook=fault)
                self._bind_and_publish(adapter)
                adapter.record_commit_manifest_for_rehearsal(self.transaction, HASH_F)
                with self.assertRaises(InjectedFault):
                    adapter.promote_committed_activation_approval(self.transaction)
                self.assertEqual(
                    ApprovalStore(adapter.state_root).read(),
                    temporary_record(self.transaction, self.package),
                )
                result = adapter.promote_committed_activation_approval(self.transaction)
                self.assertTrue(result.payload.atomically_promoted)
                self.assertIs(ApprovalStore(adapter.state_root).read().phase, ApprovalPhase.COMMITTED)

    def test_promotion_refuses_non_exact_temporary_record(self) -> None:
        adapter = self._new_adapter()
        self._bind_and_publish(adapter)
        adapter.record_commit_manifest_for_rehearsal(self.transaction, HASH_F)
        original = ApprovalStore(adapter.state_root).read()
        other = ActivationApprovalRecord(
            **{
                **original.__dict__,
                "active_route_sha256": HASH_A,
            }
        )
        ApprovalStore(adapter.state_root).replace_exact(
            original,
            other,
            lock_held=True,
        )
        with self.assertRaisesRegex(RuntimeAuthorityError, "exact temporary"):
            adapter.promote_committed_activation_approval(self.transaction)

    def test_close_refuses_temporary_approval_and_unlinks_only_exact_lock(self) -> None:
        adapter = self._new_adapter()
        self._bind_and_publish(adapter)
        with self.assertRaisesRegex(RuntimeAuthorityError, "temporary approval exists"):
            adapter.close_disposable_transaction()
        adapter.remove_temporary_activation_approval(self.transaction)
        adapter.close_disposable_transaction()
        self.assertTrue(adapter.closed)
        self.assertFalse(adapter.lock_path.exists())

        substituted = self._new_adapter()
        substituted.bind_production_lock_lease(self.transaction)
        parked = substituted.lock_path.with_name(
            substituted.lock_path.name + ".parked-test"
        )
        substituted.lock_path.rename(parked)
        substituted.lock_path.write_text("replacement\n", encoding="ascii")
        substituted.lock_path.chmod(0o600)
        with self.assertRaisesRegex(RuntimeAuthorityError, "substituted"):
            substituted.close_disposable_transaction()
        self.assertEqual(
            substituted.lock_path.read_text(encoding="ascii"),
            "replacement\n",
        )

    def test_module_is_sandbox_only_without_process_service_audio_or_generic_dispatch(self) -> None:
        source = (
            SCRIPTS
            / "stage_c_transaction/disposable_activation_approval_adapter.py"
        ).read_text(encoding="utf-8")
        self.assertIn("root / LOCK_RELATIVE", source)
        self.assertIn("root / STATE_RELATIVE", source)
        self.assertIn("O_NOFOLLOW", source)
        self.assertIn("O_EXCL", source)
        self.assertIn("flock", source)
        for forbidden in (
            "subprocess",
            "systemctl",
            "aplay",
            "amixer",
            "/dev/snd",
            "/etc/alsa",
            "socket",
            "shell=True",
            "os.system",
            "os.exec",
            "def dispatch",
            "eval(",
            "exec(",
        ):
            self.assertNotIn(forbidden, source)
        for name in (
            "bind_production_lock_lease",
            "publish_temporary_activation_approval",
            "remove_temporary_activation_approval",
            "promote_committed_activation_approval",
        ):
            signature = getattr(
                DisposableActivationApprovalLifecycleAdapter,
                name,
            ).__annotations__
            self.assertEqual(set(signature), {"transaction", "return"})


if __name__ == "__main__":
    unittest.main()
