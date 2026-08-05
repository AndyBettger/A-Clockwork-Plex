#!/usr/bin/python3
from __future__ import annotations

"""Static Stage C21 activation suffix and terminal commit policy.

The historical v1 through v6 programs remain unchanged. This module defines
only the fixed suffix that follows the physically proved C20 prefix, plus the
single approval-removal insertion required by the existing automatic exact
rollback program.

The committed activation approval is the sole externally authoritative commit
marker for the Stage C21 runtime package. A future production implementation of
`promote-committed-activation-approval` must durably prepare the commit manifest,
bind its digest into the committed approval, and atomically publish that approval
before returning PASS.

This module is immutable metadata. It contains no host access, command execution,
filesystem operation, CLI or generic dispatch boundary.
"""

from dataclasses import dataclass
from enum import Enum

from .production_adapter_contract import AdapterOperation
from .production_adapter_lifecycle_v7 import (
    ALL_OPERATIONS_V7,
    ActivationApprovalLifecycleOperation,
    ProductionOperationV7,
)
from .production_operation_programs import AUTOMATIC_EXACT_ROLLBACK_PROGRAM


class FailureDisposition(str, Enum):
    EXACT_ROLLBACK = "exact-rollback"
    TERMINAL_PUBLICATION = "terminal-publication"
    FORWARD_RECOVERY = "forward-recovery"
    FAIL_CLOSED_RETAIN_LOCK = "fail-closed-retain-lock"


@dataclass(frozen=True)
class ActivationCommitStepV7:
    position: int
    operation: ProductionOperationV7
    failure_disposition: FailureDisposition
    requires_temporary_approval: bool
    requires_committed_approval: bool
    detail: str

    def __post_init__(self) -> None:
        if self.position <= 0:
            raise ValueError("activation commit step position must be positive")
        if not isinstance(self.operation, Enum):
            raise ValueError("activation commit step requires a fixed operation enum")
        if not self.detail.strip():
            raise ValueError("activation commit step detail must not be empty")
        if self.requires_temporary_approval and self.requires_committed_approval:
            raise ValueError("activation commit step cannot require both approval phases")
        if (
            self.failure_disposition is FailureDisposition.TERMINAL_PUBLICATION
            and self.operation
            is not ActivationApprovalLifecycleOperation.
            PROMOTE_COMMITTED_ACTIVATION_APPROVAL
        ):
            raise ValueError("only committed approval promotion may be terminal")
        if (
            self.failure_disposition is FailureDisposition.FORWARD_RECOVERY
            and not self.requires_committed_approval
        ):
            raise ValueError("forward recovery requires committed state")


BIND_LOCK_LEASE = (
    ActivationApprovalLifecycleOperation.BIND_PRODUCTION_LOCK_LEASE
)
PUBLISH_TEMPORARY_APPROVAL = (
    ActivationApprovalLifecycleOperation.PUBLISH_TEMPORARY_ACTIVATION_APPROVAL
)
REMOVE_TEMPORARY_APPROVAL = (
    ActivationApprovalLifecycleOperation.REMOVE_TEMPORARY_ACTIVATION_APPROVAL
)
PROMOTE_COMMITTED_APPROVAL = (
    ActivationApprovalLifecycleOperation.PROMOTE_COMMITTED_ACTIVATION_APPROVAL
)

START_MANAGED_SERVICES = AdapterOperation.START_MANAGED_STAGE_C_SERVICES
VERIFY_SPLIT_BUS_HEALTH = AdapterOperation.VERIFY_SPLIT_BUS_HEALTH
RUN_FINITE_MUSIC_PROBE = AdapterOperation.RUN_FINITE_MUSIC_PROBE
RUN_FINITE_ALARM_PROBE = AdapterOperation.RUN_FINITE_ALARM_PROBE
RESTORE_CAPTURED_APPLICATION_SERVICES = (
    AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES
)
VERIFY_DASHBOARD_HEALTH = AdapterOperation.VERIFY_DASHBOARD_HEALTH
RELEASE_PRODUCTION_LOCK = AdapterOperation.RELEASE_PRODUCTION_LOCK
STOP_CAPTURED_APPLICATION_SERVICES = (
    AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES
)
STOP_MANAGED_SERVICES = AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES
VERIFY_DAC_RELEASED = AdapterOperation.VERIFY_DAC_RELEASED
RESTORE_EXACT_SNAPSHOT = AdapterOperation.RESTORE_EXACT_SNAPSHOT
RELOAD_SYSTEMD = AdapterOperation.RELOAD_SYSTEMD
RESTORE_MIXER_STATE = AdapterOperation.RESTORE_MIXER_STATE
RESTORE_SERVICE_STATE = AdapterOperation.RESTORE_SERVICE_STATE
VERIFY_EXACT_ROLLBACK = AdapterOperation.VERIFY_EXACT_ROLLBACK
WRITE_COMMIT_MANIFEST = AdapterOperation.WRITE_COMMIT_MANIFEST


ACTIVATION_INSTALL_SUFFIX_V7: tuple[ActivationCommitStepV7, ...] = (
    ActivationCommitStepV7(
        1,
        BIND_LOCK_LEASE,
        FailureDisposition.EXACT_ROLLBACK,
        requires_temporary_approval=False,
        requires_committed_approval=False,
        detail="bind the authoritative transaction lease to its exact held lock inode",
    ),
    ActivationCommitStepV7(
        2,
        PUBLISH_TEMPORARY_APPROVAL,
        FailureDisposition.EXACT_ROLLBACK,
        requires_temporary_approval=False,
        requires_committed_approval=False,
        detail="publish one non-bootable transaction-bound approval",
    ),
    ActivationCommitStepV7(
        3,
        START_MANAGED_SERVICES,
        FailureDisposition.EXACT_ROLLBACK,
        requires_temporary_approval=True,
        requires_committed_approval=False,
        detail="start the route authority and Type=notify CamillaDSP supervisor",
    ),
    ActivationCommitStepV7(
        4,
        VERIFY_SPLIT_BUS_HEALTH,
        FailureDisposition.EXACT_ROLLBACK,
        requires_temporary_approval=True,
        requires_committed_approval=False,
        detail="verify strict split-bus, limiter, DAC and loopback health",
    ),
    ActivationCommitStepV7(
        5,
        RUN_FINITE_MUSIC_PROBE,
        FailureDisposition.EXACT_ROLLBACK,
        requires_temporary_approval=True,
        requires_committed_approval=False,
        detail="run the finite music-lane probe under the held install transaction",
    ),
    ActivationCommitStepV7(
        6,
        RUN_FINITE_ALARM_PROBE,
        FailureDisposition.EXACT_ROLLBACK,
        requires_temporary_approval=True,
        requires_committed_approval=False,
        detail="run the finite independent alarm-lane probe under the held transaction",
    ),
    ActivationCommitStepV7(
        7,
        RESTORE_CAPTURED_APPLICATION_SERVICES,
        FailureDisposition.EXACT_ROLLBACK,
        requires_temporary_approval=True,
        requires_committed_approval=False,
        detail="restore the exact captured Plexamp, AirPlay and dashboard states",
    ),
    ActivationCommitStepV7(
        8,
        VERIFY_SPLIT_BUS_HEALTH,
        FailureDisposition.EXACT_ROLLBACK,
        requires_temporary_approval=True,
        requires_committed_approval=False,
        detail="re-verify split-bus health after captured applications return",
    ),
    ActivationCommitStepV7(
        9,
        VERIFY_DASHBOARD_HEALTH,
        FailureDisposition.EXACT_ROLLBACK,
        requires_temporary_approval=True,
        requires_committed_approval=False,
        detail="verify the restored appliance and dashboard before commit publication",
    ),
    ActivationCommitStepV7(
        10,
        PROMOTE_COMMITTED_APPROVAL,
        FailureDisposition.TERMINAL_PUBLICATION,
        requires_temporary_approval=True,
        requires_committed_approval=False,
        detail=(
            "durably prepare and digest the commit manifest, then atomically publish "
            "the boot-eligible committed approval as the sole commit marker"
        ),
    ),
    ActivationCommitStepV7(
        11,
        RELEASE_PRODUCTION_LOCK,
        FailureDisposition.FORWARD_RECOVERY,
        requires_temporary_approval=False,
        requires_committed_approval=True,
        detail="release the exact production lock after committed publication",
    ),
)


APPROVAL_ROLLBACK_INSERTION_V7: tuple[ActivationCommitStepV7, ...] = (
    ActivationCommitStepV7(
        1,
        REMOVE_TEMPORARY_APPROVAL,
        FailureDisposition.FAIL_CLOSED_RETAIN_LOCK,
        requires_temporary_approval=True,
        requires_committed_approval=False,
        detail=(
            "after managed Stage C shutdown, remove the exact temporary approval "
            "before the existing exact restoration continues"
        ),
    ),
)


_ROLLBACK_DETAILS = {
    STOP_CAPTURED_APPLICATION_SERVICES:
        "stop captured application services, including any restored late in install",
    STOP_MANAGED_SERVICES:
        "stop managed Stage C services before removing temporary approval",
    REMOVE_TEMPORARY_APPROVAL:
        "remove the exact temporary approval and prevent managed restart",
    VERIFY_DAC_RELEASED:
        "prove the DAC and relevant endpoints are released",
    RESTORE_EXACT_SNAPSHOT:
        "restore exact files, absence markers and directory metadata",
    RELOAD_SYSTEMD:
        "reload systemd after exact unit restoration",
    RESTORE_MIXER_STATE:
        "restore all four exact mixer values",
    RESTORE_SERVICE_STATE:
        "restore exact captured load, enabled and active service states",
    VERIFY_EXACT_ROLLBACK:
        "require zero exact-restoration mismatches",
    RELEASE_PRODUCTION_LOCK:
        "release only after exact rollback verification",
}

_BASE_EXACT_ROLLBACK_OPERATIONS = tuple(
    step.operation for step in AUTOMATIC_EXACT_ROLLBACK_PROGRAM.steps
)
_STOP_MANAGED_INDEX = _BASE_EXACT_ROLLBACK_OPERATIONS.index(STOP_MANAGED_SERVICES)
_EXACT_ROLLBACK_OPERATIONS_V7: tuple[ProductionOperationV7, ...] = (
    *_BASE_EXACT_ROLLBACK_OPERATIONS[: _STOP_MANAGED_INDEX + 1],
    REMOVE_TEMPORARY_APPROVAL,
    *_BASE_EXACT_ROLLBACK_OPERATIONS[_STOP_MANAGED_INDEX + 1 :],
)

ACTIVATION_EXACT_ROLLBACK_V7: tuple[ActivationCommitStepV7, ...] = tuple(
    ActivationCommitStepV7(
        position=index,
        operation=operation,
        failure_disposition=FailureDisposition.FAIL_CLOSED_RETAIN_LOCK,
        requires_temporary_approval=operation is REMOVE_TEMPORARY_APPROVAL,
        requires_committed_approval=False,
        detail=_ROLLBACK_DETAILS[operation],
    )
    for index, operation in enumerate(_EXACT_ROLLBACK_OPERATIONS_V7, start=1)
)


@dataclass(frozen=True)
class ActivationCommitPolicySnapshotV7:
    version: int
    physically_proved_prefix: str
    install_suffix_operations: tuple[str, ...]
    rollback_insertion_operations: tuple[str, ...]
    exact_rollback_operations: tuple[str, ...]
    terminal_operation: str
    historical_write_commit_manifest_used: bool
    failure_before_terminal: str
    failure_after_terminal: str
    rollback_step_failure: str

    def __post_init__(self) -> None:
        if self.version != 7:
            raise ValueError("activation commit policy snapshot version mismatch")
        if not self.physically_proved_prefix.strip():
            raise ValueError("activation commit policy requires a proved prefix identity")
        if (
            not self.install_suffix_operations
            or not self.rollback_insertion_operations
            or not self.exact_rollback_operations
        ):
            raise ValueError("activation commit policy sequences must not be empty")
        if self.terminal_operation != PROMOTE_COMMITTED_APPROVAL.value:
            raise ValueError("committed approval promotion must be the terminal marker")
        if self.historical_write_commit_manifest_used:
            raise ValueError("Stage C21 must not expose two independent commit markers")
        if self.failure_before_terminal != FailureDisposition.EXACT_ROLLBACK.value:
            raise ValueError("pre-terminal failure must use exact rollback")
        if self.failure_after_terminal != FailureDisposition.FORWARD_RECOVERY.value:
            raise ValueError("post-terminal failure must recover forward")
        if self.rollback_step_failure != FailureDisposition.FAIL_CLOSED_RETAIN_LOCK.value:
            raise ValueError("rollback-step failure must fail closed and retain the lock")


ACTIVATION_COMMIT_POLICY_V7 = ActivationCommitPolicySnapshotV7(
    version=7,
    physically_proved_prefix="stage-c20-route-selection-and-exact-rollback",
    install_suffix_operations=tuple(
        step.operation.value for step in ACTIVATION_INSTALL_SUFFIX_V7
    ),
    rollback_insertion_operations=tuple(
        step.operation.value for step in APPROVAL_ROLLBACK_INSERTION_V7
    ),
    exact_rollback_operations=tuple(
        step.operation.value for step in ACTIVATION_EXACT_ROLLBACK_V7
    ),
    terminal_operation=PROMOTE_COMMITTED_APPROVAL.value,
    historical_write_commit_manifest_used=False,
    failure_before_terminal=FailureDisposition.EXACT_ROLLBACK.value,
    failure_after_terminal=FailureDisposition.FORWARD_RECOVERY.value,
    rollback_step_failure=FailureDisposition.FAIL_CLOSED_RETAIN_LOCK.value,
)


def _validate_program() -> None:
    install_positions = tuple(step.position for step in ACTIVATION_INSTALL_SUFFIX_V7)
    if install_positions != tuple(range(1, len(ACTIVATION_INSTALL_SUFFIX_V7) + 1)):
        raise RuntimeError("Stage C21 activation suffix positions are not contiguous")
    install_operations = tuple(step.operation for step in ACTIVATION_INSTALL_SUFFIX_V7)
    if not set(install_operations).issubset(set(ALL_OPERATIONS_V7)):
        raise RuntimeError("Stage C21 activation suffix uses an unknown operation")
    duplicated = {
        operation
        for operation in install_operations
        if install_operations.count(operation) > 1
    }
    if duplicated != {VERIFY_SPLIT_BUS_HEALTH}:
        raise RuntimeError("only the two proved split-bus health gates may repeat")
    if install_operations.count(VERIFY_SPLIT_BUS_HEALTH) != 2:
        raise RuntimeError("Stage C21 activation suffix requires two split-bus health gates")
    if WRITE_COMMIT_MANIFEST in install_operations:
        raise RuntimeError("Stage C21 activation suffix contains a second commit marker")
    terminal = tuple(
        step
        for step in ACTIVATION_INSTALL_SUFFIX_V7
        if step.failure_disposition is FailureDisposition.TERMINAL_PUBLICATION
    )
    if len(terminal) != 1 or terminal[0].operation is not PROMOTE_COMMITTED_APPROVAL:
        raise RuntimeError("Stage C21 activation suffix lacks one exact terminal publication")
    terminal_index = ACTIVATION_INSTALL_SUFFIX_V7.index(terminal[0])
    if terminal_index != len(ACTIVATION_INSTALL_SUFFIX_V7) - 2:
        raise RuntimeError("only production-lock release may follow terminal publication")
    if any(
        step.failure_disposition is not FailureDisposition.EXACT_ROLLBACK
        for step in ACTIVATION_INSTALL_SUFFIX_V7[:terminal_index]
    ):
        raise RuntimeError("every pre-terminal activation step must roll back exactly")
    if (
        ACTIVATION_INSTALL_SUFFIX_V7[-1].operation is not RELEASE_PRODUCTION_LOCK
        or ACTIVATION_INSTALL_SUFFIX_V7[-1].failure_disposition
        is not FailureDisposition.FORWARD_RECOVERY
    ):
        raise RuntimeError("post-terminal lock release must use forward recovery")

    if tuple(step.operation for step in APPROVAL_ROLLBACK_INSERTION_V7) != (
        REMOVE_TEMPORARY_APPROVAL,
    ):
        raise RuntimeError("Stage C21 approval rollback insertion changed")
    exact_positions = tuple(step.position for step in ACTIVATION_EXACT_ROLLBACK_V7)
    if exact_positions != tuple(range(1, len(ACTIVATION_EXACT_ROLLBACK_V7) + 1)):
        raise RuntimeError("Stage C21 exact rollback positions are not contiguous")
    expected_exact = (
        *_BASE_EXACT_ROLLBACK_OPERATIONS[: _STOP_MANAGED_INDEX + 1],
        REMOVE_TEMPORARY_APPROVAL,
        *_BASE_EXACT_ROLLBACK_OPERATIONS[_STOP_MANAGED_INDEX + 1 :],
    )
    exact_operations = tuple(step.operation for step in ACTIVATION_EXACT_ROLLBACK_V7)
    if exact_operations != expected_exact:
        raise RuntimeError("Stage C21 exact rollback no longer preserves the proved program")
    if any(
        step.failure_disposition is not FailureDisposition.FAIL_CLOSED_RETAIN_LOCK
        for step in ACTIVATION_EXACT_ROLLBACK_V7
    ):
        raise RuntimeError("every exact rollback failure must retain the production lock")
    if exact_operations[-2:] != (VERIFY_EXACT_ROLLBACK, RELEASE_PRODUCTION_LOCK):
        raise RuntimeError("exact rollback verification and lock release order changed")
    if PROMOTE_COMMITTED_APPROVAL in exact_operations:
        raise RuntimeError("automatic rollback must never promote committed approval")


_validate_program()
