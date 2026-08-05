#!/usr/bin/python3
from __future__ import annotations

"""Stage C11 immutable transaction-policy operation programs.

The programs in this module are static metadata.  They contain no adapter,
callback, executable command or host-access implementation and cannot perform
an operation.
"""

from dataclasses import dataclass
from enum import Enum

from .production_adapter_contract import AdapterOperation, TransactionAction


class ProgramName(str, Enum):
    INSTALL = "install"
    AUTOMATIC_EXACT_ROLLBACK = "automatic-exact-rollback"
    RUNTIME_DIRECT_FAILBACK = "runtime-direct-failback"
    EXPLICIT_UNINSTALL = "explicit-uninstall"


class ProgramPhase(str, Enum):
    PREFLIGHT = "preflight"
    LOCK = "lock"
    SNAPSHOT = "snapshot"
    STAGING = "staging"
    MUTATION = "mutation"
    VALIDATION = "validation"
    RESTORATION = "restoration"
    COMMIT = "commit"
    COMPLETION = "completion"


class EntryLockState(str, Enum):
    UNHELD = "unheld"
    HELD = "held"


class SnapshotSource(str, Enum):
    FRESH_AUTHORITATIVE = "fresh-authoritative"
    ACTIVE_TRANSACTION_AUTHORITATIVE = "active-transaction-authoritative"
    COMMITTED_INSTALLATION_PLUS_LIVE = "committed-installation-plus-live-captures"
    COMMITTED_INSTALLATION_AUTHORITATIVE = "committed-installation-authoritative"


class FailureDisposition(str, Enum):
    ABORT_RELEASE_LOCK = "abort-release-lock"
    AUTOMATIC_EXACT_ROLLBACK = "automatic-exact-rollback"
    FAIL_CLOSED_RETAIN_LOCK = "fail-closed-retain-lock"


@dataclass(frozen=True)
class OperationStep:
    order: int
    phase: ProgramPhase
    operation: AdapterOperation
    changes_managed_audio_state: bool
    lock_required: bool
    detail: str

    def __post_init__(self) -> None:
        if self.order <= 0 or self.order % 10:
            raise ValueError("operation order must be a positive multiple of ten")
        if not self.detail.strip():
            raise ValueError("operation detail must not be empty")


@dataclass(frozen=True)
class OperationProgram:
    name: ProgramName
    action: TransactionAction
    entry_lock_state: EntryLockState
    snapshot_source: SnapshotSource
    before_mutation_failure: FailureDisposition
    after_mutation_failure: FailureDisposition
    steps: tuple[OperationStep, ...]

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError("operation program must contain steps")
        orders = tuple(step.order for step in self.steps)
        if orders != tuple(range(10, 10 * (len(self.steps) + 1), 10)):
            raise ValueError("operation program steps must be strictly sequential")
        if self.steps[-1].operation is not AdapterOperation.RELEASE_PRODUCTION_LOCK:
            raise ValueError("operation program must release the production lock last")
        if not self.steps[-1].lock_required:
            raise ValueError("route-lock release must occur while the lock is held")

        acquire_positions = tuple(
            index
            for index, step in enumerate(self.steps)
            if step.operation is AdapterOperation.ACQUIRE_PRODUCTION_LOCK
        )
        if self.entry_lock_state is EntryLockState.UNHELD:
            if len(acquire_positions) != 1:
                raise ValueError("unheld-entry program must acquire the lock exactly once")
            acquire_index = acquire_positions[0]
            if self.steps[acquire_index].lock_required:
                raise ValueError("lock acquisition cannot require a previously held lock")
            if any(step.lock_required for step in self.steps[:acquire_index]):
                raise ValueError("a step requires the lock before acquisition")
            if any(not step.lock_required for step in self.steps[acquire_index + 1 :]):
                raise ValueError("every step after acquisition must require the held lock")
        else:
            if acquire_positions:
                raise ValueError("held-entry program must not reacquire the lock")
            if any(not step.lock_required for step in self.steps):
                raise ValueError("every held-entry program step must require the held lock")


def _step(
    order: int,
    phase: ProgramPhase,
    operation: AdapterOperation,
    changes_managed_audio_state: bool,
    lock_required: bool,
    detail: str,
) -> OperationStep:
    return OperationStep(
        order=order,
        phase=phase,
        operation=operation,
        changes_managed_audio_state=changes_managed_audio_state,
        lock_required=lock_required,
        detail=detail,
    )


INSTALL_PROGRAM = OperationProgram(
    name=ProgramName.INSTALL,
    action=TransactionAction.INSTALL,
    entry_lock_state=EntryLockState.UNHELD,
    snapshot_source=SnapshotSource.FRESH_AUTHORITATIVE,
    before_mutation_failure=FailureDisposition.ABORT_RELEASE_LOCK,
    after_mutation_failure=FailureDisposition.AUTOMATIC_EXACT_ROLLBACK,
    steps=(
        _step(10, ProgramPhase.PREFLIGHT, AdapterOperation.INSPECT_HOST_CONTRACT, False, False, "Replay and verify the exact host contract."),
        _step(20, ProgramPhase.PREFLIGHT, AdapterOperation.INSPECT_PRODUCTION_LOCK, False, False, "Inspect the single fixed production-lock boundary."),
        _step(30, ProgramPhase.LOCK, AdapterOperation.ACQUIRE_PRODUCTION_LOCK, False, False, "Acquire the exclusive non-blocking route lock."),
        _step(40, ProgramPhase.SNAPSHOT, AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION, False, True, "Create a fresh generated install transaction identity."),
        _step(50, ProgramPhase.SNAPSHOT, AdapterOperation.CAPTURE_FILESYSTEM_STATE, False, True, "Capture managed files, directories and active ALSA state."),
        _step(60, ProgramPhase.SNAPSHOT, AdapterOperation.CAPTURE_SERVICE_STATE, False, True, "Capture exact application and Stage C service state."),
        _step(70, ProgramPhase.SNAPSHOT, AdapterOperation.CAPTURE_MIXER_STATE, False, True, "Capture all four fixed mixer restore values."),
        _step(80, ProgramPhase.SNAPSHOT, AdapterOperation.CAPTURE_LOOPBACK_STATE, False, True, "Capture loopback persistence and loaded parameters."),
        _step(90, ProgramPhase.SNAPSHOT, AdapterOperation.CAPTURE_DAC_STATE, False, True, "Capture structured DAC owner and hardware parameters."),
        _step(100, ProgramPhase.STAGING, AdapterOperation.STAGE_CANDIDATE_FILES, False, True, "Stage the reviewed package inside the transaction directory."),
        _step(110, ProgramPhase.STAGING, AdapterOperation.VALIDATE_CANDIDATE_ALSA, False, True, "Validate the staged ALSA route candidates."),
        _step(120, ProgramPhase.STAGING, AdapterOperation.VALIDATE_CANDIDATE_SUDOERS, False, True, "Validate the staged sudoers candidates."),
        _step(130, ProgramPhase.STAGING, AdapterOperation.VALIDATE_CANDIDATE_UNITS, False, True, "Validate the staged systemd units."),
        _step(140, ProgramPhase.STAGING, AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP, False, True, "Validate the pinned CamillaDSP configuration."),
        _step(150, ProgramPhase.MUTATION, AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES, True, True, "Stop only application services captured active."),
        _step(160, ProgramPhase.VALIDATION, AdapterOperation.VERIFY_DAC_RELEASED, False, True, "Prove the DAC and relevant endpoints are released."),
        _step(170, ProgramPhase.MUTATION, AdapterOperation.INSTALL_MANAGED_FILES, True, True, "Atomically install and verify all managed files."),
        _step(180, ProgramPhase.MUTATION, AdapterOperation.RELOAD_SYSTEMD, True, True, "Reload systemd once after unit installation."),
        _step(190, ProgramPhase.MUTATION, AdapterOperation.SELECT_SPLIT_BUS_ROUTE, True, True, "Select the physically proven split-bus route."),
        _step(200, ProgramPhase.MUTATION, AdapterOperation.START_MANAGED_STAGE_C_SERVICES, True, True, "Start only the managed Stage C services."),
        _step(210, ProgramPhase.VALIDATION, AdapterOperation.VERIFY_SPLIT_BUS_HEALTH, False, True, "Verify loopback, CamillaDSP and DAC health."),
        _step(220, ProgramPhase.VALIDATION, AdapterOperation.RUN_FINITE_MUSIC_PROBE, False, True, "Run the bounded music-lane probe."),
        _step(230, ProgramPhase.VALIDATION, AdapterOperation.RUN_FINITE_ALARM_PROBE, False, True, "Run the bounded alarm-lane probe."),
        _step(240, ProgramPhase.MUTATION, AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES, True, True, "Restore only application services captured active."),
        _step(250, ProgramPhase.VALIDATION, AdapterOperation.VERIFY_SPLIT_BUS_HEALTH, False, True, "Re-verify split-bus health after application startup."),
        _step(260, ProgramPhase.VALIDATION, AdapterOperation.VERIFY_DASHBOARD_HEALTH, False, True, "Require dashboard and root-route health agreement."),
        _step(270, ProgramPhase.COMMIT, AdapterOperation.WRITE_COMMIT_MANIFEST, True, True, "Atomically commit the successful install transaction."),
        _step(280, ProgramPhase.COMPLETION, AdapterOperation.RELEASE_PRODUCTION_LOCK, False, True, "Release the route lock only after commit."),
    ),
)


AUTOMATIC_EXACT_ROLLBACK_PROGRAM = OperationProgram(
    name=ProgramName.AUTOMATIC_EXACT_ROLLBACK,
    action=TransactionAction.EXACT_ROLLBACK,
    entry_lock_state=EntryLockState.HELD,
    snapshot_source=SnapshotSource.ACTIVE_TRANSACTION_AUTHORITATIVE,
    before_mutation_failure=FailureDisposition.FAIL_CLOSED_RETAIN_LOCK,
    after_mutation_failure=FailureDisposition.FAIL_CLOSED_RETAIN_LOCK,
    steps=(
        _step(10, ProgramPhase.RESTORATION, AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES, True, True, "Stop captured application services, including late-restored services."),
        _step(20, ProgramPhase.RESTORATION, AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES, True, True, "Stop managed Stage C services before restoring files."),
        _step(30, ProgramPhase.VALIDATION, AdapterOperation.VERIFY_DAC_RELEASED, False, True, "Prove the DAC and relevant endpoints are released."),
        _step(40, ProgramPhase.RESTORATION, AdapterOperation.RESTORE_EXACT_SNAPSHOT, True, True, "Restore exact files, absence markers and directory metadata."),
        _step(50, ProgramPhase.RESTORATION, AdapterOperation.RELOAD_SYSTEMD, True, True, "Reload systemd after exact unit restoration."),
        _step(60, ProgramPhase.RESTORATION, AdapterOperation.RESTORE_MIXER_STATE, True, True, "Restore all four exact mixer values."),
        _step(70, ProgramPhase.RESTORATION, AdapterOperation.RESTORE_SERVICE_STATE, True, True, "Restore exact captured load, enabled and active service states."),
        _step(80, ProgramPhase.VALIDATION, AdapterOperation.VERIFY_EXACT_ROLLBACK, False, True, "Require zero exact-restoration mismatches."),
        _step(90, ProgramPhase.COMPLETION, AdapterOperation.RELEASE_PRODUCTION_LOCK, False, True, "Release only after exact rollback verification."),
    ),
)


RUNTIME_DIRECT_FAILBACK_PROGRAM = OperationProgram(
    name=ProgramName.RUNTIME_DIRECT_FAILBACK,
    action=TransactionAction.RUNTIME_FAILBACK,
    entry_lock_state=EntryLockState.UNHELD,
    snapshot_source=SnapshotSource.COMMITTED_INSTALLATION_PLUS_LIVE,
    before_mutation_failure=FailureDisposition.ABORT_RELEASE_LOCK,
    after_mutation_failure=FailureDisposition.FAIL_CLOSED_RETAIN_LOCK,
    steps=(
        _step(10, ProgramPhase.PREFLIGHT, AdapterOperation.INSPECT_HOST_CONTRACT, False, False, "Verify the committed Stage C host boundary."),
        _step(20, ProgramPhase.PREFLIGHT, AdapterOperation.INSPECT_PRODUCTION_LOCK, False, False, "Inspect the single production-lock boundary."),
        _step(30, ProgramPhase.LOCK, AdapterOperation.ACQUIRE_PRODUCTION_LOCK, False, False, "Acquire the same route lock used by install and uninstall."),
        _step(40, ProgramPhase.SNAPSHOT, AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION, False, True, "Create a fresh runtime-failback transaction record."),
        _step(50, ProgramPhase.SNAPSHOT, AdapterOperation.CAPTURE_SERVICE_STATE, False, True, "Capture current application and Stage C service state."),
        _step(60, ProgramPhase.SNAPSHOT, AdapterOperation.CAPTURE_MIXER_STATE, False, True, "Capture current live mixer values for restoration."),
        _step(70, ProgramPhase.SNAPSHOT, AdapterOperation.CAPTURE_DAC_STATE, False, True, "Capture current structured DAC ownership and format."),
        _step(80, ProgramPhase.MUTATION, AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES, True, True, "Stop only application services captured active."),
        _step(90, ProgramPhase.MUTATION, AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES, True, True, "Stop managed Stage C services and surviving CamillaDSP ownership."),
        _step(100, ProgramPhase.VALIDATION, AdapterOperation.VERIFY_DAC_RELEASED, False, True, "Prove the DAC and relevant endpoints are released."),
        _step(110, ProgramPhase.MUTATION, AdapterOperation.SELECT_DIRECT_FAILBACK_ROUTE, True, True, "Select the physically proven direct alarm-bypass route."),
        _step(120, ProgramPhase.RESTORATION, AdapterOperation.RESTORE_MIXER_STATE, True, True, "Restore the captured live mixer values."),
        _step(130, ProgramPhase.RESTORATION, AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES, True, True, "Restore only application services captured active."),
        _step(140, ProgramPhase.VALIDATION, AdapterOperation.RUN_FINITE_MUSIC_PROBE, False, True, "Run a bounded direct-route music probe."),
        _step(150, ProgramPhase.VALIDATION, AdapterOperation.RUN_FINITE_ALARM_PROBE, False, True, "Run a bounded direct-route alarm probe."),
        _step(160, ProgramPhase.VALIDATION, AdapterOperation.VERIFY_DASHBOARD_HEALTH, False, True, "Verify dashboard degraded-route health agreement."),
        _step(170, ProgramPhase.COMMIT, AdapterOperation.WRITE_COMMIT_MANIFEST, True, True, "Record the completed direct-failback transition."),
        _step(180, ProgramPhase.COMPLETION, AdapterOperation.RELEASE_PRODUCTION_LOCK, False, True, "Release only after failback verification and recording."),
    ),
)


EXPLICIT_UNINSTALL_PROGRAM = OperationProgram(
    name=ProgramName.EXPLICIT_UNINSTALL,
    action=TransactionAction.EXPLICIT_UNINSTALL,
    entry_lock_state=EntryLockState.UNHELD,
    snapshot_source=SnapshotSource.COMMITTED_INSTALLATION_AUTHORITATIVE,
    before_mutation_failure=FailureDisposition.ABORT_RELEASE_LOCK,
    after_mutation_failure=FailureDisposition.FAIL_CLOSED_RETAIN_LOCK,
    steps=(
        _step(10, ProgramPhase.PREFLIGHT, AdapterOperation.INSPECT_HOST_CONTRACT, False, False, "Verify the installed Stage C host boundary and committed snapshot."),
        _step(20, ProgramPhase.PREFLIGHT, AdapterOperation.INSPECT_PRODUCTION_LOCK, False, False, "Inspect the single production-lock boundary."),
        _step(30, ProgramPhase.LOCK, AdapterOperation.ACQUIRE_PRODUCTION_LOCK, False, False, "Acquire the same route lock used by install and failback."),
        _step(40, ProgramPhase.SNAPSHOT, AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION, False, True, "Create a fresh explicit-uninstall transaction record."),
        _step(50, ProgramPhase.SNAPSHOT, AdapterOperation.CAPTURE_SERVICE_STATE, False, True, "Capture current service observations for uninstall audit."),
        _step(60, ProgramPhase.SNAPSHOT, AdapterOperation.CAPTURE_MIXER_STATE, False, True, "Capture current mixer observations for uninstall audit."),
        _step(70, ProgramPhase.SNAPSHOT, AdapterOperation.CAPTURE_DAC_STATE, False, True, "Capture current DAC observations for uninstall audit."),
        _step(80, ProgramPhase.MUTATION, AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES, True, True, "Stop application services before exact restoration."),
        _step(90, ProgramPhase.MUTATION, AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES, True, True, "Stop all managed Stage C services."),
        _step(100, ProgramPhase.VALIDATION, AdapterOperation.VERIFY_DAC_RELEASED, False, True, "Prove the DAC and relevant endpoints are released."),
        _step(110, ProgramPhase.RESTORATION, AdapterOperation.RESTORE_EXACT_SNAPSHOT, True, True, "Restore the committed installation's pre-install files and absence markers."),
        _step(120, ProgramPhase.RESTORATION, AdapterOperation.RELOAD_SYSTEMD, True, True, "Reload systemd after exact unit restoration."),
        _step(130, ProgramPhase.RESTORATION, AdapterOperation.RESTORE_MIXER_STATE, True, True, "Restore original pre-install mixer values."),
        _step(140, ProgramPhase.RESTORATION, AdapterOperation.RESTORE_SERVICE_STATE, True, True, "Restore original pre-install service states."),
        _step(150, ProgramPhase.VALIDATION, AdapterOperation.VERIFY_EXACT_ROLLBACK, False, True, "Require zero exact-uninstall restoration mismatches."),
        _step(160, ProgramPhase.COMMIT, AdapterOperation.WRITE_COMMIT_MANIFEST, True, True, "Record the completed explicit-uninstall transaction."),
        _step(170, ProgramPhase.COMPLETION, AdapterOperation.RELEASE_PRODUCTION_LOCK, False, True, "Release only after exact uninstall verification and recording."),
    ),
)


PROGRAMS = (
    INSTALL_PROGRAM,
    AUTOMATIC_EXACT_ROLLBACK_PROGRAM,
    RUNTIME_DIRECT_FAILBACK_PROGRAM,
    EXPLICIT_UNINSTALL_PROGRAM,
)


def program_for_action(action: TransactionAction) -> OperationProgram:
    """Return immutable program metadata for an exact transaction action."""

    matches = tuple(program for program in PROGRAMS if program.action is action)
    if len(matches) != 1:
        raise ValueError(f"no unique Stage C11 program for action: {action.value}")
    return matches[0]


def program_snapshot() -> tuple[tuple[str, str, str, str], ...]:
    """Return static review metadata without constructing or invoking an adapter."""

    return tuple(
        (
            program.name.value,
            program.action.value,
            program.entry_lock_state.value,
            ",".join(step.operation.value for step in program.steps),
        )
        for program in PROGRAMS
    )
