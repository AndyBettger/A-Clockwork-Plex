#!/usr/bin/python3
from __future__ import annotations

"""Stage C17 service-quiescence and exact-restoration rehearsal adapter."""

import os
import shutil
import stat
import time
from pathlib import Path
from typing import Self
from urllib.error import URLError
from urllib.request import Request, urlopen

from .authoritative_snapshot_rehearsal_adapter import (
    AuthoritativeSnapshotFailure,
    _assert_regular_tree,
    _atomic_text,
    _remove_regular_tree,
    _verify_state,
)
from .candidate_validation_rehearsal_adapter import (
    CandidateValidationFailure,
    CandidateValidationRehearsalAdapter,
)
from .production_adapter_contract import (
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    ServiceActiveState,
    ServiceLoadState,
    ServiceSnapshot,
    ServiceUnit,
    TransactionIdentity,
)
from .production_adapter_lifecycle_v2 import (
    LifecycleAdapterResult,
    TransactionLifecycleOperation,
)
from .production_adapter_lifecycle_v3 import (
    ProductionAdapterV3,
    RestoredRehearsalAdapterResult,
    RestoredRehearsalLifecycleOperation,
    RestoredRehearsalTransactionReceipt,
)
from .read_only_host_adapter import (
    APPLICATION_SERVICE_UNITS,
    STAGE_C_SERVICE_UNITS,
    ObservationFailure,
    _fail,
    _observe_dac_snapshot,
    _observe_host_contract,
    _observe_loopback_snapshot,
    _observe_mixer_snapshot,
    _observe_service_snapshot,
    _physical_dac_device,
)
from .snapshot_core import write_evidence_manifest
from .host_review import run as host_run


APPLICATION_STOP_ORDER = (
    ServiceUnit.DASHBOARD,
    ServiceUnit.SHAIRPORT_SYNC,
    ServiceUnit.PLEXAMP,
)
APPLICATION_START_ORDER = (
    ServiceUnit.PLEXAMP,
    ServiceUnit.SHAIRPORT_SYNC,
    ServiceUnit.DASHBOARD,
)
DASHBOARD_URL = "http://127.0.0.1:8088/"
SERVICE_ACTIONS_NAME = "service-actions.tsv"
RESTORED_REHEARSAL_COPY_NAME = "transaction-rehearsal-copy"

PERMITTED_V1_OPERATIONS = (
    AdapterOperation.INSPECT_HOST_CONTRACT,
    AdapterOperation.INSPECT_PRODUCTION_LOCK,
    AdapterOperation.ACQUIRE_PRODUCTION_LOCK,
    AdapterOperation.RELEASE_PRODUCTION_LOCK,
    AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION,
    AdapterOperation.CAPTURE_FILESYSTEM_STATE,
    AdapterOperation.CAPTURE_SERVICE_STATE,
    AdapterOperation.CAPTURE_MIXER_STATE,
    AdapterOperation.CAPTURE_LOOPBACK_STATE,
    AdapterOperation.CAPTURE_DAC_STATE,
    AdapterOperation.STAGE_CANDIDATE_FILES,
    AdapterOperation.VALIDATE_CANDIDATE_ALSA,
    AdapterOperation.VALIDATE_CANDIDATE_SUDOERS,
    AdapterOperation.VALIDATE_CANDIDATE_UNITS,
    AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP,
    AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES,
    AdapterOperation.VERIFY_DAC_RELEASED,
    AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES,
    AdapterOperation.VERIFY_DASHBOARD_HEALTH,
)
PERMITTED_V3_COUNT = len(PERMITTED_V1_OPERATIONS) + 2
BLOCKED_V3_COUNT = 35 - PERMITTED_V3_COUNT

if PERMITTED_V3_COUNT != 21 or BLOCKED_V3_COUNT != 14:
    raise RuntimeError("Stage C17 operation partition changed unexpectedly")


class ServiceQuiescenceFailure(RuntimeError):
    """Stage C17 could not stop, verify or restore the exact application state."""


def _service_map(snapshot: ServiceSnapshot) -> dict[ServiceUnit, object]:
    return {state.unit: state for state in snapshot.services}


class ServiceQuiescenceRehearsalAdapter(
    CandidateValidationRehearsalAdapter,
    ProductionAdapterV3,
):
    """C16 candidate validation plus one reversible application-service mutation."""

    def __init__(
        self,
        package_root: Path,
        invoking_user: str,
        evidence_root: Path,
    ) -> None:
        super().__init__(package_root, invoking_user, evidence_root)
        self._evidence_root = evidence_root.resolve()
        self._captured_services_exact: ServiceSnapshot | None = None
        self._captured_mixer_exact = None
        self._captured_loopback_exact = None
        self._captured_dac_exact = None
        self._stopped_services: list[ServiceUnit] = []
        self._mutation_started = False
        self._services_stopped = False
        self._dac_release_verified = False
        self._services_restored = False
        self._dashboard_verified = False
        self._restored_transaction_copy: Path | None = None
        self._service_actions = self._evidence_root / SERVICE_ACTIONS_NAME
        self._service_actions.write_text(
            "order\tmonotonic_ns\taction\tunit\tresult\tdetail\n",
            encoding="utf-8",
        )
        os.chown(self._service_actions, 0, 0)
        self._service_actions.chmod(0o600)
        self._service_action_order = 0

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        del traceback
        if self._mutation_started and not self._services_restored:
            try:
                self._restore_captured_services_exact()
            except (ObservationFailure, ServiceQuiescenceFailure) as restore_exc:
                raise ServiceQuiescenceFailure(
                    "mandatory Stage C17 service restoration failed; "
                    "the production lock and transaction are intentionally retained: "
                    f"{restore_exc}"
                ) from exc
        super().__exit__(exc_type, exc, None)

    @property
    def mutation_started(self) -> bool:
        return self._mutation_started

    @property
    def services_restored(self) -> bool:
        return self._services_restored

    @property
    def restored_transaction_copy(self) -> Path | None:
        return self._restored_transaction_copy

    @property
    def stopped_services(self) -> tuple[ServiceUnit, ...]:
        return tuple(self._stopped_services)

    def _record_service_action(
        self,
        action: str,
        unit: ServiceUnit,
        result: str,
        detail: str,
    ) -> None:
        self._service_action_order += 1
        clean = detail.replace("\t", " ").replace("\n", " ").strip()
        with self._service_actions.open("a", encoding="utf-8") as output:
            output.write(
                f"{self._service_action_order}\t{time.monotonic_ns()}\t"
                f"{action}\t{unit.value}\t{result}\t{clean}\n"
            )

    @staticmethod
    def _state(snapshot: ServiceSnapshot, unit: ServiceUnit):
        return next(state for state in snapshot.services if state.unit is unit)

    @staticmethod
    def _run_systemctl(action: str, unit: ServiceUnit) -> None:
        if action not in {"start", "stop"}:
            raise ServiceQuiescenceFailure("unsupported fixed systemctl action")
        result = host_run(["systemctl", action, unit.value])
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip() or str(result.returncode)
            raise ServiceQuiescenceFailure(
                f"systemctl {action} {unit.value} failed: {detail}"
            )

    @staticmethod
    def _wait_for_active(
        unit: ServiceUnit,
        expected: ServiceActiveState,
        timeout_seconds: float = 15.0,
    ) -> None:
        deadline = time.monotonic() + timeout_seconds
        last = ""
        while time.monotonic() < deadline:
            result = host_run(["systemctl", "is-active", unit.value])
            last = result.stdout.strip() or "inactive"
            if expected is ServiceActiveState.ACTIVE and last == "active":
                return
            if expected is ServiceActiveState.INACTIVE and last in {
                "inactive",
                "failed",
                "unknown",
            }:
                return
            time.sleep(0.2)
        raise ServiceQuiescenceFailure(
            f"{unit.value} did not reach {expected.value}; last state {last}"
        )

    def _candidate_ready_for_mutation(
        self,
        operation: AdapterOperation,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None] | None:
        invalid = self._require_candidate(operation, transaction)
        if invalid is not None:
            return invalid
        if not all(
            (
                self._alsa_validated,
                self._sudoers_validated,
                self._units_validated,
                self._camilladsp_validated,
            )
        ):
            return _fail(
                operation,
                "all four candidate validation domains must pass before mutation",
            )
        if self._captured_services_exact is None:
            return _fail(operation, "authoritative service snapshot is unavailable")
        return None

    def capture_service_state(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[ServiceSnapshot]:
        result = super().capture_service_state(transaction)
        if result.status is AdapterStatus.PASS and result.payload is not None:
            self._captured_services_exact = result.payload
        return result

    def capture_mixer_state(self, transaction: TransactionIdentity):
        result = super().capture_mixer_state(transaction)
        if result.status is AdapterStatus.PASS and result.payload is not None:
            self._captured_mixer_exact = result.payload
        return result

    def capture_loopback_state(self, transaction: TransactionIdentity):
        result = super().capture_loopback_state(transaction)
        if result.status is AdapterStatus.PASS and result.payload is not None:
            self._captured_loopback_exact = result.payload
        return result

    def capture_dac_state(self, transaction: TransactionIdentity):
        result = super().capture_dac_state(transaction)
        if result.status is AdapterStatus.PASS and result.payload is not None:
            self._captured_dac_exact = result.payload
        return result

    def _validate_captured_application_boundary(
        self,
        services: ServiceSnapshot,
    ) -> None:
        states = _service_map(services)
        for unit in APPLICATION_SERVICE_UNITS:
            state = states[unit]
            if state.load is not ServiceLoadState.LOADED:
                raise ServiceQuiescenceFailure(
                    f"captured application service is not loaded: {unit.value}"
                )
            if state.active is not ServiceActiveState.ACTIVE:
                raise ServiceQuiescenceFailure(
                    f"Stage C17 requires captured-active service: {unit.value}"
                )
        for unit in STAGE_C_SERVICE_UNITS:
            state = states[unit]
            if state.active is ServiceActiveState.ACTIVE:
                raise ServiceQuiescenceFailure(
                    f"unexpected active Stage C service before rehearsal: {unit.value}"
                )

    def stop_captured_application_services(
        self,
        transaction: TransactionIdentity,
        services: ServiceSnapshot,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES
        invalid = self._candidate_ready_for_mutation(operation, transaction)
        if invalid is not None:
            return invalid
        if self._mutation_started or self._services_stopped:
            return _fail(operation, "application-service mutation already started")
        if services != self._captured_services_exact:
            return _fail(operation, "service snapshot is not adapter-captured")
        try:
            self._validate_captured_application_boundary(services)
            current = _observe_service_snapshot()
            if current != services:
                raise ServiceQuiescenceFailure(
                    "application or Stage C service state drifted after snapshot"
                )
            self._mutation_started = True
            for unit in APPLICATION_STOP_ORDER:
                self._run_systemctl("stop", unit)
                self._wait_for_active(unit, ServiceActiveState.INACTIVE)
                self._stopped_services.append(unit)
                self._services_stopped = True
                self._record_service_action(
                    "stop",
                    unit,
                    "PASS",
                    "captured-active application service stopped",
                )
            observed = _observe_service_snapshot()
            observed_map = _service_map(observed)
            captured_map = _service_map(services)
            for unit in APPLICATION_SERVICE_UNITS:
                if observed_map[unit].active is not ServiceActiveState.INACTIVE:
                    raise ServiceQuiescenceFailure(
                        f"application service remained active: {unit.value}"
                    )
            for unit in STAGE_C_SERVICE_UNITS:
                if observed_map[unit] != captured_map[unit]:
                    raise ServiceQuiescenceFailure(
                        f"Stage C service changed during quiescence: {unit.value}"
                    )
        except (ObservationFailure, ServiceQuiescenceFailure) as exc:
            return _fail(operation, str(exc))
        self._services_stopped = True
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="only the three captured-active application services were stopped",
            evidence=(
                ("stopped_services", ",".join(unit.value for unit in self._stopped_services)),
                ("managed_stage_c_services_touched", "false"),
            ),
        )

    @staticmethod
    def _released_endpoint_rows() -> tuple[tuple[str, str], ...]:
        endpoints = (
            ("physical_dac", str(_physical_dac_device())),
            ("loopback_music_playback", "/dev/snd/pcmC7D0p"),
            ("loopback_dsp_capture", "/dev/snd/pcmC7D1c"),
        )
        rows: list[tuple[str, str]] = []
        for label, raw_path in endpoints:
            path = Path(raw_path)
            if not path.exists():
                raise ServiceQuiescenceFailure(
                    f"required release endpoint is missing: {path}"
                )
            result = host_run(["fuser", str(path)])
            if result.returncode not in (0, 1):
                detail = (result.stderr or result.stdout).strip()
                raise ServiceQuiescenceFailure(
                    f"could not inspect {label} ownership: {detail}"
                )
            if result.returncode == 0 or result.stdout.strip():
                raise ServiceQuiescenceFailure(
                    f"{label} remains owned after service stop: "
                    f"{result.stdout.strip()}"
                )
            rows.append((label, str(path)))
        return tuple(rows)

    def verify_dac_released(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.VERIFY_DAC_RELEASED
        invalid = self._require_candidate(operation, transaction)
        if invalid is not None:
            return invalid
        if not self._services_stopped or not self._mutation_started:
            return _fail(operation, "application services were not stopped")
        if self._dac_release_verified:
            return _fail(operation, "DAC release was already verified")
        try:
            rows = self._released_endpoint_rows()
        except (ObservationFailure, ServiceQuiescenceFailure) as exc:
            return _fail(operation, str(exc))
        self._dac_release_verified = True
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="physical DAC and fixed loopback endpoints have no owners",
            evidence=rows,
        )

    def _restore_captured_services_exact(self) -> None:
        services = self._captured_services_exact
        if services is None:
            raise ServiceQuiescenceFailure(
                "cannot restore without authoritative service snapshot"
            )
        captured_map = _service_map(services)
        for unit in APPLICATION_START_ORDER:
            expected = captured_map[unit]
            if expected.active is ServiceActiveState.ACTIVE:
                try:
                    self._run_systemctl("start", unit)
                    self._wait_for_active(unit, ServiceActiveState.ACTIVE)
                except ServiceQuiescenceFailure as exc:
                    self._record_service_action("start", unit, "FAIL", str(exc))
                    raise
                self._record_service_action(
                    "start",
                    unit,
                    "PASS",
                    "captured-active application service restored",
                )
            else:
                self._run_systemctl("stop", unit)
                self._wait_for_active(unit, ServiceActiveState.INACTIVE)
                self._record_service_action(
                    "restore-inactive",
                    unit,
                    "PASS",
                    "captured-inactive application service retained inactive",
                )
        observed = _observe_service_snapshot()
        observed_map = _service_map(observed)
        for unit in APPLICATION_SERVICE_UNITS:
            expected = captured_map[unit]
            current = observed_map[unit]
            if (
                current.load is not expected.load
                or current.active is not expected.active
                or current.enabled is not expected.enabled
            ):
                raise ServiceQuiescenceFailure(
                    f"application service state did not restore exactly: {unit.value}"
                )
        for unit in STAGE_C_SERVICE_UNITS:
            if observed_map[unit] != captured_map[unit]:
                raise ServiceQuiescenceFailure(
                    f"Stage C service changed during restoration: {unit.value}"
                )
        self._services_stopped = False
        self._services_restored = True

    def restore_captured_application_services(
        self,
        transaction: TransactionIdentity,
        services: ServiceSnapshot,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES
        invalid = self._require_candidate(operation, transaction)
        if invalid is not None:
            return invalid
        if not self._mutation_started or not self._services_stopped:
            return _fail(operation, "application services are not quiesced")
        if not self._dac_release_verified:
            return _fail(operation, "DAC release must be proved before restoration")
        if services != self._captured_services_exact:
            return _fail(operation, "service snapshot is not adapter-captured")
        try:
            self._restore_captured_services_exact()
        except (ObservationFailure, ServiceQuiescenceFailure) as exc:
            return _fail(operation, str(exc))
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="captured application service state restored exactly",
            evidence=(
                ("restored_services", ",".join(unit.value for unit in APPLICATION_START_ORDER)),
                ("enablement_changed", "false"),
            ),
        )

    @staticmethod
    def _wait_for_dashboard() -> tuple[int, str]:
        deadline = time.monotonic() + 20.0
        last = ""
        while time.monotonic() < deadline:
            try:
                request = Request(
                    DASHBOARD_URL,
                    headers={"User-Agent": "A-Clockwork-Plex-Stage-C17/1"},
                    method="GET",
                )
                with urlopen(request, timeout=2.0) as response:
                    status = int(response.status)
                    content_type = response.headers.get("Content-Type", "")
                    if status == 200 and "text/html" in content_type.lower():
                        return status, content_type
                    last = f"HTTP {status} {content_type}"
            except (OSError, URLError, TimeoutError) as exc:
                last = str(exc)
            time.sleep(0.25)
        raise ServiceQuiescenceFailure(
            f"dashboard did not become healthy at the fixed local URL: {last}"
        )

    def verify_dashboard_health(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.VERIFY_DASHBOARD_HEALTH
        invalid = self._require_candidate(operation, transaction)
        if invalid is not None:
            return invalid
        if not self._services_restored:
            return _fail(operation, "captured application services are not restored")
        if self._dashboard_verified:
            return _fail(operation, "dashboard restoration was already verified")
        try:
            if _observe_service_snapshot() != self._captured_services_exact:
                raise ServiceQuiescenceFailure(
                    "six-service state differs from the authoritative snapshot"
                )
            _observe_host_contract()
            if _observe_mixer_snapshot() != self._captured_mixer_exact:
                raise ServiceQuiescenceFailure(
                    "mixer state changed during service quiescence"
                )
            if _observe_loopback_snapshot() != self._captured_loopback_exact:
                raise ServiceQuiescenceFailure(
                    "loopback state changed during service quiescence"
                )
            restored_dac = _observe_dac_snapshot()
            if restored_dac.released or not restored_dac.owners:
                raise ServiceQuiescenceFailure(
                    "physical DAC ownership did not return after service restoration"
                )
            status, content_type = self._wait_for_dashboard()
        except (
            ObservationFailure,
            ServiceQuiescenceFailure,
            OSError,
        ) as exc:
            return _fail(operation, str(exc))
        self._dashboard_verified = True
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="service, route, mixer, loopback, DAC and dashboard health restored",
            evidence=(
                ("dashboard_url", DASHBOARD_URL),
                ("http_status", str(status)),
                ("content_type", content_type),
                ("dac_owner_count", str(len(restored_dac.owners))),
            ),
        )

    def abort_uncommitted_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> LifecycleAdapterResult:
        if self._mutation_started:
            return LifecycleAdapterResult(
                operation=(
                    TransactionLifecycleOperation.ABORT_UNCOMMITTED_TRANSACTION
                ),
                status=AdapterStatus.FAIL,
                detail=(
                    "pre-mutation abort is unavailable after the service mutation "
                    "boundary; use restored-rehearsal closure"
                ),
            )
        return super().abort_uncommitted_transaction(transaction)

    def close_restored_rehearsal_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> RestoredRehearsalAdapterResult:
        operation = (
            RestoredRehearsalLifecycleOperation.
            CLOSE_RESTORED_REHEARSAL_TRANSACTION
        )
        current = self.authoritative_transaction
        if current is None or transaction != current.transaction:
            return RestoredRehearsalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail="rejected non-authoritative transaction identity",
            )
        if not all(
            (
                self._mutation_started,
                self._dac_release_verified,
                self._services_restored,
                self._dashboard_verified,
                self._candidate_staged,
                self._alsa_validated,
                self._sudoers_validated,
                self._units_validated,
                self._camilladsp_validated,
            )
        ):
            return RestoredRehearsalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=(
                    "candidate validation, service quiescence, DAC release and "
                    "exact restoration must complete before closure"
                ),
            )
        invalid = self._require_candidate(
            AdapterOperation.STAGE_CANDIDATE_FILES,
            transaction,
        )
        if invalid is not None:
            return RestoredRehearsalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=invalid.detail,
            )
        assert self._candidate_root is not None
        assert self.transaction_path is not None
        path = self.transaction_path
        review_copy = self._evidence_root / "candidate-review-copy"
        transaction_copy = self._evidence_root / RESTORED_REHEARSAL_COPY_NAME
        try:
            if review_copy.exists() or transaction_copy.exists():
                raise ServiceQuiescenceFailure(
                    "Stage C17 audit destination already exists"
                )
            review_copy.mkdir(mode=0o700, exist_ok=False)
            os.chown(review_copy, 0, 0)
            review_copy.chmod(0o700)
            shutil.copytree(
                self._candidate_root,
                review_copy / "candidate-rootfs",
                copy_function=shutil.copy2,
            )
            if self._validation_root is not None:
                shutil.copytree(
                    self._validation_root,
                    review_copy / "candidate-validation",
                    copy_function=shutil.copy2,
                )
            _assert_regular_tree(review_copy)
            _remove_regular_tree(self._candidate_root)
            self._candidate_root = None
            self._candidate_staged = False
            if self._validation_root is not None:
                _remove_regular_tree(self._validation_root)
                self._validation_root = None

            info = path.lstat()
            if (
                info.st_dev != self._transaction_device
                or info.st_ino != self._transaction_inode
                or stat.S_ISLNK(info.st_mode)
                or not stat.S_ISDIR(info.st_mode)
            ):
                raise ServiceQuiescenceFailure(
                    "refusing closure after transaction pathname substitution"
                )
            _assert_regular_tree(path)
            _atomic_text(
                path / "state.tsv",
                "item\tvalue\n"
                "state\trehearsal-restored-and-closed\n"
                "mutation_started\ttrue\n"
                "restored\ttrue\n"
                "committed\tfalse\n",
            )
            write_evidence_manifest(path / "snapshot")
            write_evidence_manifest(path)
            shutil.copytree(path, transaction_copy, symlinks=False)
            _atomic_text(
                transaction_copy / "rehearsal-label.tsv",
                "item\tvalue\n"
                "rehearsal_copy\ttrue\n"
                "production_authoritative\tfalse\n"
                "reusable_for_activation\tfalse\n"
                "reusable_for_rollback\tfalse\n",
            )
            write_evidence_manifest(transaction_copy)
            _remove_regular_tree(path)
            for created in reversed(self._created_parents):
                created.rmdir()
            for state in self._parent_states:
                _verify_state(state)
        except (
            OSError,
            AuthoritativeSnapshotFailure,
            CandidateValidationFailure,
            ServiceQuiescenceFailure,
        ) as exc:
            return RestoredRehearsalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=str(exc),
            )

        self._transaction = None
        self._transaction_path = None
        self._transaction_device = None
        self._transaction_inode = None
        self._created_parents = ()
        self._candidate_review_copy = review_copy
        self._restored_transaction_copy = transaction_copy
        assert self._captured_services_exact is not None
        restored_services = tuple(
            unit
            for unit in APPLICATION_START_ORDER
            if self._state(self._captured_services_exact, unit).active
            is ServiceActiveState.ACTIVE
        )
        receipt = RestoredRehearsalTransactionReceipt(
            transaction=transaction,
            state="rehearsal-restored-and-closed",
            mutation_started=True,
            restored=True,
            committed=False,
            transaction_path_absent=True,
            parents_restored=True,
            restored_services=restored_services,
            audit_evidence=str(self._evidence_root),
        )
        return RestoredRehearsalAdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail=(
                "restored rehearsal evidence retained and authoritative "
                "transaction removed exactly"
            ),
            payload=receipt,
        )
