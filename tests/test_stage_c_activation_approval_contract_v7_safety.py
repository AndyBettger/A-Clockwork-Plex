from __future__ import annotations

import ast
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from scripts.stage_c_transaction.production_adapter_contract import (
    AdapterStatus,
    PackageFingerprint,
    TransactionIdentity,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v6 import (
    ALL_OPERATIONS_V6,
    MUTATING_OPERATIONS_V6,
    READ_ONLY_OPERATIONS_V6,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v7 import (
    ACTIVATION_APPROVAL_PATH,
    ALL_OPERATIONS_V7,
    COMMITTED_APPROVAL_PHASE,
    MUTATING_OPERATIONS_V7,
    PRODUCTION_LOCK_PATH,
    READ_ONLY_OPERATIONS_V7,
    STAGE_BOUNDARIES_V7,
    TEMPORARY_APPROVAL_PHASE,
    ActivationApprovalAdapterResult,
    ActivationApprovalLifecycleOperation,
    ActivationApprovalRemovalReceipt,
    BlockedProductionAdapterV7,
    CommittedActivationApprovalReceipt,
    ProductionActivationApprovalAdapterBlocked,
    ProductionAdapterV7,
    ProductionLockLeaseBindingReceipt,
    TemporaryActivationApprovalReceipt,
    contract_snapshot_v7,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE = REPO_ROOT / "scripts/stage_c_transaction/production_adapter_lifecycle_v7.py"
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64


class StageCActivationApprovalContractV7SafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = MODULE.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)
        self.transaction = TransactionIdentity("stage-c21-approval-contract-test")
        self.package = PackageFingerprint(HASH_A)

    def lock_receipt(self, **overrides):
        values = {
            "transaction": self.transaction,
            "lock_path": PRODUCTION_LOCK_PATH,
            "lease_id": "stage-c21-lock-lease-test",
            "lock_device": 42,
            "lock_inode": 84,
            "transaction_owns_lock": True,
            "canonical_content_written": True,
            "exact_inode_verified": True,
            "external_observer_ready": True,
        }
        values.update(overrides)
        return ProductionLockLeaseBindingReceipt(**values)

    def temporary_receipt(self, **overrides):
        values = {
            "transaction": self.transaction,
            "approval_path": ACTIVATION_APPROVAL_PATH,
            "phase": TEMPORARY_APPROVAL_PHASE,
            "package": self.package,
            "lock_lease_id": "stage-c21-lock-lease-test",
            "record_sha256": HASH_B,
            "active_route_sha256": HASH_C,
            "boot_eligible": False,
            "atomically_published": True,
            "exact_record_verified": True,
        }
        values.update(overrides)
        return TemporaryActivationApprovalReceipt(**values)

    def removal_receipt(self, **overrides):
        values = {
            "transaction": self.transaction,
            "approval_path": ACTIVATION_APPROVAL_PATH,
            "expected_record_sha256": HASH_B,
            "exact_record_removed": True,
            "approval_absent": True,
            "rollback_owned": True,
        }
        values.update(overrides)
        return ActivationApprovalRemovalReceipt(**values)

    def committed_receipt(self, **overrides):
        values = {
            "transaction": self.transaction,
            "approval_path": ACTIVATION_APPROVAL_PATH,
            "phase": COMMITTED_APPROVAL_PHASE,
            "package": self.package,
            "lock_lease_id": "stage-c21-lock-lease-test",
            "temporary_record_sha256": HASH_B,
            "committed_record_sha256": HASH_C,
            "commit_manifest_sha256": HASH_D,
            "boot_eligible": True,
            "atomically_promoted": True,
            "exact_record_verified": True,
        }
        values.update(overrides)
        return CommittedActivationApprovalReceipt(**values)

    def test_v1_through_v6_history_remains_exact(self) -> None:
        self.assertEqual(tuple(ALL_OPERATIONS_V7[:38]), ALL_OPERATIONS_V6)
        self.assertEqual(tuple(READ_ONLY_OPERATIONS_V7), READ_ONLY_OPERATIONS_V6)
        self.assertEqual(tuple(MUTATING_OPERATIONS_V7[:21]), MUTATING_OPERATIONS_V6)

    def test_v7_adds_exactly_four_unique_transaction_operations(self) -> None:
        self.assertEqual(len(ALL_OPERATIONS_V6), 38)
        self.assertEqual(len(ALL_OPERATIONS_V7), 42)
        self.assertEqual(
            tuple(ALL_OPERATIONS_V7[-4:]),
            tuple(ActivationApprovalLifecycleOperation),
        )
        self.assertEqual(
            tuple(operation.value for operation in ActivationApprovalLifecycleOperation),
            (
                "bind-production-lock-lease",
                "publish-temporary-activation-approval",
                "remove-temporary-activation-approval",
                "promote-committed-activation-approval",
            ),
        )
        values = tuple(operation.value for operation in ALL_OPERATIONS_V7)
        self.assertEqual(len(values), len(set(values)))

    def test_v7_partition_is_seventeen_and_twenty_five(self) -> None:
        self.assertEqual(len(READ_ONLY_OPERATIONS_V7), 17)
        self.assertEqual(len(MUTATING_OPERATIONS_V7), 25)
        self.assertFalse(set(READ_ONLY_OPERATIONS_V7).intersection(MUTATING_OPERATIONS_V7))
        self.assertEqual(
            set(READ_ONLY_OPERATIONS_V7).union(MUTATING_OPERATIONS_V7),
            set(ALL_OPERATIONS_V7),
        )

    def test_contract_gate_blocks_all_four_new_operations(self) -> None:
        self.assertEqual(len(STAGE_BOUNDARIES_V7), 1)
        boundary = STAGE_BOUNDARIES_V7[0]
        self.assertEqual(boundary.stage, "C21-approval-bridge-contract")
        self.assertEqual(boundary.new_operations_permitted, 0)
        self.assertEqual(boundary.new_operations_blocked, 4)

    def test_lock_receipt_is_frozen_and_requires_exact_external_identity(self) -> None:
        receipt = self.lock_receipt()
        self.assertEqual(receipt.lock_inode, 84)
        with self.assertRaises(FrozenInstanceError):
            receipt.lease_id = "changed"  # type: ignore[misc]
        invalid = (
            {"lock_path": "/tmp/wrong"},
            {"lease_id": ""},
            {"lease_id": "has space"},
            {"lock_device": -1},
            {"lock_inode": 0},
            {"transaction_owns_lock": False},
            {"canonical_content_written": False},
            {"exact_inode_verified": False},
            {"external_observer_ready": False},
        )
        for override in invalid:
            with self.subTest(override=override):
                with self.assertRaises(ValueError):
                    self.lock_receipt(**override)

    def test_temporary_receipt_is_exact_and_never_boot_eligible(self) -> None:
        receipt = self.temporary_receipt()
        self.assertFalse(receipt.boot_eligible)
        invalid = (
            {"approval_path": "/tmp/wrong"},
            {"phase": "committed"},
            {"lock_lease_id": ""},
            {"record_sha256": "0" * 63},
            {"active_route_sha256": "G" * 64},
            {"boot_eligible": True},
            {"atomically_published": False},
            {"exact_record_verified": False},
        )
        for override in invalid:
            with self.subTest(override=override):
                with self.assertRaises(ValueError):
                    self.temporary_receipt(**override)

    def test_removal_receipt_requires_exact_rollback_owned_absence(self) -> None:
        receipt = self.removal_receipt()
        self.assertTrue(receipt.approval_absent)
        invalid = (
            {"approval_path": "/tmp/wrong"},
            {"expected_record_sha256": "bad"},
            {"exact_record_removed": False},
            {"approval_absent": False},
            {"rollback_owned": False},
        )
        for override in invalid:
            with self.subTest(override=override):
                with self.assertRaises(ValueError):
                    self.removal_receipt(**override)

    def test_committed_receipt_binds_changed_record_and_commit_manifest(self) -> None:
        receipt = self.committed_receipt()
        self.assertTrue(receipt.boot_eligible)
        invalid = (
            {"approval_path": "/tmp/wrong"},
            {"phase": "temporary"},
            {"lock_lease_id": ""},
            {"temporary_record_sha256": "bad"},
            {"committed_record_sha256": "bad"},
            {"commit_manifest_sha256": "bad"},
            {"committed_record_sha256": HASH_B},
            {"boot_eligible": False},
            {"atomically_promoted": False},
            {"exact_record_verified": False},
        )
        for override in invalid:
            with self.subTest(override=override):
                with self.assertRaises(ValueError):
                    self.committed_receipt(**override)

    def test_result_accepts_only_the_receipt_for_its_exact_operation(self) -> None:
        pairs = (
            (
                ActivationApprovalLifecycleOperation.BIND_PRODUCTION_LOCK_LEASE,
                self.lock_receipt(),
            ),
            (
                ActivationApprovalLifecycleOperation.PUBLISH_TEMPORARY_ACTIVATION_APPROVAL,
                self.temporary_receipt(),
            ),
            (
                ActivationApprovalLifecycleOperation.REMOVE_TEMPORARY_ACTIVATION_APPROVAL,
                self.removal_receipt(),
            ),
            (
                ActivationApprovalLifecycleOperation.PROMOTE_COMMITTED_ACTIVATION_APPROVAL,
                self.committed_receipt(),
            ),
        )
        for operation, payload in pairs:
            with self.subTest(operation=operation):
                result = ActivationApprovalAdapterResult(
                    operation=operation,
                    status=AdapterStatus.PASS,
                    detail="exact typed receipt",
                    payload=payload,
                )
                self.assertIs(result.payload, payload)
                wrong = self.temporary_receipt() if operation is not ActivationApprovalLifecycleOperation.PUBLISH_TEMPORARY_ACTIVATION_APPROVAL else self.lock_receipt()
                with self.assertRaises(ValueError):
                    ActivationApprovalAdapterResult(
                        operation=operation,
                        status=AdapterStatus.PASS,
                        detail="wrong receipt",
                        payload=wrong,
                    )
        with self.assertRaises(ValueError):
            ActivationApprovalAdapterResult(
                operation=ActivationApprovalLifecycleOperation.BIND_PRODUCTION_LOCK_LEASE,
                status=AdapterStatus.FAIL,
                detail="failed",
                payload=self.lock_receipt(),
            )

    def test_blocked_v7_adapter_fails_with_each_exact_identity(self) -> None:
        adapter = BlockedProductionAdapterV7()
        self.assertIsInstance(adapter, ProductionAdapterV7)
        calls = (
            (
                ActivationApprovalLifecycleOperation.BIND_PRODUCTION_LOCK_LEASE,
                adapter.bind_production_lock_lease,
            ),
            (
                ActivationApprovalLifecycleOperation.PUBLISH_TEMPORARY_ACTIVATION_APPROVAL,
                adapter.publish_temporary_activation_approval,
            ),
            (
                ActivationApprovalLifecycleOperation.REMOVE_TEMPORARY_ACTIVATION_APPROVAL,
                adapter.remove_temporary_activation_approval,
            ),
            (
                ActivationApprovalLifecycleOperation.PROMOTE_COMMITTED_ACTIVATION_APPROVAL,
                adapter.promote_committed_activation_approval,
            ),
        )
        for operation, call in calls:
            with self.subTest(operation=operation):
                with self.assertRaises(ProductionActivationApprovalAdapterBlocked) as raised:
                    call(self.transaction)
                self.assertIs(raised.exception.operation, operation)

    def test_contract_snapshot_is_static_and_transaction_only(self) -> None:
        snapshot = dict(contract_snapshot_v7())
        self.assertEqual(snapshot["version"], "7")
        self.assertEqual(snapshot["v6_operation_count"], "38")
        self.assertEqual(snapshot["operation_count"], "42")
        self.assertEqual(snapshot["read_only_count"], "17")
        self.assertEqual(snapshot["mutating_count"], "25")
        self.assertEqual(snapshot["approval_path"], ACTIVATION_APPROVAL_PATH)
        self.assertEqual(snapshot["lock_path"], PRODUCTION_LOCK_PATH)
        self.assertEqual(snapshot["new_operations_permitted"], "0")
        self.assertEqual(snapshot["new_operations_blocked"], "4")
        self.assertEqual(snapshot["service_helper_approval_interface"], "absent")
        for operation in ActivationApprovalLifecycleOperation:
            self.assertIn(operation.value, snapshot["operations"])

    def test_module_has_no_host_access_cli_or_generic_dispatch(self) -> None:
        imported = {
            alias.name
            for node in self.tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertFalse(
            imported.intersection(
                {
                    "argparse",
                    "ctypes",
                    "fcntl",
                    "json",
                    "os",
                    "pathlib",
                    "subprocess",
                    "sys",
                }
            )
        )
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.assertNotIn("dispatch", node.name.lower())
                names = {arg.arg for arg in (*node.args.args, *node.args.kwonlyargs)}
                self.assertTrue(
                    names.isdisjoint(
                        {
                            "path",
                            "lease_id",
                            "record",
                            "record_sha256",
                            "commit_manifest_sha256",
                            "command",
                        }
                    ),
                    (node.name, names),
                )
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"eval", "exec", "getattr", "open"})
                elif isinstance(node.func, ast.Attribute):
                    self.assertNotEqual(node.func.attr, "dispatch")


if __name__ == "__main__":
    unittest.main()
