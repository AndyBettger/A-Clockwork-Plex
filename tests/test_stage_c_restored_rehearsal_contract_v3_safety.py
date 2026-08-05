from __future__ import annotations

import ast
import inspect
import unittest
from pathlib import Path

from scripts.stage_c_transaction.production_adapter_contract import (
    AdapterOperation,
    ServiceUnit,
    TransactionIdentity,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v2 import (
    ALL_OPERATIONS_V2,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v3 import (
    ALL_OPERATIONS_V3,
    MUTATING_OPERATIONS_V3,
    READ_ONLY_OPERATIONS_V3,
    STAGE_BOUNDARIES_V3,
    BlockedProductionAdapterV3,
    ProductionAdapterV3,
    ProductionRestoredRehearsalAdapterBlocked,
    RestoredRehearsalLifecycleOperation,
    RestoredRehearsalTransactionReceipt,
    contract_snapshot_v3,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE = (
    REPO_ROOT
    / "scripts/stage_c_transaction/production_adapter_lifecycle_v3.py"
)


class StageCRestoredRehearsalContractV3SafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = MODULE.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    def receipt(self, **overrides):
        values = {
            "transaction": TransactionIdentity("stage-c17-test-transaction"),
            "state": "rehearsal-restored-and-closed",
            "mutation_started": True,
            "restored": True,
            "committed": False,
            "transaction_path_absent": True,
            "parents_restored": True,
            "restored_services": (
                ServiceUnit.PLEXAMP,
                ServiceUnit.SHAIRPORT_SYNC,
                ServiceUnit.DASHBOARD,
            ),
            "audit_evidence": "/var/tmp/stage-c17-test",
        }
        values.update(overrides)
        return RestoredRehearsalTransactionReceipt(**values)

    def test_v1_and_v2_history_remain_exact(self) -> None:
        self.assertEqual(len(AdapterOperation), 33)
        self.assertEqual(len(ALL_OPERATIONS_V2), 34)
        self.assertEqual(
            tuple(ALL_OPERATIONS_V3[:-1]),
            tuple(ALL_OPERATIONS_V2),
        )

    def test_v3_adds_exactly_one_unique_operation(self) -> None:
        self.assertEqual(len(ALL_OPERATIONS_V3), 35)
        self.assertIs(
            ALL_OPERATIONS_V3[-1],
            RestoredRehearsalLifecycleOperation.
            CLOSE_RESTORED_REHEARSAL_TRANSACTION,
        )
        values = tuple(operation.value for operation in ALL_OPERATIONS_V3)
        self.assertEqual(len(values), len(set(values)))

    def test_v3_partition_is_seventeen_and_eighteen(self) -> None:
        self.assertEqual(len(READ_ONLY_OPERATIONS_V3), 17)
        self.assertEqual(len(MUTATING_OPERATIONS_V3), 18)
        self.assertFalse(
            set(READ_ONLY_OPERATIONS_V3).intersection(
                MUTATING_OPERATIONS_V3
            )
        )
        self.assertEqual(
            set(READ_ONLY_OPERATIONS_V3).union(MUTATING_OPERATIONS_V3),
            set(ALL_OPERATIONS_V3),
        )

    def test_stage_c17_boundary_is_exactly_twenty_one_and_fourteen(self) -> None:
        self.assertEqual(len(STAGE_BOUNDARIES_V3), 1)
        boundary = STAGE_BOUNDARIES_V3[0]
        self.assertEqual(boundary.stage, "C17")
        self.assertEqual(boundary.permitted, 21)
        self.assertEqual(boundary.blocked, 14)

    def test_receipt_is_frozen_and_accepts_only_restored_state(self) -> None:
        receipt = self.receipt()
        self.assertTrue(receipt.mutation_started)
        self.assertTrue(receipt.restored)
        self.assertFalse(receipt.committed)
        for override in (
            {"state": "aborted-before-mutation"},
            {"mutation_started": False},
            {"restored": False},
            {"committed": True},
            {"transaction_path_absent": False},
            {"parents_restored": False},
            {"restored_services": ()},
            {"audit_evidence": ""},
        ):
            with self.subTest(override=override):
                with self.assertRaises(ValueError):
                    self.receipt(**override)

    def test_receipt_rejects_non_application_or_duplicate_services(self) -> None:
        for services in (
            (ServiceUnit.PLEXAMP, ServiceUnit.PLEXAMP),
            (ServiceUnit.PLEXAMP, ServiceUnit.CAMILLADSP),
        ):
            with self.subTest(services=services):
                with self.assertRaises(ValueError):
                    self.receipt(restored_services=services)

    def test_v3_protocol_adds_only_transaction_identity_method(self) -> None:
        signature = inspect.signature(
            ProductionAdapterV3.close_restored_rehearsal_transaction
        )
        self.assertEqual(tuple(signature.parameters), ("self", "transaction"))
        self.assertEqual(
            signature.parameters["transaction"].annotation,
            "TransactionIdentity",
        )

    def test_blocked_v3_adapter_fails_with_exact_identity(self) -> None:
        adapter = BlockedProductionAdapterV3()
        transaction = TransactionIdentity("stage-c17-blocked-test")
        with self.assertRaises(
            ProductionRestoredRehearsalAdapterBlocked
        ) as context:
            adapter.close_restored_rehearsal_transaction(transaction)
        self.assertIs(
            context.exception.operation,
            RestoredRehearsalLifecycleOperation.
            CLOSE_RESTORED_REHEARSAL_TRANSACTION,
        )

    def test_module_has_no_host_access_or_generic_dispatch(self) -> None:
        imports = {
            alias.name
            for node in self.tree.body
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertFalse(
            imports.intersection(
                {"os", "subprocess", "pathlib", "shutil", "socket"}
            )
        )
        for forbidden in (
            "Popen",
            "subprocess.run",
            "os.system",
            "shell=True",
            "eval(",
            "exec(",
            "argparse",
            "__main__",
        ):
            self.assertNotIn(forbidden, self.source)

        dispatch_definitions = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "dispatch"
        ]
        dispatch_calls = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Name) and node.func.id == "dispatch")
                or (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "dispatch"
                )
            )
        ]
        generic_getattr_calls = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
        ]
        self.assertEqual(dispatch_definitions, [])
        self.assertEqual(dispatch_calls, [])
        self.assertEqual(generic_getattr_calls, [])

    def test_contract_snapshot_is_static_and_complete(self) -> None:
        snapshot = dict(contract_snapshot_v3())
        self.assertEqual(snapshot["version"], "3")
        self.assertEqual(snapshot["v2_operation_count"], "34")
        self.assertEqual(snapshot["operation_count"], "35")
        self.assertEqual(snapshot["read_only_count"], "17")
        self.assertEqual(snapshot["mutating_count"], "18")
        self.assertEqual(snapshot["activation_interface"], "absent")
        self.assertEqual(
            snapshot["restored_rehearsal_operation"],
            "close-restored-rehearsal-transaction",
        )


if __name__ == "__main__":
    unittest.main()
