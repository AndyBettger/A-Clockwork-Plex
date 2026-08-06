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

ADAPTER_V15 = (
    ROOT
    / "scripts/stage_c_transaction/current_package_terminal_install_adapter_v15.py"
)
ADAPTER_V16 = (
    ROOT
    / "scripts/stage_c_transaction/current_package_terminal_install_adapter_v16.py"
)
ENTRY = ROOT / "scripts/stage_c_transaction/current_package_terminal_install_v16.py"
WRAPPER = ROOT / "scripts/install-and-enable-stage-c-eq.sh"


class StageCTerminalInstallV16Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter_v15 = ADAPTER_V15.read_text(encoding="utf-8")
        self.adapter_v16 = ADAPTER_V16.read_text(encoding="utf-8")
        self.entry = ENTRY.read_text(encoding="utf-8")
        self.wrapper = WRAPPER.read_text(encoding="utf-8")

    def test_python_and_shell_sources_parse(self) -> None:
        ast.parse(self.adapter_v15)
        ast.parse(self.adapter_v16)
        ast.parse(self.entry)
        result = subprocess.run(
            ["bash", "-n", str(WRAPPER)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_terminal_modules_import(self) -> None:
        from scripts.stage_c_transaction.current_package_terminal_install_adapter_v16 import (  # noqa: E501
            CurrentPackageTerminalInstallAdapterV16,
        )
        from scripts.stage_c_transaction.current_package_terminal_install_v16 import (
            EXPECTED_CHECKS,
            REQUIRED_CONFIRMATION,
        )

        self.assertEqual(REQUIRED_CONFIRMATION, "INSTALL-AND-ENABLE-STAGE-C-EQ")
        self.assertEqual(len(EXPECTED_CHECKS), 22)
        self.assertTrue(CurrentPackageTerminalInstallAdapterV16.__name__.endswith("V16"))

    def test_wrapper_has_one_fixed_privileged_entry(self) -> None:
        self.assertEqual(self.wrapper.count("exec sudo env"), 1)
        self.assertIn("current_package_terminal_install_v16", self.wrapper)
        self.assertIn("INSTALL-AND-ENABLE-STAGE-C-EQ", self.wrapper)
        self.assertNotIn("--route", self.wrapper)
        self.assertNotIn("--unit", self.wrapper)
        self.assertNotIn("--probe", self.wrapper)
        self.assertNotIn("--keep-active", self.wrapper)

    def test_legacy_installer_is_named_only_in_prohibition_text(self) -> None:
        self.assertIn("legacy install-master-eq.sh path is not used", self.wrapper)
        self.assertNotIn("bash scripts/install-master-eq.sh", self.wrapper)
        self.assertNotIn("exec scripts/install-master-eq.sh", self.wrapper)
        self.assertNotIn("subprocess", self.entry)

    def test_physical_prefix_precedes_terminal_executor(self) -> None:
        install = self.entry.index("adapter.install_managed_files(")
        reload = self.entry.index("adapter.reload_systemd(", install)
        route = self.entry.index("adapter.select_split_bus_route(", reload)
        executor = self.entry.index("execute_activation_commit_v7(", route)
        self.assertEqual((install, reload, route, executor), tuple(sorted((install, reload, route, executor))))

    def test_commit_is_one_atomic_approval_marker(self) -> None:
        self.assertIn("store.replace_exact(", self.adapter_v16)
        self.assertIn("plan_committed_approval_v7(", self.adapter_v16)
        self.assertIn("COMMITTED_INSTALL_ROOT", self.adapter_v16)
        self.assertNotIn("write_commit_manifest(", self.entry)
        self.assertIn("ApprovalPhase.COMMITTED", self.entry)

    def test_precommit_runtime_is_not_boot_enabled(self) -> None:
        start = self.adapter_v15.index("def start_managed_stage_c_services(")
        promote = self.adapter_v16.index("def promote_committed_activation_approval(")
        self.assertNotIn("systemctl\", \"enable", self.adapter_v15[start:])
        self.assertIn("\"systemctl\",\n                \"enable\"", self.adapter_v16[promote:])

    def test_committed_install_retains_uninstall_source(self) -> None:
        self.assertIn("ORIGINAL_ROUTE_NAME = \"pre-eq-active-route.conf\"", self.adapter_v15)
        self.assertIn("os.rename(parked_route, original_destination)", self.adapter_v16)
        self.assertIn("pre_eq_route_sha256", self.adapter_v16)
        self.assertIn("reboot_verification\": \"pending\"", self.adapter_v16)

    def test_failure_outcomes_are_explicit(self) -> None:
        self.assertIn("ActivationExecutionOutcomeV7.COMMITTED", self.entry)
        self.assertIn("ActivationExecutionOutcomeV7.EXACTLY_ROLLED_BACK", self.entry)
        self.assertIn("retained authority for inspection", self.entry)
        self.assertIn("if execution is None and adapter.lock_held", self.entry)

    def test_pr_and_reboot_boundaries_remain_explicit(self) -> None:
        self.assertIn("PR #2 remains Draft", self.entry)
        self.assertIn("reboot_verification\\tpending", self.entry)
        self.assertIn("pr_ready_or_merged\\tfalse", self.entry)


if __name__ == "__main__":
    unittest.main()
