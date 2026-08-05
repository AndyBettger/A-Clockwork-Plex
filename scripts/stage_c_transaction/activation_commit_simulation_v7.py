#!/usr/bin/python3
from __future__ import annotations

"""Pure failure simulation for the Stage C21 activation suffix.

This module proves failure ownership around the single committed-approval
terminal marker. It contains no host adapter, filesystem access, command
execution, CLI or generic dispatch boundary.
"""

from dataclasses import dataclass
from enum import Enum

from .activation_commit_program_v7 import (
    ACTIVATION_INSTALL_SUFFIX_V7,
    PROMOTE_COMMITTED_APPROVAL,
    PUBLISH_TEMPORARY_APPROVAL,
    RELEASE_PRODUCTION_LOCK,
    REMOVE_TEMPORARY_APPROVAL,
    RESTORE_PREVIOUS_INSTALLATION,
    STOP_MANAGED_SERVICES,
)
from .production_adapter_lifecycle_v7 import (
    ALL_OPERATIONS_V7,
    ProductionOperationV7,
)


class ActivationSimulationStatus(str, Enum):
    PASS = "pass"
    EXACTLY_ROLLED_BACK = "exactly-rolled-back"
    FORWARD_RECOVERY_REQUIRED = "forward-recovery-required"
    ROLLBACK_FAILED_LOCK_RETAINED = "rollback-failed-lock-retained"


@dataclass(frozen=True)
class ActivationSimulationStateV7:
    lock_held: bool
    lease_bound: bool
    temporary_approval_present: bool
    managed_runtime_running: bool
    applications_restored: bool
    split_health_verified: bool
    dashboard_health_verified: bool
    committed_approval_present: bool
    exact_previous_installation_restored: bool

    def __post_init__(self) -> None:
        if self.committed_approval_present and self.temporary_approval_present:
            raise ValueError("simulation cannot hold temporary and committed approval together")
        if self.committed_approval_present and self.exact_previous_installation_restored:
            raise ValueError("committed installation cannot also be rolled back")
        if self.exact_previous_installation_restored and self.managed_runtime_running:
            raise ValueError("restored previous installation cannot retain managed runtime")


@dataclass(frozen=True)
class ActivationSimulationResultV7:
    status: ActivationSimulationStatus
    attempted_operations: tuple[str, ...]
    rollback_operations: tuple[str, ...]
    failed_operation: str | None
    rollback_failed_operation: str | None
    final_state: ActivationSimulationStateV7

    def __post_init__(self) -> None:
        if not self.attempted_operations:
            raise ValueError("activation simulation must attempt at least one operation")
        if self.status is ActivationSimulationStatus.PASS:
            if self.failed_operation is not None or self.rollback_failed_operation is not None:
                raise ValueError("successful simulation cannot carry failure identities")
            if not self.final_state.committed_approval_present:
                raise ValueError("successful simulation requires committed approval")
            if self.final_state.lock_held:
                raise ValueError("successful simulation must release the lock")
            if self.rollback_operations:
                raise ValueError("successful simulation must not run rollback")
        elif self.status is ActivationSimulationStatus.EXACTLY_ROLLED_BACK:
            if self.failed_operation is None or self.rollback_failed_operation is not None:
                raise ValueError("exact rollback result has invalid failure identities")
            if not self.final_state.exact_previous_installation_restored:
                raise ValueError("exact rollback result must restore the previous installation")
            if self.final_state.lock_held:
                raise ValueError("completed exact rollback must release the lock")
            if self.final_state.temporary_approval_present:
                raise ValueError("completed exact rollback must remove temporary approval")
        elif self.status is ActivationSimulationStatus.FORWARD_RECOVERY_REQUIRED:
            if self.failed_operation != RELEASE_PRODUCTION_LOCK.value:
                raise ValueError("only post-commit lock release may require forward recovery")
            if not self.final_state.committed_approval_present:
                raise ValueError("forward recovery requires committed approval")
            if not self.final_state.lock_held:
                raise ValueError("failed post-commit release must retain the lock")
            if self.rollback_operations:
                raise ValueError("post-commit forward recovery must never run rollback")
        elif self.status is ActivationSimulationStatus.ROLLBACK_FAILED_LOCK_RETAINED:
            if self.failed_operation is None or self.rollback_failed_operation is None:
                raise ValueError("rollback-failure result requires both failure identities")
            if not self.final_state.lock_held:
                raise ValueError("failed rollback must retain the lock")
            if self.final_state.committed_approval_present:
                raise ValueError("failed pre-terminal rollback cannot invent committed state")


def _fixed_operation(value: str) -> ProductionOperationV7:
    matches = tuple(operation for operation in ALL_OPERATIONS_V7 if operation.value == value)
    if len(matches) != 1:
        raise RuntimeError(f"fixed simulation operation is unavailable: {value}")
    return matches[0]


VERIFY_EXACT_RESTORATION = _fixed_operation("verify-exact-restoration")


def _initial_state() -> dict[str, bool]:
    return {
        "lock_held": True,
        "lease_bound": False,
        "temporary_approval_present": False,
        "managed_runtime_running": False,
        "applications_restored": False,
        "split_health_verified": False,
        "dashboard_health_verified": False,
        "committed_approval_present": False,
        "exact_previous_installation_restored": False,
    }


def _frozen_state(state: dict[str, bool]) -> ActivationSimulationStateV7:
    return ActivationSimulationStateV7(**state)


def _apply_install_operation(
    operation: ProductionOperationV7,
    state: dict[str, bool],
) -> None:
    value = operation.value
    if value == "bind-production-lock-lease":
        if not state["lock_held"]:
            raise RuntimeError("lease binding requires the held transaction lock")
        state["lease_bound"] = True
    elif operation is PUBLISH_TEMPORARY_APPROVAL:
        if not state["lease_bound"] or state["temporary_approval_present"]:
            raise RuntimeError("temporary approval publication precondition failed")
        state["temporary_approval_present"] = True
    elif value == "start-managed-stage-c-services":
        if not state["temporary_approval_present"]:
            raise RuntimeError("managed startup requires temporary approval")
        state["managed_runtime_running"] = True
    elif value in {"open-music-probe", "open-alarm-probe"}:
        if not state["managed_runtime_running"]:
            raise RuntimeError("finite probe requires managed runtime")
    elif value == "verify-post-start-health":
        if not state["managed_runtime_running"]:
            raise RuntimeError("post-start health requires managed runtime")
        state["split_health_verified"] = True
    elif value == "restore-application-services":
        if not state["split_health_verified"]:
            raise RuntimeError("application restoration requires split health")
        state["applications_restored"] = True
    elif value == "verify-dashboard-health":
        if not state["applications_restored"]:
            raise RuntimeError("dashboard health requires restored applications")
        state["dashboard_health_verified"] = True
    elif operation is PROMOTE_COMMITTED_APPROVAL:
        if not (
            state["temporary_approval_present"]
            and state["split_health_verified"]
            and state["dashboard_health_verified"]
        ):
            raise RuntimeError("terminal promotion precondition failed")
        state["temporary_approval_present"] = False
        state["committed_approval_present"] = True
    elif operation is RELEASE_PRODUCTION_LOCK:
        if not state["committed_approval_present"]:
            raise RuntimeError("normal lock release requires committed approval")
        state["lock_held"] = False
    else:
        raise RuntimeError(f"unsupported fixed activation simulation step: {value}")


def _run_exact_rollback(
    state: dict[str, bool],
    *,
    rollback_fail_at: ProductionOperationV7 | None,
) -> tuple[tuple[str, ...], str | None]:
    trace: list[str] = []

    def attempt(operation: ProductionOperationV7) -> bool:
        trace.append(operation.value)
        return operation is rollback_fail_at

    if attempt(STOP_MANAGED_SERVICES):
        return tuple(trace), STOP_MANAGED_SERVICES.value
    state["managed_runtime_running"] = False

    if state["temporary_approval_present"]:
        if attempt(REMOVE_TEMPORARY_APPROVAL):
            return tuple(trace), REMOVE_TEMPORARY_APPROVAL.value
        state["temporary_approval_present"] = False

    if attempt(RESTORE_PREVIOUS_INSTALLATION):
        return tuple(trace), RESTORE_PREVIOUS_INSTALLATION.value
    state["lease_bound"] = False
    state["applications_restored"] = True
    state["split_health_verified"] = False
    state["dashboard_health_verified"] = False
    state["exact_previous_installation_restored"] = True

    if attempt(VERIFY_EXACT_RESTORATION):
        return tuple(trace), VERIFY_EXACT_RESTORATION.value

    if attempt(RELEASE_PRODUCTION_LOCK):
        return tuple(trace), RELEASE_PRODUCTION_LOCK.value
    state["lock_held"] = False
    return tuple(trace), None


def simulate_activation_commit_v7(
    *,
    fail_at: ProductionOperationV7 | None = None,
    rollback_fail_at: ProductionOperationV7 | None = None,
) -> ActivationSimulationResultV7:
    if fail_at is not None and fail_at not in tuple(
        step.operation for step in ACTIVATION_INSTALL_SUFFIX_V7
    ):
        raise ValueError("install failure injection is outside the fixed activation suffix")
    valid_rollback_failures = {
        STOP_MANAGED_SERVICES,
        REMOVE_TEMPORARY_APPROVAL,
        RESTORE_PREVIOUS_INSTALLATION,
        VERIFY_EXACT_RESTORATION,
        RELEASE_PRODUCTION_LOCK,
    }
    if rollback_fail_at is not None and rollback_fail_at not in valid_rollback_failures:
        raise ValueError("rollback failure injection is outside the fixed exact rollback")
    if fail_at is None and rollback_fail_at is not None:
        raise ValueError("rollback failure injection requires an install failure")

    state = _initial_state()
    attempted: list[str] = []
    for step in ACTIVATION_INSTALL_SUFFIX_V7:
        operation = step.operation
        attempted.append(operation.value)
        if operation is fail_at:
            if operation is RELEASE_PRODUCTION_LOCK:
                return ActivationSimulationResultV7(
                    status=ActivationSimulationStatus.FORWARD_RECOVERY_REQUIRED,
                    attempted_operations=tuple(attempted),
                    rollback_operations=(),
                    failed_operation=operation.value,
                    rollback_failed_operation=None,
                    final_state=_frozen_state(state),
                )
            rollback, rollback_failure = _run_exact_rollback(
                state,
                rollback_fail_at=rollback_fail_at,
            )
            return ActivationSimulationResultV7(
                status=(
                    ActivationSimulationStatus.ROLLBACK_FAILED_LOCK_RETAINED
                    if rollback_failure is not None
                    else ActivationSimulationStatus.EXACTLY_ROLLED_BACK
                ),
                attempted_operations=tuple(attempted),
                rollback_operations=rollback,
                failed_operation=operation.value,
                rollback_failed_operation=rollback_failure,
                final_state=_frozen_state(state),
            )
        _apply_install_operation(operation, state)

    return ActivationSimulationResultV7(
        status=ActivationSimulationStatus.PASS,
        attempted_operations=tuple(attempted),
        rollback_operations=(),
        failed_operation=None,
        rollback_failed_operation=None,
        final_state=_frozen_state(state),
    )
