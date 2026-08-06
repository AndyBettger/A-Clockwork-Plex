from __future__ import annotations

import ast
import hashlib
import json
import os
import stat
import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
MODULE_PATH = (
    ROOT
    / "scripts/stage_c_transaction/production_prepare_only_inspector_v7.py"
)

from scripts.stage_c_runtime_authority.model import (  # noqa: E402
    ActivationApprovalRecord,
    HardwareContract,
    canonical_json_bytes,
)
from scripts.stage_c_transaction import (  # noqa: E402
    production_prepare_only_inspector_v7 as inspector_module,
)
from scripts.stage_c_transaction.production_adapter_contract import (  # noqa: E402
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    DAC_CONTRACT,
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
)
from scripts.stage_c_transaction.production_adapter_lifecycle_v7 import (  # noqa: E402
    ALL_OPERATIONS_V7,
    BlockedProductionAdapterV7,
    ProductionActivationApprovalAdapterBlocked,
)
from scripts.stage_c_transaction.production_prepare_only_inspector_v7 import (  # noqa: E402
    APPROVAL_MODE,
    MAX_APPROVAL_BYTES,
    ProductionApprovalBaselineObservationV7,
    ProductionApprovalBaselineStateV7,
    ProductionPrepareOnlyDispositionV7,
    ProductionPrepareOnlyInspectorV7,
    ProductionPrepareOnlyReportV7,
    classify_production_approval_bytes_v7,
)
from scripts.stage_c_transaction.read_only_host_adapter import (  # noqa: E402
    ReadOnlyHostProductionAdapter,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
HASH_E = "e" * 64
HASH_F = "f" * 64


class StageCProductionPrepareOnlyInspectorV7Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = MODULE_PATH.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)
        self.package = PackageFingerprint(HASH_A)

    def _host_contract(self, *, status: AdapterStatus = AdapterStatus.PASS):
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
        )

    def _lock(
        self,
        *,
        present: bool = False,
        status: AdapterStatus = AdapterStatus.PASS,
    ):
        return AdapterResult(
            operation=AdapterOperation.INSPECT_PRODUCTION_LOCK,
            status=status,
            detail="production lock observation",
            payload=(
                ProductionLockObservation(
                    path=PRODUCTION_LOCK_PATH,
                    exists=present,
                    held_by_caller=False,
                    owner_uid=0 if present else None,
                    owner_gid=0 if present else None,
                    mode=0o600 if present else None,
                )
                if status is AdapterStatus.PASS
                else None
            ),
        )

    def _services(self, *, status: AdapterStatus = AdapterStatus.PASS):
        application_units = {
            ServiceUnit.PLEXAMP,
            ServiceUnit.SHAIRPORT_SYNC,
            ServiceUnit.DASHBOARD,
        }
        states = tuple(
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
        return AdapterResult(
            operation=AdapterOperation.CAPTURE_SERVICE_STATE,
            status=status,
            detail="service observation",
            payload=ServiceSnapshot(states) if status is AdapterStatus.PASS else None,
        )

    def _mixer(self, *, status: AdapterStatus = AdapterStatus.PASS):
        return AdapterResult(
            operation=AdapterOperation.CAPTURE_MIXER_STATE,
            status=status,
            detail="mixer observation",
            payload=(
                MixerSnapshot(
                    plexamp_output=75,
                    airplay_output=75,
                    music_master=80,
                    maximum_alarm_volume=70,
                )
                if status is AdapterStatus.PASS
                else None
            ),
        )

    def _loopback(self, *, status: AdapterStatus = AdapterStatus.PASS):
        return AdapterResult(
            operation=AdapterOperation.CAPTURE_LOOPBACK_STATE,
            status=status,
            detail="loopback observation",
            payload=(
                LoopbackSnapshot(contract=LOOPBACK_CONTRACT, loaded=False)
                if status is AdapterStatus.PASS
                else None
            ),
        )

    def _dac(self, *, status: AdapterStatus = AdapterStatus.PASS):
        return AdapterResult(
            operation=AdapterOperation.CAPTURE_DAC_STATE,
            status=status,
            detail="DAC observation",
            payload=(
                DacSnapshot(contract=DAC_CONTRACT, owners=(), released=True)
                if status is AdapterStatus.PASS
                else None
            ),
        )

    def _absent_approval(self):
        return ProductionApprovalBaselineObservationV7(
            state=ProductionApprovalBaselineStateV7.ABSENT,
            detail="approval absent",
        )

    def _failed_approval(self):
        return ProductionApprovalBaselineObservationV7(
            state=ProductionApprovalBaselineStateV7.OBSERVATION_FAILURE,
            detail="approval unavailable",
        )

    def _mismatched_approval(self):
        info = self._file_info(4)
        return ProductionApprovalBaselineObservationV7(
            state=ProductionApprovalBaselineStateV7.MISMATCHED,
            detail="approval mismatch",
            raw_sha256=HASH_B,
            device=info.st_dev,
            inode=info.st_ino,
            mode=stat.S_IMODE(info.st_mode),
            owner_uid=info.st_uid,
            owner_gid=info.st_gid,
            link_count=info.st_nlink,
            size=info.st_size,
        )

    def _patch_adapter(
        self,
        adapter: ReadOnlyHostProductionAdapter,
        *,
        host=None,
        lock=None,
        services=None,
        mixer=None,
        loopback=None,
        dac=None,
    ):
        mocks = {
            "host": Mock(return_value=host or self._host_contract()),
            "lock": Mock(return_value=lock or self._lock()),
            "services": Mock(return_value=services or self._services()),
            "mixer": Mock(return_value=mixer or self._mixer()),
            "loopback": Mock(return_value=loopback or self._loopback()),
            "dac": Mock(return_value=dac or self._dac()),
        }
        patches = (
            patch.object(adapter, "inspect_host_contract", mocks["host"]),
            patch.object(adapter, "inspect_production_lock", mocks["lock"]),
            patch.object(adapter, "capture_service_state", mocks["services"]),
            patch.object(adapter, "capture_mixer_state", mocks["mixer"]),
            patch.object(adapter, "capture_loopback_state", mocks["loopback"]),
            patch.object(adapter, "capture_dac_state", mocks["dac"]),
        )
        return mocks, patches

    def _inspect(
        self,
        *,
        approval=None,
        host=None,
        lock=None,
        services=None,
        mixer=None,
        loopback=None,
        dac=None,
    ):
        adapter = ReadOnlyHostProductionAdapter()
        mocks, patches = self._patch_adapter(
            adapter,
            host=host,
            lock=lock,
            services=services,
            mixer=mixer,
            loopback=loopback,
            dac=dac,
        )
        for item in patches:
            item.start()
        try:
            with patch.object(
                inspector_module,
                "observe_production_approval_baseline_v7",
                return_value=approval or self._absent_approval(),
            ) as approval_mock:
                report = ProductionPrepareOnlyInspectorV7(
                    adapter,
                    self.package,
                ).inspect()
        finally:
            for item in reversed(patches):
                item.stop()
        return adapter, mocks, approval_mock, report

    def _assert_calls_once(self, adapter, mocks, approval_mock) -> None:
        mocks["host"].assert_called_once_with()
        mocks["lock"].assert_called_once_with()
        mocks["services"].assert_called_once_with(adapter.observation_transaction)
        mocks["mixer"].assert_called_once_with(adapter.observation_transaction)
        mocks["loopback"].assert_called_once_with(adapter.observation_transaction)
        mocks["dac"].assert_called_once_with(adapter.observation_transaction)
        approval_mock.assert_called_once_with()

    def test_exact_baseline_ready_report_is_read_only_and_preserves_results(self) -> None:
        adapter, mocks, approval_mock, report = self._inspect()
        self._assert_calls_once(adapter, mocks, approval_mock)
        self.assertIs(report.status, AdapterStatus.PASS)
        self.assertIs(
            report.disposition,
            ProductionPrepareOnlyDispositionV7.BASELINE_READY,
        )
        self.assertTrue(report.ready_for_human_review)
        self.assertIs(report.candidate_package, self.package)
        self.assertIs(report.host_contract, mocks["host"].return_value)
        self.assertIs(report.production_lock, mocks["lock"].return_value)
        self.assertIs(report.services, mocks["services"].return_value)
        self.assertIs(report.mixer, mocks["mixer"].return_value)
        self.assertIs(report.loopback, mocks["loopback"].return_value)
        self.assertIs(report.dac, mocks["dac"].return_value)
        for flag in (
            report.production_mutation_authorised,
            report.activation_authorised,
            report.pi_execution_authorised,
            report.review_bundle_persisted,
            report.production_lock_acquired,
            report.transaction_created,
        ):
            self.assertFalse(flag)

    def test_all_observations_are_attempted_once_when_one_raises(self) -> None:
        adapter = ReadOnlyHostProductionAdapter()
        mocks, patches = self._patch_adapter(adapter)
        mocks["host"].side_effect = RuntimeError("injected host exception")
        for item in patches:
            item.start()
        try:
            with patch.object(
                inspector_module,
                "observe_production_approval_baseline_v7",
                return_value=self._absent_approval(),
            ) as approval_mock:
                report = ProductionPrepareOnlyInspectorV7(
                    adapter,
                    self.package,
                ).inspect()
        finally:
            for item in reversed(patches):
                item.stop()
        self._assert_calls_once(adapter, mocks, approval_mock)
        self.assertIs(
            report.disposition,
            ProductionPrepareOnlyDispositionV7.HOST_OBSERVATION_FAILED,
        )
        self.assertIs(report.host_contract.status, AdapterStatus.FAIL)
        self.assertIs(
            report.host_contract.operation,
            AdapterOperation.INSPECT_HOST_CONTRACT,
        )
        self.assertIn("RuntimeError", report.host_contract.detail)

    def test_disposition_precedence_is_fail_closed(self) -> None:
        cases = (
            (
                "approval-unavailable",
                dict(
                    approval=self._failed_approval(),
                    lock=self._lock(present=True),
                    host=self._host_contract(status=AdapterStatus.FAIL),
                ),
                ProductionPrepareOnlyDispositionV7.APPROVAL_OBSERVATION_UNAVAILABLE,
            ),
            (
                "approval-present",
                dict(
                    approval=self._mismatched_approval(),
                    lock=self._lock(status=AdapterStatus.FAIL),
                ),
                ProductionPrepareOnlyDispositionV7.EXISTING_APPROVAL_REQUIRES_REVIEW,
            ),
            (
                "lock-observation-failed",
                dict(
                    lock=self._lock(status=AdapterStatus.FAIL),
                    host=self._host_contract(status=AdapterStatus.FAIL),
                ),
                ProductionPrepareOnlyDispositionV7.HOST_OBSERVATION_FAILED,
            ),
            (
                "lock-present",
                dict(
                    lock=self._lock(present=True),
                    host=self._host_contract(status=AdapterStatus.FAIL),
                ),
                ProductionPrepareOnlyDispositionV7.PRODUCTION_LOCK_PRESENT,
            ),
            (
                "other-host-failed",
                dict(mixer=self._mixer(status=AdapterStatus.FAIL)),
                ProductionPrepareOnlyDispositionV7.HOST_OBSERVATION_FAILED,
            ),
        )
        for label, kwargs, expected in cases:
            with self.subTest(label=label):
                _adapter, _mocks, _approval_mock, report = self._inspect(**kwargs)
                self.assertIs(report.status, AdapterStatus.FAIL)
                self.assertIs(report.disposition, expected)
                self.assertFalse(report.ready_for_human_review)

    def _contract(self) -> HardwareContract:
        return HardwareContract(
            package_fingerprint=HASH_A,
            split_route_sha256=HASH_B,
            direct_route_sha256=HASH_C,
            camilladsp_config_sha256=HASH_D,
            camilladsp_binary_version="4.1.3",
            camilladsp_binary_sha256=HASH_E,
            loopback_index=7,
            loopback_id="ACP_Loopback",
            loopback_pcm_substreams=2,
            loopback_pcm_notify=1,
            dac_card="Pro",
            dac_device=0,
            sample_rate=44100,
            sample_format="S16_LE",
            period_size=1024,
            buffer_size=8192,
        )

    def _record_bytes(self, record: ActivationApprovalRecord) -> bytes:
        return canonical_json_bytes(
            {
                "record": record.as_dict(),
                "record_sha256": record.record_sha256,
            }
        ) + b"\n"

    def _file_info(
        self,
        size: int,
        *,
        mode: int = APPROVAL_MODE,
        uid: int = 0,
        gid: int = 0,
        links: int = 1,
    ) -> os.stat_result:
        return os.stat_result(
            (
                stat.S_IFREG | mode,
                12345,
                678,
                links,
                uid,
                gid,
                size,
                0,
                0,
                0,
            )
        )

    def test_classifier_accepts_exact_temporary_and_committed_records(self) -> None:
        temporary = ActivationApprovalRecord.temporary(
            transaction_id="stage-c21-inspector-test",
            lock_lease_id="stage-c21-inspector-lease",
            contract=self._contract(),
            created_at="2026-08-06T01:30:00Z",
        )
        committed = temporary.promote(
            commit_manifest_sha256=HASH_F,
            committed_at="2026-08-06T01:31:00Z",
        )
        cases = (
            (
                temporary,
                ProductionApprovalBaselineStateV7.VALID_TEMPORARY_UNBOUND,
            ),
            (committed, ProductionApprovalBaselineStateV7.VALID_COMMITTED),
        )
        for record, expected in cases:
            with self.subTest(phase=record.phase.value):
                raw = self._record_bytes(record)
                observed = classify_production_approval_bytes_v7(
                    raw,
                    file_info=self._file_info(len(raw)),
                )
                self.assertIs(observed.state, expected)
                self.assertTrue(observed.present)
                self.assertTrue(observed.canonical_record)
                self.assertEqual(observed.transaction_id, record.transaction_id)
                self.assertEqual(observed.lock_lease_id, record.lock_lease_id)
                self.assertEqual(
                    observed.package_fingerprint,
                    record.package_fingerprint,
                )
                self.assertEqual(observed.record_sha256, record.record_sha256)
                self.assertEqual(
                    observed.raw_sha256,
                    hashlib.sha256(raw).hexdigest(),
                )

    def test_classifier_rejects_invalid_checksum_types_schema_and_encoding(self) -> None:
        temporary = ActivationApprovalRecord.temporary(
            transaction_id="stage-c21-inspector-test",
            lock_lease_id="stage-c21-inspector-lease",
            contract=self._contract(),
            created_at="2026-08-06T01:30:00Z",
        )
        canonical = self._record_bytes(temporary)
        envelope = json.loads(canonical)

        bad_checksum = dict(envelope)
        bad_checksum["record_sha256"] = HASH_F

        bad_type = json.loads(canonical)
        bad_type["record"]["loopback_index"] = True

        bad_schema = json.loads(canonical)
        bad_schema["record"]["schema_version"] = 2

        noncanonical = json.dumps(
            envelope,
            indent=2,
            sort_keys=False,
        ).encode() + b"\n"
        duplicate = (
            b'{"record":{},"record":{},"record_sha256":"'
            + HASH_A.encode()
            + b'"}\n'
        )
        variants = (
            b"not-json\n",
            canonical[:-1],
            canonical + b"\n",
            canonical.replace(b'"record":', b'"extra":0,"record":', 1),
            canonical_json_bytes(bad_checksum) + b"\n",
            canonical_json_bytes(bad_type) + b"\n",
            canonical_json_bytes(bad_schema) + b"\n",
            noncanonical,
            duplicate,
        )
        for index, raw in enumerate(variants):
            with self.subTest(index=index):
                observed = classify_production_approval_bytes_v7(
                    raw,
                    file_info=self._file_info(len(raw)),
                )
                self.assertIs(
                    observed.state,
                    ProductionApprovalBaselineStateV7.MISMATCHED,
                )
                self.assertTrue(observed.present)
                self.assertFalse(observed.canonical_record)
                self.assertIsNone(observed.record_sha256)

    def test_classifier_rejects_wrong_metadata_and_oversize(self) -> None:
        raw = b"{}\n"
        variants = (
            self._file_info(len(raw), mode=0o644),
            self._file_info(len(raw), uid=1000),
            self._file_info(len(raw), gid=1000),
            self._file_info(len(raw), links=2),
            self._file_info(MAX_APPROVAL_BYTES + 1),
        )
        for info in variants:
            with self.subTest(
                mode=stat.S_IMODE(info.st_mode),
                size=info.st_size,
            ):
                observed = classify_production_approval_bytes_v7(
                    raw,
                    file_info=info,
                )
                self.assertIs(
                    observed.state,
                    ProductionApprovalBaselineStateV7.MISMATCHED,
                )

    def test_constructor_and_frozen_result_invariants_fail_closed(self) -> None:
        class DerivedReadOnlyAdapter(ReadOnlyHostProductionAdapter):
            pass

        with self.assertRaises(TypeError):
            ProductionPrepareOnlyInspectorV7(DerivedReadOnlyAdapter(), self.package)
        with self.assertRaises(TypeError):
            ProductionPrepareOnlyInspectorV7(  # type: ignore[arg-type]
                ReadOnlyHostProductionAdapter(),
                HASH_A,
            )

        _adapter, _mocks, _approval_mock, report = self._inspect()
        with self.assertRaises(FrozenInstanceError):
            report.activation_authorised = True  # type: ignore[misc]
        with self.assertRaises(ValueError):
            ProductionPrepareOnlyReportV7(
                status=report.status,
                disposition=report.disposition,
                detail=report.detail,
                candidate_package=report.candidate_package,
                host_contract=report.host_contract,
                production_lock=report.production_lock,
                services=report.services,
                mixer=report.mixer,
                loopback=report.loopback,
                dac=report.dac,
                approval=report.approval,
                pi_execution_authorised=True,
            )
        with self.assertRaises(FrozenInstanceError):
            report.approval.detail = "changed"  # type: ignore[misc]

    def test_source_is_read_only_fixed_and_production_mutations_stay_blocked(self) -> None:
        imported_roots = {
            node.names[0].name.split(".")[0]
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Import) and node.names
        }
        imported_roots.update(
            (node.module or "").split(".")[0]
            for node in ast.walk(self.tree)
            if isinstance(node, ast.ImportFrom)
        )
        self.assertFalse(
            imported_roots.intersection(
                {"argparse", "ctypes", "fcntl", "subprocess", "socket"}
            )
        )

        forbidden_attributes = {
            "write",
            "pwrite",
            "truncate",
            "ftruncate",
            "fsync",
            "fdatasync",
            "mkdir",
            "makedirs",
            "unlink",
            "remove",
            "rename",
            "replace",
            "link",
            "symlink",
            "chmod",
            "fchmod",
            "chown",
            "fchown",
            "system",
            "execv",
            "execve",
            "spawnv",
            "Popen",
            "run",
        }
        used_attributes = {
            node.attr for node in ast.walk(self.tree) if isinstance(node, ast.Attribute)
        }
        self.assertFalse(used_attributes.intersection(forbidden_attributes))
        for token in ("O_CREAT", "O_WRONLY", "O_RDWR", "O_EXCL", "shell=True"):
            self.assertNotIn(token, self.source)
        functions = {
            node.name
            for node in ast.walk(self.tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertFalse(
            functions.intersection({"main", "dispatch", "execute", "activate"})
        )
        self.assertNotIn("__main__", self.source)
        self.assertNotIn("install-master-eq.sh", self.source)
        self.assertEqual(self.source.count("self._adapter.inspect_host_contract()"), 1)
        self.assertEqual(self.source.count("self._adapter.inspect_production_lock()"), 1)
        self.assertEqual(
            self.source.count("self._adapter.capture_service_state("),
            1,
        )
        self.assertEqual(
            self.source.count("self._adapter.capture_mixer_state("),
            1,
        )
        self.assertEqual(
            self.source.count("self._adapter.capture_loopback_state("),
            1,
        )
        self.assertEqual(self.source.count("self._adapter.capture_dac_state("), 1)

        self.assertEqual(len(ALL_OPERATIONS_V7), 42)
        blocked = BlockedProductionAdapterV7()
        transaction = ReadOnlyHostProductionAdapter().observation_transaction
        for method_name in (
            "bind_production_lock_lease",
            "publish_temporary_activation_approval",
            "remove_temporary_activation_approval",
            "promote_committed_activation_approval",
        ):
            with self.subTest(method=method_name), self.assertRaises(
                ProductionActivationApprovalAdapterBlocked
            ):
                getattr(blocked, method_name)(transaction)
