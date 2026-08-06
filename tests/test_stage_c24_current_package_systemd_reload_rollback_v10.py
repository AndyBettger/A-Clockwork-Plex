from __future__ import annotations

import ast
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

ADAPTER_PATH = (
    ROOT
    / "scripts/stage_c_transaction/"
    "current_package_systemd_reload_rollback_adapter_v10.py"
)
REHEARSAL_PATH = (
    ROOT
    / "scripts/stage_c_transaction/"
    "current_package_systemd_reload_rollback_rehearsal_v10.py"
)
WRAPPER_PATH = (
    ROOT / "scripts/test-stage-c24-current-package-systemd-reload-rollback.sh"
)

from scripts.stage_c_transaction import (  # noqa: E402
    current_package_candidate_rehearsal_adapter_v7 as current_v7,
)
from scripts.stage_c_transaction.current_package_managed_file_rollback_adapter_v9 import (  # noqa: E402
    CURRENT_PACKAGE_FILE_COUNT_V9,
    CURRENT_PACKAGE_PAYLOAD_COUNT_V9,
    CurrentPackageManagedFileRollbackAdapterV9,
)
from scripts.stage_c_transaction.current_package_systemd_reload_rollback_adapter_v10 import (  # noqa: E402
    CURRENT_SYSTEMD_SNAPSHOT_PREFIX_V10,
    CURRENT_SYSTEMD_TRANSACTION_PREFIX_V10,
    CurrentPackageSystemdReloadRollbackAdapterV10,
    CurrentPackageSystemdReloadRollbackReceiptV10,
    apply_current_systemd_reload_identity_contract_v10,
)
from scripts.stage_c_transaction.current_package_systemd_reload_rollback_rehearsal_v10 import (  # noqa: E402
    EVIDENCE_PREFIX,
    EXPECTED_CHECKS,
    REQUIRED_CONFIRMATION,
    STAGE_C23_MANIFEST_ENTRIES,
)
from scripts.stage_c_transaction.production_adapter_contract import (  # noqa: E402
    TransactionIdentity,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v3 import (  # noqa: E402
    ProductionAdapterV3,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v7 import (  # noqa: E402
    ProductionAdapterV7,
)
from scripts.stage_c_transaction.stage_c23_evidence_identity import (  # noqa: E402
    ACCEPTED_STAGE_C23_MANIFEST_ROWS,
    ACCEPTED_STAGE_C23_MANIFEST_SHA256,
)
from scripts.stage_c_transaction.systemd_reload_rollback_rehearsal_adapter import (  # noqa: E402
    SystemdReloadRollbackRehearsalAdapter,
)


class StageC24CurrentPackageSystemdReloadRollbackV10Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter_source = ADAPTER_PATH.read_text(encoding="utf-8")
        self.rehearsal_source = REHEARSAL_PATH.read_text(encoding="utf-8")
        self.wrapper_source = WRAPPER_PATH.read_text(encoding="utf-8")
        self.adapter_literals = {
            node.value
            for node in ast.walk(ast.parse(self.adapter_source))
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }

    def test_adapter_extends_accepted_current_package_file_owner(self) -> None:
        self.assertTrue(
            issubclass(
                CurrentPackageSystemdReloadRollbackAdapterV10,
                CurrentPackageManagedFileRollbackAdapterV9,
            )
        )
        self.assertTrue(
            issubclass(
                CurrentPackageSystemdReloadRollbackAdapterV10,
                ProductionAdapterV3,
            )
        )
        self.assertFalse(
            issubclass(
                CurrentPackageSystemdReloadRollbackAdapterV10,
                ProductionAdapterV7,
            )
        )

    def test_physically_exercised_systemd_primitives_are_reused_by_identity(
        self,
    ) -> None:
        self.assertIs(
            CurrentPackageSystemdReloadRollbackAdapterV10._run_daemon_reload,
            SystemdReloadRollbackRehearsalAdapter._run_daemon_reload,
        )
        self.assertIs(
            CurrentPackageSystemdReloadRollbackAdapterV10._observe_managed_units,
            SystemdReloadRollbackRehearsalAdapter._observe_managed_units,
        )
        self.assertIs(
            CurrentPackageSystemdReloadRollbackAdapterV10._parse_systemctl_show,
            SystemdReloadRollbackRehearsalAdapter._parse_systemctl_show,
        )

    def test_current_package_systemd_identities_are_fixed(self) -> None:
        self.assertEqual(
            CURRENT_SYSTEMD_TRANSACTION_PREFIX_V10,
            "stage-c24-systemd-reload-rollback-install-",
        )
        self.assertEqual(
            CURRENT_SYSTEMD_SNAPSHOT_PREFIX_V10,
            "stage-c24-systemd-reload-rollback-snapshot-",
        )

    def test_identity_binding_accepts_only_legacy_or_already_bound_state(
        self,
    ) -> None:
        with (
            patch.object(
                current_v7,
                "CURRENT_TRANSACTION_PREFIX",
                "stage-c21-prepare-install-",
            ),
            patch.object(
                current_v7,
                "CURRENT_SNAPSHOT_PREFIX",
                "stage-c21-prepare-snapshot-",
            ),
        ):
            apply_current_systemd_reload_identity_contract_v10()
            self.assertEqual(
                current_v7.CURRENT_TRANSACTION_PREFIX,
                CURRENT_SYSTEMD_TRANSACTION_PREFIX_V10,
            )
            self.assertEqual(
                current_v7.CURRENT_SNAPSHOT_PREFIX,
                CURRENT_SYSTEMD_SNAPSHOT_PREFIX_V10,
            )
            apply_current_systemd_reload_identity_contract_v10()

        with (
            patch.object(
                current_v7,
                "CURRENT_TRANSACTION_PREFIX",
                "unexpected-",
            ),
            patch.object(
                current_v7,
                "CURRENT_SNAPSHOT_PREFIX",
                "unexpected-",
            ),
        ):
            with self.assertRaisesRegex(SystemExit, "contract changed"):
                apply_current_systemd_reload_identity_contract_v10()

    def test_receipt_requires_28_files_27_payloads_and_two_reloads(self) -> None:
        transaction = TransactionIdentity(
            "stage-c24-systemd-reload-rollback-install-test"
        )
        receipt = CurrentPackageSystemdReloadRollbackReceiptV10(
            transaction=transaction,
            state="current-package-systemd-reload-rolled-back-and-closed",
            mutation_started=True,
            managed_files_installed=True,
            systemd_reloaded=True,
            filesystem_restored=True,
            systemd_manager_restored=True,
            services_restored=True,
            committed=False,
            transaction_path_absent=True,
            parents_restored=True,
            installed_file_count=28,
            payload_file_count=27,
            daemon_reload_count=2,
            audit_evidence="/var/tmp/evidence",
        )
        self.assertEqual(receipt.installed_file_count, 28)
        self.assertEqual(receipt.payload_file_count, 27)
        self.assertEqual(receipt.daemon_reload_count, 2)

        with self.assertRaisesRegex(ValueError, "exactly two"):
            CurrentPackageSystemdReloadRollbackReceiptV10(
                **{**receipt.__dict__, "daemon_reload_count": 1}
            )

    def test_frozen_stage_c23_evidence_shape_is_exact(self) -> None:
        self.assertEqual(
            ACCEPTED_STAGE_C23_MANIFEST_SHA256,
            "e51bac4fb54357c5b30a31152af1309f484b5f2a82c0d2e9e9a866f64432466a",
        )
        self.assertEqual(ACCEPTED_STAGE_C23_MANIFEST_ROWS, 144)
        self.assertEqual(STAGE_C23_MANIFEST_ENTRIES, 143)
        self.assertIn(
            "ACCEPTED_STAGE_C23_MANIFEST_SHA256",
            self.rehearsal_source,
        )
        self.assertIn(
            "ACCEPTED_STAGE_C23_MANIFEST_ROWS",
            self.rehearsal_source,
        )
        self.assertIn("validate_stage_c23_results", self.rehearsal_source)
        self.assertIn("validate_stage_c23_identity", self.rehearsal_source)

    def test_check_order_covers_two_reload_exact_rollback_sequence(self) -> None:
        self.assertEqual(len(EXPECTED_CHECKS), 54)
        for earlier, later in (
            ("stage-c23-evidence-replay", "pre-lock-live-baseline"),
            ("service-quiescence", "dac-release"),
            ("dac-release", "managed-file-installation"),
            ("managed-file-installation", "systemd-candidate-reload"),
            ("systemd-candidate-reload", "exact-filesystem-rollback"),
            (
                "exact-filesystem-rollback",
                "pre-manager-rollback-service-refusal",
            ),
            (
                "pre-manager-rollback-service-refusal",
                "systemd-manager-rollback",
            ),
            ("systemd-manager-rollback", "application-service-restoration"),
            ("dashboard-health", "exact-rollback-verification"),
            ("exact-rollback-verification", "c23-closure-refusal"),
            ("c23-closure-refusal", "exact-rollback-close-c24"),
            ("exact-rollback-close-c24", "production-lock-released"),
            ("production-lock-released", "post-lock-live-baseline"),
        ):
            self.assertLess(
                EXPECTED_CHECKS.index(earlier),
                EXPECTED_CHECKS.index(later),
            )

    def test_confirmation_and_evidence_prefix_are_fixed(self) -> None:
        self.assertEqual(
            REQUIRED_CONFIRMATION,
            "STAGE-C24-CURRENT-PACKAGE-SYSTEMD-RELOAD-EXACT-ROLLBACK",
        )
        self.assertEqual(
            EVIDENCE_PREFIX,
            "a-clockwork-plex-stage-c24-current-package-systemd-reload-rollback.",
        )

    def test_wrapper_defaults_to_inert_prepare_only(self) -> None:
        self.assertIn('MODE="prepare"', self.wrapper_source)
        self.assertIn("Prepare-only invoked no sudo", self.wrapper_source)
        self.assertIn("called no systemctl command", self.wrapper_source)
        self.assertIn("wrote no production file", self.wrapper_source)
        self.assertEqual(self.wrapper_source.count("exec sudo env"), 1)

    def test_wrapper_has_valid_shell_syntax(self) -> None:
        checked = subprocess.run(
            ["bash", "-n", str(WRAPPER_PATH)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_wrapper_requires_only_fixed_inputs(self) -> None:
        for option in (
            "--package-root",
            "--baseline-root",
            "--stage-c21-root",
            "--stage-c22-root",
            "--stage-c23-root",
            "--evidence-root",
            "--confirm",
        ):
            self.assertIn(option, self.wrapper_source)
        for forbidden in (
            "--install",
            "--activate",
            "--service",
            "--route",
            "--mixer",
            "--approval",
            "--transaction-id",
            "--lock-path",
            "--command",
        ):
            self.assertNotIn(forbidden, self.wrapper_source)

    def test_new_adapter_has_no_second_host_command_owner(self) -> None:
        for forbidden in (
            "subprocess.run",
            "os.system",
            "host_run(",
            "Popen(",
        ):
            self.assertNotIn(forbidden, self.adapter_source)
        self.assertIn(
            "SystemdReloadRollbackRehearsalAdapter._run_daemon_reload",
            self.adapter_source,
        )
        self.assertIn(
            "SystemdReloadRollbackRehearsalAdapter._observe_managed_units",
            self.adapter_source,
        )

    def test_route_audio_commit_and_approvals_remain_blocked(self) -> None:
        for marker in (
            "prove_c24_blocked_operations",
            "prove_approval_operations_blocked",
            "AdapterOperation.SELECT_SPLIT_BUS_ROUTE",
            '"route_selected": False',
            '"approval_operations_exposed": False',
            '"committed": False',
        ):
            self.assertIn(marker, self.rehearsal_source)
        self.assertNotIn(
            "start_managed_stage_c_services(",
            self.adapter_source,
        )
        self.assertNotIn("select_split_bus_route(", self.adapter_source)

    def test_failure_cleanup_orders_files_manager_then_services(self) -> None:
        exit_start = self.adapter_source.index("def __exit__")
        exit_end = self.adapter_source.index("    @property", exit_start)
        exit_source = self.adapter_source[exit_start:exit_end]
        self.assertLess(
            exit_source.index("self._restore_managed_files_exact()"),
            exit_source.index("self._restore_systemd_manager_exact()"),
        )
        self.assertLess(
            exit_source.index("self._restore_systemd_manager_exact()"),
            exit_source.index(
                "CurrentPackageManagedFileRollbackAdapterV9.__exit__"
            ),
        )

    def test_failure_path_retains_lock_and_transaction(self) -> None:
        self.assertTrue(
            any(
                "production lock and transaction are intentionally retained"
                in literal
                for literal in self.adapter_literals
            )
        )
        self.assertIn("do not clean it manually", self.wrapper_source)

    def test_c23_file_only_closure_is_refused_after_manager_mutation(self) -> None:
        self.assertTrue(
            any(
                "C23 file-only closure is unavailable after systemd-manager mutation"
                in literal
                for literal in self.adapter_literals
            )
        )
        self.assertIn("c23-closure-refusal", self.rehearsal_source)

    def test_historical_twelve_file_receipt_is_not_reused(self) -> None:
        self.assertNotIn(
            "SystemdReloadRollbackTransactionReceipt",
            self.adapter_source,
        )
        self.assertNotIn("installed_file_count=12", self.adapter_source)
        self.assertEqual(CURRENT_PACKAGE_FILE_COUNT_V9, 28)
        self.assertEqual(CURRENT_PACKAGE_PAYLOAD_COUNT_V9, 27)
        self.assertIn("CURRENT_PACKAGE_FILE_COUNT_V9", self.adapter_source)
        self.assertIn("CURRENT_PACKAGE_PAYLOAD_COUNT_V9", self.adapter_source)

    def test_no_master_eq_installer_reference(self) -> None:
        combined = "\n".join(
            (self.adapter_source, self.rehearsal_source, self.wrapper_source)
        )
        self.assertNotIn("install-master-eq.sh", combined)

    def test_new_python_modules_parse(self) -> None:
        ast.parse(self.adapter_source)
        ast.parse(self.rehearsal_source)


if __name__ == "__main__":
    unittest.main()
