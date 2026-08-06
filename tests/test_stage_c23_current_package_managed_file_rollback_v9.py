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

ADAPTER_PATH = ROOT / "scripts/stage_c_transaction/current_package_managed_file_rollback_adapter_v9.py"
REHEARSAL_PATH = ROOT / "scripts/stage_c_transaction/current_package_managed_file_rollback_rehearsal_v9.py"
WRAPPER_PATH = ROOT / "scripts/test-stage-c23-current-package-managed-file-rollback.sh"

from scripts.stage_c_transaction.current_package_managed_file_rollback_adapter_v9 import (  # noqa: E402
    CURRENT_MANAGED_SNAPSHOT_PREFIX_V9,
    CURRENT_MANAGED_TRANSACTION_PREFIX_V9,
    CURRENT_PACKAGE_FILE_COUNT_V9,
    CURRENT_PACKAGE_PAYLOAD_COUNT_V9,
    CurrentPackageManagedFileRollbackAdapterV9,
)
from scripts.stage_c_transaction.current_package_managed_file_rollback_rehearsal_v9 import (  # noqa: E402
    EVIDENCE_PREFIX,
    EXPECTED_CHECKS,
    REQUIRED_CONFIRMATION,
    STAGE_C22_EVIDENCE_MANIFEST_SHA256,
    STAGE_C22_MANIFEST_ENTRIES,
    STAGE_C22_MANIFEST_ROWS,
)
from scripts.stage_c_transaction.current_package_service_quiescence_adapter_v8 import (  # noqa: E402
    CurrentPackageServiceQuiescenceAdapterV8,
)
from scripts.stage_c_transaction.managed_file_rollback_rehearsal_adapter import (  # noqa: E402
    ManagedFileRollbackRehearsalAdapter,
)
from scripts.stage_c_transaction.managed_file_rollback_rehearsal_adapter_v3 import (  # noqa: E402
    ManagedFileRollbackRehearsalAdapterV3,
)
from scripts.stage_c_transaction.managed_file_rollback_rehearsal_adapter_v4 import (  # noqa: E402
    ManagedFileRollbackRehearsalAdapterV4,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v3 import (  # noqa: E402
    ProductionAdapterV3,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v7 import (  # noqa: E402
    ProductionAdapterV7,
)


class StageC23CurrentPackageManagedFileRollbackV9Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter_source = ADAPTER_PATH.read_text(encoding="utf-8")
        self.rehearsal_source = REHEARSAL_PATH.read_text(encoding="utf-8")
        self.wrapper_source = WRAPPER_PATH.read_text(encoding="utf-8")

    def test_adapter_extends_accepted_current_package_service_owner(self) -> None:
        self.assertTrue(
            issubclass(
                CurrentPackageManagedFileRollbackAdapterV9,
                CurrentPackageServiceQuiescenceAdapterV8,
            )
        )
        self.assertTrue(
            issubclass(CurrentPackageManagedFileRollbackAdapterV9, ProductionAdapterV3)
        )
        self.assertFalse(
            issubclass(CurrentPackageManagedFileRollbackAdapterV9, ProductionAdapterV7)
        )

    def test_physically_exercised_mutation_primitives_are_reused_by_identity(self) -> None:
        self.assertIs(
            CurrentPackageManagedFileRollbackAdapterV9._snapshot_rows,
            ManagedFileRollbackRehearsalAdapter._snapshot_rows,
        )
        self.assertIs(
            CurrentPackageManagedFileRollbackAdapterV9._atomic_install_file,
            ManagedFileRollbackRehearsalAdapterV3._atomic_install_file,
        )
        self.assertIs(
            CurrentPackageManagedFileRollbackAdapterV9._restore_managed_files_exact,
            ManagedFileRollbackRehearsalAdapterV4._restore_managed_files_exact,
        )
        self.assertIs(
            CurrentPackageManagedFileRollbackAdapterV9.verify_exact_rollback,
            ManagedFileRollbackRehearsalAdapter.verify_exact_rollback,
        )

    def test_current_package_counts_and_identities_are_fixed(self) -> None:
        self.assertEqual(CURRENT_PACKAGE_FILE_COUNT_V9, 28)
        self.assertEqual(CURRENT_PACKAGE_PAYLOAD_COUNT_V9, 27)
        self.assertEqual(
            CURRENT_MANAGED_TRANSACTION_PREFIX_V9,
            "stage-c23-managed-file-rollback-install-",
        )
        self.assertEqual(
            CURRENT_MANAGED_SNAPSHOT_PREFIX_V9,
            "stage-c23-managed-file-rollback-snapshot-",
        )

    def test_frozen_stage_c22_evidence_identity_is_exact(self) -> None:
        self.assertEqual(
            STAGE_C22_EVIDENCE_MANIFEST_SHA256,
            "4720c6d2dd99080abbde5b9d34b4862ecd0cb0c62b44262fd695c40de7c169eb",
        )
        self.assertEqual(STAGE_C22_MANIFEST_ROWS, 140)
        self.assertEqual(STAGE_C22_MANIFEST_ENTRIES, 139)
        self.assertIn("validate_stage_c22_results", self.rehearsal_source)
        self.assertIn("validate_stage_c22_input_binding", self.rehearsal_source)
        self.assertIn("validate_stage_c22_identity", self.rehearsal_source)

    def test_check_order_covers_install_before_exact_rollback(self) -> None:
        self.assertEqual(len(EXPECTED_CHECKS), 47)
        for earlier, later in (
            ("stage-c22-evidence-replay", "pre-lock-live-baseline"),
            ("service-quiescence", "dac-release"),
            ("dac-release", "managed-file-installation"),
            ("managed-file-installation", "post-install-boundary"),
            ("post-install-boundary", "exact-filesystem-rollback"),
            ("exact-filesystem-rollback", "application-service-restoration"),
            ("dashboard-health", "exact-rollback-verification"),
            ("exact-rollback-verification", "exact-rollback-close-c23"),
            ("exact-rollback-close-c23", "production-lock-released"),
            ("production-lock-released", "post-lock-live-baseline"),
        ):
            self.assertLess(EXPECTED_CHECKS.index(earlier), EXPECTED_CHECKS.index(later))

    def test_confirmation_and_evidence_prefix_are_fixed(self) -> None:
        self.assertEqual(
            REQUIRED_CONFIRMATION,
            "STAGE-C23-CURRENT-PACKAGE-MANAGED-FILES-EXACT-ROLLBACK",
        )
        self.assertEqual(
            EVIDENCE_PREFIX,
            "a-clockwork-plex-stage-c23-current-package-managed-file-rollback.",
        )

    def test_wrapper_defaults_to_inert_prepare_only(self) -> None:
        self.assertIn('MODE="prepare"', self.wrapper_source)
        self.assertIn("Prepare-only invoked no sudo", self.wrapper_source)
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

    def test_new_layer_has_no_direct_host_command_implementation(self) -> None:
        combined = "\n".join(
            (self.adapter_source, self.rehearsal_source, self.wrapper_source)
        )
        for forbidden in (
            "subprocess.run",
            "os.system",
            "systemctl ",
            "amixer ",
            "alsactl ",
            "aplay ",
            "speaker-test",
            "camilladsp --",
        ):
            self.assertNotIn(forbidden, combined)

    def test_reload_route_audio_commit_and_approvals_remain_blocked(self) -> None:
        for marker in (
            "prove_blocked_operations",
            "prove_approval_operations_blocked",
            "AdapterOperation.RELOAD_SYSTEMD",
            "AdapterOperation.SELECT_SPLIT_BUS_ROUTE",
            "systemd_reloaded\": False",
            "route_selected\": False",
            "approval_operations_exposed\": False",
            "committed\": False",
        ):
            self.assertIn(marker, self.rehearsal_source)

    def test_failure_cleanup_rolls_files_back_before_services(self) -> None:
        exit_start = self.adapter_source.index("def __exit__")
        exit_end = self.adapter_source.index("    @property", exit_start)
        exit_source = self.adapter_source[exit_start:exit_end]
        self.assertLess(
            exit_source.index("self._restore_managed_files_exact()"),
            exit_source.index("CurrentPackageServiceQuiescenceAdapterV8.__exit__"),
        )

    def test_failure_path_retains_lock_and_transaction(self) -> None:
        self.assertIn(
            "production lock and transaction are intentionally retained",
            self.adapter_source,
        )
        self.assertIn("do not clean them manually", self.wrapper_source)

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
