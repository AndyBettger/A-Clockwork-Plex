from __future__ import annotations

import ast
import errno
import fcntl
import os
import stat
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
OWNER_MODULE = (
    ROOT / "scripts/stage_c_transaction/disposable_c20_lock_owner_v7.py"
)
BINDER_MODULE = (
    ROOT / "scripts/stage_c_transaction/disposable_canonical_lease_binder_v7.py"
)

from scripts.stage_c_transaction.disposable_c20_lock_owner_v7 import (
    DisposableC20LockObservationResultV7,
    DisposableC20LockOwnerFailure,
    DisposableC20LockOwnerV7,
)
from scripts.stage_c_transaction.disposable_canonical_lease_binder_v7 import (
    DisposableCanonicalLeaseBinderV7,
    DisposableCanonicalLeaseBindingResultV7,
    DisposableLeaseBindingDispositionV7,
)
from scripts.stage_c_transaction.production_adapter_contract import AdapterStatus
from scripts.stage_c_transaction.production_adapter_lifecycle_v7 import (
    ALL_OPERATIONS_V7,
)


class InjectedLeaseBindingFailure(RuntimeError):
    pass


class StageCDisposableCanonicalLeaseBindingV7Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.owner_source = OWNER_MODULE.read_text(encoding="utf-8")
        self.binder_source = BINDER_MODULE.read_text(encoding="utf-8")
        self.binder_tree = ast.parse(self.binder_source)

    def _root(self, temporary: str, name: str = "laboratory") -> Path:
        root = Path(temporary) / name
        root.mkdir(mode=0o700)
        root.chmod(0o700)
        return root.resolve()

    def _assert_independent_lock_is_blocked(
        self,
        owner: DisposableC20LockOwnerV7,
    ) -> None:
        fd = os.open(
            owner.lock_path,
            os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        try:
            with self.assertRaises(OSError) as captured:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertIn(captured.exception.errno, (errno.EACCES, errno.EAGAIN))
        finally:
            os.close(fd)

    @staticmethod
    def _fault_at(expected: str):
        def hook(point: str) -> None:
            if point == expected:
                raise InjectedLeaseBindingFailure(expected)

        return hook

    def test_success_binds_exact_bytes_and_owner_alone_releases_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            owner = DisposableC20LockOwnerV7(self._root(temporary))
            try:
                self.assertTrue(owner.lock_held)
                self.assertEqual(owner.lock_path.read_bytes(), b"")
                self._assert_independent_lock_is_blocked(owner)

                binder = DisposableCanonicalLeaseBinderV7(owner)
                result = binder.bind()

                self.assertIs(result.status, AdapterStatus.PASS)
                self.assertIs(
                    result.disposition,
                    DisposableLeaseBindingDispositionV7.CANONICAL_BOUND,
                )
                self.assertFalse(result.reconciled_after_exception)
                self.assertFalse(result.ordinary_rollback_permitted)
                self.assertFalse(result.manual_reconciliation_required)
                self.assertTrue(result.owner_lock_remains_held)
                self.assertEqual(owner.lock_path.read_bytes(), owner.canonical_lease_bytes)
                self.assertEqual(result.canonical_bytes, owner.canonical_lease_bytes)
                self.assertFalse(hasattr(binder, "close"))
                self.assertFalse(hasattr(binder, "release"))
                self._assert_independent_lock_is_blocked(owner)
            finally:
                owner.close_owner()
            self.assertTrue(owner.closed)
            self.assertFalse(owner.lock_path.exists())

    def test_exact_existing_lease_is_idempotent_and_performs_no_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with DisposableC20LockOwnerV7(self._root(temporary)) as owner:
                first = DisposableCanonicalLeaseBinderV7(owner).bind()
                self.assertIs(first.status, AdapterStatus.PASS)
                with patch(
                    "scripts.stage_c_transaction.disposable_canonical_lease_binder_v7.os.ftruncate"
                ) as truncate_mock, patch(
                    "scripts.stage_c_transaction.disposable_canonical_lease_binder_v7.os.pwrite"
                ) as write_mock, patch(
                    "scripts.stage_c_transaction.disposable_canonical_lease_binder_v7.os.fsync"
                ) as fsync_mock:
                    second = DisposableCanonicalLeaseBinderV7(owner).bind()
                self.assertIs(second.status, AdapterStatus.PASS)
                self.assertIn("already bound", second.detail)
                truncate_mock.assert_not_called()
                write_mock.assert_not_called()
                fsync_mock.assert_not_called()
                self._assert_independent_lock_is_blocked(owner)

    def test_every_named_fault_boundary_is_classified_from_observed_bytes(self) -> None:
        expectations = {
            "before-lease-truncate": (
                AdapterStatus.FAIL,
                DisposableLeaseBindingDispositionV7.EMPTY_ROLLBACK_PERMITTED,
                False,
            ),
            "after-lease-truncate": (
                AdapterStatus.FAIL,
                DisposableLeaseBindingDispositionV7.EMPTY_ROLLBACK_PERMITTED,
                False,
            ),
            "after-lease-write": (
                AdapterStatus.PASS,
                DisposableLeaseBindingDispositionV7.CANONICAL_BOUND,
                True,
            ),
            "after-lease-exact-truncate": (
                AdapterStatus.PASS,
                DisposableLeaseBindingDispositionV7.CANONICAL_BOUND,
                True,
            ),
            "after-lease-fsync": (
                AdapterStatus.PASS,
                DisposableLeaseBindingDispositionV7.CANONICAL_BOUND,
                True,
            ),
        }
        for index, (point, expected) in enumerate(expectations.items()):
            with self.subTest(point=point), tempfile.TemporaryDirectory() as temporary:
                with DisposableC20LockOwnerV7(
                    self._root(temporary, f"laboratory-{index}")
                ) as owner:
                    result = DisposableCanonicalLeaseBinderV7(
                        owner,
                        fault_hook=self._fault_at(point),
                    ).bind()
                    self.assertIs(result.status, expected[0])
                    self.assertIs(result.disposition, expected[1])
                    self.assertEqual(result.reconciled_after_exception, expected[2])
                    self.assertTrue(result.owner_lock_remains_held)
                    if expected[1] is DisposableLeaseBindingDispositionV7.EMPTY_ROLLBACK_PERMITTED:
                        self.assertEqual(owner.lock_path.read_bytes(), b"")
                        self.assertTrue(result.ordinary_rollback_permitted)
                    else:
                        self.assertEqual(
                            owner.lock_path.read_bytes(),
                            owner.canonical_lease_bytes,
                        )
                    self._assert_independent_lock_is_blocked(owner)

    def test_short_pwrite_then_failure_requires_manual_reconciliation(self) -> None:
        real_pwrite = os.pwrite
        call_count = 0

        def partial_then_fail(fd: int, payload, offset: int) -> int:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                first = bytes(payload[:3])
                return real_pwrite(fd, first, offset)
            raise OSError("injected pwrite failure")

        with tempfile.TemporaryDirectory() as temporary:
            with DisposableC20LockOwnerV7(self._root(temporary)) as owner:
                with patch(
                    "scripts.stage_c_transaction.disposable_canonical_lease_binder_v7.os.pwrite",
                    side_effect=partial_then_fail,
                ):
                    result = DisposableCanonicalLeaseBinderV7(owner).bind()
                self.assertIs(result.status, AdapterStatus.FAIL)
                self.assertIs(
                    result.disposition,
                    DisposableLeaseBindingDispositionV7.MANUAL_RECONCILIATION,
                )
                self.assertTrue(result.manual_reconciliation_required)
                self.assertFalse(result.ordinary_rollback_permitted)
                self.assertEqual(len(owner.lock_path.read_bytes()), 3)
                self.assertNotEqual(
                    owner.lock_path.read_bytes(),
                    owner.canonical_lease_bytes,
                )
                self._assert_independent_lock_is_blocked(owner)

    def test_malformed_preexisting_content_is_never_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with DisposableC20LockOwnerV7(self._root(temporary)) as owner:
                owner.lock_path.write_bytes(b"not-the-canonical-lease\n")
                owner.lock_path.chmod(0o600)
                result = DisposableCanonicalLeaseBinderV7(owner).bind()
                self.assertIs(result.status, AdapterStatus.FAIL)
                self.assertIs(
                    result.disposition,
                    DisposableLeaseBindingDispositionV7.MANUAL_RECONCILIATION,
                )
                self.assertEqual(
                    owner.lock_path.read_bytes(),
                    b"not-the-canonical-lease\n",
                )
                self._assert_independent_lock_is_blocked(owner)

    def test_owner_closed_before_binding_reports_unavailable_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            owner = DisposableC20LockOwnerV7(self._root(temporary))
            binder = DisposableCanonicalLeaseBinderV7(owner)
            owner.close_owner()
            result = binder.bind()
            self.assertIs(result.status, AdapterStatus.FAIL)
            self.assertIs(
                result.disposition,
                DisposableLeaseBindingDispositionV7.MANUAL_RECONCILIATION,
            )
            self.assertFalse(result.owner_lock_remains_held)
            self.assertIn("no longer holds", result.detail)

    def test_path_substitution_and_mode_change_fail_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            owner = DisposableC20LockOwnerV7(self._root(temporary))
            parked = owner.lock_path.with_name("parked-owner-lock")
            try:
                owner.lock_path.rename(parked)
                owner.lock_path.write_bytes(b"")
                owner.lock_path.chmod(0o600)
                result = DisposableCanonicalLeaseBinderV7(owner).bind()
                self.assertIs(result.status, AdapterStatus.FAIL)
                self.assertIs(
                    result.disposition,
                    DisposableLeaseBindingDispositionV7.MANUAL_RECONCILIATION,
                )
                self.assertIn("substituted", result.detail)
            finally:
                if owner.lock_path.exists():
                    owner.lock_path.unlink()
                parked.rename(owner.lock_path)
                owner.close_owner()

        with tempfile.TemporaryDirectory() as temporary:
            owner = DisposableC20LockOwnerV7(self._root(temporary))
            try:
                owner.lock_path.chmod(0o644)
                result = DisposableCanonicalLeaseBinderV7(owner).bind()
                self.assertIs(result.status, AdapterStatus.FAIL)
                self.assertIn("mode changed", result.detail)
            finally:
                owner.lock_path.chmod(0o600)
                owner.close_owner()

    def test_owner_metadata_mismatch_fails_before_write(self) -> None:
        real_fstat = os.fstat
        with tempfile.TemporaryDirectory() as temporary:
            with DisposableC20LockOwnerV7(self._root(temporary)) as owner:
                owner_fd = owner._borrow_descriptor_for_lease_binder()

                def wrong_owner(fd: int):
                    actual = real_fstat(fd)
                    if fd != owner_fd:
                        return actual
                    return SimpleNamespace(
                        st_dev=actual.st_dev,
                        st_ino=actual.st_ino,
                        st_mode=actual.st_mode,
                        st_uid=actual.st_uid + 1,
                        st_gid=actual.st_gid,
                        st_size=actual.st_size,
                    )

                with patch(
                    "scripts.stage_c_transaction.disposable_c20_lock_owner_v7.os.fstat",
                    side_effect=wrong_owner,
                ):
                    result = DisposableCanonicalLeaseBinderV7(owner).bind()
                self.assertIs(result.status, AdapterStatus.FAIL)
                self.assertIn("owner changed", result.detail)
                self.assertEqual(owner.lock_path.read_bytes(), b"")
                self._assert_independent_lock_is_blocked(owner)

    def test_unavailable_post_write_observation_retains_manual_authority(self) -> None:
        unavailable = DisposableC20LockObservationResultV7(
            status=AdapterStatus.FAIL,
            detail="injected observation failure",
        )
        with tempfile.TemporaryDirectory() as temporary:
            with DisposableC20LockOwnerV7(self._root(temporary)) as owner:
                before = owner.observe()
                with patch.object(
                    owner,
                    "observe",
                    side_effect=[before, unavailable],
                ):
                    result = DisposableCanonicalLeaseBinderV7(owner).bind()
                self.assertIs(result.status, AdapterStatus.FAIL)
                self.assertIs(
                    result.disposition,
                    DisposableLeaseBindingDispositionV7.MANUAL_RECONCILIATION,
                )
                self.assertIn("could not be proved", result.detail)
                self.assertEqual(
                    owner.lock_path.read_bytes(),
                    owner.canonical_lease_bytes,
                )
                self._assert_independent_lock_is_blocked(owner)

    def test_unavailable_exception_reconciliation_never_assumes_success(self) -> None:
        unavailable = DisposableC20LockObservationResultV7(
            status=AdapterStatus.FAIL,
            detail="injected reconciliation observation failure",
        )
        with tempfile.TemporaryDirectory() as temporary:
            with DisposableC20LockOwnerV7(self._root(temporary)) as owner:
                before = owner.observe()
                with patch.object(
                    owner,
                    "observe",
                    side_effect=[before, unavailable],
                ):
                    result = DisposableCanonicalLeaseBinderV7(
                        owner,
                        fault_hook=self._fault_at("after-lease-fsync"),
                    ).bind()
                self.assertIs(result.status, AdapterStatus.FAIL)
                self.assertIs(
                    result.disposition,
                    DisposableLeaseBindingDispositionV7.MANUAL_RECONCILIATION,
                )
                self.assertIn("observation failed", result.detail)
                self.assertTrue(result.owner_lock_remains_held)
                self.assertEqual(
                    owner.lock_path.read_bytes(),
                    owner.canonical_lease_bytes,
                )
                self._assert_independent_lock_is_blocked(owner)

    def test_owner_requires_a_fresh_real_private_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing"
            with self.assertRaises(DisposableC20LockOwnerFailure):
                DisposableC20LockOwnerV7(missing.resolve())

            wrong_mode = Path(temporary) / "wrong-mode"
            wrong_mode.mkdir(mode=0o755)
            wrong_mode.chmod(0o755)
            with self.assertRaises(DisposableC20LockOwnerFailure):
                DisposableC20LockOwnerV7(wrong_mode.resolve())

            nonempty = self._root(temporary, "nonempty")
            (nonempty / "existing").write_text("x", encoding="utf-8")
            with self.assertRaises(DisposableC20LockOwnerFailure):
                DisposableC20LockOwnerV7(nonempty)

    def test_result_is_frozen_and_rejects_inconsistent_recovery_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with DisposableC20LockOwnerV7(self._root(temporary)) as owner:
                result = DisposableCanonicalLeaseBinderV7(owner).bind()
                with self.assertRaises(FrozenInstanceError):
                    result.detail = "changed"  # type: ignore[misc]
                with self.assertRaises(ValueError):
                    DisposableCanonicalLeaseBindingResultV7(
                        status=AdapterStatus.PASS,
                        disposition=(
                            DisposableLeaseBindingDispositionV7.CANONICAL_BOUND
                        ),
                        detail="invalid",
                        lease_id=owner.lease_id,
                        canonical_bytes=owner.canonical_lease_bytes,
                        reconciled_after_exception=False,
                        ordinary_rollback_permitted=True,
                        manual_reconciliation_required=False,
                        owner_lock_remains_held=True,
                    )

    def test_binder_static_boundary_has_no_lock_lifetime_or_production_access(self) -> None:
        self.assertEqual(len(ALL_OPERATIONS_V7), 42)
        forbidden_imports = {
            "argparse",
            "ctypes",
            "fcntl",
            "json",
            "socket",
            "subprocess",
            "sys",
        }
        imported = {
            alias.name.split(".")[0]
            for node in self.binder_tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(imported.isdisjoint(forbidden_imports))
        forbidden_attributes = {
            "open",
            "close",
            "dup",
            "flock",
            "unlink",
            "remove",
            "replace",
            "rename",
            "renameat2",
            "mkdir",
            "rmdir",
            "chmod",
            "chown",
            "system",
            "run",
            "popen",
            "dispatch",
        }
        for node in ast.walk(self.binder_tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.assertNotIn("dispatch", node.name.lower())
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    self.assertNotIn(
                        node.func.id,
                        {"eval", "exec", "open", "getattr", "setattr"},
                    )
                elif isinstance(node.func, ast.Attribute):
                    self.assertNotIn(node.func.attr, forbidden_attributes)
        for forbidden_text in (
            "/run/lock",
            "/var/lib",
            "/etc/alsa",
            "/dev/snd",
            "activation-approved",
            "systemctl",
            "aplay",
            "amixer",
            "CamillaDSP",
            "shell=True",
            "__enter__",
            "__exit__",
            "__del__",
        ):
            self.assertNotIn(forbidden_text, self.binder_source)
        self.assertNotIn("/run/lock", self.owner_source)
        self.assertNotIn("/var/lib", self.owner_source)


if __name__ == "__main__":
    unittest.main()
