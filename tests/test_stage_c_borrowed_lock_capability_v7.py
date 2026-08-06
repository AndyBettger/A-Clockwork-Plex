from __future__ import annotations

import ast
import stat
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/stage_c_transaction/borrowed_lock_capability_v7.py"

from scripts.stage_c_transaction.approval_authority_binding_v7 import (
    ApprovalHardwareContractV7,
    bind_approval_authority_v7,
)
from scripts.stage_c_transaction.borrowed_authority_view_v7 import (
    BorrowedAuthorityViewResultV7,
    BorrowedAuthorityViewV7,
)
from scripts.stage_c_transaction.borrowed_lock_capability_v7 import (
    BorrowedLeaseContentStateV7,
    BorrowedLockCapabilityResultV7,
    BorrowedProductionLockCapabilityV7,
    borrow_production_lock_capability_v7,
)
from scripts.stage_c_transaction.production_adapter_contract import (
    AUTHORITATIVE_TRANSACTION_ROOT,
    PRODUCTION_LOCK_PATH,
    AdapterStatus,
    PackageFingerprint,
    SnapshotIdentity,
    TransactionIdentity,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v7 import (
    ALL_OPERATIONS_V7,
)
from scripts.stage_c_transaction.route_selection_rollback_rehearsal_adapter_v2 import (
    RouteSelectionRollbackRehearsalAdapterV2,
)
from scripts.stage_c_transaction.snapshot_core import CURRENT_ALSA_DESTINATION


LOCK_FD = 77
LOCK_DEVICE = 101
LOCK_INODE = 102
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
HASH_E = "e" * 64


class StageCBorrowedLockCapabilityV7Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = MODULE.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)
        self.transaction = TransactionIdentity("stage-c21-capability-test")
        self.snapshot = SnapshotIdentity("stage-c21-capability-snapshot")
        self.package = PackageFingerprint(HASH_A)
        self.authority = BorrowedAuthorityViewV7(
            production_lock_path=PRODUCTION_LOCK_PATH,
            lock_lease_id="stage-c21-capability-lease",
            lock_device=LOCK_DEVICE,
            lock_inode=LOCK_INODE,
            transaction=self.transaction,
            snapshot=self.snapshot,
            package=self.package,
            authoritative_transaction_path=str(
                Path(AUTHORITATIVE_TRANSACTION_ROOT) / self.transaction.value
            ),
            transaction_device=201,
            transaction_inode=202,
            selected_route_path=CURRENT_ALSA_DESTINATION,
            selected_route_device=301,
            selected_route_inode=302,
            selected_route_sha256=HASH_B,
            snapshot_complete=True,
            split_bus_route_selected=True,
            exact_lock_owned=True,
            exact_transaction_verified=True,
        )
        hardware = ApprovalHardwareContractV7(
            package=self.package,
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
        self.binding = bind_approval_authority_v7(
            self.authority,
            hardware,
        ).payload
        assert self.binding is not None
        self.owner = object.__new__(RouteSelectionRollbackRehearsalAdapterV2)
        self.owner._lock_fd = LOCK_FD

    def _inspection(self, authority: BorrowedAuthorityViewV7 | None = None):
        return patch(
            "scripts.stage_c_transaction.borrowed_lock_capability_v7.inspect_borrowed_authority_v7",
            return_value=BorrowedAuthorityViewResultV7(
                status=AdapterStatus.PASS,
                detail="exact owner",
                payload=authority or self.authority,
            ),
        )

    def _descriptor(self, *, size: int):
        return patch(
            "scripts.stage_c_transaction.borrowed_lock_capability_v7.os.fstat",
            return_value=SimpleNamespace(
                st_dev=LOCK_DEVICE,
                st_ino=LOCK_INODE,
                st_mode=stat.S_IFREG | 0o600,
                st_uid=0,
                st_gid=0,
                st_size=size,
            ),
        )

    def _borrow(self, raw: bytes = b""):
        with self._inspection(), self._descriptor(size=len(raw)), patch(
            "scripts.stage_c_transaction.borrowed_lock_capability_v7.os.pread",
            return_value=raw,
        ):
            capability, result = borrow_production_lock_capability_v7(
                self.owner,
                self.binding,
            )
        assert capability is not None
        return capability, result

    def test_factory_borrows_empty_lock_without_transferring_descriptor(self) -> None:
        capability, result = self._borrow()
        self.assertIsInstance(capability, BorrowedProductionLockCapabilityV7)
        self.assertIs(result.status, AdapterStatus.PASS)
        proof = result.payload
        assert proof is not None
        self.assertIs(proof.lease_content_state, BorrowedLeaseContentStateV7.EMPTY)
        self.assertEqual(proof.lock_device, LOCK_DEVICE)
        self.assertEqual(proof.lock_inode, LOCK_INODE)
        self.assertEqual(proof.lock_lease_id, self.binding.lock_lease_id)
        self.assertEqual(
            proof.canonical_lease_bytes,
            (self.binding.lock_lease_id + "\n").encode("ascii"),
        )
        self.assertEqual(proof.binding_sha256, self.binding.binding_sha256)
        self.assertEqual(capability.binding, self.binding)
        self.assertFalse(hasattr(capability, "descriptor"))
        self.assertFalse(hasattr(capability, "close"))
        self.assertFalse(hasattr(capability, "release"))

    def test_exact_bound_lease_passes_required_bound_gate(self) -> None:
        canonical = (self.binding.lock_lease_id + "\n").encode("ascii")
        capability, _result = self._borrow(canonical)
        with self._inspection(), self._descriptor(size=len(canonical)), patch(
            "scripts.stage_c_transaction.borrowed_lock_capability_v7.os.pread",
            return_value=canonical,
        ):
            result = capability.reverify(require_bound_lease=True)
        self.assertIs(result.status, AdapterStatus.PASS)
        assert result.payload is not None
        self.assertIs(
            result.payload.lease_content_state,
            BorrowedLeaseContentStateV7.EXACT_CANONICAL,
        )
        self.assertIn("canonical lease", result.detail)

    def test_empty_lease_refuses_a_required_bound_gate(self) -> None:
        capability, _result = self._borrow()
        with self._inspection(), self._descriptor(size=0), patch(
            "scripts.stage_c_transaction.borrowed_lock_capability_v7.os.pread",
            return_value=b"",
        ):
            result = capability.reverify(require_bound_lease=True)
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertIsNone(result.payload)
        self.assertIn("not been canonically bound", result.detail)

    def test_noncanonical_or_changing_content_fails_closed(self) -> None:
        with self._inspection(), self._descriptor(size=5), patch(
            "scripts.stage_c_transaction.borrowed_lock_capability_v7.os.pread",
            return_value=b"wrong",
        ):
            capability, result = borrow_production_lock_capability_v7(
                self.owner,
                self.binding,
            )
        self.assertIsNone(capability)
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertIn("not canonical", result.detail)

        with self._inspection(), self._descriptor(size=2), patch(
            "scripts.stage_c_transaction.borrowed_lock_capability_v7.os.pread",
            return_value=b"",
        ):
            capability, result = borrow_production_lock_capability_v7(
                self.owner,
                self.binding,
            )
        self.assertIsNone(capability)
        self.assertIn("changed during observation", result.detail)

    def test_owner_descriptor_loss_or_replacement_fails_before_observation(self) -> None:
        capability, _result = self._borrow()
        self.owner._lock_fd = None
        with patch(
            "scripts.stage_c_transaction.borrowed_lock_capability_v7.inspect_borrowed_authority_v7"
        ) as inspect_mock:
            result = capability.reverify(require_bound_lease=False)
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertIn("no longer exposes", result.detail)
        inspect_mock.assert_not_called()

        self.owner._lock_fd = LOCK_FD + 1
        result = capability.reverify(require_bound_lease=False)
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertIn("original borrowed descriptor", result.detail)

    def test_changed_authority_or_descriptor_identity_fails_closed(self) -> None:
        capability, _result = self._borrow()
        changed = replace(self.authority, selected_route_inode=999)
        with self._inspection(changed):
            result = capability.reverify(require_bound_lease=False)
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertIn("immutable binding", result.detail)

        with self._inspection(), patch(
            "scripts.stage_c_transaction.borrowed_lock_capability_v7.os.fstat",
            return_value=SimpleNamespace(
                st_dev=LOCK_DEVICE,
                st_ino=LOCK_INODE + 1,
                st_mode=stat.S_IFREG | 0o600,
                st_uid=0,
                st_gid=0,
                st_size=0,
            ),
        ):
            result = capability.reverify(require_bound_lease=False)
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertIn("identity changed", result.detail)

    def test_failed_owner_inspection_and_os_error_are_typed_failures(self) -> None:
        capability, _result = self._borrow()
        with patch(
            "scripts.stage_c_transaction.borrowed_lock_capability_v7.inspect_borrowed_authority_v7",
            return_value=BorrowedAuthorityViewResultV7(
                status=AdapterStatus.FAIL,
                detail="route changed",
            ),
        ):
            result = capability.reverify(require_bound_lease=False)
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertIn("route changed", result.detail)

        with self._inspection(), patch(
            "scripts.stage_c_transaction.borrowed_lock_capability_v7.os.fstat",
            side_effect=OSError("bad descriptor"),
        ):
            result = capability.reverify(require_bound_lease=False)
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertIn("bad descriptor", result.detail)

    def test_factory_requires_exact_types_and_live_descriptor(self) -> None:
        with self.assertRaises(TypeError):
            borrow_production_lock_capability_v7(object(), self.binding)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            borrow_production_lock_capability_v7(self.owner, object())  # type: ignore[arg-type]

        self.owner._lock_fd = None
        capability, result = borrow_production_lock_capability_v7(
            self.owner,
            self.binding,
        )
        self.assertIsNone(capability)
        self.assertIs(result.status, AdapterStatus.FAIL)

        with self.assertRaises(TypeError):
            BorrowedProductionLockCapabilityV7(
                self.owner,
                self.binding,
                LOCK_FD,
                _factory_token=object(),
            )

    def test_proof_and_result_invariants_are_frozen_and_typed(self) -> None:
        _capability, result = self._borrow()
        proof = result.payload
        assert proof is not None
        with self.assertRaises(FrozenInstanceError):
            proof.lock_inode = 999  # type: ignore[misc]
        with self.assertRaises(ValueError):
            BorrowedLockCapabilityResultV7(
                status=AdapterStatus.PASS,
                detail="missing",
            )
        with self.assertRaises(ValueError):
            BorrowedLockCapabilityResultV7(
                status=AdapterStatus.FAIL,
                detail="invented",
                payload=proof,
            )

    def test_capability_adds_no_adapter_operation_or_host_mutation_boundary(self) -> None:
        self.assertEqual(len(ALL_OPERATIONS_V7), 42)
        self.assertNotIn(
            "borrow-production-lock-capability",
            {operation.value for operation in ALL_OPERATIONS_V7},
        )
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
            "close",
            "dup",
            "flock",
            "ftruncate",
            "pwrite",
            "write",
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
            "__enter__",
            "__exit__",
            "__del__",
        ):
            self.assertNotIn(forbidden_text, self.source)


if __name__ == "__main__":
    unittest.main()
