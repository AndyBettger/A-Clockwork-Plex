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

ADAPTER_PATH = (
    ROOT
    / "scripts/stage_c_transaction/"
    "current_package_service_quiescence_adapter_v8.py"
)
REHEARSAL_PATH = (
    ROOT
    / "scripts/stage_c_transaction/"
    "current_package_service_quiescence_rehearsal_v8.py"
)
WRAPPER_PATH = (
    ROOT / "scripts/test-stage-c22-current-package-service-quiescence.sh"
)

from scripts.stage_c_transaction.current_package_candidate_rehearsal_adapter_v7 import (  # noqa: E402
    CurrentPackageCandidateValidationAdapterV7,
)
from scripts.stage_c_transaction.current_package_service_quiescence_adapter_v8 import (  # noqa: E402
    CURRENT_SERVICE_SNAPSHOT_PREFIX_V8,
    CURRENT_SERVICE_TRANSACTION_PREFIX_V8,
    CurrentPackageServiceQuiescenceAdapterV8,
)
from scripts.stage_c_transaction.current_package_service_quiescence_rehearsal_v8 import (  # noqa: E402
    EVIDENCE_PREFIX,
    EXPECTED_CHECKS,
    REQUIRED_CONFIRMATION,
    STAGE_C21_EVIDENCE_MANIFEST_SHA256,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v3 import (  # noqa: E402
    ProductionAdapterV3,
)
from scripts.stage_c_transaction.service_quiescence_rehearsal_adapter import (  # noqa: E402
    ServiceQuiescenceRehearsalAdapter,
)
from scripts.stage_c_transaction.service_quiescence_rehearsal_adapter_v2 import (  # noqa: E402
    ServiceQuiescenceRehearsalAdapterV2,
)


class StageC22CurrentPackageServiceQuiescenceV8Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter_source = ADAPTER_PATH.read_text(encoding="utf-8")
        self.rehearsal_source = REHEARSAL_PATH.read_text(encoding="utf-8")
        self.wrapper_source = WRAPPER_PATH.read_text(encoding="utf-8")

    def test_composed_adapter_mro_is_current_package_then_historical_candidate(self) -> None:
        mro = CurrentPackageServiceQuiescenceAdapterV8.mro()
        self.assertLess(mro.index(ServiceQuiescenceRehearsalAdapterV2), mro.index(ServiceQuiescenceRehearsalAdapter))
        self.assertLess(mro.index(ServiceQuiescenceRehearsalAdapter), mro.index(CurrentPackageCandidateValidationAdapterV7))
        self.assertTrue(issubclass(CurrentPackageServiceQuiescenceAdapterV8, ProductionAdapterV3))

    def test_current_package_owns_staging_and_transaction_methods(self) -> None:
        self.assertIs(
            CurrentPackageServiceQuiescenceAdapterV8.stage_candidate_files,
            CurrentPackageCandidateValidationAdapterV7.stage_candidate_files,
        )
        self.assertIs(
            CurrentPackageServiceQuiescenceAdapterV8.create_authoritative_transaction,
            CurrentPackageCandidateValidationAdapterV7.create_authoritative_transaction,
        )

    def test_physically_exercised_layer_owns_service_mutation(self) -> None:
        self.assertIs(
            CurrentPackageServiceQuiescenceAdapterV8.stop_captured_application_services,
            ServiceQuiescenceRehearsalAdapter.stop_captured_application_services,
        )
        self.assertIs(
            CurrentPackageServiceQuiescenceAdapterV8.restore_captured_application_services,
            ServiceQuiescenceRehearsalAdapter.restore_captured_application_services,
        )
        self.assertIs(
            CurrentPackageServiceQuiescenceAdapterV8.verify_dashboard_health,
            ServiceQuiescenceRehearsalAdapterV2.verify_dashboard_health,
        )

    def test_stage_c22_identity_prefixes_are_fixed(self) -> None:
        self.assertEqual(
            CURRENT_SERVICE_TRANSACTION_PREFIX_V8,
            "stage-c22-service-rehearsal-install-",
        )
        self.assertEqual(
            CURRENT_SERVICE_SNAPSHOT_PREFIX_V8,
            "stage-c22-service-rehearsal-snapshot-",
        )

    def test_exact_accepted_stage_c21_manifest_is_bound(self) -> None:
        self.assertEqual(
            STAGE_C21_EVIDENCE_MANIFEST_SHA256,
            "a630c6ff399c2c7081a4da8a74af79615d72497727ce302a6261ae0449bbedff",
        )
        self.assertIn("STAGE_C21_EXPECTED_CHECKS", self.rehearsal_source)
        self.assertIn("candidate-review-copy", self.rehearsal_source)
        self.assertIn("transaction-rehearsal-copy", self.rehearsal_source)

    def test_check_order_covers_complete_reversible_mutation(self) -> None:
        self.assertEqual(len(EXPECTED_CHECKS), 41)
        for earlier, later in (
            ("approval-operation-boundary", "service-quiescence"),
            ("service-quiescence", "dac-release"),
            ("dac-release", "pre-install-boundary"),
            ("pre-install-boundary", "application-service-restoration"),
            ("dashboard-health", "restored-transaction-close-v3"),
            ("restored-transaction-close-v3", "production-lock-released"),
            ("production-lock-released", "post-lock-live-baseline"),
            ("post-lock-live-baseline", "evidence-integrity"),
        ):
            self.assertLess(EXPECTED_CHECKS.index(earlier), EXPECTED_CHECKS.index(later))

    def test_confirmation_and_evidence_prefix_are_fixed(self) -> None:
        self.assertEqual(
            REQUIRED_CONFIRMATION,
            "STAGE-C22-CURRENT-PACKAGE-SERVICE-QUIESCE-RESTORE",
        )
        self.assertEqual(
            EVIDENCE_PREFIX,
            "a-clockwork-plex-stage-c22-current-package-service-quiescence.",
        )

    def test_wrapper_defaults_to_inert_prepare_only(self) -> None:
        self.assertIn('MODE="prepare"', self.wrapper_source)
        self.assertIn("Prepare-only invoked no sudo", self.wrapper_source)
        self.assertIn("stopped no service", self.wrapper_source)
        self.assertEqual(self.wrapper_source.count("exec sudo env"), 1)

    def test_wrapper_has_only_fixed_required_roots(self) -> None:
        for option in (
            "--package-root",
            "--baseline-root",
            "--stage-c21-root",
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

    def test_new_layer_contains_no_direct_systemctl_or_audio_command(self) -> None:
        combined = "\n".join(
            (self.adapter_source, self.rehearsal_source, self.wrapper_source)
        )
        for forbidden in (
            "systemctl",
            "amixer",
            "alsactl",
            "aplay",
            "speaker-test",
            "camilladsp --",
        ):
            self.assertNotIn(forbidden, combined)

    def test_installation_remains_blocked_after_dac_release(self) -> None:
        self.assertIn("AdapterOperation.INSTALL_MANAGED_FILES", self.rehearsal_source)
        self.assertIn("pre-install-boundary", self.rehearsal_source)
        self.assertNotIn("adapter.install_managed_files(transaction.transaction)\n            require_receipt", self.rehearsal_source)

    def test_approval_interface_remains_absent(self) -> None:
        self.assertIn("prove_approval_operations_blocked", self.rehearsal_source)
        self.assertIn("ProductionAdapterV7", self.rehearsal_source)
        self.assertIn("unexpectedly exposes approval-capable v7", self.rehearsal_source)

    def test_full_baseline_is_reobserved_after_lock_release(self) -> None:
        release_index = self.rehearsal_source.index('"production-lock-released"')
        post_index = self.rehearsal_source.index('"post-lock-live-baseline"')
        self.assertLess(release_index, post_index)
        self.assertGreaterEqual(
            self.rehearsal_source.count("ProductionPrepareOnlyInspectorV7("),
            2,
        )

    def test_no_master_eq_installer_reference(self) -> None:
        combined = "\n".join(
            (self.adapter_source, self.rehearsal_source, self.wrapper_source)
        )
        self.assertNotIn("install-master-eq.sh", combined)

    def test_new_python_modules_parse(self) -> None:
        ast.parse(self.adapter_source)
        ast.parse(self.rehearsal_source)

    def test_prepare_only_text_names_the_temporary_outage(self) -> None:
        self.assertIn("temporarily unavailable", self.wrapper_source)
        self.assertIn("SSH remains outside", self.wrapper_source)
        self.assertIn("restoration failure deliberately", self.wrapper_source)


if __name__ == "__main__":
    unittest.main()
