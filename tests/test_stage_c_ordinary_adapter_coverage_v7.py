from __future__ import annotations

import ast
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/stage_c_transaction/ordinary_adapter_coverage_v7.py"

from scripts.stage_c_transaction.activation_commit_program_v7 import (
    ACTIVATION_EXACT_ROLLBACK_V7,
    ACTIVATION_INSTALL_SUFFIX_V7,
)
from scripts.stage_c_transaction.ordinary_adapter_coverage_v7 import (
    AUTHORITY_OWNERSHIP_V7,
    C20_BLOCKED_ORDINARY_OPERATIONS,
    C20_REHEARSAL_OPERATIONS,
    COVERAGE_BY_OPERATION_V7,
    DISPOSABLE_APPROVAL_OPERATIONS,
    OPERATION_COVERAGE_V7,
    RUNTIME_AUTHORITY_RELATED_OPERATIONS,
    TERMINAL_READINESS_V7,
    AdapterEvidenceV7,
    RelatedRuntimeMechanicsV7,
)
from scripts.stage_c_transaction.production_adapter_contract import (
    AUTHORITATIVE_TRANSACTION_ROOT,
    PRODUCTION_LOCK_PATH,
    AdapterOperation,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v6 import (
    ALL_OPERATIONS_V6,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v7 import (
    ALL_OPERATIONS_V7,
    ActivationApprovalLifecycleOperation,
)
from scripts.stage_c_transaction.route_selection_rollback_rehearsal_adapter import (
    BLOCKED_V6_COUNT,
    PERMITTED_V1_OPERATIONS,
    PERMITTED_V6_COUNT,
)


class StageCOrdinaryAdapterCoverageV7Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = MODULE.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    def test_all_forty_two_operations_are_classified_once_in_frozen_order(self) -> None:
        self.assertEqual(len(ALL_OPERATIONS_V7), 42)
        self.assertEqual(len(OPERATION_COVERAGE_V7), 42)
        self.assertEqual(len(COVERAGE_BY_OPERATION_V7), 42)
        self.assertEqual(
            tuple(item.operation for item in OPERATION_COVERAGE_V7),
            ALL_OPERATIONS_V7,
        )
        self.assertEqual(
            set(COVERAGE_BY_OPERATION_V7),
            set(ALL_OPERATIONS_V7),
        )

    def test_c20_partition_matches_the_real_rehearsal_adapter_boundary(self) -> None:
        self.assertEqual(PERMITTED_V6_COUNT, 29)
        self.assertEqual(BLOCKED_V6_COUNT, 9)
        self.assertEqual(len(C20_REHEARSAL_OPERATIONS), 29)
        self.assertEqual(len(C20_BLOCKED_ORDINARY_OPERATIONS), 9)
        self.assertEqual(
            set(C20_REHEARSAL_OPERATIONS).union(
                C20_BLOCKED_ORDINARY_OPERATIONS
            ),
            set(ALL_OPERATIONS_V6),
        )
        self.assertFalse(
            set(C20_REHEARSAL_OPERATIONS).intersection(
                C20_BLOCKED_ORDINARY_OPERATIONS
            )
        )
        self.assertEqual(
            tuple(C20_REHEARSAL_OPERATIONS[: len(PERMITTED_V1_OPERATIONS)]),
            PERMITTED_V1_OPERATIONS,
        )

    def test_exact_nine_ordinary_operations_remain_blocked(self) -> None:
        self.assertEqual(
            set(C20_BLOCKED_ORDINARY_OPERATIONS),
            {
                AdapterOperation.START_MANAGED_STAGE_C_SERVICES,
                AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES,
                AdapterOperation.VERIFY_SPLIT_BUS_HEALTH,
                AdapterOperation.RUN_FINITE_MUSIC_PROBE,
                AdapterOperation.RUN_FINITE_ALARM_PROBE,
                AdapterOperation.WRITE_COMMIT_MANIFEST,
                AdapterOperation.SELECT_DIRECT_FAILBACK_ROUTE,
                AdapterOperation.RESTORE_MIXER_STATE,
                AdapterOperation.RESTORE_SERVICE_STATE,
            },
        )
        for operation in C20_BLOCKED_ORDINARY_OPERATIONS:
            record = COVERAGE_BY_OPERATION_V7[operation]
            self.assertIs(
                record.evidence,
                AdapterEvidenceV7.BLOCKED_ORDINARY_CONTRACT,
            )
            self.assertFalse(record.physically_rehearsed_on_appliance)
            self.assertFalse(record.disposable_filesystem_proved)
            self.assertFalse(record.production_terminal_ready)

    def test_twenty_nine_operations_are_rehearsal_not_production_evidence(self) -> None:
        for operation in C20_REHEARSAL_OPERATIONS:
            record = COVERAGE_BY_OPERATION_V7[operation]
            self.assertIs(
                record.evidence,
                AdapterEvidenceV7.C20_MANDATORY_ROLLBACK_REHEARSAL,
            )
            self.assertTrue(record.physically_rehearsed_on_appliance)
            self.assertFalse(record.disposable_filesystem_proved)
            self.assertFalse(record.production_terminal_ready)
            self.assertIn("mandatory-rollback", record.detail)

    def test_four_approval_operations_are_disposable_only(self) -> None:
        self.assertEqual(
            DISPOSABLE_APPROVAL_OPERATIONS,
            tuple(ActivationApprovalLifecycleOperation),
        )
        self.assertEqual(len(DISPOSABLE_APPROVAL_OPERATIONS), 4)
        for operation in DISPOSABLE_APPROVAL_OPERATIONS:
            record = COVERAGE_BY_OPERATION_V7[operation]
            self.assertIs(
                record.evidence,
                AdapterEvidenceV7.DISPOSABLE_APPROVAL_LABORATORY,
            )
            self.assertFalse(record.physically_rehearsed_on_appliance)
            self.assertTrue(record.disposable_filesystem_proved)
            self.assertFalse(record.production_terminal_ready)

    def test_related_runtime_mechanics_do_not_claim_protocol_implementation(self) -> None:
        self.assertEqual(
            set(RUNTIME_AUTHORITY_RELATED_OPERATIONS),
            {
                AdapterOperation.START_MANAGED_STAGE_C_SERVICES,
                AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES,
                AdapterOperation.VERIFY_SPLIT_BUS_HEALTH,
                AdapterOperation.SELECT_DIRECT_FAILBACK_ROUTE,
            },
        )
        for operation in RUNTIME_AUTHORITY_RELATED_OPERATIONS:
            record = COVERAGE_BY_OPERATION_V7[operation]
            self.assertIs(
                record.evidence,
                AdapterEvidenceV7.BLOCKED_ORDINARY_CONTRACT,
            )
            self.assertIs(
                record.related_runtime_mechanics,
                RelatedRuntimeMechanicsV7.SEPARATE_RUNTIME_AUTHORITY_PROTOCOL,
            )
            self.assertFalse(record.production_terminal_ready)
        for operation in set(ALL_OPERATIONS_V7).difference(
            RUNTIME_AUTHORITY_RELATED_OPERATIONS
        ):
            self.assertIs(
                COVERAGE_BY_OPERATION_V7[operation].related_runtime_mechanics,
                RelatedRuntimeMechanicsV7.NONE,
            )

    def test_activation_suffix_and_exact_rollback_have_no_ready_operation(self) -> None:
        suffix = tuple(step.operation for step in ACTIVATION_INSTALL_SUFFIX_V7)
        rollback = tuple(step.operation for step in ACTIVATION_EXACT_ROLLBACK_V7)
        self.assertEqual(len(suffix), 11)
        self.assertEqual(len(rollback), 10)
        for operation in (*suffix, *rollback):
            self.assertFalse(
                COVERAGE_BY_OPERATION_V7[operation].production_terminal_ready
            )
        self.assertFalse(TERMINAL_READINESS_V7.production_activation_ready)
        self.assertFalse(TERMINAL_READINESS_V7.production_exact_rollback_ready)
        self.assertEqual(TERMINAL_READINESS_V7.production_ready_operations, 0)

    def test_readiness_counts_are_exact_and_point_to_read_only_next_step(self) -> None:
        self.assertEqual(TERMINAL_READINESS_V7.total_operations, 42)
        self.assertEqual(TERMINAL_READINESS_V7.c20_rehearsal_operations, 29)
        self.assertEqual(TERMINAL_READINESS_V7.blocked_ordinary_operations, 9)
        self.assertEqual(TERMINAL_READINESS_V7.disposable_approval_operations, 4)
        self.assertEqual(TERMINAL_READINESS_V7.activation_suffix_operations, 11)
        self.assertEqual(TERMINAL_READINESS_V7.exact_rollback_operations, 10)
        self.assertIn(
            "read-only typed view",
            TERMINAL_READINESS_V7.smallest_safe_next_increment,
        )
        with self.assertRaises(FrozenInstanceError):
            TERMINAL_READINESS_V7.production_activation_ready = True  # type: ignore[misc]

    def test_one_existing_lock_and_transaction_authority_remain_canonical(self) -> None:
        self.assertEqual(
            AUTHORITY_OWNERSHIP_V7.production_lock_path,
            PRODUCTION_LOCK_PATH,
        )
        self.assertEqual(
            AUTHORITY_OWNERSHIP_V7.authoritative_transaction_root,
            AUTHORITATIVE_TRANSACTION_ROOT,
        )
        self.assertTrue(AUTHORITY_OWNERSHIP_V7.approval_must_bind_existing_lock)
        self.assertTrue(
            AUTHORITY_OWNERSHIP_V7.second_production_lock_authority_forbidden
        )
        self.assertIn(
            "ProductionLockRehearsalAdapter",
            AUTHORITY_OWNERSHIP_V7.current_lock_owner,
        )
        self.assertIn(
            "AuthoritativeSnapshotRehearsalAdapter",
            AUTHORITY_OWNERSHIP_V7.current_transaction_owner,
        )

    def test_module_is_static_metadata_without_host_or_dispatch_boundary(self) -> None:
        forbidden_imports = {
            "argparse",
            "ctypes",
            "fcntl",
            "json",
            "os",
            "pathlib",
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
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.assertNotIn("dispatch", node.name.lower())
                names = {
                    argument.arg
                    for argument in (*node.args.args, *node.args.kwonlyargs)
                }
                self.assertTrue(
                    names.isdisjoint(
                        {
                            "command",
                            "path",
                            "unit_name",
                            "transaction_root",
                            "lease_id",
                        }
                    )
                )
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    self.assertNotIn(
                        node.func.id,
                        {"eval", "exec", "open", "getattr", "setattr"},
                    )
                elif isinstance(node.func, ast.Attribute):
                    self.assertNotEqual(node.func.attr, "dispatch")
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
