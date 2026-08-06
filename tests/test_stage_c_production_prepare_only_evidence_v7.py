from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
MODULE_PATH = (
    ROOT
    / "scripts/stage_c_transaction/production_prepare_only_evidence_v7.py"
)
WRAPPER_PATH = ROOT / "scripts/prepare-stage-c21-production-baseline.sh"

from scripts.stage_c_transaction import (  # noqa: E402
    production_prepare_only_evidence_v7 as evidence_module,
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
    ALL_OPERATIONS_V7,
    ActivationApprovalLifecycleOperation,
    BlockedProductionAdapterV7,
    ProductionActivationApprovalAdapterBlocked,
)
from scripts.stage_c_transaction.production_prepare_only_evidence_v7 import (  # noqa: E402
    FILE_MODE,
    MANIFEST_JSON_NAME,
    MANIFEST_SCHEMA,
    REPORT_JSON_NAME,
    REPORT_SCHEMA,
    REPORT_TEXT_NAME,
    REVIEW_PREFIX,
    ROOT_MODE,
    ProductionPrepareOnlyEvidenceBundleV7,
    ProductionPrepareOnlyEvidenceErrorV7,
    PublishedEvidenceFileV7,
    production_prepare_only_report_json_v7,
    production_prepare_only_report_payload_v7,
    production_prepare_only_report_text_v7,
    publish_production_prepare_only_evidence_v7,
)
from scripts.stage_c_transaction.production_prepare_only_inspector_v7 import (  # noqa: E402
    ProductionApprovalBaselineObservationV7,
    ProductionApprovalBaselineStateV7,
    ProductionPrepareOnlyDispositionV7,
    ProductionPrepareOnlyReportV7,
)


HASH_A = "a" * 64
HASH_B = "b" * 64


class StageCProductionPrepareOnlyEvidenceV7Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = MODULE_PATH.read_text(encoding="utf-8")
        self.wrapper = WRAPPER_PATH.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    def _host_contract(self, status: AdapterStatus = AdapterStatus.PASS):
        return AdapterResult(
            operation=AdapterOperation.INSPECT_HOST_CONTRACT,
            status=status,
            detail="host contract observation",
            payload=(
                HostContractSnapshot(
                    service_units=tuple(ServiceUnit),
                    mixer_controls=tuple(MixerControl),
                    loopback=LOOPBACK_CONTRACT,
                    dac=DAC_CONTRACT,
                )
                if status is AdapterStatus.PASS
                else None
            ),
            evidence=(("alsa_sha256", HASH_B),),
        )

    def _lock(self):
        return AdapterResult(
            operation=AdapterOperation.INSPECT_PRODUCTION_LOCK,
            status=AdapterStatus.PASS,
            detail="production lock absent",
            payload=ProductionLockObservation(
                path=PRODUCTION_LOCK_PATH,
                exists=False,
                held_by_caller=False,
                owner_uid=None,
                owner_gid=None,
                mode=None,
            ),
        )

    def _services(self):
        application_units = {
            ServiceUnit.PLEXAMP,
            ServiceUnit.SHAIRPORT_SYNC,
            ServiceUnit.DASHBOARD,
        }
        return AdapterResult(
            operation=AdapterOperation.CAPTURE_SERVICE_STATE,
            status=AdapterStatus.PASS,
            detail="service observation",
            payload=ServiceSnapshot(
                tuple(
                    ServiceState(
                        unit=unit,
                        load=(
                            ServiceLoadState.LOADED
                            if unit in application_units
                            else ServiceLoadState.NOT_FOUND
                        ),
                        active=(
                            ServiceActiveState.ACTIVE
                            if unit in application_units
                            else ServiceActiveState.INACTIVE
                        ),
                        enabled=(
                            ServiceEnableState.ENABLED
                            if unit in application_units
                            else ServiceEnableState.NOT_FOUND
                        ),
                    )
                    for unit in ServiceUnit
                )
            ),
        )

    def _mixer(self):
        return AdapterResult(
            operation=AdapterOperation.CAPTURE_MIXER_STATE,
            status=AdapterStatus.PASS,
            detail="mixer observation",
            payload=MixerSnapshot(
                plexamp_output=75,
                airplay_output=76,
                music_master=80,
                maximum_alarm_volume=70,
            ),
        )

    def _loopback(self):
        return AdapterResult(
            operation=AdapterOperation.CAPTURE_LOOPBACK_STATE,
            status=AdapterStatus.PASS,
            detail="loopback observation",
            payload=LoopbackSnapshot(contract=LOOPBACK_CONTRACT, loaded=False),
        )

    def _dac(self):
        return AdapterResult(
            operation=AdapterOperation.CAPTURE_DAC_STATE,
            status=AdapterStatus.PASS,
            detail="DAC observation",
            payload=DacSnapshot(
                contract=DAC_CONTRACT,
                owners=(
                    DacOwner(
                        pid=1234,
                        user="andy",
                        command="plexamp",
                        access="playback",
                    ),
                ),
                released=False,
            ),
        )

    def _report(self, *, failed: bool = False) -> ProductionPrepareOnlyReportV7:
        return ProductionPrepareOnlyReportV7(
            status=AdapterStatus.FAIL if failed else AdapterStatus.PASS,
            disposition=(
                ProductionPrepareOnlyDispositionV7.HOST_OBSERVATION_FAILED
                if failed
                else ProductionPrepareOnlyDispositionV7.BASELINE_READY
            ),
            detail=(
                "one or more fixed host observations failed"
                if failed
                else "fixed production baseline is ready for human review"
            ),
            candidate_package=PackageFingerprint(HASH_A),
            host_contract=self._host_contract(
                AdapterStatus.FAIL if failed else AdapterStatus.PASS
            ),
            production_lock=self._lock(),
            services=self._services(),
            mixer=self._mixer(),
            loopback=self._loopback(),
            dac=self._dac(),
            approval=ProductionApprovalBaselineObservationV7(
                state=ProductionApprovalBaselineStateV7.ABSENT,
                detail="production approval is absent",
            ),
        )

    def test_json_and_text_are_deterministic_explicit_and_non_authoritative(self) -> None:
        report = self._report()
        first_json = production_prepare_only_report_json_v7(report)
        second_json = production_prepare_only_report_json_v7(report)
        first_text = production_prepare_only_report_text_v7(report)
        second_text = production_prepare_only_report_text_v7(report)
        self.assertEqual(first_json, second_json)
        self.assertEqual(first_text, second_text)
        self.assertTrue(first_json.endswith(b"\n"))
        self.assertFalse(first_json.endswith(b"\n\n"))
        self.assertTrue(first_text.endswith(b"\n"))
        self.assertFalse(first_text.endswith(b"\n\n"))

        payload = json.loads(first_json)
        self.assertEqual(payload, production_prepare_only_report_payload_v7(report))
        self.assertEqual(payload["schema"], REPORT_SCHEMA)
        self.assertEqual(payload["disposition"], "baseline-ready")
        self.assertEqual(payload["candidate_package"]["sha256"], HASH_A)
        self.assertEqual(
            payload["observations"]["host_contract"]["payload"]["service_units"],
            [unit.value for unit in ServiceUnit],
        )
        self.assertEqual(
            payload["observations"]["services"]["payload"]["services"][0]["unit"],
            ServiceUnit.PLEXAMP.value,
        )
        self.assertEqual(
            payload["observations"]["mixer"]["payload"]["music_master"],
            80,
        )
        self.assertEqual(
            payload["observations"]["loopback"]["payload"]["contract"]["card_index"],
            7,
        )
        self.assertEqual(
            payload["observations"]["dac"]["payload"]["owners"][0]["pid"],
            1234,
        )
        self.assertEqual(
            payload["observations"]["approval"]["state"],
            "absent",
        )
        self.assertTrue(all(value is False for value in payload["authority"].values()))

        text = first_text.decode("utf-8")
        self.assertIn("REVIEW ONLY — NO INSTALLATION OR ACTIVATION AUTHORITY", text)
        self.assertIn("Music Master: 80", text)
        self.assertIn("Maximum Alarm Volume: 70", text)
        self.assertIn("State: absent", text)
        self.assertNotIn("--activate", text)
        self.assertNotIn("sudo ", text)
        self.assertNotIn("systemctl ", text)

    def test_complete_bundle_has_fixed_scope_modes_hashes_and_manifest(self) -> None:
        report = self._report()
        with tempfile.TemporaryDirectory() as parent:
            with patch.object(evidence_module, "REVIEW_PARENT", parent):
                bundle = publish_production_prepare_only_evidence_v7(report)
            root = Path(bundle.root)
            self.assertEqual(root.parent, Path(parent))
            self.assertTrue(root.name.startswith(REVIEW_PREFIX))
            root_info = root.lstat()
            self.assertTrue(stat.S_ISDIR(root_info.st_mode))
            self.assertEqual(stat.S_IMODE(root_info.st_mode), ROOT_MODE)
            self.assertEqual(root_info.st_uid, os.geteuid())
            self.assertEqual(root_info.st_gid, os.getegid())
            self.assertEqual(
                {path.name for path in root.iterdir()},
                {REPORT_JSON_NAME, REPORT_TEXT_NAME, MANIFEST_JSON_NAME},
            )
            for item in (bundle.report_json, bundle.report_text, bundle.manifest_json):
                info = Path(item.path).lstat()
                content = Path(item.path).read_bytes()
                self.assertTrue(stat.S_ISREG(info.st_mode))
                self.assertEqual(stat.S_IMODE(info.st_mode), FILE_MODE)
                self.assertEqual(info.st_uid, os.geteuid())
                self.assertEqual(info.st_gid, os.getegid())
                self.assertEqual(info.st_nlink, 1)
                self.assertEqual(item.byte_length, len(content))
                self.assertEqual(item.sha256, hashlib.sha256(content).hexdigest())

            manifest = json.loads(Path(bundle.manifest_json.path).read_bytes())
            self.assertEqual(manifest["schema"], MANIFEST_SCHEMA)
            self.assertTrue(manifest["complete"])
            self.assertEqual(manifest["disposition"], "baseline-ready")
            self.assertEqual(manifest["candidate_package_sha256"], HASH_A)
            self.assertEqual(
                manifest["files"][REPORT_JSON_NAME]["sha256"],
                bundle.report_json.sha256,
            )
            self.assertEqual(
                manifest["files"][REPORT_TEXT_NAME]["sha256"],
                bundle.report_text.sha256,
            )
            self.assertTrue(
                all(value is False for value in manifest["authority"].values())
            )
            self.assertTrue(bundle.complete)
            self.assertFalse(bundle.production_mutation_authorised)
            self.assertFalse(bundle.activation_authorised)
            self.assertFalse(bundle.pi_execution_authorised)
            self.assertFalse(bundle.production_lock_acquired)
            self.assertFalse(bundle.transaction_created)

    def test_blocking_report_is_still_persisted_without_becoming_ready(self) -> None:
        report = self._report(failed=True)
        with tempfile.TemporaryDirectory() as parent:
            with patch.object(evidence_module, "REVIEW_PARENT", parent):
                bundle = publish_production_prepare_only_evidence_v7(report)
            payload = json.loads(Path(bundle.report_json.path).read_bytes())
            manifest = json.loads(Path(bundle.manifest_json.path).read_bytes())
            self.assertEqual(bundle.disposition, report.disposition)
            self.assertEqual(payload["status"], "fail")
            self.assertEqual(payload["disposition"], "host-observation-failed")
            self.assertEqual(manifest["disposition"], "host-observation-failed")
            self.assertFalse(report.ready_for_human_review)

    def test_failed_publication_retains_incomplete_root_without_manifest(self) -> None:
        report = self._report()
        original = evidence_module._publish_file
        names: list[str] = []

        def fail_on_text(**kwargs):
            names.append(kwargs["name"])
            if kwargs["name"] == REPORT_TEXT_NAME:
                raise OSError("injected text publication failure")
            return original(**kwargs)

        with tempfile.TemporaryDirectory() as parent:
            with patch.object(evidence_module, "REVIEW_PARENT", parent), patch.object(
                evidence_module, "_publish_file", side_effect=fail_on_text
            ):
                with self.assertRaises(ProductionPrepareOnlyEvidenceErrorV7) as caught:
                    publish_production_prepare_only_evidence_v7(report)
            self.assertEqual(names, [REPORT_JSON_NAME, REPORT_TEXT_NAME])
            retained = Path(str(caught.exception).split(" retained at ", 1)[1].split(": ", 1)[0])
            self.assertTrue(retained.is_dir())
            self.assertTrue((retained / REPORT_JSON_NAME).is_file())
            self.assertFalse((retained / REPORT_TEXT_NAME).exists())
            self.assertFalse((retained / MANIFEST_JSON_NAME).exists())

    def test_exclusive_creation_never_overwrites_existing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / f"{REVIEW_PREFIX}exclusive"
            root.mkdir(mode=ROOT_MODE)
            os.chmod(root, ROOT_MODE)
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
            directory_fd = os.open(root, flags)
            try:
                identity = evidence_module._root_identity(str(root), directory_fd)
                first = evidence_module._publish_file(
                    root=str(root),
                    directory_fd=directory_fd,
                    root_identity=identity,
                    name=REPORT_JSON_NAME,
                    content=b"first\n",
                )
                with self.assertRaises(FileExistsError):
                    evidence_module._publish_file(
                        root=str(root),
                        directory_fd=directory_fd,
                        root_identity=identity,
                        name=REPORT_JSON_NAME,
                        content=b"second\n",
                    )
            finally:
                os.close(directory_fd)
            self.assertEqual(Path(first.path).read_bytes(), b"first\n")

    def test_result_records_reject_wrong_scope_names_digests_and_authority(self) -> None:
        valid_file = PublishedEvidenceFileV7(
            name=REPORT_JSON_NAME,
            path=f"/var/tmp/{REVIEW_PREFIX}fixed/{REPORT_JSON_NAME}",
            sha256=HASH_A,
            byte_length=1,
        )
        with self.assertRaises(ValueError):
            PublishedEvidenceFileV7(
                name="other.json",
                path="/var/tmp/other.json",
                sha256=HASH_A,
                byte_length=1,
            )
        with self.assertRaises(ValueError):
            PublishedEvidenceFileV7(
                name=REPORT_JSON_NAME,
                path=f"/var/tmp/{REVIEW_PREFIX}fixed/{REPORT_JSON_NAME}",
                sha256="bad",
                byte_length=1,
            )
        with self.assertRaises(ValueError):
            ProductionPrepareOnlyEvidenceBundleV7(
                root=f"/var/tmp/{REVIEW_PREFIX}fixed",
                disposition=ProductionPrepareOnlyDispositionV7.BASELINE_READY,
                candidate_package=PackageFingerprint(HASH_A),
                report_json=valid_file,
                report_text=PublishedEvidenceFileV7(
                    name=REPORT_TEXT_NAME,
                    path=f"/var/tmp/{REVIEW_PREFIX}fixed/{REPORT_TEXT_NAME}",
                    sha256=HASH_A,
                    byte_length=1,
                ),
                manifest_json=PublishedEvidenceFileV7(
                    name=MANIFEST_JSON_NAME,
                    path=f"/var/tmp/{REVIEW_PREFIX}fixed/{MANIFEST_JSON_NAME}",
                    sha256=HASH_A,
                    byte_length=1,
                ),
                activation_authorised=True,
            )

    def test_cli_returns_zero_only_for_exact_baseline_ready(self) -> None:
        ready = self._report()
        blocked = self._report(failed=True)
        ready_bundle = SimpleNamespace(root="/var/tmp/ready")
        blocked_bundle = SimpleNamespace(root="/var/tmp/blocked")
        with patch.object(evidence_module.os, "geteuid", return_value=1000), patch.object(
            evidence_module,
            "run_production_prepare_only_evidence_v7",
            return_value=(ready, ready_bundle),
        ):
            self.assertEqual(evidence_module.main(["--package-fingerprint", HASH_A]), 0)
        with patch.object(evidence_module.os, "geteuid", return_value=1000), patch.object(
            evidence_module,
            "run_production_prepare_only_evidence_v7",
            return_value=(blocked, blocked_bundle),
        ):
            self.assertEqual(evidence_module.main(["--package-fingerprint", HASH_A]), 1)
        with patch.object(evidence_module.os, "geteuid", return_value=0):
            with self.assertRaises(SystemExit):
                evidence_module.main(["--package-fingerprint", HASH_A])
        with self.assertRaises(SystemExit):
            evidence_module.parse_args(["--output", "/tmp/escape"])
        with self.assertRaises(ValueError):
            evidence_module.run_production_prepare_only_evidence_v7("bad")

    def test_wrapper_is_fixed_unprivileged_and_has_valid_shell_syntax(self) -> None:
        syntax = subprocess.run(
            ["bash", "-n", str(WRAPPER_PATH)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        self.assertIn("--package-fingerprint", self.wrapper)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", self.wrapper)
        self.assertIn(
            "stage_c_transaction.production_prepare_only_evidence_v7",
            self.wrapper,
        )
        self.assertNotIn("exec sudo", self.wrapper)
        self.assertNotIn("sudo env", self.wrapper)
        self.assertNotIn("--activate", self.wrapper)
        self.assertNotIn("--confirm", self.wrapper)
        self.assertNotIn("--output", self.wrapper)
        self.assertNotIn("--package-root", self.wrapper)
        self.assertNotIn("--binary", self.wrapper)
        self.assertNotIn("install-master-eq.sh", self.wrapper)

    def test_source_scope_is_evidence_only_and_production_remains_blocked(self) -> None:
        imports = {
            node.names[0].name.split(".")[0]
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Import)
        }
        imports.update(
            node.module.split(".")[0]
            for node in ast.walk(self.tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        self.assertFalse(
            imports.intersection(
                {"ctypes", "fcntl", "requests", "socket", "subprocess"}
            )
        )
        called_attributes = {
            node.func.attr
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertFalse(
            called_attributes.intersection(
                {
                    "unlink",
                    "remove",
                    "rmdir",
                    "rename",
                    "replace",
                    "symlink",
                    "link",
                    "truncate",
                    "system",
                    "popen",
                }
            )
        )
        self.assertIn("os.O_EXCL", self.source)
        self.assertIn("os.O_NOFOLLOW", self.source)
        self.assertIn("os.O_CLOEXEC", self.source)
        self.assertIn("os.fsync(file_fd)", self.source)
        self.assertIn("os.fsync(directory_fd)", self.source)
        self.assertNotIn("install-master-eq.sh", self.source)
        for forbidden in (
            "acquire_production_lock(",
            "release_production_lock(",
            "create_authoritative_transaction(",
            "publish_temporary_activation_approval(",
            "remove_temporary_activation_approval(",
            "promote_committed_activation_approval(",
            "start_managed_stage_c_services(",
            "select_split_bus_route(",
            "select_direct_failback_route(",
        ):
            self.assertNotIn(forbidden, self.source)

        self.assertEqual(len(ALL_OPERATIONS_V7), 42)
        adapter = BlockedProductionAdapterV7()
        transaction = TransactionIdentity("transaction")
        methods = (
            adapter.bind_production_lock_lease,
            adapter.publish_temporary_activation_approval,
            adapter.remove_temporary_activation_approval,
            adapter.promote_committed_activation_approval,
        )
        for method, operation in zip(
            methods, tuple(ActivationApprovalLifecycleOperation), strict=True
        ):
            with self.assertRaises(ProductionActivationApprovalAdapterBlocked) as caught:
                method(transaction)
            self.assertIs(caught.exception.operation, operation)


if __name__ == "__main__":
    unittest.main()
