from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

MODULE_PATH = (
    ROOT
    / "scripts/stage_c_transaction/"
    "current_package_candidate_rehearsal_parent_contract_v8.py"
)
WRAPPER_PATH = (
    ROOT / "scripts/test-stage-c21-current-package-transaction-preparation.sh"
)

from scripts.stage_c_transaction import (  # noqa: E402
    current_package_candidate_rehearsal_adapter_v7 as adapter_v7,
)
from scripts.stage_c_transaction.current_package_candidate_rehearsal_parent_contract_v8 import (  # noqa: E402
    LEGACY_CURRENT_PARENT_CONTRACT_V7,
    TARGET_PROVED_PARENT_CONTRACT_V8,
    apply_target_proved_parent_contract_v8,
)


class StageC21TargetParentContractV8Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.module_source = MODULE_PATH.read_text(encoding="utf-8")
        self.wrapper_source = WRAPPER_PATH.read_text(encoding="utf-8")

    def test_target_proved_contract_is_exact(self) -> None:
        self.assertEqual(
            TARGET_PROVED_PARENT_CONTRACT_V8,
            (
                (Path("/var/lib/a-clockwork-plex"), 0o755),
                (Path("/var/lib/a-clockwork-plex/split-bus"), 0o755),
                (
                    Path("/var/lib/a-clockwork-plex/split-bus/transactions"),
                    0o700,
                ),
            ),
        )

    def test_correction_changes_only_the_outer_mode(self) -> None:
        self.assertEqual(
            tuple(path for path, _mode in LEGACY_CURRENT_PARENT_CONTRACT_V7),
            tuple(path for path, _mode in TARGET_PROVED_PARENT_CONTRACT_V8),
        )
        changed = tuple(
            index
            for index, (legacy, corrected) in enumerate(
                zip(
                    LEGACY_CURRENT_PARENT_CONTRACT_V7,
                    TARGET_PROVED_PARENT_CONTRACT_V8,
                    strict=True,
                )
            )
            if legacy[1] != corrected[1]
        )
        self.assertEqual(changed, (0,))
        self.assertEqual(LEGACY_CURRENT_PARENT_CONTRACT_V7[0][1], 0o750)
        self.assertEqual(TARGET_PROVED_PARENT_CONTRACT_V8[0][1], 0o755)

    def test_correction_applies_only_to_the_exact_v7_contract(self) -> None:
        original = adapter_v7.CURRENT_PARENT_CONTRACT
        try:
            adapter_v7.CURRENT_PARENT_CONTRACT = LEGACY_CURRENT_PARENT_CONTRACT_V7
            apply_target_proved_parent_contract_v8()
            self.assertEqual(
                adapter_v7.CURRENT_PARENT_CONTRACT,
                TARGET_PROVED_PARENT_CONTRACT_V8,
            )
        finally:
            adapter_v7.CURRENT_PARENT_CONTRACT = original

    def test_correction_refuses_unreviewed_contract_drift(self) -> None:
        original = adapter_v7.CURRENT_PARENT_CONTRACT
        try:
            adapter_v7.CURRENT_PARENT_CONTRACT = (
                (Path("/var/lib/a-clockwork-plex"), 0o777),
                *LEGACY_CURRENT_PARENT_CONTRACT_V7[1:],
            )
            with self.assertRaisesRegex(SystemExit, "v7 parent contract changed"):
                apply_target_proved_parent_contract_v8()
        finally:
            adapter_v7.CURRENT_PARENT_CONTRACT = original

    def test_wrapper_invokes_only_the_corrected_entrypoint(self) -> None:
        self.assertIn(
            "stage_c_transaction."
            "current_package_candidate_rehearsal_parent_contract_v8",
            self.wrapper_source,
        )
        self.assertNotIn(
            "python3 -B -m stage_c_transaction."
            "current_package_candidate_rehearsal_v7",
            self.wrapper_source,
        )
        self.assertEqual(self.wrapper_source.count("exec sudo env"), 1)

    def test_correction_has_no_permission_repair_or_appliance_mutation(self) -> None:
        forbidden = (
            ".chmod(",
            "os.chown(",
            "systemctl",
            "amixer",
            "modprobe",
            "aplay",
            "install-master-eq.sh",
        )
        for token in forbidden:
            self.assertNotIn(token, self.module_source)

    def test_module_parses(self) -> None:
        ast.parse(self.module_source)


if __name__ == "__main__":
    unittest.main()
