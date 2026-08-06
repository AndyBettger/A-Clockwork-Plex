#!/usr/bin/python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from stage_c_transaction import current_package_candidate_rehearsal_adapter_v7 as adapter_v7
from stage_c_transaction import current_package_candidate_rehearsal_parent_contract_v8 as contract_v8
from stage_c_transaction import current_package_candidate_rehearsal_v7 as rehearsal_v7


class StageC21EvidenceTreeContractV8Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_parent_contract = adapter_v7.CURRENT_PARENT_CONTRACT
        self.original_checker = rehearsal_v7._assert_regular_tree

    def tearDown(self) -> None:
        adapter_v7.CURRENT_PARENT_CONTRACT = self.original_parent_contract
        rehearsal_v7._assert_regular_tree = self.original_checker

    def test_current_helper_receives_fixed_stage_c21_label(self) -> None:
        calls: list[tuple[Path, str]] = []

        def checker(root: Path, label: str) -> None:
            calls.append((root, label))

        rehearsal_v7._assert_regular_tree = checker
        contract_v8.apply_evidence_tree_label_contract_v8()

        evidence = Path("/var/tmp/stage-c21-evidence")
        rehearsal_v7._assert_regular_tree(evidence)

        self.assertEqual(
            calls,
            [(evidence, contract_v8.EVIDENCE_TREE_LABEL_V8)],
        )

    def test_binding_is_idempotent(self) -> None:
        def checker(root: Path, label: str) -> None:
            del root, label

        rehearsal_v7._assert_regular_tree = checker
        contract_v8.apply_evidence_tree_label_contract_v8()
        wrapped = rehearsal_v7._assert_regular_tree
        contract_v8.apply_evidence_tree_label_contract_v8()

        self.assertIs(rehearsal_v7._assert_regular_tree, wrapped)

    def test_unreviewed_helper_signature_drift_is_rejected(self) -> None:
        def changed_checker(root: Path) -> None:
            del root

        rehearsal_v7._assert_regular_tree = changed_checker
        with self.assertRaisesRegex(
            SystemExit,
            "regular-tree helper signature changed",
        ):
            contract_v8.apply_evidence_tree_label_contract_v8()

    def test_main_applies_both_bindings_before_v7_rehearsal(self) -> None:
        order: list[str] = []

        with mock.patch.object(
            contract_v8,
            "apply_target_proved_parent_contract_v8",
            side_effect=lambda: order.append("parent"),
        ), mock.patch.object(
            contract_v8,
            "apply_evidence_tree_label_contract_v8",
            side_effect=lambda: order.append("evidence"),
        ), mock.patch.object(
            rehearsal_v7,
            "main",
            side_effect=lambda argv: order.append(f"main:{argv[0]}") or 17,
        ):
            result = contract_v8.main(["approved"])

        self.assertEqual(result, 17)
        self.assertEqual(order, ["parent", "evidence", "main:approved"])

    def test_compatibility_entrypoint_adds_no_mutation_command(self) -> None:
        source = Path(contract_v8.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "os.chmod",
            "os.chown",
            "subprocess",
            "systemctl",
            "amixer",
            "aplay",
            "install-master-eq.sh",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
