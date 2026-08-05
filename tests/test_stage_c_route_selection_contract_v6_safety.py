from __future__ import annotations

import ast
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from scripts.stage_c_transaction.production_adapter_contract import (
    AdapterStatus,
    TransactionIdentity,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v5 import (
    ALL_OPERATIONS_V5,
    MUTATING_OPERATIONS_V5,
    READ_ONLY_OPERATIONS_V5,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v6 import (
    ALL_OPERATIONS_V6,
    MUTATING_OPERATIONS_V6,
    READ_ONLY_OPERATIONS_V6,
    BlockedProductionAdapterV6,
    ProductionAdapterV6,
    ProductionRouteSelectionRollbackAdapterBlocked,
    RouteSelectionRollbackLifecycleOperation,
    RouteSelectionRollbackTransactionReceipt,
    STAGE_BOUNDARIES_V6,
    contract_snapshot_v6,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE = (
    REPO_ROOT
    / "scripts/stage_c_transaction/production_adapter_lifecycle_v6.py"
)


class StageCRouteSelectionContractV6SafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = MODULE.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)
        self.transaction = TransactionIdentity("stage-c15-install-test-route-v6")

    def receipt(self, **overrides):
        values = {
            "transaction": self.transaction,
            "state": "split-bus-route-rolled-back-and-closed",
            "mutation_started": True,
            "managed_files_installed": True,
            "systemd_reloaded": True,
            "split_bus_route_selected": True,
            "active_route_restored": True,
            "filesystem_restored": True,
            "systemd_manager_restored": True,
            "services_restored": True,
            "committed": False,
            "transaction_path_absent": True,
            "parents_restored": True,
            "installed_file_count": 12,
            "daemon_reload_count": 2,
            "route_selection_count": 1,
            "audit_evidence": "/var/tmp/stage-c20-test",
        }
        values.update(overrides)
        return RouteSelectionRollbackTransactionReceipt(**values)

    def test_v1_through_v5_history_remains_exact(self) -> None:
        self.assertEqual(tuple(ALL_OPERATIONS_V6[:-1]), ALL_OPERATIONS_V5)
        self.assertEqual(tuple(READ_ONLY_OPERATIONS_V6), READ_ONLY_OPERATIONS_V5)
        self.assertEqual(
            tuple(MUTATING_OPERATIONS_V6[:-1]),
            MUTATING_OPERATIONS_V5,
        )

    def test_v6_adds_exactly_one_unique_operation(self) -> None:
        self.assertEqual(len(ALL_OPERATIONS_V5), 37)
        self.assertEqual(len(ALL_OPERATIONS_V6), 38)
        self.assertIs(
            ALL_OPERATIONS_V6[-1],
            RouteSelectionRollbackLifecycleOperation.
            CLOSE_ROUTE_SELECTION_ROLLBACK_REHEARSAL_TRANSACTION,
        )
        values = tuple(operation.value for operation in ALL_OPERATIONS_V6)
        self.assertEqual(len(values), len(set(values)))

    def test_v6_partition_is_seventeen_and_twenty_one(self) -> None:
        self.assertEqual(len(READ_ONLY_OPERATIONS_V6), 17)
        self.assertEqual(len(MUTATING_OPERATIONS_V6), 21)
        self.assertFalse(
            set(READ_ONLY_OPERATIONS_V6).intersection(MUTATING_OPERATIONS_V6)
        )
        self.assertEqual(
            set(READ_ONLY_OPERATIONS_V6).union(MUTATING_OPERATIONS_V6),
            set(ALL_OPERATIONS_V6),
        )

    def test_stage_c20_boundary_is_exactly_twenty_nine_and_nine(self) -> None:
        self.assertEqual(len(STAGE_BOUNDARIES_V6), 1)
        boundary = STAGE_BOUNDARIES_V6[0]
        self.assertEqual(boundary.stage, "C20")
        self.assertEqual(boundary.permitted, 29)
        self.assertEqual(boundary.blocked, 9)

    def test_receipt_is_frozen_and_accepts_only_exact_state(self) -> None:
        receipt = self.receipt()
        self.assertEqual(receipt.route_selection_count, 1)
        with self.assertRaises(FrozenInstanceError):
            receipt.state = "changed"  # type: ignore[misc]
        invalid = (
            {"state": "wrong"},
            {"mutation_started": False},
            {"managed_files_installed": False},
            {"systemd_reloaded": False},
            {"split_bus_route_selected": False},
            {"active_route_restored": False},
            {"filesystem_restored": False},
            {"systemd_manager_restored": False},
            {"services_restored": False},
            {"committed": True},
            {"transaction_path_absent": False},
            {"parents_restored": False},
            {"installed_file_count": 11},
            {"daemon_reload_count": 1},
            {"route_selection_count": 0},
            {"audit_evidence": ""},
        )
        for override in invalid:
            with self.subTest(override=override):
                with self.assertRaises(ValueError):
                    self.receipt(**override)

    def test_blocked_v6_adapter_fails_with_exact_identity(self) -> None:
        adapter = BlockedProductionAdapterV6()
        self.assertIsInstance(adapter, ProductionAdapterV6)
        with self.assertRaises(
            ProductionRouteSelectionRollbackAdapterBlocked
        ) as raised:
            adapter.close_route_selection_rollback_rehearsal_transaction(
                self.transaction
            )
        self.assertIs(
            raised.exception.operation,
            RouteSelectionRollbackLifecycleOperation.
            CLOSE_ROUTE_SELECTION_ROLLBACK_REHEARSAL_TRANSACTION,
        )

    def test_contract_snapshot_is_static_and_complete(self) -> None:
        snapshot = dict(contract_snapshot_v6())
        self.assertEqual(snapshot["version"], "6")
        self.assertEqual(snapshot["v5_operation_count"], "37")
        self.assertEqual(snapshot["operation_count"], "38")
        self.assertEqual(snapshot["read_only_count"], "17")
        self.assertEqual(snapshot["mutating_count"], "21")
        self.assertEqual(snapshot["activation_interface"], "absent")
        self.assertIn(
            "close-route-selection-rollback-rehearsal-transaction",
            snapshot["operations"],
        )

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
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"eval", "exec", "getattr"})
                elif isinstance(node.func, ast.Attribute):
                    self.assertNotEqual(node.func.attr, "dispatch")

    def test_result_status_type_remains_adapter_status(self) -> None:
        self.assertIs(AdapterStatus.PASS, AdapterStatus.PASS)


if __name__ == "__main__":
    unittest.main()
