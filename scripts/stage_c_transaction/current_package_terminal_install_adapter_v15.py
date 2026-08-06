#!/usr/bin/python3
from __future__ import annotations

"""Guarded persistent Stage C EQ installation adapter.

This terminal layer extends the physically accepted C25 owner.  It keeps the
same fixed package, lock, transaction, snapshot, managed-file, daemon-reload and
atomic route-selection implementations, then supplies the reviewed activation
suffix: temporary transaction approval, managed runtime startup, finite lane
probes, application restoration and one atomic committed approval.

No caller-selectable path, unit, route, command or probe is exposed.
"""

import json
import os
import stat
import time
import wave
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from stage_c_runtime_authority.approval_store import ApprovalStore
from stage_c_runtime_authority.model import RuntimeAuthorityError, utc_timestamp

from .approval_authority_binding_v7 import (
    ApprovalAuthorityBindingV7,
    ApprovalHardwareContractV7,
    bind_approval_authority_v7,
)
from .approval_record_plan_v7 import (
    CommittedApprovalRecordPlanV7,
    TemporaryApprovalRecordPlanV7,
    plan_committed_approval_v7,
    plan_temporary_approval_v7,
)
from .authoritative_snapshot_rehearsal_adapter import _atomic_text
from .borrowed_authority_view_v7 import inspect_borrowed_authority_v7
from .current_package_route_selection_rollback_adapter_v13 import (
    CurrentPackageRouteSelectionRollbackAdapterV13,
)
from .host_review import run as host_run
from .package_review import sha256
from .production_adapter_contract import (
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    MixerSnapshot,
    ServiceActiveState,
    ServiceSnapshot,
    ServiceUnit,
    SnapshotIdentity,
    TransactionIdentity,
)
from .production_adapter_lifecycle_v7 import (
    ACTIVATION_APPROVAL_PATH,
    COMMITTED_APPROVAL_PHASE,
    PRODUCTION_LOCK_PATH,
    TEMPORARY_APPROVAL_PHASE,
    ActivationApprovalAdapterResult,
    ActivationApprovalLifecycleOperation,
    ActivationApprovalRemovalReceipt,
    CommittedActivationApprovalReceipt,
    ProductionAdapterV7,
    ProductionLockLeaseBindingReceipt,
    TemporaryActivationApprovalReceipt,
)
from .production_lock_rehearsal_adapter import _descriptor_evidence, _prove_contention
from .read_only_host_adapter import (
    APPLICATION_SERVICE_UNITS,
    STAGE_C_SERVICE_UNITS,
    ObservationFailure,
    _fail,
    _observe_mixer_snapshot,
    _observe_service_snapshot,
)
from .route_selection_rollback_rehearsal_adapter import (
    RouteSelectionRollbackFailure,
    _require_identity,
)
from .service_quiescence_rehearsal_adapter import (
    APPLICATION_START_ORDER,
    APPLICATION_STOP_ORDER,
    ServiceQuiescenceFailure,
    _service_map,
)
from .snapshot_core import CURRENT_ALSA_DESTINATION


STATE_ROOT = Path("/var/lib/a-clockwork-plex/split-bus")
TRANSACTION_ROOT = STATE_ROOT / "transactions"
COMMITTED_INSTALL_ROOT = STATE_ROOT / "committed-install"
APPROVAL_PATH = Path(ACTIVATION_APPROVAL_PATH)
ACTIVE_ROUTE = Path(CURRENT_ALSA_DESTINATION)
SPLIT_ROUTE = Path("/etc/a-clockwork-plex/audio-routes/split-bus.conf")
DIRECT_ROUTE = Path("/etc/a-clockwork-plex/audio-routes/direct-alarm-bypass.conf")
CAMILLADSP_CONFIG = Path("/etc/a-clockwork-plex/camilladsp-split-bus.yml")
CAMILLADSP_BINARY = Path(
    "/usr/local/lib/a-clockwork-plex/camilladsp-4.1.3/camilladsp"
)
RUNTIME_HELPER = Path("/usr/local/bin/a-clockwork-plex-audio-route")
RUNTIME_STATE = STATE_ROOT / "route-state.json"
COMMIT_MANIFEST_NAME = "commit-manifest.json"
ORIGINAL_ROUTE_NAME = "pre-eq-active-route.conf"
DASHBOARD_URL = "http://127.0.0.1:8088/"

MANAGED_START_ORDER = (
    ServiceUnit.ROUTE_AUTHORITY,
    ServiceUnit.CAMILLADSP,
)
MANAGED_STOP_ORDER = (
    ServiceUnit.CAMILLADSP,
    ServiceUnit.AUDIO_FAILBACK,
    ServiceUnit.ROUTE_AUTHORITY,
)
ENABLE_UNITS = (
    ServiceUnit.ROUTE_AUTHORITY,
    ServiceUnit.CAMILLADSP,
)


class TerminalInstallFailure(RuntimeError):
    """The fixed terminal install could not advance safely."""


def _clean_detail(value: str) -> str:
    return value.replace("\t", " ").replace("\n", " ").strip()


def _run_fixed(*arguments: str) -> str:
    result = host_run(list(arguments))
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip() or str(result.returncode)
        raise TerminalInstallFailure(
            f"fixed command failed ({' '.join(arguments)}): {detail}"
        )
    return result.stdout.strip()


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    _atomic_text(
        path,
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
    )


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class CurrentPackageTerminalInstallAdapterV15(
    CurrentPackageRouteSelectionRollbackAdapterV13,
    ProductionAdapterV7,
):
    """C25 owner plus the one guarded persistent activation suffix."""

    def __init__(
        self,
        package_root: Path,
        invoking_user: str,
        evidence_root: Path,
        *,
        accepted_c25_evidence: Path,
    ) -> None:
        super().__init__(package_root, invoking_user, evidence_root)
        self._accepted_c25_evidence = accepted_c25_evidence.resolve()
        self._approval_binding: ApprovalAuthorityBindingV7 | None = None
        self._temporary_plan: TemporaryApprovalRecordPlanV7 | None = None
        self._committed_plan: CommittedApprovalRecordPlanV7 | None = None
        self._managed_services_started = False
        self._managed_enablement_started = False
        self._terminal_committed = False
        self._commit_manifest_sha256: str | None = None
        self._committed_install_root: Path | None = None
        self._runtime_actions = self._evidence_root / "terminal-runtime-actions.tsv"
        self._runtime_actions.write_text(
            "order\tmonotonic_ns\taction\tresult\tdetail\n",
            encoding="utf-8",
        )
        os.chown(self._runtime_actions, 0, 0)
        self._runtime_actions.chmod(0o600)
        self._runtime_action_order = 0

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._terminal_committed:
            return None
        return super().__exit__(exc_type, exc, traceback)

    @property
    def terminal_committed(self) -> bool:
        return self._terminal_committed

    @property
    def committed_install_root(self) -> Path | None:
        return self._committed_install_root

    @property
    def commit_manifest_sha256(self) -> str | None:
        return self._commit_manifest_sha256

    def _record_runtime_action(self, action: str, result: str, detail: str) -> None:
        self._runtime_action_order += 1
        with self._runtime_actions.open("a", encoding="utf-8") as output:
            output.write(
                f"{self._runtime_action_order}\t{time.monotonic_ns()}\t"
                f"{action}\t{result}\t{_clean_detail(detail)}\n"
            )

    def _require_terminal_transaction(
        self,
        operation: AdapterOperation | ActivationApprovalLifecycleOperation,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None] | ActivationApprovalAdapterResult | None:
        current = self.authoritative_transaction
        if current is None or current.transaction != transaction:
            if isinstance(operation, ActivationApprovalLifecycleOperation):
                return ActivationApprovalAdapterResult(
                    operation=operation,
                    status=AdapterStatus.FAIL,
                    detail="rejected non-authoritative terminal transaction identity",
                )
            return _fail(operation, "rejected non-authoritative terminal transaction identity")
        if not self.lock_held or self.lease is None or self._lock_fd is None:
            if isinstance(operation, ActivationApprovalLifecycleOperation):
                return ActivationApprovalAdapterResult(
                    operation=operation,
                    status=AdapterStatus.FAIL,
                    detail="terminal operation requires the exact held production lock",
                )
            return _fail(operation, "terminal operation requires the exact held production lock")
        return None

    def _hardware_contract(self) -> ApprovalHardwareContractV7:
        return ApprovalHardwareContractV7(
            package=self.package,
            split_route_sha256=sha256(SPLIT_ROUTE),
            direct_route_sha256=sha256(DIRECT_ROUTE),
            camilladsp_config_sha256=sha256(CAMILLADSP_CONFIG),
            camilladsp_binary_version="4.1.3",
            camilladsp_binary_sha256=sha256(CAMILLADSP_BINARY),
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

    def bind_production_lock_lease(
        self,
        transaction: TransactionIdentity,
    ) -> ActivationApprovalAdapterResult:
        operation = ActivationApprovalLifecycleOperation.BIND_PRODUCTION_LOCK_LEASE
        invalid = self._require_terminal_transaction(operation, transaction)
        if invalid is not None:
            assert isinstance(invalid, ActivationApprovalAdapterResult)
            return invalid
        if self._approval_binding is not None:
            return ActivationApprovalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail="production lock lease is already bound",
            )
        try:
            borrowed_result = inspect_borrowed_authority_v7(self)
            if (
                borrowed_result.status is not AdapterStatus.PASS
                or borrowed_result.payload is None
            ):
                raise TerminalInstallFailure(borrowed_result.detail)
            binding_result = bind_approval_authority_v7(
                borrowed_result.payload,
                self._hardware_contract(),
            )
            if binding_result.status is not AdapterStatus.PASS or binding_result.payload is None:
                raise TerminalInstallFailure(binding_result.detail)
            assert self._lock_fd is not None
            assert self.lease is not None
            payload = (self.lease.lease_id + "\n").encode("ascii")
            os.ftruncate(self._lock_fd, 0)
            os.lseek(self._lock_fd, 0, os.SEEK_SET)
            view = memoryview(payload)
            while view:
                written = os.write(self._lock_fd, view)
                if written <= 0:
                    raise TerminalInstallFailure("short production-lock lease write")
                view = view[written:]
            os.fsync(self._lock_fd)
            if os.pread(self._lock_fd, 512, 0) != payload:
                raise TerminalInstallFailure("production-lock lease content verification failed")
            evidence = _descriptor_evidence(self._lock_fd)
            _prove_contention()
            self._approval_binding = binding_result.payload
            assert self.transaction_path is not None
            _atomic_json(
                self.transaction_path / "approval-authority-binding.json",
                self._approval_binding.as_dict(),
            )
        except (OSError, ValueError, TerminalInstallFailure) as exc:
            self._record_runtime_action("bind-production-lock-lease", "FAIL", str(exc))
            return ActivationApprovalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=str(exc),
            )
        self._record_runtime_action(
            "bind-production-lock-lease",
            "PASS",
            f"lease={self.lease.lease_id} inode={evidence.inode}",
        )
        return ActivationApprovalAdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="held production-lock inode now exposes the canonical transaction lease",
            payload=ProductionLockLeaseBindingReceipt(
                transaction=transaction,
                lock_path=PRODUCTION_LOCK_PATH,
                lease_id=self.lease.lease_id,
                lock_device=os.fstat(self._lock_fd).st_dev,
                lock_inode=evidence.inode,
                transaction_owns_lock=True,
                canonical_content_written=True,
                exact_inode_verified=True,
                external_observer_ready=True,
            ),
        )

    def publish_temporary_activation_approval(
        self,
        transaction: TransactionIdentity,
    ) -> ActivationApprovalAdapterResult:
        operation = (
            ActivationApprovalLifecycleOperation.PUBLISH_TEMPORARY_ACTIVATION_APPROVAL
        )
        invalid = self._require_terminal_transaction(operation, transaction)
        if invalid is not None:
            assert isinstance(invalid, ActivationApprovalAdapterResult)
            return invalid
        if self._approval_binding is None:
            return ActivationApprovalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail="production lock lease is not bound",
            )
        if self._temporary_plan is not None:
            return ActivationApprovalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail="temporary activation approval is already planned",
            )
        try:
            plan = plan_temporary_approval_v7(
                self._approval_binding,
                created_at=utc_timestamp(),
            )
            store = ApprovalStore(STATE_ROOT)
            store.publish_new(plan.record, lock_held=True)
            if store.read() != plan.record:
                raise TerminalInstallFailure("published temporary approval changed")
            self._temporary_plan = plan
            assert self.transaction_path is not None
            _atomic_text(
                self.transaction_path / "temporary-approval-sha256.txt",
                plan.record_sha256 + "\n",
            )
        except (OSError, ValueError, RuntimeAuthorityError, TerminalInstallFailure) as exc:
            self._record_runtime_action("publish-temporary-approval", "FAIL", str(exc))
            return ActivationApprovalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=str(exc),
            )
        self._record_runtime_action(
            "publish-temporary-approval",
            "PASS",
            plan.record_sha256,
        )
        return ActivationApprovalAdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="one non-bootable transaction-bound approval was atomically published",
            payload=TemporaryActivationApprovalReceipt(
                transaction=transaction,
                approval_path=ACTIVATION_APPROVAL_PATH,
                phase=TEMPORARY_APPROVAL_PHASE,
                package=self.package,
                lock_lease_id=self.lease.lease_id,
                record_sha256=plan.record_sha256,
                active_route_sha256=self._approval_binding.selected_route_sha256,
                boot_eligible=False,
                atomically_published=True,
                exact_record_verified=True,
            ),
        )

    def remove_temporary_activation_approval(
        self,
        transaction: TransactionIdentity,
    ) -> ActivationApprovalAdapterResult:
        operation = (
            ActivationApprovalLifecycleOperation.REMOVE_TEMPORARY_ACTIVATION_APPROVAL
        )
        invalid = self._require_terminal_transaction(operation, transaction)
        if invalid is not None:
            assert isinstance(invalid, ActivationApprovalAdapterResult)
            return invalid
        plan = self._temporary_plan
        if plan is None:
            return ActivationApprovalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail="no adapter-owned temporary approval exists",
            )
        try:
            store = ApprovalStore(STATE_ROOT)
            store.remove_exact(plan.record, lock_held=True)
            try:
                store.read()
            except RuntimeAuthorityError:
                pass
            else:
                raise TerminalInstallFailure("temporary approval remains after exact removal")
        except (OSError, RuntimeAuthorityError, TerminalInstallFailure) as exc:
            self._record_runtime_action("remove-temporary-approval", "FAIL", str(exc))
            return ActivationApprovalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=str(exc),
            )
        self._record_runtime_action(
            "remove-temporary-approval",
            "PASS",
            plan.record_sha256,
        )
        return ActivationApprovalAdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="exact temporary activation approval removed by rollback owner",
            payload=ActivationApprovalRemovalReceipt(
                transaction=transaction,
                approval_path=ACTIVATION_APPROVAL_PATH,
                expected_record_sha256=plan.record_sha256,
                exact_record_removed=True,
                approval_absent=True,
                rollback_owned=True,
            ),
        )

    def _wait_unit(self, unit: ServiceUnit, expected: str, timeout: float = 30.0) -> None:
        deadline = time.monotonic() + timeout
        last = ""
        while time.monotonic() < deadline:
            result = host_run(["systemctl", "is-active", unit.value])
            last = result.stdout.strip() or "inactive"
            if expected == "active" and last == "active":
                return
            if expected == "inactive" and last in {"inactive", "failed", "unknown"}:
                return
            time.sleep(0.2)
        raise TerminalInstallFailure(
            f"{unit.value} did not become {expected}; last state {last}"
        )

    def start_managed_stage_c_services(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.START_MANAGED_STAGE_C_SERVICES
        invalid = self._require_terminal_transaction(operation, transaction)
        if invalid is not None:
            assert isinstance(invalid, AdapterResult)
            return invalid
        if self._temporary_plan is None:
            return _fail(operation, "temporary approval is absent")
        if self._managed_services_started:
            return _fail(operation, "managed Stage C services already started")
        try:
            for unit in MANAGED_START_ORDER:
                _run_fixed("systemctl", "reset-failed", unit.value)
                _run_fixed("systemctl", "start", unit.value)
                self._wait_unit(unit, "active")
                self._record_runtime_action("start-managed-service", "PASS", unit.value)
            failback = host_run(
                ["systemctl", "is-active", ServiceUnit.AUDIO_FAILBACK.value]
            ).stdout.strip()
            if failback == "active":
                raise TerminalInstallFailure("failback service became active during install startup")
            self._managed_services_started = True
        except (OSError, TerminalInstallFailure) as exc:
            self._record_runtime_action("start-managed-services", "FAIL", str(exc))
            return _fail(operation, str(exc))
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="route authority and Type=notify CamillaDSP supervisor are active under temporary approval",
            evidence=(
                ("route_authority", "active"),
                ("camilladsp_supervisor", "active"),
                ("failback", "inactive"),
                ("enabled_during_start", "false"),
            ),
        )

    def verify_split_bus_health(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.VERIFY_SPLIT_BUS_HEALTH
        invalid = self._require_terminal_transaction(operation, transaction)
        if invalid is not None:
            assert isinstance(invalid, AdapterResult)
            return invalid
        if not self._managed_services_started or self._approval_binding is None:
            return _fail(operation, "managed temporary runtime is not active")
        try:
            for unit in MANAGED_START_ORDER:
                if _run_fixed("systemctl", "is-active", unit.value) != "active":
                    raise TerminalInstallFailure(f"managed unit is not active: {unit.value}")
            _run_fixed(str(RUNTIME_HELPER), "validate-runtime")
            status_raw = _run_fixed(str(RUNTIME_HELPER), "status")
            status_payload = json.loads(status_raw)
            if status_payload.get("ok") is not True:
                raise TerminalInstallFailure("runtime helper status is not healthy")
            state = json.loads(RUNTIME_STATE.read_text(encoding="utf-8"))
            if state.get("runtime_mode") != "split-active":
                raise TerminalInstallFailure("runtime state is not split-active")
            if sha256(ACTIVE_ROUTE) != self._approval_binding.selected_route_sha256:
                raise TerminalInstallFailure("active split route digest changed")
            pid = _run_fixed(
                "systemctl",
                "show",
                "--property=MainPID",
                "--value",
                ServiceUnit.CAMILLADSP.value,
            )
            if not pid.isdigit() or int(pid) <= 0:
                raise TerminalInstallFailure("CamillaDSP supervisor has no live MainPID")
        except (
            OSError,
            ValueError,
            json.JSONDecodeError,
            TerminalInstallFailure,
        ) as exc:
            self._record_runtime_action("verify-split-bus-health", "FAIL", str(exc))
            return _fail(operation, str(exc))
        self._record_runtime_action("verify-split-bus-health", "PASS", f"pid={pid}")
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="temporary split-bus runtime, package, active route and supervisor are healthy",
            evidence=(
                ("runtime_mode", "split-active"),
                ("camilladsp_main_pid", pid),
                ("active_route_sha256", self._approval_binding.selected_route_sha256),
            ),
        )

    def _run_probe(self, lane: str) -> tuple[Path, str]:
        if lane not in {"music", "alarm"}:
            raise TerminalInstallFailure("unsupported fixed probe lane")
        pcm = "acp_music" if lane == "music" else "acp_alarm"
        probe = self._evidence_root / f"terminal-{lane}-probe.wav"
        with wave.open(str(probe), "wb") as output:
            output.setnchannels(2)
            output.setsampwidth(2)
            output.setframerate(44100)
            output.writeframes(b"\x00\x00\x00\x00" * 11025)
        os.chown(probe, 0, 0)
        probe.chmod(0o600)
        _run_fixed("aplay", "-q", "-D", pcm, str(probe))
        return probe, sha256(probe)

    def run_finite_music_probe(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.RUN_FINITE_MUSIC_PROBE
        invalid = self._require_terminal_transaction(operation, transaction)
        if invalid is not None:
            assert isinstance(invalid, AdapterResult)
            return invalid
        try:
            probe, digest = self._run_probe("music")
        except (OSError, TerminalInstallFailure) as exc:
            self._record_runtime_action("finite-music-probe", "FAIL", str(exc))
            return _fail(operation, str(exc))
        self._record_runtime_action("finite-music-probe", "PASS", digest)
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="finite silent stereo probe opened and closed the music lane",
            evidence=(("probe", str(probe)), ("sha256", digest), ("frames", "11025")),
        )

    def run_finite_alarm_probe(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.RUN_FINITE_ALARM_PROBE
        invalid = self._require_terminal_transaction(operation, transaction)
        if invalid is not None:
            assert isinstance(invalid, AdapterResult)
            return invalid
        try:
            probe, digest = self._run_probe("alarm")
        except (OSError, TerminalInstallFailure) as exc:
            self._record_runtime_action("finite-alarm-probe", "FAIL", str(exc))
            return _fail(operation, str(exc))
        self._record_runtime_action("finite-alarm-probe", "PASS", digest)
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="finite silent stereo probe opened and closed the independent alarm lane",
            evidence=(("probe", str(probe)), ("sha256", digest), ("frames", "11025")),
        )

    def restore_captured_application_services(
        self,
        transaction: TransactionIdentity,
        services: ServiceSnapshot,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES
        invalid = self._require_terminal_transaction(operation, transaction)
        if invalid is not None:
            assert isinstance(invalid, AdapterResult)
            return invalid
        if services != self._captured_services_exact:
            return _fail(operation, "service snapshot is not adapter-captured")
        if not self._services_stopped:
            return _fail(operation, "captured applications are not quiesced")
        captured = _service_map(services)
        try:
            for unit in APPLICATION_START_ORDER:
                expected = captured[unit]
                if expected.active is ServiceActiveState.ACTIVE:
                    _run_fixed("systemctl", "start", unit.value)
                    self._wait_unit(unit, "active")
                else:
                    _run_fixed("systemctl", "stop", unit.value)
                    self._wait_unit(unit, "inactive")
                self._record_runtime_action(
                    "restore-application-service",
                    "PASS",
                    f"{unit.value}={expected.active.value}",
                )
            observed = _service_map(_observe_service_snapshot())
            for unit in APPLICATION_SERVICE_UNITS:
                expected = captured[unit]
                current = observed[unit]
                if (
                    current.load is not expected.load
                    or current.active is not expected.active
                    or current.enabled is not expected.enabled
                ):
                    raise TerminalInstallFailure(
                        f"application service did not restore exactly: {unit.value}"
                    )
        except (ObservationFailure, OSError, TerminalInstallFailure) as exc:
            return _fail(operation, str(exc))
        self._services_stopped = False
        self._services_restored = True
        self._stopped_services.clear()
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="captured Plexamp, AirPlay and dashboard states restored while managed EQ remained active",
            evidence=(("managed_runtime_retained", "true"),),
        )

    def verify_dashboard_health(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.VERIFY_DASHBOARD_HEALTH
        invalid = self._require_terminal_transaction(operation, transaction)
        if invalid is not None:
            assert isinstance(invalid, AdapterResult)
            return invalid
        if not self._services_restored or not self._managed_services_started:
            return _fail(operation, "application and managed services are not both active")
        try:
            captured = _service_map(self._captured_services_exact)
            observed = _service_map(_observe_service_snapshot())
            for unit in APPLICATION_SERVICE_UNITS:
                if observed[unit].active is not captured[unit].active:
                    raise TerminalInstallFailure(
                        f"application active state changed: {unit.value}"
                    )
            for unit in MANAGED_START_ORDER:
                if observed[unit].active is not ServiceActiveState.ACTIVE:
                    raise TerminalInstallFailure(f"managed unit is not active: {unit.value}")
            deadline = time.monotonic() + 20.0
            last = ""
            while time.monotonic() < deadline:
                try:
                    request = Request(
                        DASHBOARD_URL,
                        headers={"User-Agent": "A-Clockwork-Plex-Terminal-Install/1"},
                        method="GET",
                    )
                    with urlopen(request, timeout=2.0) as response:
                        if int(response.status) == 200:
                            last = response.headers.get("Content-Type", "")
                            break
                except (OSError, URLError, TimeoutError) as exc:
                    last = str(exc)
                time.sleep(0.25)
            else:
                raise TerminalInstallFailure(f"dashboard did not become healthy: {last}")
        except (ObservationFailure, OSError, TerminalInstallFailure) as exc:
            return _fail(operation, str(exc))
        self._dashboard_verified = True
        self._record_runtime_action("verify-dashboard-health", "PASS", last)
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="dashboard and all application and managed EQ services are healthy before commit",
            evidence=(("dashboard_url", DASHBOARD_URL), ("content_type", last)),
        )

    def stop_captured_application_services(
        self,
        transaction: TransactionIdentity,
        services: ServiceSnapshot,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES
        invalid = self._require_terminal_transaction(operation, transaction)
        if invalid is not None:
            assert isinstance(invalid, AdapterResult)
            return invalid
        if services != self._captured_services_exact:
            return _fail(operation, "service snapshot is not adapter-captured")
        if self._services_stopped:
            return AdapterResult(
                operation=operation,
                status=AdapterStatus.PASS,
                detail="captured application services were already quiesced",
            )
        try:
            for unit in APPLICATION_STOP_ORDER:
                _run_fixed("systemctl", "stop", unit.value)
                self._wait_unit(unit, "inactive")
                self._record_runtime_action("rollback-stop-application", "PASS", unit.value)
        except (OSError, TerminalInstallFailure) as exc:
            return _fail(operation, str(exc))
        self._services_stopped = True
        self._services_restored = False
        self._dashboard_verified = False
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="captured application services quiesced for exact terminal rollback",
        )

    def stop_managed_stage_c_services(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES
        invalid = self._require_terminal_transaction(operation, transaction)
        if invalid is not None:
            assert isinstance(invalid, AdapterResult)
            return invalid
        try:
            for unit in MANAGED_STOP_ORDER:
                result = host_run(["systemctl", "stop", unit.value])
                if result.returncode not in (0, 5):
                    detail = (result.stderr or result.stdout).strip()
                    raise TerminalInstallFailure(
                        f"could not stop managed unit {unit.value}: {detail}"
                    )
                self._wait_unit(unit, "inactive")
                self._record_runtime_action("rollback-stop-managed", "PASS", unit.value)
            if self._managed_enablement_started:
                _run_fixed(
                    "systemctl",
                    "disable",
                    ServiceUnit.CAMILLADSP.value,
                    ServiceUnit.ROUTE_AUTHORITY.value,
                )
                self._managed_enablement_started = False
            try:
                info = RUNTIME_STATE.lstat()
            except FileNotFoundError:
                pass
            else:
                if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                    raise TerminalInstallFailure("runtime state is not a removable regular file")
                RUNTIME_STATE.unlink()
                _fsync_directory(STATE_ROOT)
        except (OSError, TerminalInstallFailure) as exc:
            return _fail(operation, str(exc))
        self._managed_services_started = False
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="managed route, CamillaDSP and failback services stopped and transient runtime state removed",
        )

    def verify_dac_released(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.VERIFY_DAC_RELEASED
        invalid = self._require_terminal_transaction(operation, transaction)
        if invalid is not None:
            assert isinstance(invalid, AdapterResult)
            return invalid
        try:
            rows = self._released_endpoint_rows()
        except (ObservationFailure, ServiceQuiescenceFailure) as exc:
            return _fail(operation, str(exc))
        self._dac_release_verified = True
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="physical DAC and fixed loopback endpoints are released for exact rollback",
            evidence=rows,
        )

    def restore_mixer_state(
        self,
        transaction: TransactionIdentity,
        mixer: MixerSnapshot,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.RESTORE_MIXER_STATE
        invalid = self._require_terminal_transaction(operation, transaction)
        if invalid is not None:
            assert isinstance(invalid, AdapterResult)
            return invalid
        if mixer != self._captured_mixer_exact:
            return _fail(operation, "mixer snapshot is not adapter-captured")
        controls = (
            ("A Clockwork Plexamp", mixer.plexamp_output),
            ("A Clockwork AirPlay", mixer.airplay_output),
            ("A Clockwork Master", mixer.music_master),
            ("A Clockwork Alarm", mixer.maximum_alarm_volume),
        )
        try:
            if _observe_mixer_snapshot() != mixer:
                for control, value in controls:
                    _run_fixed("amixer", "-c", "Pro", "sset", control, f"{value}%")
            if _observe_mixer_snapshot() != mixer:
                raise TerminalInstallFailure("mixer values did not restore exactly")
        except (ObservationFailure, OSError, TerminalInstallFailure) as exc:
            return _fail(operation, str(exc))
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="all four captured mixer values are restored exactly",
        )

    def restore_service_state(
        self,
        transaction: TransactionIdentity,
        services: ServiceSnapshot,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.RESTORE_SERVICE_STATE
        invalid = self._require_terminal_transaction(operation, transaction)
        if invalid is not None:
            assert isinstance(invalid, AdapterResult)
            return invalid
        if services != self._captured_services_exact:
            return _fail(operation, "service snapshot is not adapter-captured")
        try:
            self._restore_captured_services_exact()
        except (ObservationFailure, ServiceQuiescenceFailure) as exc:
            return _fail(operation, str(exc))
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="captured six-service state restored exactly after terminal rollback",
        )

    def _revert_commit_preparation(
        self,
        *,
        transaction_path: Path,
        committed_root: Path,
        parked_route: Path,
        original_destination: Path,
        transaction_moved: bool,
        route_moved: bool,
    ) -> None:
        if transaction_moved:
            os.rename(committed_root, transaction_path)
            _fsync_directory(STATE_ROOT)
        if route_moved:
            source = transaction_path / "uninstall" / ORIGINAL_ROUTE_NAME
            os.rename(source, parked_route)
            _fsync_directory(parked_route.parent)
            if source.parent.exists():
                source.parent.rmdir()
        if self._managed_enablement_started:
            result = host_run(
                [
                    "systemctl",
                    "disable",
                    ServiceUnit.CAMILLADSP.value,
                    ServiceUnit.ROUTE_AUTHORITY.value,
                ]
            )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip()
                raise TerminalInstallFailure(
                    f"could not reverse managed enablement: {detail}"
                )
            self._managed_enablement_started = False
        _require_identity(parked_route, self._route_original, "restored parked original route")
        if original_destination.exists():
            raise TerminalInstallFailure("temporary committed original-route destination remains")

    def promote_committed_activation_approval(
        self,
        transaction: TransactionIdentity,
    ) -> ActivationApprovalAdapterResult:
        operation = (
            ActivationApprovalLifecycleOperation.PROMOTE_COMMITTED_ACTIVATION_APPROVAL
        )
        invalid = self._require_terminal_transaction(operation, transaction)
        if invalid is not None:
            assert isinstance(invalid, ActivationApprovalAdapterResult)
            return invalid
        if self._temporary_plan is None or self._approval_binding is None:
            return ActivationApprovalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail="temporary approval or authority binding is unavailable",
            )
        if not all(
            (
                self._managed_services_started,
                self._services_restored,
                self._dashboard_verified,
                self._route_selected,
                self._route_selected_once,
                self._route_exchange_completed,
            )
        ):
            return ActivationApprovalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail="runtime, applications, dashboard and selected route must be healthy before commit",
            )
        if COMMITTED_INSTALL_ROOT.exists() or COMMITTED_INSTALL_ROOT.is_symlink():
            return ActivationApprovalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail="a committed Stage C installation already exists",
            )
        assert self.transaction_path is not None
        assert self._route_rollback_name is not None
        assert self._route_original is not None
        assert self._route_candidate is not None
        transaction_path = self.transaction_path
        parked_route = ACTIVE_ROUTE.parent / self._route_rollback_name
        uninstall_root = transaction_path / "uninstall"
        original_destination = uninstall_root / ORIGINAL_ROUTE_NAME
        route_moved = False
        transaction_moved = False
        store = ApprovalStore(STATE_ROOT)
        committed_plan: CommittedApprovalRecordPlanV7 | None = None
        try:
            uninstall_root.mkdir(mode=0o700, exist_ok=False)
            os.chown(uninstall_root, 0, 0)
            uninstall_root.chmod(0o700)
            _require_identity(parked_route, self._route_original, "parked pre-EQ route")
            os.rename(parked_route, original_destination)
            route_moved = True
            _fsync_directory(ACTIVE_ROUTE.parent)
            _fsync_directory(uninstall_root)
            _require_identity(
                original_destination,
                self._route_original,
                "committed pre-EQ uninstall route",
            )

            _run_fixed(
                "systemctl",
                "enable",
                ServiceUnit.ROUTE_AUTHORITY.value,
                ServiceUnit.CAMILLADSP.value,
            )
            self._managed_enablement_started = True
            for unit in ENABLE_UNITS:
                if _run_fixed("systemctl", "is-enabled", unit.value) != "enabled":
                    raise TerminalInstallFailure(f"managed unit did not become enabled: {unit.value}")

            manifest_path = transaction_path / COMMIT_MANIFEST_NAME
            manifest_payload: dict[str, object] = {
                "schema_version": 1,
                "state": "committed-stage-c-eq-install",
                "committed_at": utc_timestamp(),
                "transaction_id": transaction.value,
                "snapshot_id": self.authoritative_transaction.snapshot.value,
                "package_fingerprint": self.package.sha256,
                "active_route_path": str(ACTIVE_ROUTE),
                "active_route_sha256": self._route_candidate.digest,
                "pre_eq_route_path": f"uninstall/{ORIGINAL_ROUTE_NAME}",
                "pre_eq_route_sha256": self._route_original.digest,
                "managed_file_count": 28,
                "payload_file_count": 27,
                "enabled_units": [unit.value for unit in ENABLE_UNITS],
                "accepted_c25_evidence": str(self._accepted_c25_evidence),
                "temporary_approval_sha256": self._temporary_plan.record_sha256,
                "reboot_verification": "pending",
                "pr_ready_or_merged": False,
            }
            _atomic_json(manifest_path, manifest_payload)
            manifest_sha256 = sha256(manifest_path)
            committed_plan = plan_committed_approval_v7(
                self._temporary_plan,
                commit_manifest_sha256=manifest_sha256,
                committed_at=utc_timestamp(),
            )
            _atomic_text(
                transaction_path / "committed-approval-sha256.txt",
                committed_plan.record_sha256 + "\n",
            )
            _fsync_directory(transaction_path)

            os.rename(transaction_path, COMMITTED_INSTALL_ROOT)
            transaction_moved = True
            _fsync_directory(STATE_ROOT)

            try:
                store.replace_exact(
                    self._temporary_plan.record,
                    committed_plan.record,
                    lock_held=True,
                )
            except BaseException as publication_exc:
                try:
                    observed = store.read()
                except BaseException:
                    raise
                if observed == committed_plan.record:
                    pass
                elif observed == self._temporary_plan.record:
                    self._revert_commit_preparation(
                        transaction_path=transaction_path,
                        committed_root=COMMITTED_INSTALL_ROOT,
                        parked_route=parked_route,
                        original_destination=original_destination,
                        transaction_moved=transaction_moved,
                        route_moved=route_moved,
                    )
                    return ActivationApprovalAdapterResult(
                        operation=operation,
                        status=AdapterStatus.FAIL,
                        detail=f"committed approval was not published: {publication_exc}",
                    )
                else:
                    raise

            if store.read() != committed_plan.record:
                raise TerminalInstallFailure("committed approval changed after publication")
        except ActivationApprovalAdapterResult:
            raise
        except BaseException as exc:
            if committed_plan is not None:
                try:
                    observed = store.read()
                except BaseException:
                    observed = None
                if observed == committed_plan.record:
                    raise
            try:
                if transaction_moved or route_moved or self._managed_enablement_started:
                    self._revert_commit_preparation(
                        transaction_path=transaction_path,
                        committed_root=COMMITTED_INSTALL_ROOT,
                        parked_route=parked_route,
                        original_destination=original_destination,
                        transaction_moved=transaction_moved,
                        route_moved=route_moved,
                    )
            except BaseException as revert_exc:
                raise TerminalInstallFailure(
                    f"commit preparation failed: {exc}; preparation reversal failed: {revert_exc}"
                ) from exc
            self._record_runtime_action("promote-committed-approval", "FAIL", str(exc))
            return ActivationApprovalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=str(exc),
            )

        assert committed_plan is not None
        self._committed_plan = committed_plan
        self._commit_manifest_sha256 = committed_plan.commit_manifest_sha256
        self._committed_install_root = COMMITTED_INSTALL_ROOT
        self._terminal_committed = True
        self._route_exchange_completed = False
        self._route_rollback_name = None
        self.transaction_path = None
        if TRANSACTION_ROOT.exists():
            try:
                TRANSACTION_ROOT.rmdir()
            except OSError:
                pass
        self._record_runtime_action(
            "promote-committed-approval",
            "PASS",
            committed_plan.record_sha256,
        )
        return ActivationApprovalAdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="durable uninstall snapshot and manifest prepared, managed boot units enabled and committed approval atomically published",
            payload=CommittedActivationApprovalReceipt(
                transaction=transaction,
                approval_path=ACTIVATION_APPROVAL_PATH,
                phase=COMMITTED_APPROVAL_PHASE,
                package=self.package,
                lock_lease_id=self.lease.lease_id,
                temporary_record_sha256=self._temporary_plan.record_sha256,
                committed_record_sha256=committed_plan.record_sha256,
                commit_manifest_sha256=committed_plan.commit_manifest_sha256,
                boot_eligible=True,
                atomically_promoted=True,
                exact_record_verified=True,
            ),
        )


assert issubclass(CurrentPackageTerminalInstallAdapterV15, ProductionAdapterV7)
