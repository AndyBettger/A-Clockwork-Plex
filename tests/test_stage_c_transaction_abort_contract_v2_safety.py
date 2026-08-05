from __future__ import annotations

import ast
import inspect
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from scripts.stage_c_transaction import authoritative_snapshot_rehearsal_adapter as c15
from scripts.stage_c_transaction import production_adapter_contract as v1
from scripts.stage_c_transaction import production_adapter_lifecycle_v2 as v2


class StageCTransactionAbortContractV2SafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(__file__).resolve().parents[1]
        self.module = (
            self.repo
            / "scripts"
            / "stage_c_transaction"
            / "production_adapter_lifecycle_v2.py"
        )
        self.source = self.module.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    def test_v1_contract_remains_historically_exact(self) -> None:
        self.assertEqual(len(v1.AdapterOperation), 33)
        self.assertEqual(len(v1.READ_ONLY_OPERATIONS), 17)
        self.assertEqual(len(v1.MUTATING_OPERATIONS), 16)
        self.assertFalse(hasattr(v1.AdapterOperation, "ABORT_UNCOMMITTED_TRANSACTION"))
        self.assertFalse(hasattr(v1.AdapterOperation, "EXPLICIT_UNINSTALL"))

    def test_v2_adds_exactly_one_unique_operation(self) -> None:
        self.assertEqual(tuple(v2.TransactionLifecycleOperation), (
            v2.TransactionLifecycleOperation.ABORT_UNCOMMITTED_TRANSACTION,
        ))
        self.assertEqual(len(v2.ALL_OPERATIONS_V2), 34)
        self.assertEqual(
            v2.ALL_OPERATIONS_V2[:-1],
            tuple(v1.AdapterOperation),
        )
        self.assertIs(
            v2.ALL_OPERATIONS_V2[-1],
            v2.TransactionLifecycleOperation.ABORT_UNCOMMITTED_TRANSACTION,
        )
        values = tuple(operation.value for operation in v2.ALL_OPERATIONS_V2)
        self.assertEqual(len(values), len(set(values)))

    def test_v2_is_partitioned_seventeen_and_seventeen(self) -> None:
        self.assertEqual(len(v2.READ_ONLY_OPERATIONS_V2), 17)
        self.assertEqual(len(v2.MUTATING_OPERATIONS_V2), 17)
        self.assertEqual(
            set(v2.READ_ONLY_OPERATIONS_V2).union(v2.MUTATING_OPERATIONS_V2),
            set(v2.ALL_OPERATIONS_V2),
        )
        self.assertTrue(
            set(v2.READ_ONLY_OPERATIONS_V2).isdisjoint(
                v2.MUTATING_OPERATIONS_V2
            )
        )
        self.assertIn(
            v2.TransactionLifecycleOperation.ABORT_UNCOMMITTED_TRANSACTION,
            v2.MUTATING_OPERATIONS_V2,
        )
        self.assertNotIn(
            v2.TransactionLifecycleOperation.ABORT_UNCOMMITTED_TRANSACTION,
            v2.READ_ONLY_OPERATIONS_V2,
        )

    def test_v2_protocol_adds_only_the_typed_abort_method(self) -> None:
        v1_methods = {
            name
            for name, value in v1.ProductionAdapter.__dict__.items()
            if callable(value) and not name.startswith("_")
        }
        v2_local_methods = {
            name
            for name, value in v2.ProductionAdapterV2.__dict__.items()
            if callable(value) and not name.startswith("_")
        }
        self.assertEqual(v2_local_methods, {"abort_uncommitted_transaction"})
        self.assertEqual(len(v1_methods), 33)
        signature = inspect.signature(
            v2.ProductionAdapterV2.abort_uncommitted_transaction
        )
        self.assertEqual(tuple(signature.parameters), ("self", "transaction"))
        forbidden = {
            "command",
            "argv",
            "path",
            "root",
            "evidence_copy",
            "unit_name",
            "control_name",
        }
        self.assertTrue(forbidden.isdisjoint(signature.parameters))

    def test_blocked_v2_adapter_conforms_and_fails_closed(self) -> None:
        adapter = v2.BlockedProductionAdapterV2()
        self.assertIsInstance(adapter, v1.ProductionAdapter)
        self.assertIsInstance(adapter, v2.ProductionAdapterV2)
        transaction = v1.TransactionIdentity("stage-c15a-transaction")
        with self.assertRaises(v2.ProductionLifecycleAdapterBlocked) as raised:
            adapter.abort_uncommitted_transaction(transaction)
        self.assertIs(
            raised.exception.operation,
            v2.TransactionLifecycleOperation.ABORT_UNCOMMITTED_TRANSACTION,
        )
        self.assertIn("abort-uncommitted-transaction", str(raised.exception))
        with self.assertRaises(v1.ProductionAdapterBlocked):
            adapter.acquire_production_lock()

    def test_abort_receipt_is_frozen_exact_and_fail_closed(self) -> None:
        transaction = v1.TransactionIdentity("stage-c15a-transaction")
        receipt = v2.AbortUncommittedTransactionReceipt(
            transaction=transaction,
            state="aborted-before-mutation",
            mutation_started=False,
            committed=False,
            transaction_path_absent=True,
            parents_restored=True,
            audit_evidence="transaction-audit-copy",
        )
        result = v2.LifecycleAdapterResult(
            operation=v2.TransactionLifecycleOperation.ABORT_UNCOMMITTED_TRANSACTION,
            status=v1.AdapterStatus.PASS,
            detail="transaction aborted exactly",
            payload=receipt,
        )
        self.assertIs(result.payload, receipt)
        with self.assertRaises(FrozenInstanceError):
            receipt.state = "changed"  # type: ignore[misc]
        with self.assertRaises(ValueError):
            v2.LifecycleAdapterResult(
                operation=v2.TransactionLifecycleOperation.ABORT_UNCOMMITTED_TRANSACTION,
                status=v1.AdapterStatus.FAIL,
                detail="failed",
                payload=receipt,
            )
        invalid = (
            dict(state="wrong"),
            dict(mutation_started=True),
            dict(committed=True),
            dict(transaction_path_absent=False),
            dict(parents_restored=False),
            dict(audit_evidence=""),
        )
        base = dict(
            transaction=transaction,
            state="aborted-before-mutation",
            mutation_started=False,
            committed=False,
            transaction_path_absent=True,
            parents_restored=True,
            audit_evidence="transaction-audit-copy",
        )
        for override in invalid:
            with self.subTest(override=override):
                with self.assertRaises(ValueError):
                    v2.AbortUncommittedTransactionReceipt(
                        **(base | override)
                    )

    def test_versioned_stage_boundaries_are_exact(self) -> None:
        self.assertEqual(
            v2.STAGE_BOUNDARIES_V2,
            (
                v2.VersionedStageBoundary("C13", 6, 28),
                v2.VersionedStageBoundary("C14", 8, 26),
                v2.VersionedStageBoundary("C15", 11, 23),
            ),
        )
        with self.assertRaises(ValueError):
            v2.VersionedStageBoundary("bad", 1, 1)

    def test_c15_rehearsal_helper_is_distinct_from_production_shape(self) -> None:
        rehearsal_signature = inspect.signature(
            c15.AuthoritativeSnapshotRehearsalAdapter.abort_uncommitted_transaction
        )
        production_signature = inspect.signature(
            v2.ProductionAdapterV2.abort_uncommitted_transaction
        )
        self.assertEqual(
            tuple(rehearsal_signature.parameters),
            ("self", "evidence_copy"),
        )
        self.assertEqual(
            tuple(production_signature.parameters),
            ("self", "transaction"),
        )
        self.assertNotEqual(rehearsal_signature, production_signature)

    def test_explicit_uninstall_remains_policy_not_adapter_shortcut(self) -> None:
        self.assertIn(
            v1.TransactionAction.EXPLICIT_UNINSTALL,
            tuple(v1.TransactionAction),
        )
        self.assertNotIn(
            "explicit-uninstall",
            tuple(operation.value for operation in v2.ALL_OPERATIONS_V2),
        )
        self.assertFalse(
            hasattr(v2.ProductionAdapterV2, "explicit_uninstall")
        )
        self.assertFalse(
            hasattr(v2.BlockedProductionAdapterV2, "explicit_uninstall")
        )

    def test_module_has_no_host_access_cli_or_generic_dispatch(self) -> None:
        imported: set[str] = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        self.assertTrue(
            {
                "argparse",
                "fcntl",
                "os",
                "pathlib",
                "requests",
                "shlex",
                "shutil",
                "socket",
                "subprocess",
                "urllib",
            }.isdisjoint(imported)
        )
        methods = {
            node.name
            for node in ast.walk(self.tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertTrue(
            {"execute", "dispatch", "run", "run_command", "main"}.isdisjoint(
                methods
            )
        )
        for marker in (
            "if __name__",
            "REQUIRED_CONFIRMATION",
            "--confirm",
            "shell=True",
            "systemctl",
            "amixer",
            "modprobe",
            "aplay",
        ):
            self.assertNotIn(marker, self.source)

    def test_contract_snapshot_is_static_and_complete(self) -> None:
        snapshot = dict(v2.contract_snapshot_v2())
        self.assertEqual(snapshot["version"], "2")
        self.assertEqual(snapshot["v1_operation_count"], "33")
        self.assertEqual(snapshot["operation_count"], "34")
        self.assertEqual(snapshot["read_only_count"], "17")
        self.assertEqual(snapshot["mutating_count"], "17")
        self.assertEqual(snapshot["activation_interface"], "absent")
        self.assertEqual(
            snapshot["operations"].split(","),
            [operation.value for operation in v2.ALL_OPERATIONS_V2],
        )


if __name__ == "__main__":
    unittest.main()
