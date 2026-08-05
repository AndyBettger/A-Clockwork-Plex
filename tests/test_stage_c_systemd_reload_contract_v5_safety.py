from __future__ import annotations

import ast
import unittest
from dataclasses import replace
from pathlib import Path

from scripts.stage_c_transaction.production_adapter_contract import AdapterStatus
from scripts.stage_c_transaction.production_adapter_lifecycle_v4 import (
    ALL_OPERATIONS_V4,
    MUTATING_OPERATIONS_V4,
    READ_ONLY_OPERATIONS_V4,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v5 import (
    ALL_OPERATIONS_V5,
    MUTATING_OPERATIONS_V5,
    READ_ONLY_OPERATIONS_V5,
    STAGE_BOUNDARIES_V5,
    BlockedProductionAdapterV5,
    ProductionAdapterV5,
    ProductionSystemdReloadRollbackAdapterBlocked,
    SystemdReloadRollbackAdapterResult,
    SystemdReloadRollbackLifecycleOperation,
    SystemdReloadRollbackTransactionReceipt,
    contract_snapshot_v5,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE = (
    REPO_ROOT
    / "scripts/stage_c_transaction/production_adapter_lifecycle_v5.py"
)


class StageCSystemdReloadContractV5SafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = MODULE.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    @staticmethod
    def valid_receipt() -> SystemdReloadRollbackTransactionReceipt:
        return SystemdReloadRollbackTransactionReceipt(
            transaction=object(),  # type: ignore[arg-type]
            state="systemd-reload-rolled-back-and-closed",
            mutation_started=True,
            managed_files_installed=True,
            systemd_reloaded=True,
            filesystem_restored=True,
            systemd_manager_restored=True,
            services_restored=True,
            committed=False,
            transaction_path_absent=True,
            parents_restored=True,
            installed_file_count=12,
            daemon_reload_count=2,
            audit_evidence="/var/tmp/stage-c19-evidence",
        )

    def test_v1_through_v4_history_remains_exact(self) -> None:
        self.assertEqual(len(ALL_OPERATIONS_V4), 36)
        self.assertEqual(len(READ_ONLY_OPERATIONS_V4), 17)
        self.assertEqual(len(MUTATING_OPERATIONS_V4), 19)
        self.assertEqual(
            tuple(ALL_OPERATIONS_V5[:-1]),
            tuple(ALL_OPERATIONS_V4),
        )

    def test_v5_adds_exactly_one_unique_operation(self) -> None:
        self.assertEqual(len(ALL_OPERATIONS_V5), 37)
        self.assertIs(
            ALL_OPERATIONS_V5[-1],
            SystemdReloadRollbackLifecycleOperation.
            CLOSE_SYSTEMD_RELOAD_ROLLBACK_REHEARSAL_TRANSACTION,
        )
        values = tuple(operation.value for operation in ALL_OPERATIONS_V5)
        self.assertEqual(len(values), len(set(values)))

    def test_v5_partition_is_seventeen_and_twenty(self) -> None:
        self.assertEqual(len(READ_ONLY_OPERATIONS_V5), 17)
        self.assertEqual(len(MUTATING_OPERATIONS_V5), 20)
        self.assertFalse(
            set(READ_ONLY_OPERATIONS_V5).intersection(MUTATING_OPERATIONS_V5)
        )
        self.assertEqual(
            set(READ_ONLY_OPERATIONS_V5).union(MUTATING_OPERATIONS_V5),
            set(ALL_OPERATIONS_V5),
        )

    def test_stage_c19_boundary_is_exactly_twenty_seven_and_ten(self) -> None:
        self.assertEqual(len(STAGE_BOUNDARIES_V5), 1)
        boundary = STAGE_BOUNDARIES_V5[0]
        self.assertEqual(boundary.stage, "C19")
        self.assertEqual(boundary.permitted, 27)
        self.assertEqual(boundary.blocked, 10)

    def test_v5_protocol_adds_only_transaction_identity_method(self) -> None:
        self.assertTrue(
            hasattr(
                ProductionAdapterV5,
                "close_systemd_reload_rollback_rehearsal_transaction",
            )
        )
        method = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "ProductionAdapterV5"
        )
        methods = [
            node.name
            for node in method.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        self.assertEqual(
            methods,
            ["close_systemd_reload_rollback_rehearsal_transaction"],
        )

    def test_blocked_v5_adapter_fails_with_exact_identity(self) -> None:
        adapter = BlockedProductionAdapterV5()
        expected = (
            SystemdReloadRollbackLifecycleOperation.
            CLOSE_SYSTEMD_RELOAD_ROLLBACK_REHEARSAL_TRANSACTION
        )
        with self.assertRaises(
            ProductionSystemdReloadRollbackAdapterBlocked
        ) as caught:
            adapter.close_systemd_reload_rollback_rehearsal_transaction(
                object()  # type: ignore[arg-type]
            )
        self.assertIs(caught.exception.operation, expected)

    def test_receipt_is_frozen_and_accepts_only_exact_state(self) -> None:
        receipt = self.valid_receipt()
        self.assertEqual(receipt.daemon_reload_count, 2)
        invalid = (
            ("state", "wrong"),
            ("mutation_started", False),
            ("managed_files_installed", False),
            ("systemd_reloaded", False),
            ("filesystem_restored", False),
            ("systemd_manager_restored", False),
            ("services_restored", False),
            ("committed", True),
            ("transaction_path_absent", False),
            ("parents_restored", False),
            ("installed_file_count", 11),
            ("daemon_reload_count", 1),
            ("audit_evidence", ""),
        )
        for field, value in invalid:
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    replace(receipt, **{field: value})

    def test_result_payload_is_present_only_for_pass(self) -> None:
        receipt = self.valid_receipt()
        operation = (
            SystemdReloadRollbackLifecycleOperation.
            CLOSE_SYSTEMD_RELOAD_ROLLBACK_REHEARSAL_TRANSACTION
        )
        result = SystemdReloadRollbackAdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="closed",
            payload=receipt,
        )
        self.assertIs(result.payload, receipt)
        with self.assertRaises(ValueError):
            SystemdReloadRollbackAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail="failed",
                payload=receipt,
            )

    def test_contract_snapshot_is_static_and_complete(self) -> None:
        snapshot = dict(contract_snapshot_v5())
        self.assertEqual(snapshot["version"], "5")
        self.assertEqual(snapshot["v4_operation_count"], "36")
        self.assertEqual(snapshot["operation_count"], "37")
        self.assertEqual(snapshot["read_only_count"], "17")
        self.assertEqual(snapshot["mutating_count"], "20")
        self.assertEqual(snapshot["activation_interface"], "absent")
        self.assertIn(
            "close-systemd-reload-rollback-rehearsal-transaction",
            snapshot["operations"],
        )

    def test_module_has_no_host_access_cli_or_generic_dispatch(self) -> None:
        forbidden_imports = {
            "argparse",
            "os",
            "pathlib",
            "subprocess",
            "sys",
        }
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                self.assertFalse(
                    forbidden_imports.intersection(alias.name for alias in node.names)
                )
            elif isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module, forbidden_imports)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.assertNotIn(node.name, {"main", "dispatch", "run_command"})
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"getattr", "eval", "exec"})


if __name__ == "__main__":
    unittest.main()
