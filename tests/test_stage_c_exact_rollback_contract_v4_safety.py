from __future__ import annotations

import ast
import unittest
from dataclasses import replace
from pathlib import Path

from scripts.stage_c_transaction.production_adapter_contract import (
    AdapterOperation,
    AdapterStatus,
    TransactionIdentity,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v2 import (
    ALL_OPERATIONS_V2,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v3 import (
    ALL_OPERATIONS_V3,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v4 import (
    ALL_OPERATIONS_V4,
    MUTATING_OPERATIONS_V4,
    READ_ONLY_OPERATIONS_V4,
    STAGE_BOUNDARIES_V4,
    BlockedProductionAdapterV4,
    ExactRollbackRehearsalLifecycleOperation,
    ExactRollbackRehearsalTransactionReceipt,
    ProductionAdapterV4,
    ProductionExactRollbackRehearsalAdapterBlocked,
    contract_snapshot_v4,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    REPO_ROOT
    / "scripts/stage_c_transaction/production_adapter_lifecycle_v4.py"
)


class StageCExactRollbackContractV4SafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = CONTRACT.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)
        self.receipt = ExactRollbackRehearsalTransactionReceipt(
            transaction=TransactionIdentity("stage-c18-test-transaction"),
            state="managed-files-rolled-back-and-closed",
            mutation_started=True,
            managed_files_installed=True,
            filesystem_restored=True,
            services_restored=True,
            committed=False,
            transaction_path_absent=True,
            parents_restored=True,
            installed_file_count=12,
            audit_evidence="/var/tmp/stage-c18-test-evidence",
        )

    def test_v1_v2_and_v3_history_remain_exact(self) -> None:
        self.assertEqual(len(tuple(AdapterOperation)), 33)
        self.assertEqual(len(ALL_OPERATIONS_V2), 34)
        self.assertEqual(len(ALL_OPERATIONS_V3), 35)
        self.assertEqual(
            tuple(ALL_OPERATIONS_V4[: len(ALL_OPERATIONS_V3)]),
            tuple(ALL_OPERATIONS_V3),
        )

    def test_v4_adds_exactly_one_unique_operation(self) -> None:
        self.assertEqual(len(ALL_OPERATIONS_V4), 36)
        self.assertEqual(len({operation.value for operation in ALL_OPERATIONS_V4}), 36)
        self.assertEqual(
            ALL_OPERATIONS_V4[-1],
            ExactRollbackRehearsalLifecycleOperation.
            CLOSE_EXACT_ROLLBACK_REHEARSAL_TRANSACTION,
        )

    def test_v4_partition_is_seventeen_and_nineteen(self) -> None:
        self.assertEqual(len(READ_ONLY_OPERATIONS_V4), 17)
        self.assertEqual(len(MUTATING_OPERATIONS_V4), 19)
        self.assertFalse(
            set(READ_ONLY_OPERATIONS_V4).intersection(MUTATING_OPERATIONS_V4)
        )
        self.assertEqual(
            set(READ_ONLY_OPERATIONS_V4).union(MUTATING_OPERATIONS_V4),
            set(ALL_OPERATIONS_V4),
        )

    def test_stage_c18_boundary_is_exactly_twenty_five_and_eleven(self) -> None:
        self.assertEqual(len(STAGE_BOUNDARIES_V4), 1)
        boundary = STAGE_BOUNDARIES_V4[0]
        self.assertEqual(boundary.stage, "C18")
        self.assertEqual(boundary.permitted, 25)
        self.assertEqual(boundary.blocked, 11)

    def test_receipt_is_frozen_and_accepts_only_exact_rollback_state(self) -> None:
        self.assertEqual(self.receipt.installed_file_count, 12)
        with self.assertRaises(Exception):
            self.receipt.committed = True  # type: ignore[misc]
        invalid = (
            ("state", "rehearsal-restored-and-closed"),
            ("mutation_started", False),
            ("managed_files_installed", False),
            ("filesystem_restored", False),
            ("services_restored", False),
            ("committed", True),
            ("transaction_path_absent", False),
            ("parents_restored", False),
            ("installed_file_count", 11),
            ("audit_evidence", ""),
        )
        for field, value in invalid:
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    replace(self.receipt, **{field: value})

    def test_v4_protocol_adds_only_transaction_identity_method(self) -> None:
        node = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.ClassDef) and node.name == "ProductionAdapterV4"
        )
        methods = [
            item.name
            for item in node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        self.assertEqual(
            methods,
            ["close_exact_rollback_rehearsal_transaction"],
        )
        method = next(
            item
            for item in node.body
            if isinstance(item, ast.FunctionDef)
        )
        annotation = ast.unparse(method.args.args[1].annotation)
        self.assertEqual(annotation, "TransactionIdentity")

    def test_blocked_v4_adapter_fails_with_exact_identity(self) -> None:
        adapter = BlockedProductionAdapterV4()
        self.assertIsInstance(adapter, ProductionAdapterV4)
        with self.assertRaises(
            ProductionExactRollbackRehearsalAdapterBlocked
        ) as caught:
            adapter.close_exact_rollback_rehearsal_transaction(
                self.receipt.transaction
            )
        self.assertIs(
            caught.exception.operation,
            ExactRollbackRehearsalLifecycleOperation.
            CLOSE_EXACT_ROLLBACK_REHEARSAL_TRANSACTION,
        )

    def test_contract_snapshot_is_static_and_complete(self) -> None:
        snapshot = dict(contract_snapshot_v4())
        self.assertEqual(snapshot["version"], "4")
        self.assertEqual(snapshot["v3_operation_count"], "35")
        self.assertEqual(snapshot["operation_count"], "36")
        self.assertEqual(snapshot["read_only_count"], "17")
        self.assertEqual(snapshot["mutating_count"], "19")
        self.assertEqual(snapshot["activation_interface"], "absent")
        self.assertEqual(
            snapshot["exact_rollback_rehearsal_operation"],
            "close-exact-rollback-rehearsal-transaction",
        )

    def test_module_has_no_host_access_cli_or_generic_dispatch(self) -> None:
        imports = {
            alias.name
            for node in self.tree.body
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module or ""
            for node in self.tree.body
            if isinstance(node, ast.ImportFrom)
        )
        for forbidden in (
            "os",
            "pathlib",
            "subprocess",
            "argparse",
            "socket",
            "urllib",
        ):
            self.assertNotIn(forbidden, imports)
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.assertNotIn(node.name, {"dispatch", "execute", "run_command"})
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"getattr", "eval", "exec"})

    def test_result_payload_is_present_only_for_pass(self) -> None:
        from scripts.stage_c_transaction.production_adapter_lifecycle_v4 import (
            ExactRollbackRehearsalAdapterResult,
        )

        passed = ExactRollbackRehearsalAdapterResult(
            operation=(
                ExactRollbackRehearsalLifecycleOperation.
                CLOSE_EXACT_ROLLBACK_REHEARSAL_TRANSACTION
            ),
            status=AdapterStatus.PASS,
            detail="closed",
            payload=self.receipt,
        )
        self.assertIs(passed.payload, self.receipt)
        with self.assertRaises(ValueError):
            ExactRollbackRehearsalAdapterResult(
                operation=(
                    ExactRollbackRehearsalLifecycleOperation.
                    CLOSE_EXACT_ROLLBACK_REHEARSAL_TRANSACTION
                ),
                status=AdapterStatus.FAIL,
                detail="failed",
                payload=self.receipt,
            )


if __name__ == "__main__":
    unittest.main()
