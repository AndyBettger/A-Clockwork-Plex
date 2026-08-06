from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

ADAPTER_PATH = (
    ROOT
    / "scripts/stage_c_transaction/"
    "current_package_candidate_rehearsal_adapter_v7.py"
)
CONTRACT_PATH = (
    ROOT / "scripts/stage_c_transaction/current_package_contract_v7.py"
)
REHEARSAL_PATH = (
    ROOT
    / "scripts/stage_c_transaction/current_package_candidate_rehearsal_v7.py"
)
WRAPPER_PATH = (
    ROOT / "scripts/test-stage-c21-current-package-transaction-preparation.sh"
)

from scripts.stage_c_activation_package.core import (  # noqa: E402
    EXPECTED_FILES,
    RUNTIME_MODULES,
)
from scripts.stage_c_activation_package.runtime_templates import (  # noqa: E402
    PACKAGE_PHASE,
)
from scripts.stage_c_transaction.current_package_candidate_rehearsal_adapter_v7 import (  # noqa: E402
    CURRENT_PARENT_CONTRACT,
    CURRENT_SNAPSHOT_PREFIX,
    CURRENT_TRANSACTION_PREFIX,
)
from scripts.stage_c_transaction.current_package_candidate_rehearsal_v7 import (  # noqa: E402
    EVIDENCE_PREFIX,
    EXPECTED_CHECKS,
    PACKAGE_PREFIX,
    REQUIRED_CONFIRMATION,
    prove_approval_operations_blocked,
)
from scripts.stage_c_transaction.current_package_contract_v7 import (  # noqa: E402
    ACCEPTED_PACKAGE_FINGERPRINT,
    BASELINE_MANIFEST_JSON_SHA256,
    BASELINE_PREFIX,
    BASELINE_REPORT_JSON_SHA256,
    BASELINE_REPORT_TEXT_SHA256,
    CurrentPackageContractErrorV7,
    validate_prepare_only_report_against_accepted_v7,
    validate_snapshot_payloads_against_accepted_v7,
)
from scripts.stage_c_transaction.production_adapter_contract import (  # noqa: E402
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    DAC_CONTRACT,
    DacOwner,
    DacSnapshot,
    HostContractSnapshot,
    LOOPBACK_CONTRACT,
    LoopbackSnapshot,
    MixerControl,
    MixerSnapshot,
    PackageFingerprint,
    PRODUCTION_LOCK_PATH,
    ProductionLockObservation,
    ServiceActiveState,
    ServiceEnableState,
    ServiceLoadState,
    ServiceSnapshot,
    ServiceState,
    ServiceUnit,
    TransactionIdentity,
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v7 import (  # noqa: E402
    ActivationApprovalLifecycleOperation,
)
from scripts.stage_c_transaction.production_prepare_only_inspector_v7 import (  # noqa: E402
    ProductionApprovalBaselineObservationV7,
    ProductionApprovalBaselineStateV7,
    ProductionPrepareOnlyDispositionV7,
    ProductionPrepareOnlyReportV7,
)


class StageC21CurrentPackagePreparationV7Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter_source = ADAPTER_PATH.read_text(encoding="utf-8")
        self.contract_source = CONTRACT_PATH.read_text(encoding="utf-8")
        self.rehearsal_source = REHEARSAL_PATH.read_text(encoding="utf-8")
        self.wrapper_source = WRAPPER_PATH.read_text(encoding="utf-8")

    @staticmethod
    def services() -> ServiceSnapshot:
        application = {
            ServiceUnit.PLEXAMP,
            ServiceUnit.SHAIRPORT_SYNC,
            ServiceUnit.DASHBOARD,
        }
        return ServiceSnapshot(
            tuple(
                ServiceState(
                    unit=unit,
                    load=(
                        ServiceLoadState.LOADED
                        if unit in application
                        else ServiceLoadState.NOT_FOUND
                    ),
                    active=(
                        ServiceActiveState.ACTIVE
                        if unit in application
                        else ServiceActiveState.INACTIVE
                    ),
                    enabled=(
                        ServiceEnableState.ENABLED
                        if unit in application
                        else ServiceEnableState.NOT_FOUND
                    ),
                )
                for unit in ServiceUnit
            )
        )

    @staticmethod
    def mixer() -> MixerSnapshot:
        return MixerSnapshot(
            plexamp_output=94,
            airplay_output=100,
            music_master=100,
            maximum_alarm_volume=100,
        )

    @staticmethod
    def loopback() -> LoopbackSnapshot:
        return LoopbackSnapshot(contract=LOOPBACK_CONTRACT, loaded=True)

    @staticmethod
    def dac(*, pid: int = 2180045, user: str = "andy") -> DacSnapshot:
        return DacSnapshot(
            contract=DAC_CONTRACT,
            owners=(
                DacOwner(
                    pid=pid,
                    user=user,
                    command="node",
                    access="read-write",
                ),
            ),
            released=False,
        )

    def report(self, *, pid: int = 2180045) -> ProductionPrepareOnlyReportV7:
        package = PackageFingerprint(ACCEPTED_PACKAGE_FINGERPRINT)
        return ProductionPrepareOnlyReportV7(
            status=AdapterStatus.PASS,
            disposition=ProductionPrepareOnlyDispositionV7.BASELINE_READY,
            detail="fixed untouched-appliance baseline is ready for human review only",
            candidate_package=package,
            host_contract=AdapterResult(
                operation=AdapterOperation.INSPECT_HOST_CONTRACT,
                status=AdapterStatus.PASS,
                detail="host contract",
                payload=HostContractSnapshot(
                    service_units=tuple(ServiceUnit),
                    mixer_controls=tuple(MixerControl),
                    loopback=LOOPBACK_CONTRACT,
                    dac=DAC_CONTRACT,
                ),
            ),
            production_lock=AdapterResult(
                operation=AdapterOperation.INSPECT_PRODUCTION_LOCK,
                status=AdapterStatus.PASS,
                detail="lock absent",
                payload=ProductionLockObservation(
                    path=PRODUCTION_LOCK_PATH,
                    exists=False,
                    held_by_caller=False,
                    owner_uid=None,
                    owner_gid=None,
                    mode=None,
                ),
            ),
            services=AdapterResult(
                operation=AdapterOperation.CAPTURE_SERVICE_STATE,
                status=AdapterStatus.PASS,
                detail="services",
                payload=self.services(),
            ),
            mixer=AdapterResult(
                operation=AdapterOperation.CAPTURE_MIXER_STATE,
                status=AdapterStatus.PASS,
                detail="mixer",
                payload=self.mixer(),
            ),
            loopback=AdapterResult(
                operation=AdapterOperation.CAPTURE_LOOPBACK_STATE,
                status=AdapterStatus.PASS,
                detail="loopback",
                payload=self.loopback(),
            ),
            dac=AdapterResult(
                operation=AdapterOperation.CAPTURE_DAC_STATE,
                status=AdapterStatus.PASS,
                detail="DAC",
                payload=self.dac(pid=pid),
            ),
            approval=ProductionApprovalBaselineObservationV7(
                state=ProductionApprovalBaselineStateV7.ABSENT,
                detail="approval absent",
            ),
        )

    def test_exact_accepted_package_identity(self) -> None:
        self.assertEqual(EXPECTED_FILES, 28)
        self.assertEqual(len(RUNTIME_MODULES), 15)
        self.assertEqual(PACKAGE_PHASE, "stage-c21-activation-capable-review-v2")
        self.assertEqual(
            ACCEPTED_PACKAGE_FINGERPRINT,
            "dd4e8da82a3eb8f309b8e68c848652d806ca25ff9c0a7a3f16947e851486c2b5",
        )

    def test_exact_accepted_evidence_hashes(self) -> None:
        self.assertEqual(
            BASELINE_REPORT_TEXT_SHA256,
            "350ae99ee63911cb524f7220e4629e5da669f3c79f8e409d2f9fdf4652c16a85",
        )
        self.assertEqual(
            BASELINE_REPORT_JSON_SHA256,
            "3c6dcd3c17a3ce363ddf3f5bdd9d93c8891a2a006c0c154905a3a809b79348e0",
        )
        self.assertEqual(
            BASELINE_MANIFEST_JSON_SHA256,
            "4995bdf85cb06995a9b26c164fdc28991d755631e9c4dbe527eddc005253c1dc",
        )

    def test_snapshot_accepts_exact_target_state(self) -> None:
        validate_snapshot_payloads_against_accepted_v7(
            self.services(),
            self.mixer(),
            self.loopback(),
            self.dac(),
        )

    def test_snapshot_accepts_changed_pid_with_same_owner_contract(self) -> None:
        validate_snapshot_payloads_against_accepted_v7(
            self.services(),
            self.mixer(),
            self.loopback(),
            self.dac(pid=999999),
        )

    def test_snapshot_rejects_wrong_dac_owner(self) -> None:
        with self.assertRaisesRegex(
            CurrentPackageContractErrorV7,
            "DAC ownership",
        ):
            validate_snapshot_payloads_against_accepted_v7(
                self.services(),
                self.mixer(),
                self.loopback(),
                self.dac(user="root"),
            )

    def test_snapshot_rejects_mixer_drift(self) -> None:
        with self.assertRaisesRegex(
            CurrentPackageContractErrorV7,
            "mixer snapshot",
        ):
            validate_snapshot_payloads_against_accepted_v7(
                self.services(),
                MixerSnapshot(
                    plexamp_output=93,
                    airplay_output=100,
                    music_master=100,
                    maximum_alarm_volume=100,
                ),
                self.loopback(),
                self.dac(),
            )

    def test_prepare_only_report_accepts_pid_flexibility(self) -> None:
        validate_prepare_only_report_against_accepted_v7(
            self.report(pid=7654321),
            PackageFingerprint(ACCEPTED_PACKAGE_FINGERPRINT),
        )

    def test_prepare_only_report_rejects_wrong_package(self) -> None:
        with self.assertRaisesRegex(
            CurrentPackageContractErrorV7,
            "wrong package",
        ):
            validate_prepare_only_report_against_accepted_v7(
                self.report(),
                PackageFingerprint("a" * 64),
            )

    def test_corrected_parent_contract_is_exact(self) -> None:
        self.assertEqual(
            CURRENT_PARENT_CONTRACT,
            (
                (Path("/var/lib/a-clockwork-plex"), 0o750),
                (Path("/var/lib/a-clockwork-plex/split-bus"), 0o755),
                (
                    Path("/var/lib/a-clockwork-plex/split-bus/transactions"),
                    0o700,
                ),
            ),
        )
        self.assertTrue(CURRENT_TRANSACTION_PREFIX.startswith("stage-c21-"))
        self.assertTrue(CURRENT_SNAPSHOT_PREFIX.startswith("stage-c21-"))

    def test_staged_contract_replay_is_candidate_root_bound(self) -> None:
        self.assertIn('"candidate_root": self._candidate_root', self.adapter_source)
        self.assertIn(
            'candidate = paths["candidate_root"] / row["path"].lstrip("/")',
            self.adapter_source,
        )
        self.assertNotIn('parents[3] / row["path"]', self.adapter_source)

    def test_current_unit_contract_replaces_obsolete_stage_c1_actions(self) -> None:
        for action in (
            "boot-prepare",
            "supervise",
            "emergency-direct-failback",
        ):
            self.assertIn(action, self.adapter_source)
        self.assertNotIn("stage-c1-candidate-only", self.adapter_source)
        self.assertNotIn("return 78", self.adapter_source)

    def test_current_runtime_and_sudoers_boundary_is_fixed(self) -> None:
        self.assertIn("RUNTIME_MODULES", self.adapter_source)
        self.assertIn("recording_runtime_adapter.py", self.adapter_source)
        self.assertIn("status", self.adapter_source)
        self.assertIn("validate-runtime", self.adapter_source)
        self.assertIn("approval_operations_exposed", self.adapter_source)

    def test_all_four_approval_operations_remain_blocked(self) -> None:
        rows = prove_approval_operations_blocked(
            SimpleNamespace(),
            TransactionIdentity("stage-c21-test-transaction"),
        )
        self.assertEqual(len(rows), 4)
        self.assertEqual(
            {row[0] for row in rows},
            {operation.value for operation in ActivationApprovalLifecycleOperation},
        )
        self.assertTrue(all(row[1:] == ("blocked", "not-exposed-by-rehearsal") for row in rows))

    def test_rehearsal_check_order_covers_abort_and_approval_boundary(self) -> None:
        self.assertEqual(len(EXPECTED_CHECKS), 32)
        self.assertLess(
            EXPECTED_CHECKS.index("approval-operation-boundary"),
            EXPECTED_CHECKS.index("transaction-abort-v2"),
        )
        self.assertLess(
            EXPECTED_CHECKS.index("transaction-abort-v2"),
            EXPECTED_CHECKS.index("production-lock-released"),
        )

    def test_fixed_path_prefixes_and_confirmation(self) -> None:
        self.assertEqual(
            REQUIRED_CONFIRMATION,
            "STAGE-C21-CURRENT-PACKAGE-STAGE-VALIDATE-ABORT",
        )
        self.assertEqual(
            PACKAGE_PREFIX,
            "a-clockwork-plex-stage-c21-activation-package-v2.",
        )
        self.assertEqual(
            BASELINE_PREFIX,
            "a-clockwork-plex-stage-c21-production-baseline.",
        )
        self.assertEqual(
            EVIDENCE_PREFIX,
            "a-clockwork-plex-stage-c21-current-package-preparation.",
        )

    def test_wrapper_defaults_to_prepare_only(self) -> None:
        self.assertIn('MODE="prepare"', self.wrapper_source)
        self.assertIn("Prepare-only invoked no sudo", self.wrapper_source)
        self.assertIn("--rehearse-current-package", self.wrapper_source)
        self.assertEqual(self.wrapper_source.count("exec sudo env"), 1)

    def test_wrapper_has_no_install_activation_or_authority_selector(self) -> None:
        forbidden = (
            "--install",
            "--activate",
            "--service",
            "--route",
            "--mixer",
            "--approval",
            "--transaction-id",
            "--lock-path",
            "--command",
        )
        for option in forbidden:
            self.assertNotIn(option, self.wrapper_source)

    def test_no_master_eq_installer_reference(self) -> None:
        combined = "\n".join(
            (
                self.adapter_source,
                self.contract_source,
                self.rehearsal_source,
                self.wrapper_source,
            )
        )
        self.assertNotIn("install-master-eq.sh", combined)

    def test_new_python_modules_parse(self) -> None:
        ast.parse(self.adapter_source)
        ast.parse(self.contract_source)
        ast.parse(self.rehearsal_source)

    def test_rehearsal_contains_no_direct_mutation_commands(self) -> None:
        forbidden = (
            "systemctl stop",
            "systemctl start",
            "systemctl restart",
            "systemctl enable",
            "systemctl disable",
            "systemctl daemon-reload",
            "amixer set",
            "modprobe",
            "aplay -D",
        )
        for command in forbidden:
            self.assertNotIn(command, self.rehearsal_source)


if __name__ == "__main__":
    unittest.main()
