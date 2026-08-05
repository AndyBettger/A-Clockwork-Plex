from __future__ import annotations

import ast
import os
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
BASE = REPO_ROOT / "scripts/stage_c_transaction/managed_file_rollback_rehearsal_adapter.py"
V2 = REPO_ROOT / "scripts/stage_c_transaction/managed_file_rollback_rehearsal_adapter_v2.py"
V3 = REPO_ROOT / "scripts/stage_c_transaction/managed_file_rollback_rehearsal_adapter_v3.py"
V4 = REPO_ROOT / "scripts/stage_c_transaction/managed_file_rollback_rehearsal_adapter_v4.py"
ENGINE = REPO_ROOT / "scripts/stage_c_transaction/managed_file_rollback_rehearsal.py"
WRAPPER = REPO_ROOT / "scripts/test-stage-c-managed-file-rollback-rehearsal.sh"
DESIGN = REPO_ROOT / "docs/stage-c18-managed-file-install-exact-rollback-rehearsal-design.md"


class StageCManagedFileRollbackRehearsalSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = BASE.read_text(encoding="utf-8")
        self.v2 = V2.read_text(encoding="utf-8")
        self.v3 = V3.read_text(encoding="utf-8")
        self.v4 = V4.read_text(encoding="utf-8")
        self.engine = ENGINE.read_text(encoding="utf-8")
        self.wrapper = WRAPPER.read_text(encoding="utf-8")
        self.design = DESIGN.read_text(encoding="utf-8")
        self.base_tree = ast.parse(self.base)
        self.v3_tree = ast.parse(self.v3)
        self.v4_tree = ast.parse(self.v4)
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

    def test_final_adapter_conforms_to_v4(self) -> None:
        instance = object.__new__(ManagedFileRollbackRehearsalAdapterV4)
        self.assertIsInstance(instance, ProductionAdapterV4)
        for method in (
            "install_managed_files",
            "restore_exact_snapshot",
            "verify_exact_rollback",
            "close_exact_rollback_rehearsal_transaction",
        ):
            self.assertTrue(hasattr(instance, method))

    def test_engine_has_exact_forty_checks(self) -> None:
        self.assertEqual(len(EXPECTED_CHECKS), 40)
        self.assertEqual(len(set(EXPECTED_CHECKS)), 40)
        self.assertEqual(EXPECTED_CHECKS[23], "managed-file-installation")
        self.assertEqual(EXPECTED_CHECKS[26], "exact-filesystem-rollback")
        self.assertEqual(EXPECTED_CHECKS[34], "exact-rollback-close-v4")
        self.assertEqual(EXPECTED_CHECKS[-1], "activation-interface")

    def test_successful_c17_replay_is_required(self) -> None:
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

    def test_manifest_and_snapshot_own_destinations(self) -> None:
        source = self.method_source(
            self.base_tree,
            self.base,
            "ManagedFileRollbackRehearsalAdapter",
            "_snapshot_rows",
        )
        for marker in (
            "self._entries",
            "CURRENT_ALSA_DESTINATION",
            'row.state != "absent"',
            "authoritative filesystem state",
        ):
            self.assertIn(marker, source)
        parser = self.function_source("parse_args")
        for forbidden in (
            "--destination",
            "--unit",
            "--command",
            "--route",
            "--keep-active",
        ):
            self.assertNotIn(forbidden, parser)

    def test_rollback_is_armed_before_first_write(self) -> None:
        create = self.method_source(
            self.v3_tree,
            self.v3,
            "ManagedFileRollbackRehearsalAdapterV3",
            "_create_directory",
        )
        install = self.method_source(
            self.v3_tree,
            self.v3,
            "ManagedFileRollbackRehearsalAdapterV3",
            "_atomic_install_file",
        )
        self.assertLess(
            create.index("self._arm_managed_rollback()"),
            create.index("os.mkdir("),
        )
        self.assertLess(
            install.index("self._arm_managed_rollback()"),
            install.index("os.open(temporary"),
        )

    def test_rollback_ledger_adopts_created_path_before_later_failure(self) -> None:
        create = self.method_source(
            self.v3_tree,
            self.v3,
            "ManagedFileRollbackRehearsalAdapterV3",
            "_create_directory",
        )
        install = self.method_source(
            self.v3_tree,
            self.v3,
            "ManagedFileRollbackRehearsalAdapterV3",
            "_atomic_install_file",
        )
        self.assertLess(
            create.index("self._created_directories.append(installed)"),
            create.index("os.fchmod(child_fd"),
        )
        self.assertLess(
            install.index("os.replace("),
            install.index("self._installed_files.append(record)"),
        )
        self.assertLess(
            install.index("self._installed_files.append(record)"),
            install.index("os.fsync(parent_fd)"),
        )

    def test_install_acceptance_is_stricter_than_rollback_identity(self) -> None:
        strict = self.method_source(
            self.base_tree,
            self.base,
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
            self.assertIn(marker, strict)

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
                ManagedFileRollbackRehearsalAdapterV4._verify_rollback_identity(
                    record
                ),
                path,
            )
            with self.assertRaises(ManagedFileRollbackFailure):
                ManagedFileRollbackRehearsalAdapter._verify_installed_object(
                    record
                )

            substitute = Path(raw) / "substitute"
            substitute.write_text("substitute", encoding="utf-8")
            substitute_info = substitute.lstat()
            self.assertNotEqual(substitute_info.st_ino, record.inode)
            os.replace(substitute, path)
            with self.assertRaises(ManagedFileRollbackFailure):
                ManagedFileRollbackRehearsalAdapterV4._verify_rollback_identity(
                    record
                )

    def test_rollback_removes_only_exact_recorded_inodes(self) -> None:
        source = self.method_source(
            self.v4_tree,
            self.v4,
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

    def test_failure_cleanup_rolls_files_back_before_services(self) -> None:
        source = self.method_source(
            self.base_tree,
            self.base,
            "ManagedFileRollbackRehearsalAdapter",
            "__exit__",
        )
        self.assertLess(
            source.index("self._restore_managed_files_exact()"),
            source.index("super().__exit__"),
        )
        self.assertIn(
            "production lock and transaction are intentionally retained",
            source,
        )

    def test_normal_order_is_install_block_rollback_restore_verify(self) -> None:
        source = self.function_source("main")
        positions = [
            source.index("adapter.install_managed_files"),
            source.index('"post-install-boundary"'),
            source.index("adapter.restore_exact_snapshot"),
            source.index("adapter.restore_captured_application_services"),
            source.index("adapter.verify_dashboard_health"),
            source.index("adapter.verify_exact_rollback"),
        ]
        self.assertEqual(positions, sorted(positions))

    def test_exact_verification_covers_every_state_domain(self) -> None:
        source = self.method_source(
            self.base_tree,
            self.base,
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

    def test_v3_closure_refuses_file_mutation_and_v4_requires_rollback(self) -> None:
        v3_close = self.method_source(
            self.base_tree,
            self.base,
            "ManagedFileRollbackRehearsalAdapter",
            "close_restored_rehearsal_transaction",
        )
        self.assertIn("if self._managed_file_mutation_started", v3_close)
        self.assertIn("use v4 exact-rollback rehearsal closure", v3_close)
        v4_close = self.method_source(
            self.base_tree,
            self.base,
            "ManagedFileRollbackRehearsalAdapter",
            "close_exact_rollback_rehearsal_transaction",
        )
        for marker in (
            "self._managed_files_installed_once",
            "self._filesystem_restored",
            "self._exact_rollback_verified",
            "self._services_restored",
            "self._dashboard_verified",
            "managed-files-rolled-back-and-closed",
            "installed_file_count=EXPECTED_PACKAGE_FILES",
        ):
            self.assertIn(marker, v4_close)

    def test_blocked_operations_are_confined_to_proof_and_post_install_gate(self) -> None:
        blocked = {
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
        owners: dict[str, set[str]] = {name: set() for name in blocked}
        for node in ast.walk(self.engine_tree):
            if not isinstance(node, ast.Call) or not isinstance(
                node.func, ast.Attribute
            ):
                continue
            if node.func.attr not in blocked:
                continue
            current: ast.AST = node
            owner = "<module>"
            while current in parents:
                current = parents[current]
                if isinstance(current, ast.FunctionDef):
                    owner = current.name
                    break
            owners[node.func.attr].add(owner)
        for name, locations in owners.items():
            expected = (
                {"prove_blocked_operations", "main"}
                if name in {"reload_systemd", "select_split_bus_route"}
                else {"prove_blocked_operations"}
            )
            self.assertEqual(locations, expected, msg=name)

    def test_layers_have_no_service_route_mixer_module_or_audio_command(self) -> None:
        combined = self.base + self.v2 + self.v3 + self.v4
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

    def test_wrapper_is_prepare_only_with_one_constrained_sudo(self) -> None:
        prepare = self.wrapper.index('if [[ "$MODE" == "prepare" ]]')
        sudo = self.wrapper.index("exec sudo env")
        self.assertLess(prepare, sudo)
        self.assertEqual(self.wrapper.count("exec sudo env"), 1)
        self.assertIn(
            "STAGE-C18-MANAGED-FILES-EXACT-ROLLBACK",
            self.wrapper,
        )
        self.assertIn(
            "a-clockwork-plex-stage-c17-service-quiescence.3ySKhd",
            self.wrapper,
        )
        self.assertIn("There is no keep-active mode", self.wrapper)

    def test_python_and_shell_syntax(self) -> None:
        for path in (
            BASE,
            V2,
            V3,
            V4,
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
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_no_activation_persistence_or_keep_active_interface(self) -> None:
        combined = self.engine + self.wrapper
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
        self.assertIn(
            "Persistent Stage C activation remains blocked",
            combined,
        )

    def test_design_records_mandatory_first_write_rollback(self) -> None:
        for marker in (
            "first production-filesystem mutation boundary",
            "Rollback is armed before the first production filesystem write",
            "immediate rollback-ledger adoption",
            "close-exact-rollback-rehearsal-transaction",
            "twenty-two v1 operations",
            "remaining eleven v1 operations stay blocked",
        ):
            self.assertIn(marker, self.design)


if __name__ == "__main__":
    unittest.main()
