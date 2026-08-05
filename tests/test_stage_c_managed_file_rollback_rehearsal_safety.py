from __future__ import annotations

import ast
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.stage_c_transaction.managed_file_rollback_rehearsal import (
    EXPECTED_CHECKS,
)
from scripts.stage_c_transaction.managed_file_rollback_rehearsal_adapter import (
    BLOCKED_V4_COUNT,
    PERMITTED_V1_OPERATIONS,
    PERMITTED_V4_COUNT,
    InstalledObject,
    ManagedFileRollbackFailure,
    ManagedFileRollbackRehearsalAdapter,
)
from scripts.stage_c_transaction.managed_file_rollback_rehearsal_adapter_v4 import (
    ManagedFileRollbackRehearsalAdapterV4,
)
from scripts.stage_c_transaction.production_adapter_contract import (
    AdapterOperation,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v4 import (
    ProductionAdapterV4,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_ADAPTER = (
    REPO_ROOT
    / "scripts/stage_c_transaction/managed_file_rollback_rehearsal_adapter.py"
)
ADAPTER_V2 = (
    REPO_ROOT
    / "scripts/stage_c_transaction/managed_file_rollback_rehearsal_adapter_v2.py"
)
ADAPTER_V3 = (
    REPO_ROOT
    / "scripts/stage_c_transaction/managed_file_rollback_rehearsal_adapter_v3.py"
)
ADAPTER_V4 = (
    REPO_ROOT
    / "scripts/stage_c_transaction/managed_file_rollback_rehearsal_adapter_v4.py"
)
ENGINE = (
    REPO_ROOT
    / "scripts/stage_c_transaction/managed_file_rollback_rehearsal.py"
)
WRAPPER = REPO_ROOT / "scripts/test-stage-c-managed-file-rollback-rehearsal.sh"
DESIGN = REPO_ROOT / "docs/stage-c18-managed-file-install-exact-rollback-rehearsal-design.md"


class StageCManagedFileRollbackRehearsalSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base_source = BASE_ADAPTER.read_text(encoding="utf-8")
        self.v2_source = ADAPTER_V2.read_text(encoding="utf-8")
        self.v3_source = ADAPTER_V3.read_text(encoding="utf-8")
        self.v4_source = ADAPTER_V4.read_text(encoding="utf-8")
        self.engine_source = ENGINE.read_text(encoding="utf-8")
        self.wrapper_source = WRAPPER.read_text(encoding="utf-8")
        self.design_source = DESIGN.read_text(encoding="utf-8")
        self.base_tree = ast.parse(self.base_source)
        self.v2_tree = ast.parse(self.v2_source)
        self.v3_tree = ast.parse(self.v3_source)
        self.v4_tree = ast.parse(self.v4_source)
        self.engine_tree = ast.parse(self.engine_source)

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

    def test_exact_twenty_two_v1_plus_three_lifecycle_and_eleven_blocked(self) -> None:
        self.assertEqual(len(PERMITTED_V1_OPERATIONS), 22)
        self.assertEqual(PERMITTED_V4_COUNT, 25)
        self.assertEqual(BLOCKED_V4_COUNT, 11)
        self.assertEqual(len(set(PERMITTED_V1_OPERATIONS)), 22)
        self.assertEqual(
            PERMITTED_V1_OPERATIONS[-5:],
            (
                AdapterOperation.INSTALL_MANAGED_FILES,
                AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES,
                AdapterOperation.VERIFY_DASHBOARD_HEALTH,
                AdapterOperation.RESTORE_EXACT_SNAPSHOT,
                AdapterOperation.VERIFY_EXACT_ROLLBACK,
            ),
        )

    def test_final_adapter_conforms_to_v4_protocol(self) -> None:
        self.assertTrue(issubclass(ManagedFileRollbackRehearsalAdapterV4, object))
        required = {
            "install_managed_files",
            "restore_exact_snapshot",
            "verify_exact_rollback",
            "close_exact_rollback_rehearsal_transaction",
        }
        self.assertTrue(required.issubset(set(dir(ManagedFileRollbackRehearsalAdapterV4))))
        self.assertTrue(
            isinstance(
                object.__new__(ManagedFileRollbackRehearsalAdapterV4),
                ProductionAdapterV4,
            )
        )

    def test_engine_has_exact_forty_checks(self) -> None:
        self.assertEqual(len(EXPECTED_CHECKS), 40)
        self.assertEqual(len(EXPECTED_CHECKS), len(set(EXPECTED_CHECKS)))
        self.assertEqual(EXPECTED_CHECKS[23], "managed-file-installation")
        self.assertEqual(EXPECTED_CHECKS[26], "exact-filesystem-rollback")
        self.assertEqual(EXPECTED_CHECKS[34], "exact-rollback-close-v4")
        self.assertEqual(EXPECTED_CHECKS[-1], "activation-interface")

    def test_stage_c17_replay_is_exact_and_rejects_failed_attempt(self) -> None:
        source = self.function_source("validate_stage_c17")
        for marker in (
            "STAGE_C17_CHECKS",
            "exact thirty-five checks",
            "len(blocked) != 14",
            '"mutation_started": "true"',
            '"restored": "true"',
            '"committed": "false"',
            '"restoration-readiness.tsv"',
            "Final transaction state: rehearsal-restored-and-closed",
        ):
            self.assertIn(marker, source)

    def test_write_boundary_is_fixed_to_manifest_and_authoritative_snapshot(self) -> None:
        source = self.method_source(
            self.base_tree,
            self.base_source,
            "ManagedFileRollbackRehearsalAdapter",
            "_snapshot_rows",
        )
        self.assertIn("self._entries", source)
        self.assertIn("CURRENT_ALSA_DESTINATION", source)
        self.assertIn('row.state != "absent"', source)
        self.assertIn("authoritative filesystem state", source)
        parser_source = self.function_source("parse_args")
        for forbidden in (
            "--destination",
            "--unit",
            "--command",
            "--route",
            "--keep-active",
        ):
            self.assertNotIn(forbidden, parser_source)

    def test_rollback_is_armed_before_first_directory_and_file_write(self) -> None:
        create_source = self.method_source(
            self.v3_tree,
            self.v3_source,
            "ManagedFileRollbackRehearsalAdapterV3",
            "_create_directory",
        )
        install_source = self.method_source(
            self.v3_tree,
            self.v3_source,
            "ManagedFileRollbackRehearsalAdapterV3",
            "_atomic_install_file",
        )
        self.assertLess(
            create_source.index("self._arm_managed_rollback()"),
            create_source.index("os.mkdir("),
        )
        self.assertLess(
            install_source.index("self._arm_managed_rollback()"),
            install_source.index("os.open(temporary"),
        )

    def test_rollback_ledger_adopts_path_at_mkdir_and_rename_boundaries(self) -> None:
        create_source = self.method_source(
            self.v3_tree,
            self.v3_source,
            "ManagedFileRollbackRehearsalAdapterV3",
            "_create_directory",
        )
        install_source = self.method_source(
            self.v3_tree,
            self.v3_source,
            "ManagedFileRollbackRehearsalAdapterV3",
            "_atomic_install_file",
        )
        self.assertLess(
            create_source.index("self._created_directories.append(installed)"),
            create_source.index("os.fchmod(child_fd"),
        )
        rename_position = install_source.index("os.replace(")
        ledger_position = install_source.index("self._installed_files.append(record)")
        parent_fsync_position = install_source.index("os.fsync(parent_fd)")
        self.assertLess(rename_position, ledger_position)
        self.assertLess(ledger_position, parent_fsync_position)

    def test_successful_install_verification_remains_strict(self) -> None:
        source = self.method_source(
            self.base_tree,
            self.base_source,
            "ManagedFileRollbackRehearsalAdapter",
            "_verify_installed_object",
        )
        for marker in (
            "info.st_dev != record.device",
            "info.st_ino != record.inode",
            "stat.S_IMODE(info.st_mode) != record.mode",
            "info.st_uid != record.uid",
            "info.st_gid != record.gid",
            "sha256(path) != record.digest",
        ):
            self.assertIn(marker, source)

    def test_rollback_identity_is_narrower_than_install_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "candidate"
            path.write_text("candidate", encoding="utf-8")
            path.chmod(0o644)
            info = path.lstat()
            record = InstalledObject(
                destination=str(path),
                kind="file",
                device=info.st_dev,
                inode=info.st_ino,
                mode=0o600,
                uid=info.st_uid,
                gid=info.st_gid,
                digest=None,
            )
            self.assertEqual(
                ManagedFileRollbackRehearsalAdapterV4.
                _verify_rollback_identity(record),
                path,
            )
            with self.assertRaises(ManagedFileRollbackFailure):
                ManagedFileRollbackRehearsalAdapter._verify_installed_object(
                    record
                )

            path.unlink()
            path.write_text("substitute", encoding="utf-8")
            with self.assertRaises(ManagedFileRollbackFailure):
                ManagedFileRollbackRehearsalAdapterV4.
                _verify_rollback_identity(record)

    def test_rollback_removes_only_exact_recorded_inodes(self) -> None:
        source = self.method_source(
            self.v4_tree,
            self.v4_source,
            "ManagedFileRollbackRehearsalAdapterV4",
            "_restore_managed_files_exact",
        )
        for marker in (
            "self._verify_rollback_identity(record)",
            "current.st_dev != record.device",
            "current.st_ino != record.inode",
            "os.unlink(path.name, dir_fd=parent_fd)",
            "os.rmdir(path.name, dir_fd=parent_fd)",
            "self._verify_directory_snapshot(path, row)",
            "self._verify_current_alsa()",
        ):
            self.assertIn(marker, source)

    def test_mandatory_filesystem_rollback_precedes_service_cleanup(self) -> None:
        source = self.method_source(
            self.base_tree,
            self.base_source,
            "ManagedFileRollbackRehearsalAdapter",
            "__exit__",
        )
        self.assertLess(
            source.index("self._restore_managed_files_exact()"),
            source.index("super().__exit__"),
        )
        self.assertIn(
            "the production lock and transaction are intentionally retained",
            source,
        )

    def test_normal_engine_order_is_install_rollback_then_service_restore(self) -> None:
        source = self.function_source("main")
        install = source.index("adapter.install_managed_files")
        post_boundary = source.index('"post-install-boundary"')
        rollback = source.index("adapter.restore_exact_snapshot")
        restore_services = source.index(
            "adapter.restore_captured_application_services"
        )
        dashboard = source.index("adapter.verify_dashboard_health")
        verify = source.index("adapter.verify_exact_rollback")
        self.assertLess(install, post_boundary)
        self.assertLess(post_boundary, rollback)
        self.assertLess(rollback, restore_services)
        self.assertLess(restore_services, dashboard)
        self.assertLess(dashboard, verify)

    def test_post_install_boundary_blocks_reload_and_route(self) -> None:
        source = self.function_source("main")
        marker = source.index('"post-install-boundary"')
        prefix = source[:marker]
        self.assertIn("adapter.reload_systemd", prefix)
        self.assertIn("adapter.select_split_bus_route", prefix)
        self.assertIn("_expect_blocked", prefix)

    def test_exact_rollback_verification_covers_all_state_domains(self) -> None:
        source = self.method_source(
            self.base_tree,
            self.base_source,
            "ManagedFileRollbackRehearsalAdapter",
            "verify_exact_rollback",
        )
        for marker in (
            "self._verify_directory_snapshot(path, row)",
            "self._verify_current_alsa()",
            "_observe_service_snapshot()",
            "_observe_host_contract()",
            "_observe_mixer_snapshot()",
            "_observe_loopback_snapshot()",
            "_observe_dac_snapshot()",
        ):
            self.assertIn(marker, source)

    def test_v3_closure_refuses_after_managed_file_mutation(self) -> None:
        source = self.method_source(
            self.base_tree,
            self.base_source,
            "ManagedFileRollbackRehearsalAdapter",
            "close_restored_rehearsal_transaction",
        )
        self.assertIn("if self._managed_file_mutation_started", source)
        self.assertIn("use v4 exact-rollback rehearsal closure", source)

    def test_v4_closure_requires_install_rollback_restore_and_verification(self) -> None:
        source = self.method_source(
            self.base_tree,
            self.base_source,
            "ManagedFileRollbackRehearsalAdapter",
            "close_exact_rollback_rehearsal_transaction",
        )
        for marker in (
            "self._managed_file_mutation_started",
            "self._managed_files_installed_once",
            "self._filesystem_restored",
            "self._exact_rollback_verified",
            "self._services_restored",
            "self._dashboard_verified",
            "managed-files-rolled-back-and-closed",
            "installed_file_count=EXPECTED_PACKAGE_FILES",
        ):
            self.assertIn(marker, source)

    def test_blocked_calls_exist_only_in_blocked_proof_or_post_install_gate(self) -> None:
        blocked_names = {
            "reload_systemd",
            "select_split_bus_route",
            "start_managed_stage_c_services",
            "stop_managed_stage_c_services",
            "verify_split_bus_health",
            "run_finite_music_probe",
            "run_finite_alarm_probe",
            "write_commit_manifest",
            "select_direct_failback_route",
            "restore_mixer_state",
            "restore_service_state",
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
                if name in {"reload_systemd", "select_split_bus_route"}:
                    self.assertEqual(owners, {"prove_blocked_operations", "main"})
                else:
                    self.assertEqual(owners, {"prove_blocked_operations"})

    def test_c18_layers_have_no_systemd_route_mixer_module_or_audio_command(self) -> None:
        combined = self.base_source + self.v2_source + self.v3_source + self.v4_source
        for forbidden in (
            'host_run(["systemctl"',
            "daemon-reload",
            "systemctl enable",
            "systemctl disable",
            "systemctl restart",
            "amixer",
            "modprobe",
            "rmmod",
            "aplay",
            "arecord",
            "activation-approved",
        ):
            self.assertNotIn(forbidden, combined)

    def test_wrapper_is_prepare_only_and_has_one_constrained_sudo(self) -> None:
        self.assertIn('MODE="prepare"', self.wrapper_source)
        prepare = self.wrapper_source.index('if [[ "$MODE" == "prepare" ]]')
        sudo = self.wrapper_source.index("exec sudo env")
        self.assertLess(prepare, sudo)
        self.assertEqual(self.wrapper_source.count("exec sudo env"), 1)
        self.assertIn(
            "STAGE-C18-MANAGED-FILES-EXACT-ROLLBACK",
            self.wrapper_source,
        )
        self.assertIn(
            "/var/tmp/a-clockwork-plex-stage-c17-service-quiescence.3ySKhd",
            self.wrapper_source,
        )
        self.assertIn("There is no keep-active mode", self.wrapper_source)

    def test_wrapper_and_python_syntax(self) -> None:
        for path in (
            BASE_ADAPTER,
            ADAPTER_V2,
            ADAPTER_V3,
            ADAPTER_V4,
            ENGINE,
            REPO_ROOT
            / "scripts/stage_c_transaction/production_adapter_lifecycle_v4.py",
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
            msg=f"stdout={result.stdout}\nstderr={result.stderr}",
        )

    def test_no_activation_persistence_or_keep_active_interface(self) -> None:
        combined = self.engine_source + self.wrapper_source
        for forbidden in (
            "--activate",
            "--keep-active",
            "--commit",
            "--failback",
            "--uninstall",
            "activation-approved",
            "systemctl daemon-reload",
        ):
            self.assertNotIn(forbidden, combined)
        self.assertIn("Persistent Stage C activation remains blocked", combined)

    def test_design_records_first_write_and_mandatory_rollback_boundary(self) -> None:
        for marker in (
            "first production-filesystem mutation boundary",
            "Rollback is armed before the first production filesystem write",
            "immediate rollback-ledger adoption",
            "systemd reload",
            "close-exact-rollback-rehearsal-transaction",
            "twenty-two v1 operations",
            "remaining eleven v1 operations stay blocked",
        ):
            self.assertIn(marker, self.design_source)


if __name__ == "__main__":
    unittest.main()
