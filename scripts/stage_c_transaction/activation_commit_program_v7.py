#!/usr/bin/python3
from __future__ import annotations

"""Static Stage C21 activation suffix and terminal commit policy.

The historical v1 through v6 programs remain unchanged. This module defines
only the fixed suffix that follows the physically proved C20 prefix, plus the
exact approval-removal insertion required by automatic rollback.

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

from .production_adapter_lifecycle_v7 import (
    ALL_OPERATIONS_V7,
    ActivationApprovalLifecycleOperation,
    ProductionOperationV7,
)


class FailureDisposition(str, Enum):
    EXACT_ROLLBACK = "exact-rollback"
    TERMINAL_PUBLICATION = "terminal-publication"
    FORWARD_RECOVERY = "forward-recovery"


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


def _fixed_operation(value: str) -> ProductionOperationV7:
    matches = tuple(operation for operation in ALL_OPERATIONS_V7 if operation.value == value)
    if len(matches) != 1:
        raise RuntimeError(f"fixed Stage C21 operation identity is unavailable: {value}")
    return matches[0]


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
START_MANAGED_SERVICES = _fixed_operation("start-managed-stage-c-services")
OPEN_MUSIC_PROBE = _fixed_operation("open-music-probe")
OPEN_ALARM_PROBE = _fixed_operation("open-alarm-probe")
VERIFY_POST_START_HEALTH = _fixed_operation("verify-post-start-health")
RESTORE_APPLICATION_SERVICES = _fixed_operation("restore-application-services")
VERIFY_DASHBOARD_HEALTH = _fixed_operation("verify-dashboard-health")
RELEASE_PRODUCTION_LOCK = _fixed_operation("release-production-lock")
STOP_MANAGED_SERVICES = _fixed_operation("stop-managed-stage-c-services")
RESTORE_PREVIOUS_INSTALLATION = _fixed_operation("restore-previous-installation")
WRITE_COMMIT_MANIFEST = _fixed_operation("write-commit-manifest")


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
        OPEN_MUSIC_PROBE,
        FailureDisposition.EXACT_ROLLBACK,
        requires_temporary_approval=True,
        requires_committed_approval=False,
        detail="run the finite music-lane probe under the held install transaction",
    ),
    ActivationCommitStepV7(
        5,
        OPEN_ALARM_PROBE,
        FailureDisposition.EXACT_ROLLBACK,
        requires_temporary_approval=True,
        requires_committed_approval=False,
        detail="run the finite independent alarm-lane probe under the held transaction",
    ),
    ActivationCommitStepV7(
        6,
        VERIFY_POST_START_HEALTH,
        FailureDisposition.EXACT_ROLLBACK,
        requires_temporary_approval=True,
        requires_committed_approval=False,
        detail="verify strict split-bus, limiter, DAC and loopback health",
    ),
    ActivationCommitStepV7(
        7,
        RESTORE_APPLICATION_SERVICES,
        FailureDisposition.EXACT_ROLLBACK,
        requires_temporary_approval=True,
        requires_committed_approval=False,
        detail="restore the exact captured Plexamp, AirPlay and dashboard states",
    ),
    ActivationCommitStepV7(
        8,
        VERIFY_DASHBOARD_HEALTH,
        FailureDisposition.EXACT_ROLLBACK,
        requires_temporary_approval=True,
        requires_committed_approval=False,
        detail="verify the restored appliance and dashboard before commit publication",
    ),
    ActivationCommitStepV7(
        9,
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
        10,
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
        STOP_MANAGED_SERVICES,
        FailureDisposition.EXACT_ROLLBACK,
        requires_temporary_approval=False,
        requires_committed_approval=False,
        detail="stop any partially started Stage C runtime before approval removal",
    ),
    ActivationCommitStepV7(
        2,
        REMOVE_TEMPORARY_APPROVAL,
        FailureDisposition.EXACT_ROLLBACK,
        requires_temporary_approval=True,
        requires_committed_approval=False,
        detail="remove the exact temporary approval and prevent managed restart",
    ),
    ActivationCommitStepV7(
        3,
        RESTORE_PREVIOUS_INSTALLATION,
        FailureDisposition.EXACT_ROLLBACK,
        requires_temporary_approval=False,
        requires_committed_approval=False,
        detail="continue the existing exact route, file, manager and service restoration",
    ),
)


@dataclass(frozen=True)
class ActivationCommitPolicySnapshotV7:
    version: int
    physically_proved_prefix: str
    install_suffix_operations: tuple[str, ...]
    rollback_insertion_operations: tuple[str, ...]
    terminal_operation: str
    historical_write_commit_manifest_used: bool
    failure_before_terminal: str
    failure_after_terminal: str

    def __post_init__(self) -> None:
        if self.version != 7:
            raise ValueError("activation commit policy snapshot version mismatch")
        if not self.physically_proved_prefix.strip():
            raise ValueError("activation commit policy requires a proved prefix identity")
        if not self.install_suffix_operations or not self.rollback_insertion_operations:
            raise ValueError("activation commit policy sequences must not be empty")
        if self.terminal_operation != PROMOTE_COMMITTED_APPROVAL.value:
            raise ValueError("committed approval promotion must be the terminal marker")
        if self.historical_write_commit_manifest_used:
            raise ValueError("Stage C21 must not expose two independent commit markers")
        if self.failure_before_terminal != FailureDisposition.EXACT_ROLLBACK.value:
            raise ValueError("pre-terminal failure must use exact rollback")
        if self.failure_after_terminal != FailureDisposition.FORWARD_RECOVERY.value:
            raise ValueError("post-terminal failure must recover forward")


ACTIVATION_COMMIT_POLICY_V7 = ActivationCommitPolicySnapshotV7(
    version=7,
    physically_proved_prefix="stage-c20-route-selection-and-exact-rollback",
    install_suffix_operations=tuple(
        step.operation.value for step in ACTIVATION_INSTALL_SUFFIX_V7
    ),
    rollback_insertion_operations=tuple(
        step.operation.value for step in APPROVAL_ROLLBACK_INSERTION_V7
    ),
    terminal_operation=PROMOTE_COMMITTED_APPROVAL.value,
    historical_write_commit_manifest_used=False,
    failure_before_terminal=FailureDisposition.EXACT_ROLLBACK.value,
    failure_after_terminal=FailureDisposition.FORWARD_RECOVERY.value,
)


def _validate_program() -> None:
    positions = tuple(step.position for step in ACTIVATION_INSTALL_SUFFIX_V7)
    if positions != tuple(range(1, len(ACTIVATION_INSTALL_SUFFIX_V7) + 1)):
        raise RuntimeError("Stage C21 activation suffix positions are not contiguous")
    operations = tuple(step.operation for step in ACTIVATION_INSTALL_SUFFIX_V7)
    if len(operations) != len(set(operations)):
        raise RuntimeError("Stage C21 activation suffix contains duplicate operations")
    if WRITE_COMMIT_MANIFEST in operations:
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
    rollback_values = tuple(
        step.operation.value for step in APPROVAL_ROLLBACK_INSERTION_V7
    )
    if rollback_values != (
        "stop-managed-stage-c-services",
        REMOVE_TEMPORARY_APPROVAL.value,
        "restore-previous-installation",
    ):
        raise RuntimeError("Stage C21 approval rollback insertion order changed")
    if any(step.operation is PROMOTE_COMMITTED_APPROVAL for step in APPROVAL_ROLLBACK_INSERTION_V7):
        raise RuntimeError("automatic rollback must never promote committed approval")


_validate_program()
