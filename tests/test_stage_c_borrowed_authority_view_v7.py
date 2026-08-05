from __future__ import annotations

import ast
import stat
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/stage_c_transaction/borrowed_authority_view_v7.py"

from scripts.stage_c_transaction.borrowed_authority_view_v7 import (
    BorrowedAuthorityViewResultV7,
    BorrowedAuthorityViewV7,
    inspect_borrowed_authority_v7,
)
from scripts.stage_c_transaction.production_adapter_contract import (
    AUTHORITATIVE_TRANSACTION_ROOT,
    PRODUCTION_LOCK_PATH,
    AdapterStatus,
    AuthoritativeTransaction,
    PackageFingerprint,
    ProductionLockLease,
    SnapshotIdentity,
    TransactionAction,
    TransactionIdentity,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v7 import (
    ALL_OPERATIONS_V7,
)
from scripts.stage_c_transaction.production_lock_rehearsal_adapter import (
    HeldLockEvidence,
    ProductionLockFailure,
)
from scripts.stage_c_transaction.route_selection_rollback_rehearsal_adapter import (
    RouteIdentity,
    RouteSelectionRollbackFailure,
)
from scripts.stage_c_transaction.route_selection_rollback_rehearsal_adapter_v2 import (
    RouteSelectionRollbackRehearsalAdapterV2,
)
from scripts.stage_c_transaction.snapshot_core import CURRENT_ALSA_DESTINATION


LOCK_DEVICE = 101
LOCK_INODE = 102
TRANSACTION_DEVICE = 201
TRANSACTION_INODE = 202
ROUTE_DEVICE = 301
ROUTE_INODE = 302
ROUTE_SHA256 = "a" * 64


class StageCBorrowedAuthorityViewV7Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = MODULE.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)
        self.transaction_identity = TransactionIdentity(
            "stage-c20-authority-view-test"
        )
        self.snapshot_identity = SnapshotIdentity(
            "stage-c20-authority-view-snapshot"
        )
        self.package = PackageFingerprint("b" * 64)
        self.transaction = AuthoritativeTransaction(
            transaction=self.transaction_identity,
            snapshot=self.snapshot_identity,
            action=TransactionAction.INSTALL,
            package=self.package,
        )
        self.transaction_path = (
            Path(AUTHORITATIVE_TRANSACTION_ROOT)
            / self.transaction_identity.value
        )
        self.lock_evidence = HeldLockEvidence(
            inode=LOCK_INODE,
            mode=0o600,
            owner_uid=0,
            owner_gid=0,
            contention_proved=True,
        )
        self.route_identity = RouteIdentity(
            device=ROUTE_DEVICE,
            inode=ROUTE_INODE,
            mode=0o644,
            uid=0,
            gid=0,
            digest=ROUTE_SHA256,
        )

    def _owner(self) -> RouteSelectionRollbackRehearsalAdapterV2:
        owner = object.__new__(RouteSelectionRollbackRehearsalAdapterV2)
        owner._lock_fd = 77
        owner._lease = ProductionLockLease(
            path=PRODUCTION_LOCK_PATH,
            lease_id="stage-c20-existing-lease",
        )
        owner._evidence = self.lock_evidence
        owner._package = self.package
        owner._transaction = self.transaction
        owner._transaction_path = self.transaction_path
        owner._transaction_device = TRANSACTION_DEVICE
        owner._transaction_inode = TRANSACTION_INODE
        owner._filesystem_captured = True
        owner._service_captured = True
        owner._mixer_captured = True
        owner._loopback_captured = True
        owner._dac_captured = True
        owner._route_selected = True
        owner._route_selected_once = True
        owner._route_restored = False
        owner._route_selection_count = 1
        owner._route_candidate = self.route_identity
        return owner

    def _success_patches(self):
        return (
            patch(
                "scripts.stage_c_transaction.borrowed_authority_view_v7._descriptor_evidence",
                return_value=self.lock_evidence,
            ),
            patch(
                "scripts.stage_c_transaction.borrowed_authority_view_v7.os.fstat",
                return_value=SimpleNamespace(
                    st_dev=LOCK_DEVICE,
                    st_ino=LOCK_INODE,
                    st_mode=stat.S_IFREG | 0o600,
                    st_uid=0,
                    st_gid=0,
                ),
            ),
            patch.object(
                Path,
                "lstat",
                return_value=SimpleNamespace(
                    st_dev=TRANSACTION_DEVICE,
                    st_ino=TRANSACTION_INODE,
                    st_mode=stat.S_IFDIR | 0o700,
                    st_uid=0,
                    st_gid=0,
                ),
            ),
            patch(
                "scripts.stage_c_transaction.borrowed_authority_view_v7._require_identity",
                return_value=self.route_identity,
            ),
        )

    def test_success_returns_only_frozen_existing_authority_identities(self) -> None:
        owner = self._owner()
        descriptor_patch, fstat_patch, lstat_patch, route_patch = (
            self._success_patches()
        )
        with descriptor_patch, fstat_patch, lstat_patch, route_patch:
            result = inspect_borrowed_authority_v7(owner)

        self.assertIs(result.status, AdapterStatus.PASS)
        self.assertIsInstance(result.payload, BorrowedAuthorityViewV7)
        view = result.payload
        assert view is not None
        self.assertEqual(view.production_lock_path, PRODUCTION_LOCK_PATH)
        self.assertEqual(view.lock_lease_id, "stage-c20-existing-lease")
        self.assertEqual(view.lock_device, LOCK_DEVICE)
        self.assertEqual(view.lock_inode, LOCK_INODE)
        self.assertEqual(view.transaction, self.transaction_identity)
        self.assertEqual(view.snapshot, self.snapshot_identity)
        self.assertEqual(view.package, self.package)
        self.assertEqual(
            view.authoritative_transaction_path,
            str(self.transaction_path),
        )
        self.assertEqual(view.transaction_device, TRANSACTION_DEVICE)
        self.assertEqual(view.transaction_inode, TRANSACTION_INODE)
        self.assertEqual(view.selected_route_path, CURRENT_ALSA_DESTINATION)
        self.assertEqual(view.selected_route_device, ROUTE_DEVICE)
        self.assertEqual(view.selected_route_inode, ROUTE_INODE)
        self.assertEqual(view.selected_route_sha256, ROUTE_SHA256)
        self.assertTrue(view.snapshot_complete)
        self.assertTrue(view.split_bus_route_selected)
        self.assertTrue(view.exact_lock_owned)
        self.assertTrue(view.exact_transaction_verified)
        self.assertNotIn("fd", BorrowedAuthorityViewV7.__dataclass_fields__)
        self.assertNotIn("descriptor", BorrowedAuthorityViewV7.__dataclass_fields__)
        with self.assertRaises(FrozenInstanceError):
            view.lock_inode = 999  # type: ignore[misc]

    def test_requires_the_existing_c20_owner_lineage(self) -> None:
        with self.assertRaises(TypeError):
            inspect_borrowed_authority_v7(object())  # type: ignore[arg-type]

    def test_missing_lock_or_transaction_fails_before_host_observation(self) -> None:
        owner = self._owner()
        owner._lock_fd = None
        with patch(
            "scripts.stage_c_transaction.borrowed_authority_view_v7.os.fstat"
        ) as fstat_mock:
            result = inspect_borrowed_authority_v7(owner)
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertIsNone(result.payload)
        self.assertIn("does not hold", result.detail)
        fstat_mock.assert_not_called()

        owner = self._owner()
        owner._transaction = None
        result = inspect_borrowed_authority_v7(owner)
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertIn("no authoritative transaction", result.detail)

    def test_incomplete_snapshot_or_inactive_route_fails_closed(self) -> None:
        owner = self._owner()
        owner._mixer_captured = False
        result = inspect_borrowed_authority_v7(owner)
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertIn("all five", result.detail)

        owner = self._owner()
        owner._route_restored = True
        result = inspect_borrowed_authority_v7(owner)
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertIn("not currently selected exactly once", result.detail)

        owner = self._owner()
        owner._route_selection_count = 2
        result = inspect_borrowed_authority_v7(owner)
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertIn("not currently selected exactly once", result.detail)

    def test_transaction_package_path_and_action_must_remain_authoritative(self) -> None:
        owner = self._owner()
        owner._package = PackageFingerprint("c" * 64)
        result = inspect_borrowed_authority_v7(owner)
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertIn("package", result.detail)

        owner = self._owner()
        owner._transaction_path = Path(AUTHORITATIVE_TRANSACTION_ROOT) / "other"
        result = inspect_borrowed_authority_v7(owner)
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertIn("not canonical", result.detail)

        owner = self._owner()
        owner._transaction = AuthoritativeTransaction(
            transaction=self.transaction_identity,
            snapshot=self.snapshot_identity,
            action=TransactionAction.EXACT_ROLLBACK,
            package=self.package,
        )
        result = inspect_borrowed_authority_v7(owner)
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertIn("install transaction", result.detail)

    def test_changed_lock_transaction_or_route_identity_fails_closed(self) -> None:
        owner = self._owner()
        changed_evidence = HeldLockEvidence(
            inode=LOCK_INODE + 1,
            mode=0o600,
            owner_uid=0,
            owner_gid=0,
            contention_proved=True,
        )
        descriptor_patch, fstat_patch, lstat_patch, route_patch = (
            self._success_patches()
        )
        descriptor_patch = patch(
            "scripts.stage_c_transaction.borrowed_authority_view_v7._descriptor_evidence",
            return_value=changed_evidence,
        )
        with descriptor_patch, fstat_patch, lstat_patch, route_patch:
            result = inspect_borrowed_authority_v7(owner)
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertIn("evidence changed", result.detail)

        owner = self._owner()
        descriptor_patch, fstat_patch, _lstat_patch, route_patch = (
            self._success_patches()
        )
        wrong_lstat = patch.object(
            Path,
            "lstat",
            return_value=SimpleNamespace(
                st_dev=TRANSACTION_DEVICE,
                st_ino=TRANSACTION_INODE + 1,
                st_mode=stat.S_IFDIR | 0o700,
                st_uid=0,
                st_gid=0,
            ),
        )
        with descriptor_patch, fstat_patch, wrong_lstat, route_patch:
            result = inspect_borrowed_authority_v7(owner)
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertIn("identity or metadata changed", result.detail)

        owner = self._owner()
        descriptor_patch, fstat_patch, lstat_patch, _route_patch = (
            self._success_patches()
        )
        failed_route = patch(
            "scripts.stage_c_transaction.borrowed_authority_view_v7._require_identity",
            side_effect=RouteSelectionRollbackFailure("route changed"),
        )
        with descriptor_patch, fstat_patch, lstat_patch, failed_route:
            result = inspect_borrowed_authority_v7(owner)
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertEqual(result.detail, "route changed")

    def test_lock_observation_exception_is_a_typed_failure(self) -> None:
        owner = self._owner()
        with patch(
            "scripts.stage_c_transaction.borrowed_authority_view_v7._descriptor_evidence",
            side_effect=ProductionLockFailure("lock substituted"),
        ):
            result = inspect_borrowed_authority_v7(owner)
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertIsNone(result.payload)
        self.assertEqual(result.detail, "lock substituted")

    def test_result_validation_rejects_missing_or_invented_payload(self) -> None:
        with self.assertRaises(ValueError):
            BorrowedAuthorityViewResultV7(
                status=AdapterStatus.PASS,
                detail="missing",
            )
        owner = self._owner()
        descriptor_patch, fstat_patch, lstat_patch, route_patch = (
            self._success_patches()
        )
        with descriptor_patch, fstat_patch, lstat_patch, route_patch:
            payload = inspect_borrowed_authority_v7(owner).payload
        assert payload is not None
        with self.assertRaises(ValueError):
            BorrowedAuthorityViewResultV7(
                status=AdapterStatus.FAIL,
                detail="invented",
                payload=payload,
            )

    def test_view_adds_no_forty_third_adapter_operation(self) -> None:
        self.assertEqual(len(ALL_OPERATIONS_V7), 42)
        self.assertNotIn("inspect-borrowed-authority", {item.value for item in ALL_OPERATIONS_V7})

    def test_module_has_no_write_cli_command_or_generic_dispatch_boundary(self) -> None:
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
            for node in self.tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(imported.isdisjoint(forbidden_imports))
        forbidden_attributes = {
            "open",
            "unlink",
            "replace",
            "rename",
            "renameat2",
            "mkdir",
            "rmdir",
            "write_text",
            "write_bytes",
            "chmod",
            "chown",
            "flock",
            "system",
            "run",
            "popen",
            "dispatch",
        }
        for node in ast.walk(self.tree):
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
