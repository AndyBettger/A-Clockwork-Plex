from __future__ import annotations

import ast
import subprocess
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from scripts.stage_c_transaction.production_adapter_contract import (
    AdapterOperation,
    ServiceUnit,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v5 import (
    ProductionAdapterV5,
)
from scripts.stage_c_transaction.systemd_reload_rollback_rehearsal import (
    EXPECTED_CHECKS,
)
from scripts.stage_c_transaction.systemd_reload_rollback_rehearsal_adapter import (
    BLOCKED_V5_COUNT,
    EXPECTED_FRAGMENT_PATH,
    EXPECTED_INSTALLED_UNIT_FILE_STATE,
    PERMITTED_V1_OPERATIONS,
    PERMITTED_V5_COUNT,
    SYSTEMD_PROPERTIES,
    SystemdReloadRollbackFailure,
    SystemdReloadRollbackRehearsalAdapter,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTER = (
    REPO_ROOT
    / "scripts/stage_c_transaction/systemd_reload_rollback_rehearsal_adapter.py"
)
ENGINE = (
    REPO_ROOT
    / "scripts/stage_c_transaction/systemd_reload_rollback_rehearsal.py"
)
WRAPPER = REPO_ROOT / "scripts/test-stage-c-systemd-reload-rollback-rehearsal.sh"
DESIGN = REPO_ROOT / "docs/stage-c19-systemd-reload-exact-rollback-rehearsal-design.md"
LIFECYCLE = (
    REPO_ROOT
    / "scripts/stage_c_transaction/production_adapter_lifecycle_v5.py"
)


class StageCSystemdReloadRollbackRehearsalSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = ADAPTER.read_text(encoding="utf-8")
        self.engine = ENGINE.read_text(encoding="utf-8")
        self.wrapper = WRAPPER.read_text(encoding="utf-8")
        self.design = DESIGN.read_text(encoding="utf-8")
        self.adapter_tree = ast.parse(self.adapter)
        self.engine_tree = ast.parse(self.engine)

    @staticmethod
    def method_source(
        tree: ast.Module,
        source: str,
        class_name: str,
        method_name: str,
    ) -> str:
        class_node = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        )
        method = next(
            node
            for node in class_node.body
            if isinstance(node, ast.FunctionDef) and node.name == method_name
        )
        return ast.get_source_segment(source, method) or ""

    def function_source(self, name: str) -> str:
        node = next(
            node
            for node in self.engine_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        )
        return ast.get_source_segment(self.engine, node) or ""

    def test_operation_boundary_is_exact(self) -> None:
        self.assertEqual(len(PERMITTED_V1_OPERATIONS), 23)
        self.assertEqual(PERMITTED_V5_COUNT, 27)
        self.assertEqual(BLOCKED_V5_COUNT, 10)
        self.assertEqual(len(set(PERMITTED_V1_OPERATIONS)), 23)
        install_index = PERMITTED_V1_OPERATIONS.index(
            AdapterOperation.INSTALL_MANAGED_FILES
        )
        self.assertIs(
            PERMITTED_V1_OPERATIONS[install_index + 1],
            AdapterOperation.RELOAD_SYSTEMD,
        )
        self.assertEqual(
            set(AdapterOperation).difference(PERMITTED_V1_OPERATIONS),
            {
                AdapterOperation.SELECT_SPLIT_BUS_ROUTE,
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

    def test_final_adapter_conforms_to_v5(self) -> None:
        instance = object.__new__(SystemdReloadRollbackRehearsalAdapter)
        self.assertIsInstance(instance, ProductionAdapterV5)
        for method in (
            "reload_systemd",
            "restore_exact_snapshot",
            "restore_captured_application_services",
            "verify_exact_rollback",
            "close_systemd_reload_rollback_rehearsal_transaction",
        ):
            self.assertTrue(hasattr(instance, method))

    def test_engine_has_exact_forty_five_checks(self) -> None:
        self.assertEqual(len(EXPECTED_CHECKS), 45)
        self.assertEqual(len(set(EXPECTED_CHECKS)), 45)
        self.assertEqual(EXPECTED_CHECKS[25], "systemd-candidate-reload")
        self.assertEqual(EXPECTED_CHECKS[28], "exact-filesystem-rollback")
        self.assertEqual(EXPECTED_CHECKS[29], "systemd-manager-restoration")
        self.assertEqual(EXPECTED_CHECKS[37], "file-only-closure-refusal")
        self.assertEqual(EXPECTED_CHECKS[-1], "activation-interface")

    def test_successful_c18_replay_is_required(self) -> None:
        source = self.function_source("validate_stage_c18")
        for marker in (
            "STAGE_C18_CHECKS",
            "exact forty checks",
            "len(blocked) != 11",
            '"managed_files_installed": "true"',
            '"filesystem_restored": "true"',
            '"services_restored": "true"',
            '"systemd_reloaded": "false"',
            "managed-files-rolled-back-and-closed",
            "Installed file count: 12",
        ):
            self.assertIn(marker, source)

    def test_daemon_reload_command_is_literal_and_only_systemd_mutation(self) -> None:
        source = self.method_source(
            self.adapter_tree,
            self.adapter,
            "SystemdReloadRollbackRehearsalAdapter",
            "_run_daemon_reload",
        )
        self.assertIn('host_run(["systemctl", "daemon-reload"])', source)
        self.assertNotIn("shell=True", self.adapter)
        self.assertNotIn("subprocess", self.adapter)
        host_calls = []
        for node in ast.walk(self.adapter_tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "host_run":
                    host_calls.append(ast.get_source_segment(self.adapter, node) or "")
        self.assertEqual(len(host_calls), 2)
        self.assertTrue(any("daemon-reload" in call for call in host_calls))
        self.assertTrue(any('"show"' in call for call in host_calls))
        for forbidden in (
            '"start"',
            '"enable"',
            '"disable"',
            '"mask"',
            '"unmask"',
            '"restart"',
        ):
            self.assertNotIn(forbidden, "\n".join(host_calls))

    def test_systemd_observation_is_fixed_to_three_units_and_five_properties(self) -> None:
        self.assertEqual(
            tuple(EXPECTED_FRAGMENT_PATH),
            (
                ServiceUnit.ROUTE_AUTHORITY,
                ServiceUnit.CAMILLADSP,
                ServiceUnit.AUDIO_FAILBACK,
            ),
        )
        self.assertEqual(
            SYSTEMD_PROPERTIES,
            (
                "LoadState",
                "ActiveState",
                "SubState",
                "UnitFileState",
                "FragmentPath",
            ),
        )
        self.assertEqual(
            EXPECTED_INSTALLED_UNIT_FILE_STATE,
            {
                ServiceUnit.ROUTE_AUTHORITY: "disabled",
                ServiceUnit.CAMILLADSP: "disabled",
                ServiceUnit.AUDIO_FAILBACK: "static",
            },
        )
        parser = self.function_source("parse_args")
        for forbidden in (
            "--unit",
            "--property",
            "--command",
            "--route",
            "--keep-active",
        ):
            self.assertNotIn(forbidden, parser)

    def test_mocked_installed_and_absent_unit_observations_are_exact(self) -> None:
        calls: list[list[str]] = []

        def fake_run(command: list[str]) -> CompletedProcess[str]:
            calls.append(command)
            unit = ServiceUnit(command[2])
            installed = len(calls) <= 3
            if installed:
                values = {
                    "LoadState": "loaded",
                    "ActiveState": "inactive",
                    "SubState": "dead",
                    "UnitFileState": EXPECTED_INSTALLED_UNIT_FILE_STATE[unit],
                    "FragmentPath": EXPECTED_FRAGMENT_PATH[unit],
                }
            else:
                values = {
                    "LoadState": "not-found",
                    "ActiveState": "inactive",
                    "SubState": "dead",
                    "UnitFileState": "",
                    "FragmentPath": "",
                }
            stdout = "".join(f"{name}={values[name]}\n" for name in SYSTEMD_PROPERTIES)
            return CompletedProcess(command, 0, stdout=stdout, stderr="")

        with tempfile.TemporaryDirectory() as raw:
            evidence = Path(raw) / "observations.tsv"
            evidence.write_text(
                "phase\tmonotonic_ns\tunit\tload_state\tactive_state\t"
                "sub_state\tunit_file_state\tfragment_path\n",
                encoding="utf-8",
            )
            adapter = object.__new__(SystemdReloadRollbackRehearsalAdapter)
            adapter._systemd_unit_observations = evidence
            with patch(
                "scripts.stage_c_transaction."
                "systemd_reload_rollback_rehearsal_adapter.host_run",
                side_effect=fake_run,
            ):
                installed = adapter._observe_managed_units(
                    "candidate-files-installed",
                    installed=True,
                )
                absent = adapter._observe_managed_units(
                    "rollback-files-absent",
                    installed=False,
                )
            self.assertEqual(len(installed), 3)
            self.assertEqual(len(absent), 3)
            rows = evidence.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(rows), 7)
        self.assertEqual(len(calls), 6)
        for call, unit in zip(calls[:3], EXPECTED_FRAGMENT_PATH, strict=True):
            self.assertEqual(call[:3], ["systemctl", "show", unit.value])
            self.assertEqual(
                call[3:-1],
                [f"--property={name}" for name in SYSTEMD_PROPERTIES],
            )
            self.assertEqual(call[-1], "--no-pager")

    def test_property_parser_rejects_missing_or_duplicate_fields(self) -> None:
        complete = "".join(f"{name}=value\n" for name in SYSTEMD_PROPERTIES)
        parsed = SystemdReloadRollbackRehearsalAdapter._parse_systemctl_show(
            complete
        )
        self.assertEqual(set(parsed), set(SYSTEMD_PROPERTIES))
        with self.assertRaises(SystemdReloadRollbackFailure):
            SystemdReloadRollbackRehearsalAdapter._parse_systemctl_show(
                "LoadState=loaded\n"
            )
        with self.assertRaises(SystemdReloadRollbackFailure):
            SystemdReloadRollbackRehearsalAdapter._parse_systemctl_show(
                complete + "LoadState=loaded\n"
            )

    def test_reload_state_machine_has_exact_two_phases(self) -> None:
        source = self.method_source(
            self.adapter_tree,
            self.adapter,
            "SystemdReloadRollbackRehearsalAdapter",
            "reload_systemd",
        )
        self.assertIn("self._systemd_reload_count == 0", source)
        self.assertIn("self._systemd_reload_count == 1", source)
        self.assertIn("permits exactly two daemon reloads", source)
        self.assertLess(
            source.index("first daemon reload requires installed managed files"),
            source.index('self._run_daemon_reload("candidate-files-installed")'),
        )
        self.assertLess(
            source.index("second daemon reload requires exact filesystem rollback"),
            source.index("self._restore_systemd_manager_exact()"),
        )

    def test_failure_cleanup_restores_files_then_manager_before_services(self) -> None:
        source = self.method_source(
            self.adapter_tree,
            self.adapter,
            "SystemdReloadRollbackRehearsalAdapter",
            "__exit__",
        )
        self.assertLess(
            source.index("self._restore_managed_files_exact()"),
            source.index("self._restore_systemd_manager_exact()"),
        )
        self.assertLess(
            source.index("self._restore_systemd_manager_exact()"),
            source.index("super().__exit__"),
        )
        self.assertIn("intentionally retained", source)

    def test_application_services_are_gated_on_manager_restoration(self) -> None:
        source = self.method_source(
            self.adapter_tree,
            self.adapter,
            "SystemdReloadRollbackRehearsalAdapter",
            "restore_captured_application_services",
        )
        self.assertIn("not self._systemd_manager_restored", source)
        self.assertIn(
            "cannot restart before systemd-manager rollback",
            source,
        )
        restore = self.method_source(
            self.adapter_tree,
            self.adapter,
            "SystemdReloadRollbackRehearsalAdapter",
            "_restore_systemd_manager_exact",
        )
        self.assertIn("continued service quiescence", restore)
        self.assertLess(
            restore.index('self._run_daemon_reload("rollback-files-absent")'),
            restore.index("self._systemd_manager_restored = True"),
        )

    def test_v4_closure_refuses_and_v5_requires_manager_rollback(self) -> None:
        v4 = self.method_source(
            self.adapter_tree,
            self.adapter,
            "SystemdReloadRollbackRehearsalAdapter",
            "close_exact_rollback_rehearsal_transaction",
        )
        self.assertIn("v4 file-only closure is unavailable", v4)
        v5 = self.method_source(
            self.adapter_tree,
            self.adapter,
            "SystemdReloadRollbackRehearsalAdapter",
            "close_systemd_reload_rollback_rehearsal_transaction",
        )
        for marker in (
            "self._systemd_candidate_visible",
            "self._systemd_manager_restored",
            "self._systemd_reload_count != 2",
            "systemd-reload-rolled-back-and-closed",
            "daemon_reload_count=2",
        ):
            self.assertIn(marker, v5)
        self.assertNotIn("lifecycle-v4.tsv", v5)

    def test_normal_order_is_reload_block_rollback_reload_restore_verify(self) -> None:
        source = self.function_source("main")
        markers = (
            "candidate_reload_result = adapter.reload_systemd",
            "post_reload_blocked = prove_blocked_operations",
            "rollback_result = adapter.restore_exact_snapshot",
            "manager_reload_result = adapter.reload_systemd",
            "restore_result = adapter.restore_captured_application_services",
            "dashboard_result = adapter.verify_dashboard_health",
            "verify_result = adapter.verify_exact_rollback",
        )
        positions = [source.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions))

    def test_wrapper_is_prepare_only_with_one_constrained_sudo(self) -> None:
        self.assertIn('MODE="prepare"', self.wrapper)
        prepare_index = self.wrapper.index('if [[ "$MODE" == "prepare" ]]')
        sudo_index = self.wrapper.index("exec sudo env")
        self.assertLess(prepare_index, sudo_index)
        self.assertEqual(self.wrapper.count("exec sudo env"), 1)
        self.assertIn(
            "STAGE-C19-SYSTEMD-RELOAD-EXACT-ROLLBACK",
            self.wrapper,
        )
        self.assertIn(
            "/var/tmp/a-clockwork-plex-stage-c18-managed-file-rollback.H3P4Po",
            self.wrapper,
        )
        self.assertIn("Exactly two `systemctl daemon-reload`", self.wrapper)
        self.assertNotIn("--keep-active", self.wrapper)

    def test_design_records_exact_manager_rollback_contract(self) -> None:
        for marker in (
            "systemctl daemon-reload",
            "loaded, inactive, dead and not enabled",
            "LoadState      not-found",
            "remove exact managed file inodes",
            "production lock and authoritative transaction are intentionally retained",
            "permitted  27",
            "blocked    10",
            "close-systemd-reload-rollback-rehearsal-transaction",
            "PR #2 must remain Draft, open and unmerged",
        ):
            self.assertIn(marker, self.design)

    def test_python_and_shell_syntax(self) -> None:
        for path in (ADAPTER, ENGINE, LIFECYCLE):
            subprocess.run(
                ["python3", "-m", "py_compile", str(path)],
                check=True,
                capture_output=True,
                text=True,
            )
        subprocess.run(
            ["bash", "-n", str(WRAPPER)],
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
