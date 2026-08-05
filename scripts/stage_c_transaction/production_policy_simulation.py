#!/usr/bin/python3
from __future__ import annotations

"""Stage C12 in-memory production-policy simulation.

This module executes Stage C11 operation metadata only against a deterministic
recording adapter. It has no filesystem, process, service, lock, network or
audio access and provides no CLI or production entrypoint.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import cast

from .production_adapter_contract import (
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    AuthoritativeTransaction,
    DAC_CONTRACT,
    DacOwner,
    DacSnapshot,
    FilesystemSnapshot,
    HostContractSnapshot,
    LOOPBACK_CONTRACT,
    LoopbackSnapshot,
    MixerControl,
    MixerSnapshot,
    PackageFingerprint,
    ProductionAdapter,
    ProductionLockLease,
    ProductionLockObservation,
    PRODUCTION_LOCK_PATH,
    ServiceActiveState,
    ServiceEnableState,
    ServiceLoadState,
    ServiceSnapshot,
    ServiceState,
    ServiceUnit,
    SnapshotIdentity,
    TransactionAction,
    TransactionIdentity,
)
from .production_operation_programs import (
    AUTOMATIC_EXACT_ROLLBACK_PROGRAM,
    EntryLockState,
    FailureDisposition,
    OperationProgram,
    OperationStep,
    ProgramName,
    program_for_action,
)


class SimulationOutcome(str, Enum):
    COMPLETED = "completed"
    FAILED_BEFORE_LOCK = "failed-before-lock"
    ABORTED = "aborted"
    ROLLED_BACK = "rolled-back"
    FAIL_CLOSED = "fail-closed"


@dataclass(frozen=True)
class FailureInjection:
    operation: AdapterOperation
    occurrence: int = 1

    def __post_init__(self) -> None:
        if self.occurrence <= 0:
            raise ValueError("failure occurrence must be positive")


@dataclass(frozen=True)
class RecordedOperation:
    sequence: int
    program: ProgramName
    operation: AdapterOperation
    status: AdapterStatus
    detail: str


@dataclass(frozen=True)
class SimulationResult:
    action: TransactionAction
    outcome: SimulationOutcome
    records: tuple[RecordedOperation, ...]
    failure_operation: AdapterOperation | None
    failure_disposition: FailureDisposition | None
    lock_held: bool
    terminal_success: bool
    rollback_started: bool
    rollback_completed: bool


@dataclass
class _SimulationContext:
    package: PackageFingerprint
    transaction: AuthoritativeTransaction | None = None
    services: ServiceSnapshot | None = None
    mixer: MixerSnapshot | None = None
    mutation_started: bool = False
    terminal_success: bool = False
    records: list[RecordedOperation] = field(default_factory=list)


class RecordingProductionAdapter:
    """Deterministic simulation-only implementation of the typed protocol."""

    def __init__(
        self,
        failures: tuple[FailureInjection, ...] = (),
        *,
        initial_lock_held: bool = False,
        initial_transaction: AuthoritativeTransaction | None = None,
    ) -> None:
        if len({(item.operation, item.occurrence) for item in failures}) != len(failures):
            raise ValueError("duplicate failure injection")
        if initial_transaction is not None and not initial_lock_held:
            raise ValueError("an initial authoritative transaction requires a held lock")
        self._failures = failures
        self._occurrences: dict[AdapterOperation, int] = {}
        self._transaction_counter = 0
        self.current_transaction = initial_transaction
        self.lock_file_exists = initial_lock_held
        self.lock_held = initial_lock_held
        self.attempted_operations: list[AdapterOperation] = []

    def _begin(self, operation: AdapterOperation) -> AdapterResult[None] | None:
        self.attempted_operations.append(operation)
        occurrence = self._occurrences.get(operation, 0) + 1
        self._occurrences[operation] = occurrence
        if FailureInjection(operation, occurrence) in self._failures:
            return AdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=f"injected in-memory failure at occurrence {occurrence}",
            )
        return None

    def _require_lock(self, operation: AdapterOperation) -> AdapterResult[None] | None:
        if self.lock_held:
            return None
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.FAIL,
            detail="simulation operation requires the held route lock",
        )

    def _require_transaction(
        self,
        operation: AdapterOperation,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None] | None:
        missing = self._require_lock(operation)
        if missing is not None:
            return missing
        authoritative = self.current_transaction
        if authoritative is None:
            return AdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail="simulation operation requires an adapter-generated transaction",
            )
        if transaction != authoritative.transaction:
            return AdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail="simulation rejected a substituted transaction identity",
            )
        return None

    def _receipt(
        self,
        operation: AdapterOperation,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        injected = self._begin(operation)
        if injected is not None:
            return injected
        invalid = self._require_transaction(operation, transaction)
        if invalid is not None:
            return invalid
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="in-memory operation recorded",
        )

    def inspect_host_contract(self) -> AdapterResult[HostContractSnapshot]:
        operation = AdapterOperation.INSPECT_HOST_CONTRACT
        injected = self._begin(operation)
        if injected is not None:
            return cast(AdapterResult[HostContractSnapshot], injected)
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="fixed synthetic host contract returned",
            payload=HostContractSnapshot(
                service_units=tuple(ServiceUnit),
                mixer_controls=tuple(MixerControl),
                loopback=LOOPBACK_CONTRACT,
                dac=DAC_CONTRACT,
            ),
        )

    def inspect_production_lock(self) -> AdapterResult[ProductionLockObservation]:
        operation = AdapterOperation.INSPECT_PRODUCTION_LOCK
        injected = self._begin(operation)
        if injected is not None:
            return cast(AdapterResult[ProductionLockObservation], injected)
        exists = self.lock_file_exists
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="synthetic production-lock boundary returned",
            payload=ProductionLockObservation(
                path=PRODUCTION_LOCK_PATH,
                exists=exists,
                held_by_caller=self.lock_held,
                owner_uid=0 if exists else None,
                owner_gid=0 if exists else None,
                mode=0o600 if exists else None,
            ),
        )

    def acquire_production_lock(self) -> AdapterResult[ProductionLockLease]:
        operation = AdapterOperation.ACQUIRE_PRODUCTION_LOCK
        injected = self._begin(operation)
        if injected is not None:
            return cast(AdapterResult[ProductionLockLease], injected)
        if self.lock_held:
            return AdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail="synthetic production lock is already held",
            )
        self.lock_file_exists = True
        self.lock_held = True
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="synthetic production lock acquired",
            payload=ProductionLockLease(
                path=PRODUCTION_LOCK_PATH,
                lease_id="simulation-lock-lease",
            ),
        )

    def release_production_lock(self) -> AdapterResult[None]:
        operation = AdapterOperation.RELEASE_PRODUCTION_LOCK
        injected = self._begin(operation)
        if injected is not None:
            return injected
        if not self.lock_held:
            return AdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail="synthetic production lock is not held",
            )
        self.lock_held = False
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="synthetic production lock released",
        )

    def create_authoritative_transaction(
        self,
        action: TransactionAction,
        package: PackageFingerprint,
    ) -> AdapterResult[AuthoritativeTransaction]:
        operation = AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION
        injected = self._begin(operation)
        if injected is not None:
            return cast(AdapterResult[AuthoritativeTransaction], injected)
        missing = self._require_lock(operation)
        if missing is not None:
            return cast(AdapterResult[AuthoritativeTransaction], missing)
        if self.current_transaction is not None:
            return AdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail="simulation already has an authoritative transaction",
            )
        self._transaction_counter += 1
        suffix = f"{action.value}-{self._transaction_counter}"
        payload = AuthoritativeTransaction(
            transaction=TransactionIdentity(f"simulation-{suffix}"),
            snapshot=SnapshotIdentity(f"simulation-snapshot-{suffix}"),
            action=action,
            package=package,
        )
        self.current_transaction = payload
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="synthetic authoritative transaction created",
            payload=payload,
        )

    def capture_filesystem_state(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[FilesystemSnapshot]:
        operation = AdapterOperation.CAPTURE_FILESYSTEM_STATE
        injected = self._begin(operation)
        if injected is not None:
            return cast(AdapterResult[FilesystemSnapshot], injected)
        invalid = self._require_transaction(operation, transaction)
        if invalid is not None:
            return cast(AdapterResult[FilesystemSnapshot], invalid)
        authoritative = cast(AuthoritativeTransaction, self.current_transaction)
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="synthetic exact filesystem snapshot captured",
            payload=FilesystemSnapshot(
                identity=authoritative.snapshot,
                managed_entries=12,
                exact=True,
            ),
        )

    def capture_service_state(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[ServiceSnapshot]:
        operation = AdapterOperation.CAPTURE_SERVICE_STATE
        injected = self._begin(operation)
        if injected is not None:
            return cast(AdapterResult[ServiceSnapshot], injected)
        invalid = self._require_transaction(operation, transaction)
        if invalid is not None:
            return cast(AdapterResult[ServiceSnapshot], invalid)
        services = tuple(
            ServiceState(
                unit=unit,
                load=ServiceLoadState.LOADED,
                active=(
                    ServiceActiveState.ACTIVE
                    if unit
                    in {
                        ServiceUnit.PLEXAMP,
                        ServiceUnit.SHAIRPORT_SYNC,
                        ServiceUnit.DASHBOARD,
                    }
                    else ServiceActiveState.INACTIVE
                ),
                enabled=(
                    ServiceEnableState.ENABLED
                    if unit
                    in {
                        ServiceUnit.PLEXAMP,
                        ServiceUnit.SHAIRPORT_SYNC,
                        ServiceUnit.DASHBOARD,
                    }
                    else ServiceEnableState.DISABLED
                ),
            )
            for unit in ServiceUnit
        )
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="synthetic service snapshot captured",
            payload=ServiceSnapshot(services),
        )

    def capture_mixer_state(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[MixerSnapshot]:
        operation = AdapterOperation.CAPTURE_MIXER_STATE
        injected = self._begin(operation)
        if injected is not None:
            return cast(AdapterResult[MixerSnapshot], injected)
        invalid = self._require_transaction(operation, transaction)
        if invalid is not None:
            return cast(AdapterResult[MixerSnapshot], invalid)
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="synthetic mixer snapshot captured",
            payload=MixerSnapshot(70, 70, 65, 80),
        )

    def capture_loopback_state(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[LoopbackSnapshot]:
        operation = AdapterOperation.CAPTURE_LOOPBACK_STATE
        injected = self._begin(operation)
        if injected is not None:
            return cast(AdapterResult[LoopbackSnapshot], injected)
        invalid = self._require_transaction(operation, transaction)
        if invalid is not None:
            return cast(AdapterResult[LoopbackSnapshot], invalid)
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="synthetic loopback snapshot captured",
            payload=LoopbackSnapshot(contract=LOOPBACK_CONTRACT, loaded=True),
        )

    def capture_dac_state(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[DacSnapshot]:
        operation = AdapterOperation.CAPTURE_DAC_STATE
        injected = self._begin(operation)
        if injected is not None:
            return cast(AdapterResult[DacSnapshot], injected)
        invalid = self._require_transaction(operation, transaction)
        if invalid is not None:
            return cast(AdapterResult[DacSnapshot], invalid)
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="synthetic DAC snapshot captured",
            payload=DacSnapshot(
                contract=DAC_CONTRACT,
                owners=(DacOwner(466057, "andy", "node", "read-write"),),
                released=False,
            ),
        )

    def stage_candidate_files(
        self,
        transaction: TransactionIdentity,
        package: PackageFingerprint,
    ) -> AdapterResult[None]:
        authoritative = self.current_transaction
        if authoritative is None or package != authoritative.package:
            return AdapterResult(
                operation=AdapterOperation.STAGE_CANDIDATE_FILES,
                status=AdapterStatus.FAIL,
                detail="simulation rejected a substituted package fingerprint",
            )
        return self._receipt(AdapterOperation.STAGE_CANDIDATE_FILES, transaction)

    def validate_candidate_alsa(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self._receipt(AdapterOperation.VALIDATE_CANDIDATE_ALSA, transaction)

    def validate_candidate_sudoers(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self._receipt(AdapterOperation.VALIDATE_CANDIDATE_SUDOERS, transaction)

    def validate_candidate_units(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self._receipt(AdapterOperation.VALIDATE_CANDIDATE_UNITS, transaction)

    def validate_candidate_camilladsp(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self._receipt(AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP, transaction)

    def stop_captured_application_services(
        self,
        transaction: TransactionIdentity,
        services: ServiceSnapshot,
    ) -> AdapterResult[None]:
        del services
        return self._receipt(
            AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES,
            transaction,
        )

    def verify_dac_released(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self._receipt(AdapterOperation.VERIFY_DAC_RELEASED, transaction)

    def install_managed_files(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self._receipt(AdapterOperation.INSTALL_MANAGED_FILES, transaction)

    def reload_systemd(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self._receipt(AdapterOperation.RELOAD_SYSTEMD, transaction)

    def select_split_bus_route(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self._receipt(AdapterOperation.SELECT_SPLIT_BUS_ROUTE, transaction)

    def start_managed_stage_c_services(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self._receipt(
            AdapterOperation.START_MANAGED_STAGE_C_SERVICES,
            transaction,
        )

    def stop_managed_stage_c_services(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self._receipt(
            AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES,
            transaction,
        )

    def verify_split_bus_health(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self._receipt(AdapterOperation.VERIFY_SPLIT_BUS_HEALTH, transaction)

    def run_finite_music_probe(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self._receipt(AdapterOperation.RUN_FINITE_MUSIC_PROBE, transaction)

    def run_finite_alarm_probe(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self._receipt(AdapterOperation.RUN_FINITE_ALARM_PROBE, transaction)

    def restore_captured_application_services(
        self,
        transaction: TransactionIdentity,
        services: ServiceSnapshot,
    ) -> AdapterResult[None]:
        del services
        return self._receipt(
            AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES,
            transaction,
        )

    def verify_dashboard_health(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self._receipt(AdapterOperation.VERIFY_DASHBOARD_HEALTH, transaction)

    def write_commit_manifest(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self._receipt(AdapterOperation.WRITE_COMMIT_MANIFEST, transaction)

    def select_direct_failback_route(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self._receipt(
            AdapterOperation.SELECT_DIRECT_FAILBACK_ROUTE,
            transaction,
        )

    def restore_exact_snapshot(
        self,
        transaction: TransactionIdentity,
        snapshot: SnapshotIdentity,
    ) -> AdapterResult[None]:
        authoritative = self.current_transaction
        if authoritative is None or snapshot != authoritative.snapshot:
            return AdapterResult(
                operation=AdapterOperation.RESTORE_EXACT_SNAPSHOT,
                status=AdapterStatus.FAIL,
                detail="simulation rejected a substituted snapshot identity",
            )
        return self._receipt(AdapterOperation.RESTORE_EXACT_SNAPSHOT, transaction)

    def restore_mixer_state(
        self,
        transaction: TransactionIdentity,
        mixer: MixerSnapshot,
    ) -> AdapterResult[None]:
        del mixer
        return self._receipt(AdapterOperation.RESTORE_MIXER_STATE, transaction)

    def restore_service_state(
        self,
        transaction: TransactionIdentity,
        services: ServiceSnapshot,
    ) -> AdapterResult[None]:
        del services
        return self._receipt(AdapterOperation.RESTORE_SERVICE_STATE, transaction)

    def verify_exact_rollback(
        self,
        transaction: TransactionIdentity,
        snapshot: SnapshotIdentity,
    ) -> AdapterResult[None]:
        authoritative = self.current_transaction
        if authoritative is None or snapshot != authoritative.snapshot:
            return AdapterResult(
                operation=AdapterOperation.VERIFY_EXACT_ROLLBACK,
                status=AdapterStatus.FAIL,
                detail="simulation rejected a substituted snapshot identity",
            )
        return self._receipt(AdapterOperation.VERIFY_EXACT_ROLLBACK, transaction)


def _require_transaction(context: _SimulationContext) -> AuthoritativeTransaction:
    if context.transaction is None:
        raise ValueError("simulation operation requires an adapter-generated transaction")
    return context.transaction


def _require_services(context: _SimulationContext) -> ServiceSnapshot:
    if context.services is None:
        raise ValueError("simulation operation requires captured service state")
    return context.services


def _require_mixer(context: _SimulationContext) -> MixerSnapshot:
    if context.mixer is None:
        raise ValueError("simulation operation requires captured mixer state")
    return context.mixer


def _invoke(
    adapter: ProductionAdapter,
    step: OperationStep,
    program: OperationProgram,
    context: _SimulationContext,
) -> AdapterResult[object]:
    operation = step.operation

    match operation:
        case AdapterOperation.INSPECT_HOST_CONTRACT:
            result = adapter.inspect_host_contract()
        case AdapterOperation.INSPECT_PRODUCTION_LOCK:
            result = adapter.inspect_production_lock()
        case AdapterOperation.ACQUIRE_PRODUCTION_LOCK:
            result = adapter.acquire_production_lock()
        case AdapterOperation.RELEASE_PRODUCTION_LOCK:
            result = adapter.release_production_lock()
        case AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION:
            result = adapter.create_authoritative_transaction(
                program.action,
                context.package,
            )
        case AdapterOperation.CAPTURE_FILESYSTEM_STATE:
            result = adapter.capture_filesystem_state(
                _require_transaction(context).transaction
            )
        case AdapterOperation.CAPTURE_SERVICE_STATE:
            result = adapter.capture_service_state(
                _require_transaction(context).transaction
            )
        case AdapterOperation.CAPTURE_MIXER_STATE:
            result = adapter.capture_mixer_state(
                _require_transaction(context).transaction
            )
        case AdapterOperation.CAPTURE_LOOPBACK_STATE:
            result = adapter.capture_loopback_state(
                _require_transaction(context).transaction
            )
        case AdapterOperation.CAPTURE_DAC_STATE:
            result = adapter.capture_dac_state(
                _require_transaction(context).transaction
            )
        case AdapterOperation.STAGE_CANDIDATE_FILES:
            result = adapter.stage_candidate_files(
                _require_transaction(context).transaction,
                context.package,
            )
        case AdapterOperation.VALIDATE_CANDIDATE_ALSA:
            result = adapter.validate_candidate_alsa(
                _require_transaction(context).transaction
            )
        case AdapterOperation.VALIDATE_CANDIDATE_SUDOERS:
            result = adapter.validate_candidate_sudoers(
                _require_transaction(context).transaction
            )
        case AdapterOperation.VALIDATE_CANDIDATE_UNITS:
            result = adapter.validate_candidate_units(
                _require_transaction(context).transaction
            )
        case AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP:
            result = adapter.validate_candidate_camilladsp(
                _require_transaction(context).transaction
            )
        case AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES:
            result = adapter.stop_captured_application_services(
                _require_transaction(context).transaction,
                _require_services(context),
            )
        case AdapterOperation.VERIFY_DAC_RELEASED:
            result = adapter.verify_dac_released(
                _require_transaction(context).transaction
            )
        case AdapterOperation.INSTALL_MANAGED_FILES:
            result = adapter.install_managed_files(
                _require_transaction(context).transaction
            )
        case AdapterOperation.RELOAD_SYSTEMD:
            result = adapter.reload_systemd(
                _require_transaction(context).transaction
            )
        case AdapterOperation.SELECT_SPLIT_BUS_ROUTE:
            result = adapter.select_split_bus_route(
                _require_transaction(context).transaction
            )
        case AdapterOperation.START_MANAGED_STAGE_C_SERVICES:
            result = adapter.start_managed_stage_c_services(
                _require_transaction(context).transaction
            )
        case AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES:
            result = adapter.stop_managed_stage_c_services(
                _require_transaction(context).transaction
            )
        case AdapterOperation.VERIFY_SPLIT_BUS_HEALTH:
            result = adapter.verify_split_bus_health(
                _require_transaction(context).transaction
            )
        case AdapterOperation.RUN_FINITE_MUSIC_PROBE:
            result = adapter.run_finite_music_probe(
                _require_transaction(context).transaction
            )
        case AdapterOperation.RUN_FINITE_ALARM_PROBE:
            result = adapter.run_finite_alarm_probe(
                _require_transaction(context).transaction
            )
        case AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES:
            result = adapter.restore_captured_application_services(
                _require_transaction(context).transaction,
                _require_services(context),
            )
        case AdapterOperation.VERIFY_DASHBOARD_HEALTH:
            result = adapter.verify_dashboard_health(
                _require_transaction(context).transaction
            )
        case AdapterOperation.WRITE_COMMIT_MANIFEST:
            result = adapter.write_commit_manifest(
                _require_transaction(context).transaction
            )
        case AdapterOperation.SELECT_DIRECT_FAILBACK_ROUTE:
            result = adapter.select_direct_failback_route(
                _require_transaction(context).transaction
            )
        case AdapterOperation.RESTORE_EXACT_SNAPSHOT:
            authoritative = _require_transaction(context)
            result = adapter.restore_exact_snapshot(
                authoritative.transaction,
                authoritative.snapshot,
            )
        case AdapterOperation.RESTORE_MIXER_STATE:
            result = adapter.restore_mixer_state(
                _require_transaction(context).transaction,
                _require_mixer(context),
            )
        case AdapterOperation.RESTORE_SERVICE_STATE:
            result = adapter.restore_service_state(
                _require_transaction(context).transaction,
                _require_services(context),
            )
        case AdapterOperation.VERIFY_EXACT_ROLLBACK:
            authoritative = _require_transaction(context)
            result = adapter.verify_exact_rollback(
                authoritative.transaction,
                authoritative.snapshot,
            )
        case _:
            raise ValueError(f"unhandled Stage C operation: {operation.value}")

    return cast(AdapterResult[object], result)


def _consume_payload(
    result: AdapterResult[object],
    context: _SimulationContext,
) -> None:
    payload = result.payload
    operation = result.operation
    expected: type[object] | None
    if operation is AdapterOperation.INSPECT_HOST_CONTRACT:
        expected = HostContractSnapshot
    elif operation is AdapterOperation.INSPECT_PRODUCTION_LOCK:
        expected = ProductionLockObservation
    elif operation is AdapterOperation.ACQUIRE_PRODUCTION_LOCK:
        expected = ProductionLockLease
    elif operation is AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION:
        expected = AuthoritativeTransaction
    elif operation is AdapterOperation.CAPTURE_FILESYSTEM_STATE:
        expected = FilesystemSnapshot
    elif operation is AdapterOperation.CAPTURE_SERVICE_STATE:
        expected = ServiceSnapshot
    elif operation is AdapterOperation.CAPTURE_MIXER_STATE:
        expected = MixerSnapshot
    elif operation is AdapterOperation.CAPTURE_LOOPBACK_STATE:
        expected = LoopbackSnapshot
    elif operation is AdapterOperation.CAPTURE_DAC_STATE:
        expected = DacSnapshot
    else:
        expected = None

    if expected is None:
        if payload is not None:
            raise ValueError(
                f"receipt-only operation returned a payload: {operation.value}"
            )
        return
    if not isinstance(payload, expected):
        raise ValueError(f"typed payload mismatch for operation: {operation.value}")

    if isinstance(payload, AuthoritativeTransaction):
        if payload.package != context.package:
            raise ValueError(
                "adapter-generated transaction changed the package fingerprint"
            )
        context.transaction = payload
    elif isinstance(payload, FilesystemSnapshot):
        authoritative = _require_transaction(context)
        if payload.identity != authoritative.snapshot:
            raise ValueError(
                "filesystem snapshot is not bound to the authoritative transaction"
            )
    elif isinstance(payload, ServiceSnapshot):
        context.services = payload
    elif isinstance(payload, MixerSnapshot):
        context.mixer = payload


def _record(
    program: OperationProgram,
    result: AdapterResult[object],
    context: _SimulationContext,
) -> None:
    context.records.append(
        RecordedOperation(
            sequence=len(context.records) + 1,
            program=program.name,
            operation=result.operation,
            status=result.status,
            detail=result.detail,
        )
    )


def _failure_disposition(
    program: OperationProgram,
    step: OperationStep,
    context: _SimulationContext,
) -> FailureDisposition:
    if context.terminal_success:
        return program.after_terminal_success_failure
    if context.mutation_started or step.changes_managed_audio_state:
        return program.after_mutation_failure
    return program.before_mutation_failure


def _execute_program(
    program: OperationProgram,
    adapter: RecordingProductionAdapter,
    context: _SimulationContext,
) -> tuple[AdapterOperation | None, FailureDisposition | None]:
    for step in program.steps:
        result = _invoke(adapter, step, program, context)
        _record(program, result, context)
        if result.status is not AdapterStatus.PASS:
            return result.operation, _failure_disposition(program, step, context)
        _consume_payload(result, context)
        if step.changes_managed_audio_state:
            context.mutation_started = True
        if step.operation is program.terminal_success_operation:
            context.terminal_success = True
    return None, None


def _release_after_abort(
    program: OperationProgram,
    adapter: RecordingProductionAdapter,
    context: _SimulationContext,
) -> bool:
    if not adapter.lock_held:
        return True
    step = OperationStep(
        order=10,
        phase=program.steps[-1].phase,
        operation=AdapterOperation.RELEASE_PRODUCTION_LOCK,
        changes_managed_audio_state=False,
        lock_required=True,
        detail="release simulated lock after pre-mutation abort",
    )
    result = _invoke(adapter, step, program, context)
    _record(program, result, context)
    return result.status is AdapterStatus.PASS


def _seed_held_rollback_context(
    package: PackageFingerprint,
) -> _SimulationContext:
    transaction = AuthoritativeTransaction(
        transaction=TransactionIdentity("simulation-existing-install"),
        snapshot=SnapshotIdentity("simulation-existing-install-snapshot"),
        action=TransactionAction.INSTALL,
        package=package,
    )
    services = ServiceSnapshot(
        tuple(
            ServiceState(
                unit=unit,
                load=ServiceLoadState.LOADED,
                active=ServiceActiveState.ACTIVE,
                enabled=ServiceEnableState.ENABLED,
            )
            for unit in ServiceUnit
        )
    )
    return _SimulationContext(
        package=package,
        transaction=transaction,
        services=services,
        mixer=MixerSnapshot(70, 70, 65, 80),
        mutation_started=True,
    )


def simulate_action(
    action: TransactionAction,
    failures: tuple[FailureInjection, ...] = (),
) -> SimulationResult:
    """Simulate one policy action entirely in memory."""

    package = PackageFingerprint("0" * 64)
    program = program_for_action(action)
    initial_lock = program.entry_lock_state is EntryLockState.HELD
    context = (
        _seed_held_rollback_context(package)
        if initial_lock
        else _SimulationContext(package=package)
    )
    adapter = RecordingProductionAdapter(
        failures,
        initial_lock_held=initial_lock,
        initial_transaction=context.transaction,
    )

    failure_operation, disposition = _execute_program(
        program,
        adapter,
        context,
    )
    rollback_started = False
    rollback_completed = False

    if failure_operation is None:
        outcome = SimulationOutcome.COMPLETED
    elif disposition is FailureDisposition.ABORT_RELEASE_LOCK:
        if not adapter.lock_held:
            outcome = SimulationOutcome.FAILED_BEFORE_LOCK
        elif _release_after_abort(program, adapter, context):
            outcome = SimulationOutcome.ABORTED
        else:
            outcome = SimulationOutcome.FAIL_CLOSED
            disposition = FailureDisposition.FAIL_CLOSED_RETAIN_LOCK
    elif disposition is FailureDisposition.AUTOMATIC_EXACT_ROLLBACK:
        rollback_started = True
        context.mutation_started = True
        context.terminal_success = False
        rollback_failure, rollback_disposition = _execute_program(
            AUTOMATIC_EXACT_ROLLBACK_PROGRAM,
            adapter,
            context,
        )
        if rollback_failure is None:
            rollback_completed = True
            outcome = SimulationOutcome.ROLLED_BACK
        else:
            failure_operation = rollback_failure
            disposition = rollback_disposition
            outcome = SimulationOutcome.FAIL_CLOSED
    else:
        outcome = SimulationOutcome.FAIL_CLOSED

    return SimulationResult(
        action=action,
        outcome=outcome,
        records=tuple(context.records),
        failure_operation=failure_operation,
        failure_disposition=disposition,
        lock_held=adapter.lock_held,
        terminal_success=context.terminal_success,
        rollback_started=rollback_started,
        rollback_completed=rollback_completed,
    )
