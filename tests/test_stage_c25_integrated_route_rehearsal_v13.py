from __future__ import annotations

import ast
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

ENTRY_PATH = (
    ROOT
    / "scripts/stage_c_transaction/"
    "current_package_route_selection_rollback_rehearsal_v13.py"
)
WRAPPER_PATH = ROOT / "scripts/test-stage-c25-current-package-route-rollback.sh"

from scripts.stage_c_transaction.current_package_route_selection_rollback_rehearsal_v13 import (  # noqa: E402
    EVIDENCE_PREFIX,
    EXPECTED_CHECKS,
    REQUIRED_CONFIRMATION,
)


class IntegratedCurrentPackageRouteRehearsalV13Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.entry = ENTRY_PATH.read_text(encoding="utf-8")
        self.wrapper = WRAPPER_PATH.read_text(encoding="utf-8")

    def test_entry_and_wrapper_parse(self) -> None:
        ast.parse(self.entry)
        result = subprocess.run(
            ["bash", "-n", str(WRAPPER_PATH)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_contract_is_one_final_rollback_checkpoint(self) -> None:
        self.assertEqual(
            REQUIRED_CONFIRMATION,
            "STAGE-C25-CURRENT-PACKAGE-ROUTE-EXACT-ROLLBACK",
        )
        self.assertEqual(
            EVIDENCE_PREFIX,
            "a-clockwork-plex-stage-c25-current-package-route-rollback.",
        )
        self.assertEqual(len(EXPECTED_CHECKS), 29)
        self.assertEqual(EXPECTED_CHECKS.count("split-bus-route-selection"), 1)
        self.assertEqual(EXPECTED_CHECKS.count("systemd-candidate-reload"), 1)
        self.assertEqual(EXPECTED_CHECKS.count("systemd-manager-rollback"), 1)

    def test_sequence_combines_install_reload_route_and_exact_rollback(self) -> None:
        install = self.entry.index("adapter.install_managed_files(")
        first_reload = self.entry.index("adapter.reload_systemd(", install)
        select = self.entry.index(
            "route_result = adapter.select_split_bus_route(",
            first_reload,
        )
        rollback = self.entry.index(
            "rollback_result = adapter.restore_exact_snapshot(",
            select,
        )
        second_reload = self.entry.index("adapter.reload_systemd(", rollback)
        restore_services = self.entry.index(
            "adapter.restore_captured_application_services(",
            second_reload,
        )
        close = self.entry.index(
            "adapter.close_current_package_route_rollback_rehearsal(",
            restore_services,
        )
        observed = (
            install,
            first_reload,
            select,
            rollback,
            second_reload,
            restore_services,
            close,
        )
        self.assertEqual(observed, tuple(sorted(observed)))

    def test_runtime_and_approval_are_only_exercised_as_blocked_boundaries(self) -> None:
        self.assertIn("runtime-activation-blocked.tsv", self.entry)
        self.assertIn("prove_approval_operations_blocked", self.entry)
        self.assertIn("START_MANAGED_STAGE_C_SERVICES", self.entry)
        self.assertIn("RUN_FINITE_MUSIC_PROBE", self.entry)
        self.assertIn("RUN_FINITE_ALARM_PROBE", self.entry)
        self.assertNotIn("host_run(", self.entry)
        self.assertNotIn("subprocess", self.entry)
        self.assertNotIn("install-master-eq.sh", self.entry)

    def test_wrapper_has_one_fixed_privileged_entry(self) -> None:
        self.assertIn(
            "current_package_route_selection_rollback_rehearsal_v13",
            self.wrapper,
        )
        self.assertEqual(self.wrapper.count("exec sudo env"), 1)
        self.assertNotIn("systemctl ", self.wrapper)
        self.assertNotIn("modprobe ", self.wrapper)
        self.assertNotIn("install-master-eq.sh", self.wrapper)
        self.assertNotIn("--keep-active", self.wrapper)
        self.assertNotIn("--route", self.wrapper)

    def test_prepare_only_exits_before_the_privileged_entry(self) -> None:
        prepare = self.wrapper.index('if [[ "$MODE" == "prepare" ]]')
        prepare_exit = self.wrapper.index("  exit 0", prepare)
        privileged = self.wrapper.index("exec sudo env")
        self.assertLess(prepare, prepare_exit)
        self.assertLess(prepare_exit, privileged)

    def test_identity_and_report_explicitly_forbid_activation_reuse(self) -> None:
        self.assertIn('"reusable_for_activation\\tfalse\\n"', self.entry)
        self.assertIn("This is the final rollback-only checkpoint", self.entry)
        self.assertIn("approval_published", self.entry)
        self.assertIn('"committed": False', self.entry)


if __name__ == "__main__":
    unittest.main()
