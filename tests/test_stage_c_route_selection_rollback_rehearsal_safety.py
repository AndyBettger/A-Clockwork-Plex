from __future__ import annotations

import ast
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.stage_c_transaction.production_adapter_contract import (
    AdapterOperation,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v6 import (
    ProductionAdapterV6,
)
from scripts.stage_c_transaction.route_selection_rollback_rehearsal import (
    EXPECTED_CHECKS,
)
from scripts.stage_c_transaction.route_selection_rollback_rehearsal_adapter import (
    BLOCKED_V6_COUNT,
    PERMITTED_V1_OPERATIONS,
    PERMITTED_V6_COUNT,
    RENAME_EXCHANGE,
    SPLIT_ROUTE_SOURCE,
    RouteSelectionRollbackRehearsalAdapter,
    _rename_exchange,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTER = (
    REPO_ROOT
    / "scripts/stage_c_transaction/route_selection_rollback_rehearsal_adapter.py"
)
ENGINE = (
    REPO_ROOT
    / "scripts/stage_c_transaction/route_selection_rollback_rehearsal.py"
)
WRAPPER = REPO_ROOT / "scripts/test-stage-c-route-selection-rollback-rehearsal.sh"
DESIGN = (
    REPO_ROOT
    / "docs/stage-c20-split-bus-route-selection-exact-rollback-rehearsal-design.md"
)
LIFECYCLE = (
    REPO_ROOT
    / "scripts/stage_c_transaction/production_adapter_lifecycle_v6.py"
)


class StageCRouteSelectionRollbackRehearsalSafetyTests(unittest.TestCase):
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
        self.assertEqual(len(PERMITTED_V1_OPERATIONS), 24)
        self.assertEqual(PERMITTED_V6_COUNT, 29)
        self.assertEqual(BLOCKED_V6_COUNT, 9)
        self.assertEqual(len(set(PERMITTED_V1_OPERATIONS)), 24)
        reload_index = PERMITTED_V1_OPERATIONS.index(
            AdapterOperation.RELOAD_SYSTEMD
        )
        self.assertIs(
            PERMITTED_V1_OPERATIONS[reload_index + 1],
            AdapterOperation.SELECT_SPLIT_BUS_ROUTE,
        )
        self.assertEqual(
            set(AdapterOperation).difference(PERMITTED_V1_OPERATIONS),
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

    def test_final_adapter_conforms_to_v6(self) -> None:
        instance = object.__new__(RouteSelectionRollbackRehearsalAdapter)
        self.assertIsInstance(instance, ProductionAdapterV6)
        for method in (
            "select_split_bus_route",
            "restore_exact_snapshot",
            "restore_captured_application_services",
            "verify_exact_rollback",
            "close_route_selection_rollback_rehearsal_transaction",
        ):
            self.assertTrue(hasattr(instance, method))

    def test_engine_has_exact_fifty_checks(self) -> None:
        self.assertEqual(len(EXPECTED_CHECKS), 50)
        self.assertEqual(len(set(EXPECTED_CHECKS)), 50)
        self.assertEqual(EXPECTED_CHECKS[21], "route-selection-gate")
        self.assertEqual(EXPECTED_CHECKS[28], "split-bus-route-selection")
        self.assertEqual(EXPECTED_CHECKS[31], "active-route-restoration")
        self.assertEqual(EXPECTED_CHECKS[42], "systemd-only-closure-refusal")
        self.assertEqual(EXPECTED_CHECKS[-1], "activation-interface")

    def test_atomic_exchange_round_trip_preserves_both_inodes(self) -> None:
        self.assertEqual(RENAME_EXCHANGE, 2)
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            left = root / "active.conf"
            right = root / ".candidate.rollback"
            left.write_text("direct\n", encoding="utf-8")
            right.write_text("split\n", encoding="utf-8")
            left_inode = left.stat().st_ino
            right_inode = right.stat().st_ino
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            parent_fd = os.open(root, flags)
            try:
                _rename_exchange(parent_fd, left.name, right.name)
                self.assertEqual(left.read_text(encoding="utf-8"), "split\n")
                self.assertEqual(right.read_text(encoding="utf-8"), "direct\n")
                self.assertEqual(left.stat().st_ino, right_inode)
                self.assertEqual(right.stat().st_ino, left_inode)
                _rename_exchange(parent_fd, left.name, right.name)
            finally:
                os.close(parent_fd)
            self.assertEqual(left.read_text(encoding="utf-8"), "direct\n")
            self.assertEqual(right.read_text(encoding="utf-8"), "split\n")
            self.assertEqual(left.stat().st_ino, left_inode)
            self.assertEqual(right.stat().st_ino, right_inode)

    def test_route_paths_are_fixed_and_not_caller_inputs(self) -> None:
        self.assertEqual(
            SPLIT_ROUTE_SOURCE,
            "/etc/a-clockwork-plex/audio-routes/split-bus.conf",
        )
        self.assertIn(
            'CURRENT_ALSA_DESTINATION = "/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"',
            (
                REPO_ROOT
                / "scripts/stage_c_transaction/snapshot_core.py"
            ).read_text(encoding="utf-8"),
        )
        parser = self.function_source("parse_args")
        for forbidden in (
            "--route",
            "--source",
            "--destination",
            "--unit",
            "--command",
            "--keep-active",
        ):
            self.assertNotIn(forbidden, parser)

    def test_adapter_has_no_shell_or_service_audio_command_boundary(self) -> None:
        self.assertNotIn("shell=True", self.adapter)
        self.assertNotIn("subprocess", self.adapter)
        self.assertNotIn("systemctl", self.adapter)
        self.assertNotIn("aplay", self.adapter)
        self.assertNotIn("speaker-test", self.adapter)
        self.assertNotIn("amixer", self.adapter)
        for node in ast.walk(self.adapter_tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"eval", "exec", "getattr"})

    def test_route_selection_requires_exact_c19_state(self) -> None:
        source = self.method_source(
            self.adapter_tree,
            self.adapter,
            "RouteSelectionRollbackRehearsalAdapter",
            "select_split_bus_route",
        )
        for marker in (
            "self._systemd_reload_count != 1",
            "not self._systemd_candidate_visible",
            "not self._managed_files_installed",
            "not self._services_stopped",
            "not self._dac_release_verified",
            "self._installed_split_route()",
            "self._original_route_identity()",
            "_rename_exchange(parent_fd, active.name, rollback_name)",
            "self._route_selection_count = 1",
            "managed_stage_c_services_started",
            "audio_probe_opened",
        ):
            self.assertIn(marker, source)

    def test_failure_cleanup_restores_route_before_inherited_cleanup(self) -> None:
        source = self.method_source(
            self.adapter_tree,
            self.adapter,
            "RouteSelectionRollbackRehearsalAdapter",
            "__exit__",
        )
        self.assertLess(
            source.index("self._restore_active_route_exact()"),
            source.index("super().__exit__"),
        )
        self.assertIn("intentionally retained", source)
        restore = self.method_source(
            self.adapter_tree,
            self.adapter,
            "RouteSelectionRollbackRehearsalAdapter",
            "restore_exact_snapshot",
        )
        self.assertLess(
            restore.index("self._restore_active_route_exact()"),
            restore.index("super().restore_exact_snapshot"),
        )

    def test_route_rollback_uses_exact_exchange_and_candidate_unlink(self) -> None:
        source = self.method_source(
            self.adapter_tree,
            self.adapter,
            "RouteSelectionRollbackRehearsalAdapter",
            "_restore_active_route_exact",
        )
        self.assertIn(
            '_require_identity(active, candidate, "selected active route")',
            source,
        )
        self.assertIn(
            '_require_identity(rollback_path, original, "parked original route")',
            source,
        )
        self.assertIn(
            "_rename_exchange(parent_fd, active.name, rollback_name)",
            source,
        )
        self.assertIn("self._unlink_partial_candidate", source)
        self.assertIn("self._route_restored = True", source)

    def test_application_services_are_gated_on_route_restoration(self) -> None:
        source = self.method_source(
            self.adapter_tree,
            self.adapter,
            "RouteSelectionRollbackRehearsalAdapter",
            "restore_captured_application_services",
        )
        self.assertIn("not self._route_restored", source)
        self.assertIn(
            "cannot restart before exact active-route rollback",
            source,
        )

    def test_v5_closure_refuses_and_v6_requires_every_rollback_domain(self) -> None:
        v5 = self.method_source(
            self.adapter_tree,
            self.adapter,
            "RouteSelectionRollbackRehearsalAdapter",
            "close_systemd_reload_rollback_rehearsal_transaction",
        )
        self.assertIn("v5 systemd-only closure is unavailable", v5)
        v6 = self.method_source(
            self.adapter_tree,
            self.adapter,
            "RouteSelectionRollbackRehearsalAdapter",
            "close_route_selection_rollback_rehearsal_transaction",
        )
        for marker in (
            "self._route_selected_once",
            "self._route_restored",
            "self._systemd_manager_restored",
            "self._filesystem_restored",
            "self._exact_rollback_verified",
            "self._services_restored",
            "self._dashboard_verified",
            "self._route_selection_count != 1",
            "self._systemd_reload_count != 2",
            "split-bus-route-rolled-back-and-closed",
        ):
            self.assertIn(marker, v6)

    def test_normal_order_is_reload_route_block_restore_reload_services(self) -> None:
        source = self.function_source("main")
        markers = (
            "candidate_reload_result = adapter.reload_systemd",
            "route_result = adapter.select_split_bus_route",
            "post_route_blocked = prove_blocked_operations",
            "rollback_result = adapter.restore_exact_snapshot",
            "manager_reload_result = adapter.reload_systemd",
            "restore_result = adapter.restore_captured_application_services",
            "dashboard_result = adapter.verify_dashboard_health",
            "verify_result = adapter.verify_exact_rollback",
        )
        positions = [source.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions))

    def test_successful_c19_replay_is_required(self) -> None:
        source = self.function_source("validate_stage_c19")
        for marker in (
            "STAGE_C19_CHECKS",
            "exact forty-five checks",
            '"post-reload-blocked-operations.tsv"',
            '"daemon_reload_count": "2"',
            '"route_selected": "false"',
            "systemd-reload-rolled-back-and-closed",
            "Persistent Stage C activation remains blocked.",
        ):
            self.assertIn(marker, source)

    def test_wrapper_is_prepare_only_with_one_constrained_sudo(self) -> None:
        self.assertIn('MODE="prepare"', self.wrapper)
        prepare_index = self.wrapper.index('if [[ "$MODE" == "prepare" ]]')
        sudo_index = self.wrapper.index("exec sudo env")
        self.assertLess(prepare_index, sudo_index)
        self.assertEqual(self.wrapper.count("exec sudo env"), 1)
        self.assertIn(
            "STAGE-C20-SPLIT-BUS-ROUTE-EXACT-ROLLBACK",
            self.wrapper,
        )
        self.assertIn(
            "/var/tmp/a-clockwork-plex-stage-c19-systemd-reload-rollback.knbfOY",
            self.wrapper,
        )
        self.assertIn("one atomic split-bus route exchange", self.wrapper)
        self.assertNotIn("--keep-active", self.wrapper)

    def test_design_records_atomic_exchange_and_retention_contract(self) -> None:
        for marker in (
            "renameat2",
            "RENAME_EXCHANGE",
            "same bytes, SHA-256, mode, ownership, device and inode",
            "production lock and authoritative transaction are intentionally retained",
            "permitted  29",
            "blocked     9",
            "close-route-selection-rollback-rehearsal-transaction",
            "PR #2 must remain Draft, open and unmerged",
        ):
            self.assertIn(marker, self.design)

    def test_python_and_shell_syntax(self) -> None:
        subprocess.run(
            [
                "python3",
                "-m",
                "py_compile",
                str(ADAPTER),
                str(ENGINE),
                str(LIFECYCLE),
            ],
            check=True,
            cwd=REPO_ROOT,
        )
        subprocess.run(
            ["bash", "-n", str(WRAPPER)],
            check=True,
            cwd=REPO_ROOT,
        )


if __name__ == "__main__":
    unittest.main()
