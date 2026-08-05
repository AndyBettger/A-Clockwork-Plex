#!/usr/bin/python3
from __future__ import annotations

"""Stage C10/C12 typed production-adapter contract.

The module defines a fixed operation vocabulary and immutable typed result
payloads. It deliberately contains no production adapter implementation,
entrypoint or host-access code. BlockedProductionAdapter refuses every host
operation.
"""

from dataclasses import dataclass, fields
from enum import Enum
from typing import Generic, NoReturn, Protocol, TypeVar, runtime_checkable


PRODUCTION_LOCK_PATH = "/run/lock/a-clockwork-plex-audio-route.lock"
AUTHORITATIVE_TRANSACTION_ROOT = "/var/lib/a-clockwork-plex/split-bus/transactions"

EXPECTED_SERVICE_UNITS = (
    "plexamp.service",
    "shairport-sync.service",
    "a-clockwork-plex.service",
    "a-clockwork-plex-audio-route.service",
    "a-clockwork-plex-camilladsp.service",
    "a-clockwork-plex-audio-failback.service",
)

EXPECTED_MIXER_CONTROLS = (
    "Plexamp Output",
    "AirPlay Output",
    "Music Master",
    "Maximum Alarm Volume",
)


class AdapterStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"


class TransactionAction(str, Enum):
    INSTALL = "install"
    RUNTIME_FAILBACK = "runtime-failback"
    EXACT_ROLLBACK = "exact-rollback"
    EXPLICIT_UNINSTALL = "explicit-uninstall"


class ServiceUnit(str, Enum):
    PLEXAMP = "plexamp.service"
    SHAIRPORT_SYNC = "shairport-sync.service"
    DASHBOARD = "a-clockwork-plex.service"
    ROUTE_AUTHORITY = "a-clockwork-plex-audio-route.service"
    CAMILLADSP = "a-clockwork-plex-camilladsp.service"
    AUDIO_FAILBACK = "a-clockwork-plex-audio-failback.service"


class ServiceLoadState(str, Enum):
    LOADED = "loaded"
    NOT_FOUND = "not-found"


class ServiceActiveState(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"


class ServiceEnableState(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    STATIC = "static"
    NOT_FOUND = "not-found"


class MixerControl(str, Enum):
    PLEXAMP_OUTPUT = "Plexamp Output"
    AIRPLAY_OUTPUT = "AirPlay Output"
    MUSIC_MASTER = "Music Master"
    MAXIMUM_ALARM_VOLUME = "Maximum Alarm Volume"


class ProbeLane(str, Enum):
    MUSIC = "music"
    ALARM = "alarm"


class RouteTarget(str, Enum):
    SPLIT_BUS = "split-bus"
    DIRECT_ALARM_BYPASS = "direct-alarm-bypass"
    EXACT_PREINSTALL = "exact-preinstall"


class AdapterOperation(str, Enum):
    INSPECT_HOST_CONTRACT = "inspect-host-contract"
    INSPECT_PRODUCTION_LOCK = "inspect-production-lock"
    ACQUIRE_PRODUCTION_LOCK = "acquire-production-lock"
    RELEASE_PRODUCTION_LOCK = "release-production-lock"
    CREATE_AUTHORITATIVE_TRANSACTION = "create-authoritative-transaction"
    CAPTURE_FILESYSTEM_STATE = "capture-filesystem-state"
    CAPTURE_SERVICE_STATE = "capture-service-state"
    CAPTURE_MIXER_STATE = "capture-mixer-state"
    CAPTURE_LOOPBACK_STATE = "capture-loopback-state"
    CAPTURE_DAC_STATE = "capture-dac-state"
    STAGE_CANDIDATE_FILES = "stage-candidate-files"
    VALIDATE_CANDIDATE_ALSA = "validate-candidate-alsa"
    VALIDATE_CANDIDATE_SUDOERS = "validate-candidate-sudoers"
    VALIDATE_CANDIDATE_UNITS = "validate-candidate-units"
    VALIDATE_CANDIDATE_CAMILLADSP = "validate-candidate-camilladsp"
    STOP_CAPTURED_APPLICATION_SERVICES = "stop-captured-application-services"
    VERIFY_DAC_RELEASED = "verify-dac-released"
    INSTALL_MANAGED_FILES = "install-managed-files"
    RELOAD_SYSTEMD = "reload-systemd"
    SELECT_SPLIT_BUS_ROUTE = "select-split-bus-route"
    START_MANAGED_STAGE_C_SERVICES = "start-managed-stage-c-services"
    STOP_MANAGED_STAGE_C_SERVICES = "stop-managed-stage-c-services"
    VERIFY_SPLIT_BUS_HEALTH = "verify-split-bus-health"
    RUN_FINITE_MUSIC_PROBE = "run-finite-music-probe"
    RUN_FINITE_ALARM_PROBE = "run-finite-alarm-probe"
    RESTORE_CAPTURED_APPLICATION_SERVICES = "restore-captured-application-services"
    VERIFY_DASHBOARD_HEALTH = "verify-dashboard-health"
    WRITE_COMMIT_MANIFEST = "write-commit-manifest"
    SELECT_DIRECT_FAILBACK_ROUTE = "select-direct-failback-route"
    RESTORE_EXACT_SNAPSHOT = "restore-exact-snapshot"
    RESTORE_MIXER_STATE = "restore-mixer-state"
    RESTORE_SERVICE_STATE = "restore-service-state"
    VERIFY_EXACT_ROLLBACK = "verify-exact-rollback"


READ_ONLY_OPERATIONS = (
    AdapterOperation.INSPECT_HOST_CONTRACT,
    AdapterOperation.INSPECT_PRODUCTION_LOCK,
    AdapterOperation.CAPTURE_FILESYSTEM_STATE,
    AdapterOperation.CAPTURE_SERVICE_STATE,
    AdapterOperation.CAPTURE_MIXER_STATE,
    AdapterOperation.CAPTURE_LOOPBACK_STATE,
    AdapterOperation.CAPTURE_DAC_STATE,
    AdapterOperation.VALIDATE_CANDIDATE_ALSA,
    AdapterOperation.VALIDATE_CANDIDATE_SUDOERS,
    AdapterOperation.VALIDATE_CANDIDATE_UNITS,
    AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP,
    AdapterOperation.VERIFY_DAC_RELEASED,
    AdapterOperation.VERIFY_SPLIT_BUS_HEALTH,
    AdapterOperation.RUN_FINITE_MUSIC_PROBE,
    AdapterOperation.RUN_FINITE_ALARM_PROBE,
    AdapterOperation.VERIFY_DASHBOARD_HEALTH,
    AdapterOperation.VERIFY_EXACT_ROLLBACK,
)

MUTATING_OPERATIONS = tuple(
    operation for operation in AdapterOperation if operation not in READ_ONLY_OPERATIONS
)


def _validate_identity(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip() or any(character.isspace() for character in value):
        raise ValueError(f"{label} must be a non-empty token without whitespace")


@dataclass(frozen=True)
class PackageFingerprint:
    sha256: str

    def __post_init__(self) -> None:
        if len(self.sha256) != 64 or any(character not in "0123456789abcdef" for character in self.sha256):
            raise ValueError("package fingerprint must be a lowercase SHA-256 digest")


@dataclass(frozen=True)
class TransactionIdentity:
    value: str

    def __post_init__(self) -> None:
        _validate_identity("transaction identity", self.value)


@dataclass(frozen=True)
class SnapshotIdentity:
    value: str

    def __post_init__(self) -> None:
        _validate_identity("snapshot identity", self.value)


@dataclass(frozen=True)
class LoopbackContract:
    module: str = "snd_aloop"
    card_index: int = 7
    card_id: str = "ACP_Loopback"
    pcm_substreams: int = 2
    pcm_notify: int = 1


@dataclass(frozen=True)
class DacContract:
    sample_format: str = "S16_LE"
    channels: int = 2
    rate: int = 44100
    period_size: int = 1024
    buffer_size: int = 8192


LOOPBACK_CONTRACT = LoopbackContract()
DAC_CONTRACT = DacContract()


@dataclass(frozen=True)
class HostContractSnapshot:
    service_units: tuple[ServiceUnit, ...]
    mixer_controls: tuple[MixerControl, ...]
    loopback: LoopbackContract
    dac: DacContract

    def __post_init__(self) -> None:
        if self.service_units != tuple(ServiceUnit):
            raise ValueError("host snapshot must contain the exact six service units")
        if self.mixer_controls != tuple(MixerControl):
            raise ValueError("host snapshot must contain the exact four mixer controls")
        if self.loopback != LOOPBACK_CONTRACT or self.dac != DAC_CONTRACT:
            raise ValueError("host snapshot does not match the fixed hardware contract")


@dataclass(frozen=True)
class ProductionLockObservation:
    path: str
    exists: bool
    held_by_caller: bool
    owner_uid: int | None
    owner_gid: int | None
    mode: int | None

    def __post_init__(self) -> None:
        if self.path != PRODUCTION_LOCK_PATH:
            raise ValueError("production lock observation uses the wrong path")
        if not self.exists and any(
            value is not None for value in (self.owner_uid, self.owner_gid, self.mode)
        ):
            raise ValueError("absent lock observation must not invent metadata")
        if self.held_by_caller and not self.exists:
            raise ValueError("an absent lock cannot be held by the caller")


@dataclass(frozen=True)
class ProductionLockLease:
    path: str
    lease_id: str
    held: bool = True

    def __post_init__(self) -> None:
        if self.path != PRODUCTION_LOCK_PATH:
            raise ValueError("production lock lease uses the wrong path")
        _validate_identity("production lock lease", self.lease_id)
        if not self.held:
            raise ValueError("a returned production lock lease must be held")


@dataclass(frozen=True)
class AuthoritativeTransaction:
    transaction: TransactionIdentity
    snapshot: SnapshotIdentity
    action: TransactionAction
    package: PackageFingerprint


@dataclass(frozen=True)
class FilesystemSnapshot:
    identity: SnapshotIdentity
    managed_entries: int
    exact: bool

    def __post_init__(self) -> None:
        if self.managed_entries <= 0:
            raise ValueError("filesystem snapshot must contain managed entries")
        if not self.exact:
            raise ValueError("filesystem snapshot must be explicitly exact")


@dataclass(frozen=True)
class ServiceState:
    unit: ServiceUnit
    load: ServiceLoadState
    active: ServiceActiveState
    enabled: ServiceEnableState


@dataclass(frozen=True)
class ServiceSnapshot:
    services: tuple[ServiceState, ...]

    def __post_init__(self) -> None:
        units = tuple(service.unit for service in self.services)
        if len(units) != len(set(units)):
            raise ValueError("service snapshot contains duplicate units")
        if set(units) != set(ServiceUnit):
            raise ValueError("service snapshot must cover the exact six service units")


@dataclass(frozen=True)
class MixerSnapshot:
    plexamp_output: int
    airplay_output: int
    music_master: int
    maximum_alarm_volume: int

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
                raise ValueError(f"{field.name} must be an integer from 0 to 100")


@dataclass(frozen=True)
class LoopbackSnapshot:
    contract: LoopbackContract
    loaded: bool

    def __post_init__(self) -> None:
        if self.contract != LOOPBACK_CONTRACT:
            raise ValueError("loopback snapshot does not match the fixed contract")


@dataclass(frozen=True)
class DacOwner:
    pid: int
    user: str
    command: str
    access: str

    def __post_init__(self) -> None:
        if self.pid <= 0 or not self.user or not self.command or not self.access:
            raise ValueError("DAC owner evidence must be complete")


@dataclass(frozen=True)
class DacSnapshot:
    contract: DacContract
    owners: tuple[DacOwner, ...]
    released: bool

    def __post_init__(self) -> None:
        if self.contract != DAC_CONTRACT:
            raise ValueError("DAC snapshot does not match the fixed contract")
        if self.released and self.owners:
            raise ValueError("released DAC snapshot must not report owners")


PayloadT = TypeVar("PayloadT")


@dataclass(frozen=True)
class AdapterResult(Generic[PayloadT]):
    operation: AdapterOperation
    status: AdapterStatus
    detail: str
    payload: PayloadT | None = None
    evidence: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("adapter result detail must not be empty")
        if self.status is not AdapterStatus.PASS and self.payload is not None:
            raise ValueError("failed or blocked adapter result must not carry a payload")


class ProductionAdapterBlocked(RuntimeError):
    """Raised whenever the blocked adapter is asked to touch the host."""

    def __init__(self, operation: AdapterOperation) -> None:
        self.operation = operation
        super().__init__(f"Stage C production adapter is blocked: {operation.value}")


@runtime_checkable
class ProductionAdapter(Protocol):
    def inspect_host_contract(self) -> AdapterResult[HostContractSnapshot]: ...
    def inspect_production_lock(self) -> AdapterResult[ProductionLockObservation]: ...
    def acquire_production_lock(self) -> AdapterResult[ProductionLockLease]: ...
    def release_production_lock(self) -> AdapterResult[None]: ...
    def create_authoritative_transaction(
        self, action: TransactionAction, package: PackageFingerprint
    ) -> AdapterResult[AuthoritativeTransaction]: ...
    def capture_filesystem_state(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[FilesystemSnapshot]: ...
    def capture_service_state(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[ServiceSnapshot]: ...
    def capture_mixer_state(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[MixerSnapshot]: ...
    def capture_loopback_state(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[LoopbackSnapshot]: ...
    def capture_dac_state(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[DacSnapshot]: ...
    def stage_candidate_files(
        self, transaction: TransactionIdentity, package: PackageFingerprint
    ) -> AdapterResult[None]: ...
    def validate_candidate_alsa(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[None]: ...
    def validate_candidate_sudoers(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[None]: ...
    def validate_candidate_units(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[None]: ...
    def validate_candidate_camilladsp(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[None]: ...
    def stop_captured_application_services(
        self, transaction: TransactionIdentity, services: ServiceSnapshot
    ) -> AdapterResult[None]: ...
    def verify_dac_released(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[None]: ...
    def install_managed_files(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[None]: ...
    def reload_systemd(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[None]: ...
    def select_split_bus_route(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[None]: ...
    def start_managed_stage_c_services(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[None]: ...
    def stop_managed_stage_c_services(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[None]: ...
    def verify_split_bus_health(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[None]: ...
    def run_finite_music_probe(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[None]: ...
    def run_finite_alarm_probe(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[None]: ...
    def restore_captured_application_services(
        self, transaction: TransactionIdentity, services: ServiceSnapshot
    ) -> AdapterResult[None]: ...
    def verify_dashboard_health(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[None]: ...
    def write_commit_manifest(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[None]: ...
    def select_direct_failback_route(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[None]: ...
    def restore_exact_snapshot(
        self, transaction: TransactionIdentity, snapshot: SnapshotIdentity
    ) -> AdapterResult[None]: ...
    def restore_mixer_state(
        self, transaction: TransactionIdentity, mixer: MixerSnapshot
    ) -> AdapterResult[None]: ...
    def restore_service_state(
        self, transaction: TransactionIdentity, services: ServiceSnapshot
    ) -> AdapterResult[None]: ...
    def verify_exact_rollback(
        self, transaction: TransactionIdentity, snapshot: SnapshotIdentity
    ) -> AdapterResult[None]: ...


class BlockedProductionAdapter:
    """Placeholder that refuses every production operation."""

    @staticmethod
    def _blocked(operation: AdapterOperation) -> NoReturn:
        raise ProductionAdapterBlocked(operation)

    def inspect_host_contract(self) -> AdapterResult[HostContractSnapshot]:
        return self._blocked(AdapterOperation.INSPECT_HOST_CONTRACT)

    def inspect_production_lock(self) -> AdapterResult[ProductionLockObservation]:
        return self._blocked(AdapterOperation.INSPECT_PRODUCTION_LOCK)

    def acquire_production_lock(self) -> AdapterResult[ProductionLockLease]:
        return self._blocked(AdapterOperation.ACQUIRE_PRODUCTION_LOCK)

    def release_production_lock(self) -> AdapterResult[None]:
        return self._blocked(AdapterOperation.RELEASE_PRODUCTION_LOCK)

    def create_authoritative_transaction(
        self, action: TransactionAction, package: PackageFingerprint
    ) -> AdapterResult[AuthoritativeTransaction]:
        del action, package
        return self._blocked(AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION)

    def capture_filesystem_state(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[FilesystemSnapshot]:
        del transaction
        return self._blocked(AdapterOperation.CAPTURE_FILESYSTEM_STATE)

    def capture_service_state(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[ServiceSnapshot]:
        del transaction
        return self._blocked(AdapterOperation.CAPTURE_SERVICE_STATE)

    def capture_mixer_state(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[MixerSnapshot]:
        del transaction
        return self._blocked(AdapterOperation.CAPTURE_MIXER_STATE)

    def capture_loopback_state(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[LoopbackSnapshot]:
        del transaction
        return self._blocked(AdapterOperation.CAPTURE_LOOPBACK_STATE)

    def capture_dac_state(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[DacSnapshot]:
        del transaction
        return self._blocked(AdapterOperation.CAPTURE_DAC_STATE)

    def stage_candidate_files(
        self, transaction: TransactionIdentity, package: PackageFingerprint
    ) -> AdapterResult[None]:
        del transaction, package
        return self._blocked(AdapterOperation.STAGE_CANDIDATE_FILES)

    def validate_candidate_alsa(self, transaction: TransactionIdentity) -> AdapterResult[None]:
        del transaction
        return self._blocked(AdapterOperation.VALIDATE_CANDIDATE_ALSA)

    def validate_candidate_sudoers(self, transaction: TransactionIdentity) -> AdapterResult[None]:
        del transaction
        return self._blocked(AdapterOperation.VALIDATE_CANDIDATE_SUDOERS)

    def validate_candidate_units(self, transaction: TransactionIdentity) -> AdapterResult[None]:
        del transaction
        return self._blocked(AdapterOperation.VALIDATE_CANDIDATE_UNITS)

    def validate_candidate_camilladsp(self, transaction: TransactionIdentity) -> AdapterResult[None]:
        del transaction
        return self._blocked(AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP)

    def stop_captured_application_services(
        self, transaction: TransactionIdentity, services: ServiceSnapshot
    ) -> AdapterResult[None]:
        del transaction, services
        return self._blocked(AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES)

    def verify_dac_released(self, transaction: TransactionIdentity) -> AdapterResult[None]:
        del transaction
        return self._blocked(AdapterOperation.VERIFY_DAC_RELEASED)

    def install_managed_files(self, transaction: TransactionIdentity) -> AdapterResult[None]:
        del transaction
        return self._blocked(AdapterOperation.INSTALL_MANAGED_FILES)

    def reload_systemd(self, transaction: TransactionIdentity) -> AdapterResult[None]:
        del transaction
        return self._blocked(AdapterOperation.RELOAD_SYSTEMD)

    def select_split_bus_route(self, transaction: TransactionIdentity) -> AdapterResult[None]:
        del transaction
        return self._blocked(AdapterOperation.SELECT_SPLIT_BUS_ROUTE)

    def start_managed_stage_c_services(self, transaction: TransactionIdentity) -> AdapterResult[None]:
        del transaction
        return self._blocked(AdapterOperation.START_MANAGED_STAGE_C_SERVICES)

    def stop_managed_stage_c_services(self, transaction: TransactionIdentity) -> AdapterResult[None]:
        del transaction
        return self._blocked(AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES)

    def verify_split_bus_health(self, transaction: TransactionIdentity) -> AdapterResult[None]:
        del transaction
        return self._blocked(AdapterOperation.VERIFY_SPLIT_BUS_HEALTH)

    def run_finite_music_probe(self, transaction: TransactionIdentity) -> AdapterResult[None]:
        del transaction
        return self._blocked(AdapterOperation.RUN_FINITE_MUSIC_PROBE)

    def run_finite_alarm_probe(self, transaction: TransactionIdentity) -> AdapterResult[None]:
        del transaction
        return self._blocked(AdapterOperation.RUN_FINITE_ALARM_PROBE)

    def restore_captured_application_services(
        self, transaction: TransactionIdentity, services: ServiceSnapshot
    ) -> AdapterResult[None]:
        del transaction, services
        return self._blocked(AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES)

    def verify_dashboard_health(self, transaction: TransactionIdentity) -> AdapterResult[None]:
        del transaction
        return self._blocked(AdapterOperation.VERIFY_DASHBOARD_HEALTH)

    def write_commit_manifest(self, transaction: TransactionIdentity) -> AdapterResult[None]:
        del transaction
        return self._blocked(AdapterOperation.WRITE_COMMIT_MANIFEST)

    def select_direct_failback_route(self, transaction: TransactionIdentity) -> AdapterResult[None]:
        del transaction
        return self._blocked(AdapterOperation.SELECT_DIRECT_FAILBACK_ROUTE)

    def restore_exact_snapshot(
        self, transaction: TransactionIdentity, snapshot: SnapshotIdentity
    ) -> AdapterResult[None]:
        del transaction, snapshot
        return self._blocked(AdapterOperation.RESTORE_EXACT_SNAPSHOT)

    def restore_mixer_state(
        self, transaction: TransactionIdentity, mixer: MixerSnapshot
    ) -> AdapterResult[None]:
        del transaction, mixer
        return self._blocked(AdapterOperation.RESTORE_MIXER_STATE)

    def restore_service_state(
        self, transaction: TransactionIdentity, services: ServiceSnapshot
    ) -> AdapterResult[None]:
        del transaction, services
        return self._blocked(AdapterOperation.RESTORE_SERVICE_STATE)

    def verify_exact_rollback(
        self, transaction: TransactionIdentity, snapshot: SnapshotIdentity
    ) -> AdapterResult[None]:
        del transaction, snapshot
        return self._blocked(AdapterOperation.VERIFY_EXACT_ROLLBACK)


def contract_snapshot() -> tuple[tuple[str, str], ...]:
    """Return static review metadata without touching the host."""

    return (
        ("status", AdapterStatus.BLOCKED.value),
        ("production_lock", PRODUCTION_LOCK_PATH),
        ("transaction_root", AUTHORITATIVE_TRANSACTION_ROOT),
        ("service_units", ",".join(EXPECTED_SERVICE_UNITS)),
        ("mixer_controls", ",".join(EXPECTED_MIXER_CONTROLS)),
        ("loopback", "snd_aloop:index=7:id=ACP_Loopback:substreams=2:notify=1"),
        ("dac", "S16_LE:2:44100:1024:8192"),
        ("operations", ",".join(operation.value for operation in AdapterOperation)),
        ("activation_interface", "absent"),
    )
