#!/usr/bin/python3
from __future__ import annotations

"""Pure failure simulation for the Stage C21 activation suffix.

This module proves failure ownership around the single committed-approval
terminal marker and the complete proved exact-rollback program with its one
Stage C21 temporary-approval removal insertion. It contains no host adapter,
filesystem access, command execution, CLI or generic dispatch boundary.
"""

from dataclasses import dataclass
from enum import Enum

from .activation_commit_program_v7 import (
    ACTIVATION_EXACT_ROLLBACK_V7,
    ACTIVATION_INSTALL_SUFFIX_V7,
    PROMOTE_COMMITTED_APPROVAL,
    PUBLISH_TEMPORARY_APPROVAL,
    RELEASE_PRODUCTION_LOCK,
    RELOAD_SYSTEMD,
    REMOVE_TEMPORARY_APPROVAL,
    RESTORE_CAPTURED_APPLICATION_SERVICES,
    RESTORE_EXACT_SNAPSHOT,
    RESTORE_MIXER_STATE,
    RESTORE_SERVICE_STATE,
    RUN_FINITE_ALARM_PROBE,
    RUN_FINITE_MUSIC_PROBE,
    START_MANAGED_SERVICES,
    STOP_CAPTURED_APPLICATION_SERVICES,
    STOP_MANAGED_SERVICES,
    VERIFY_DAC_RELEASED,
    VERIFY_DASHBOARD_HEALTH,
    VERIFY_EXACT_ROLLBACK,
    VERIFY_SPLIT_BUS_HEALTH,
)
from .production_adapter_lifecycle_v7 import ProductionOperationV7


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
    exact_snapshot_restored: bool
    mixer_state_restored: bool
    service_state_restored: bool
    exact_previous_installation_restored: bool

    def __post_init__(self) -> None:
        if self.committed_approval_present and self.temporary_approval_present:
            raise ValueError("simulation cannot hold temporary and committed approval together")
        if self.committed_approval_present and self.exact_previous_installation_restored:
            raise ValueError("committed installation cannot also be rolled back")
        if self.exact_previous_installation_restored and self.managed_runtime_running:
            raise ValueError("restored previous installation cannot retain managed runtime")
        if self.exact_previous_installation_restored and not (
            self.exact_snapshot_restored
            and self.mixer_state_restored
            and self.service_state_restored
        ):
            raise ValueError("verified exact rollback requires every restoration component")


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
        "exact_snapshot_restored": False,
        "mixer_state_restored": False,
        "service_state_restored": False,
        "exact_previous_installation_restored": False,
    }


def _frozen_state(state: dict[str, bool]) -> ActivationSimulationStateV7:
    return ActivationSimulationStateV7(**state)


def _apply_install_operation(
    operation: ProductionOperationV7,
    state: dict[str, bool],
) -> None:
    if operation.value == "bind-production-lock-lease":
        if not state["lock_held"]:
            raise RuntimeError("lease binding requires the held transaction lock")
        state["lease_bound"] = True
    elif operation is PUBLISH_TEMPORARY_APPROVAL:
        if not state["lease_bound"] or state["temporary_approval_present"]:
            raise RuntimeError("temporary approval publication precondition failed")
        state["temporary_approval_present"] = True
    elif operation is START_MANAGED_SERVICES:
        if not state["temporary_approval_present"]:
            raise RuntimeError("managed startup requires temporary approval")
        state["managed_runtime_running"] = True
    elif operation is VERIFY_SPLIT_BUS_HEALTH:
        if not state["managed_runtime_running"]:
            raise RuntimeError("split-bus health requires managed runtime")
        state["split_health_verified"] = True
    elif operation in {RUN_FINITE_MUSIC_PROBE, RUN_FINITE_ALARM_PROBE}:
        if not state["managed_runtime_running"] or not state["split_health_verified"]:
            raise RuntimeError("finite probe requires verified managed runtime")
    elif operation is RESTORE_CAPTURED_APPLICATION_SERVICES:
        if not state["split_health_verified"]:
            raise RuntimeError("application restoration requires split health")
        state["applications_restored"] = True
    elif operation is VERIFY_DASHBOARD_HEALTH:
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
        raise RuntimeError(
            f"unsupported fixed activation simulation step: {operation.value}"
        )


def _apply_rollback_operation(
    operation: ProductionOperationV7,
    state: dict[str, bool],
) -> None:
    if operation is STOP_CAPTURED_APPLICATION_SERVICES:
        state["applications_restored"] = False
        state["dashboard_health_verified"] = False
    elif operation is STOP_MANAGED_SERVICES:
        state["managed_runtime_running"] = False
        state["split_health_verified"] = False
    elif operation is REMOVE_TEMPORARY_APPROVAL:
        state["temporary_approval_present"] = False
    elif operation is VERIFY_DAC_RELEASED:
        if state["managed_runtime_running"]:
            raise RuntimeError("DAC release verification requires managed runtime stopped")
    elif operation is RESTORE_EXACT_SNAPSHOT:
        state["exact_snapshot_restored"] = True
    elif operation is RELOAD_SYSTEMD:
        if not state["exact_snapshot_restored"]:
            raise RuntimeError("systemd reload requires exact snapshot restoration")
    elif operation is RESTORE_MIXER_STATE:
        if not state["exact_snapshot_restored"]:
            raise RuntimeError("mixer restoration requires exact snapshot restoration")
        state["mixer_state_restored"] = True
    elif operation is RESTORE_SERVICE_STATE:
        if not state["mixer_state_restored"]:
            raise RuntimeError("service restoration requires mixer restoration")
        state["service_state_restored"] = True
        state["applications_restored"] = True
    elif operation is VERIFY_EXACT_ROLLBACK:
        if not (
            state["exact_snapshot_restored"]
            and state["mixer_state_restored"]
            and state["service_state_restored"]
            and not state["managed_runtime_running"]
            and not state["temporary_approval_present"]
        ):
            raise RuntimeError("exact rollback verification precondition failed")
        state["exact_previous_installation_restored"] = True
    elif operation is RELEASE_PRODUCTION_LOCK:
        if not state["exact_previous_installation_restored"]:
            raise RuntimeError("rollback lock release requires exact verification")
        state["lock_held"] = False
    else:
        raise RuntimeError(f"unsupported exact rollback step: {operation.value}")


def _run_exact_rollback(
    state: dict[str, bool],
    *,
    rollback_fail_at: ProductionOperationV7 | None,
) -> tuple[tuple[str, ...], str | None]:
    trace: list[str] = []
    for step in ACTIVATION_EXACT_ROLLBACK_V7:
        operation = step.operation
        if (
            operation is REMOVE_TEMPORARY_APPROVAL
            and not state["temporary_approval_present"]
        ):
            continue
        trace.append(operation.value)
        if operation is rollback_fail_at:
            return tuple(trace), operation.value
        _apply_rollback_operation(operation, state)
    return tuple(trace), None


def simulate_activation_commit_v7(
    *,
    fail_at: ProductionOperationV7 | None = None,
    rollback_fail_at: ProductionOperationV7 | None = None,
) -> ActivationSimulationResultV7:
    install_operations = tuple(
        step.operation for step in ACTIVATION_INSTALL_SUFFIX_V7
    )
    if fail_at is not None and fail_at not in install_operations:
        raise ValueError("install failure injection is outside the fixed activation suffix")
    valid_rollback_failures = {
        step.operation for step in ACTIVATION_EXACT_ROLLBACK_V7
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
