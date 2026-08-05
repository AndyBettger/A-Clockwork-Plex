from __future__ import annotations

import ast
import subprocess
import unittest
from pathlib import Path

from scripts.stage_c_transaction.production_adapter_contract import (
    AdapterOperation,
)
from scripts.stage_c_transaction.service_quiescence_rehearsal import (
    EXPECTED_CHECKS,
)
from scripts.stage_c_transaction.service_quiescence_rehearsal_adapter import (
    APPLICATION_START_ORDER,
    APPLICATION_STOP_ORDER,
    BLOCKED_V3_COUNT,
    DASHBOARD_URL,
    PERMITTED_V1_OPERATIONS,
    PERMITTED_V3_COUNT,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTER = (
    REPO_ROOT
    / "scripts/stage_c_transaction/service_quiescence_rehearsal_adapter.py"
)
ENGINE = (
    REPO_ROOT
    / "scripts/stage_c_transaction/service_quiescence_rehearsal.py"
)
WRAPPER = REPO_ROOT / "scripts/test-stage-c-service-quiescence-rehearsal.sh"


class StageCServiceQuiescenceRehearsalSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter_source = ADAPTER.read_text(encoding="utf-8")
        self.engine_source = ENGINE.read_text(encoding="utf-8")
        self.wrapper_source = WRAPPER.read_text(encoding="utf-8")
        self.adapter_tree = ast.parse(self.adapter_source)
        self.engine_tree = ast.parse(self.engine_source)

    def method_source(self, tree, source: str, class_name: str, method_name: str) -> str:
        class_node = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        )
        method = next(
            node
            for node in class_node.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == method_name
        )
        return ast.get_source_segment(source, method) or ""

    def function_source(self, name: str) -> str:
        node = next(
            node
            for node in self.engine_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        )
        return ast.get_source_segment(self.engine_source, node) or ""

    def test_exact_nineteen_v1_plus_two_lifecycle_and_fourteen_blocked(self) -> None:
        self.assertEqual(len(PERMITTED_V1_OPERATIONS), 19)
        self.assertEqual(PERMITTED_V3_COUNT, 21)
        self.assertEqual(BLOCKED_V3_COUNT, 14)
        self.assertEqual(len(set(PERMITTED_V1_OPERATIONS)), 19)
        self.assertEqual(
            PERMITTED_V1_OPERATIONS[-4:],
            (
                AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES,
                AdapterOperation.VERIFY_DAC_RELEASED,
                AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES,
                AdapterOperation.VERIFY_DASHBOARD_HEALTH,
            ),
        )

    def test_fixed_service_stop_and_start_order(self) -> None:
        self.assertEqual(
            tuple(unit.value for unit in APPLICATION_STOP_ORDER),
            (
                "a-clockwork-plex.service",
                "shairport-sync.service",
                "plexamp.service",
            ),
        )
        self.assertEqual(
            tuple(unit.value for unit in APPLICATION_START_ORDER),
            (
                "plexamp.service",
                "shairport-sync.service",
                "a-clockwork-plex.service",
            ),
        )
        stop = self.method_source(
            self.adapter_tree,
            self.adapter_source,
            "ServiceQuiescenceRehearsalAdapter",
            "stop_captured_application_services",
        )
        restore = self.method_source(
            self.adapter_tree,
            self.adapter_source,
            "ServiceQuiescenceRehearsalAdapter",
            "_restore_captured_services_exact",
        )
        self.assertIn("for unit in APPLICATION_STOP_ORDER", stop)
        self.assertIn("for unit in APPLICATION_START_ORDER", restore)

    def test_systemctl_boundary_allows_only_fixed_start_and_stop(self) -> None:
        runner = self.method_source(
            self.adapter_tree,
            self.adapter_source,
            "ServiceQuiescenceRehearsalAdapter",
            "_run_systemctl",
        )
        self.assertIn('action not in {"start", "stop"}', runner)
        self.assertIn('host_run(["systemctl", action, unit.value])', runner)
        for forbidden in (
            '"restart"',
            '"enable"',
            '"disable"',
            '"daemon-reload"',
            '"mask"',
            '"unmask"',
        ):
            self.assertNotIn(forbidden, runner)

    def test_mandatory_restore_precedes_inherited_cleanup(self) -> None:
        exit_source = self.method_source(
            self.adapter_tree,
            self.adapter_source,
            "ServiceQuiescenceRehearsalAdapter",
            "__exit__",
        )
        restore_position = exit_source.index("_restore_captured_services_exact")
        super_position = exit_source.index("super().__exit__")
        self.assertLess(restore_position, super_position)
        self.assertIn(
            "the production lock and transaction are intentionally retained",
            exit_source,
        )
        self.assertIn(
            "if self._mutation_started and not self._services_restored",
            exit_source,
        )

    def test_dac_release_uses_only_fixed_endpoints_and_fuser(self) -> None:
        source = self.method_source(
            self.adapter_tree,
            self.adapter_source,
            "ServiceQuiescenceRehearsalAdapter",
            "_released_endpoint_rows",
        )
        self.assertIn("_physical_dac_device()", source)
        self.assertIn('"/dev/snd/pcmC7D0p"', source)
        self.assertIn('"/dev/snd/pcmC7D1c"', source)
        self.assertIn('host_run(["fuser", str(path)])', source)
        self.assertNotIn("aplay", source)
        self.assertNotIn("arecord", source)

    def test_dashboard_health_uses_fixed_local_url_and_exact_observations(self) -> None:
        self.assertEqual(DASHBOARD_URL, "http://127.0.0.1:8088/")
        source = self.method_source(
            self.adapter_tree,
            self.adapter_source,
            "ServiceQuiescenceRehearsalAdapter",
            "verify_dashboard_health",
        )
        for marker in (
            "_observe_service_snapshot()",
            "_observe_host_contract()",
            "_observe_mixer_snapshot()",
            "_observe_loopback_snapshot()",
            "_observe_dac_snapshot()",
            "_wait_for_dashboard()",
        ):
            self.assertIn(marker, source)

    def test_pre_mutation_abort_refuses_after_mutation(self) -> None:
        source = self.method_source(
            self.adapter_tree,
            self.adapter_source,
            "ServiceQuiescenceRehearsalAdapter",
            "abort_uncommitted_transaction",
        )
        self.assertIn("if self._mutation_started", source)
        self.assertIn("use restored-rehearsal closure", source)
        self.assertIn("return super().abort_uncommitted_transaction", source)

    def test_v3_closure_requires_validation_release_and_restoration(self) -> None:
        source = self.method_source(
            self.adapter_tree,
            self.adapter_source,
            "ServiceQuiescenceRehearsalAdapter",
            "close_restored_rehearsal_transaction",
        )
        for marker in (
            "self._mutation_started",
            "self._dac_release_verified",
            "self._services_restored",
            "self._dashboard_verified",
            "self._candidate_staged",
            "self._alsa_validated",
            "self._sudoers_validated",
            "self._units_validated",
            "self._camilladsp_validated",
            "state\\trehearsal-restored-and-closed",
            "mutation_started\\ttrue",
            "restored\\ttrue",
            "committed\\tfalse",
            "_remove_regular_tree(path)",
            "_verify_state(state)",
        ):
            self.assertIn(marker, source)

    def test_adapter_has_no_install_route_mixer_module_or_audio_command(self) -> None:
        for forbidden in (
            "install_managed_files(",
            "reload_systemd(",
            "select_split_bus_route(",
            "select_direct_failback_route(",
            "start_managed_stage_c_services(",
            "stop_managed_stage_c_services(",
            "amixer",
            "modprobe",
            "rmmod",
            "aplay",
            "arecord",
            "camilladsp --",
            "systemctl enable",
            "systemctl disable",
            "systemctl restart",
        ):
            self.assertNotIn(forbidden, self.adapter_source)

    def test_engine_has_exact_thirty_five_checks(self) -> None:
        self.assertEqual(len(EXPECTED_CHECKS), 35)
        self.assertEqual(len(EXPECTED_CHECKS), len(set(EXPECTED_CHECKS)))
        self.assertEqual(EXPECTED_CHECKS[21], "service-quiescence")
        self.assertEqual(EXPECTED_CHECKS[24], "application-service-restoration")
        self.assertEqual(
            EXPECTED_CHECKS[29],
            "restored-transaction-close-v3",
        )

    def test_engine_blocked_calls_exist_only_in_blocked_proof_or_critical_gate(self) -> None:
        blocked_names = {
            "install_managed_files",
            "reload_systemd",
            "select_split_bus_route",
            "start_managed_stage_c_services",
            "stop_managed_stage_c_services",
            "verify_split_bus_health",
            "run_finite_music_probe",
            "run_finite_alarm_probe",
            "write_commit_manifest",
            "select_direct_failback_route",
            "restore_exact_snapshot",
            "restore_mixer_state",
            "restore_service_state",
            "verify_exact_rollback",
        }
        parents: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(self.engine_tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node

        locations: dict[str, set[str]] = {name: set() for name in blocked_names}
        for node in ast.walk(self.engine_tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr not in blocked_names:
                continue
            current = node
            owner = "<module>"
            while current in parents:
                current = parents[current]
                if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    owner = current.name
                    break
            locations[func.attr].add(owner)

        for name, owners in locations.items():
            with self.subTest(operation=name):
                if name == "install_managed_files":
                    self.assertEqual(
                        owners,
                        {"prove_blocked_operations", "main"},
                    )
                else:
                    self.assertEqual(owners, {"prove_blocked_operations"})

    def test_stage_c16_replay_is_exact_and_rejects_failed_attempt(self) -> None:
        source = self.function_source("validate_stage_c16")
        self.assertIn("STAGE_C16_CHECKS", source)
        self.assertIn("exact twenty-nine checks", source)
        self.assertIn("len(blocked) != 18", source)
        self.assertIn('identity.get("mutation_started") != "false"', source)
        self.assertIn('"candidate-review-copy"', source)
        self.assertIn('"transaction-rehearsal-copy"', source)
        self.assertIn(
            "Final transaction state: aborted-before-mutation and removed",
            source,
        )

    def test_wrapper_is_prepare_only_and_has_one_constrained_sudo(self) -> None:
        self.assertIn('MODE="prepare"', self.wrapper_source)
        prepare_position = self.wrapper_source.index(
            'if [[ "$MODE" == "prepare" ]]'
        )
        sudo_position = self.wrapper_source.index("exec sudo env")
        self.assertLess(prepare_position, sudo_position)
        self.assertEqual(self.wrapper_source.count("exec sudo env"), 1)
        self.assertIn(
            "STAGE-C17-SERVICE-QUIESCE-RESTORE",
            self.wrapper_source,
        )
        self.assertIn(
            "Stage C16 evidence",
            self.wrapper_source,
        )
        self.assertIn(
            "The dashboard and local touchscreen will be",
            self.wrapper_source,
        )

    def test_wrapper_and_python_syntax(self) -> None:
        for path in (
            ADAPTER,
            ENGINE,
            REPO_ROOT
            / "scripts/stage_c_transaction/production_adapter_lifecycle_v3.py",
        ):
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        result = subprocess.run(
            ("bash", "-n", str(WRAPPER)),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout={result.stdout}\\nstderr={result.stderr}",
        )

    def test_no_activation_or_persistent_interface_exists(self) -> None:
        combined = self.engine_source + self.wrapper_source
        for forbidden in (
            "--activate",
            "--keep-active",
            "--install",
            "--commit",
            "--rollback",
            "--failback",
            "--uninstall",
            "activation-approved",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
