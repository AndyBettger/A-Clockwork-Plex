#!/usr/bin/python3
from __future__ import annotations

"""Pure Stage C21 terminal activation executor.

The executor consumes the immutable Stage C21 suffix and exact-rollback
programs through one supplied ``ProductionAdapterV7``. It contains no host
adapter, filesystem access, command execution, service helper, CLI or generic
operation lookup.

An adapter exception while publishing temporary or committed approval leaves
approval state indeterminate and therefore fails closed with the production
lock retained. Explicit typed FAIL/BLOCKED results are treated as reconciled
pre-effect failures and retain their declared program disposition.
"""

from dataclasses import dataclass
from enum import Enum
from typing import cast

from .activation_commit_program_v7 import (
    ACTIVATION_EXACT_ROLLBACK_V7,
    ACTIVATION_INSTALL_SUFFIX_V7,
    BIND_LOCK_LEASE,
    PROMOTE_COMMITTED_APPROVAL,
    PUBLISH_TEMPORARY_APPROVAL,
    RELEASE_PRODUCTION_LOCK,
    REMOVE_TEMPORARY_APPROVAL,
    RELOAD_SYSTEMD,
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
from .production_adapter_contract import (
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    AuthoritativeTransaction,
    MixerSnapshot,
    ServiceSnapshot,
    TransactionAction,
)
from .production_adapter_lifecycle_v7 import (
    ActivationApprovalAdapterResult,
    ActivationApprovalLifecycleOperation,
    ActivationApprovalRemovalReceipt,
    CommittedActivationApprovalReceipt,
    ProductionAdapterV7,
    ProductionLockLeaseBindingReceipt,
    ProductionOperationV7,
    TemporaryActivationApprovalReceipt,
)


OperationResultV7 = AdapterResult[object] | ActivationApprovalAdapterResult


class ActivationExecutionPhaseV7(str, Enum):
    INSTALL_SUFFIX = "install-suffix"
    EXACT_ROLLBACK = "exact-rollback"


class ActivationExecutionOutcomeV7(str, Enum):
    COMMITTED = "committed"
    EXACTLY_ROLLED_BACK = "exactly-rolled-back"
    FORWARD_RECOVERY_REQUIRED = "forward-recovery-required"
    FAIL_CLOSED_LOCK_RETAINED = "fail-closed-lock-retained"


class ApprovalKnowledgeV7(str, Enum):
    ABSENT = "absent"
    TEMPORARY = "temporary"
    COMMITTED = "committed"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class ActivationExecutionContextV7:
    transaction: AuthoritativeTransaction
    services: ServiceSnapshot
    mixer: MixerSnapshot

    def __post_init__(self) -> None:
        if self.transaction.action is not TransactionAction.INSTALL:
            raise ValueError("Stage C21 terminal execution requires an install transaction")


@dataclass(frozen=True)
class ActivationExecutionRecordV7:
    sequence: int
    phase: ActivationExecutionPhaseV7
    operation: ProductionOperationV7
    status: AdapterStatus
    detail: str
    exception_type: str | None = None

    def __post_init__(self) -> None:
        if self.sequence <= 0:
            raise ValueError("activation execution record sequence must be positive")
        if not self.detail.strip():
            raise ValueError("activation execution record detail must not be empty")
        if self.exception_type is not None:
            if not self.exception_type.strip():
                raise ValueError("activation execution exception type must not be empty")
            if self.status is AdapterStatus.PASS:
                raise ValueError("an exception record cannot report PASS")


@dataclass(frozen=True)
class ActivationExecutionResultV7:
    outcome: ActivationExecutionOutcomeV7
    records: tuple[ActivationExecutionRecordV7, ...]
    failure_operation: ProductionOperationV7 | None
    rollback_failure_operation: ProductionOperationV7 | None
    approval: ApprovalKnowledgeV7
    exact_rollback_verified: bool
    lock_held: bool

    def __post_init__(self) -> None:
        if not self.records:
            raise ValueError("activation execution must record at least one operation")
        if self.outcome is ActivationExecutionOutcomeV7.COMMITTED:
            if self.failure_operation is not None or self.rollback_failure_operation is not None:
                raise ValueError("committed execution cannot carry a failure")
            if self.approval is not ApprovalKnowledgeV7.COMMITTED:
                raise ValueError("committed execution requires committed approval")
            if self.exact_rollback_verified or self.lock_held:
                raise ValueError("committed execution must be unlocked and not rolled back")
        elif self.outcome is ActivationExecutionOutcomeV7.EXACTLY_ROLLED_BACK:
            if self.failure_operation is None or self.rollback_failure_operation is not None:
                raise ValueError("exact rollback result has invalid failure identities")
            if self.approval is not ApprovalKnowledgeV7.ABSENT:
                raise ValueError("completed exact rollback requires approval absence")
            if not self.exact_rollback_verified or self.lock_held:
                raise ValueError("completed exact rollback must be verified and unlocked")
        elif self.outcome is ActivationExecutionOutcomeV7.FORWARD_RECOVERY_REQUIRED:
            if self.failure_operation is not RELEASE_PRODUCTION_LOCK:
                raise ValueError("only post-commit lock release may recover forward")
            if self.rollback_failure_operation is not None:
                raise ValueError("forward recovery must not run exact rollback")
            if self.approval is not ApprovalKnowledgeV7.COMMITTED or not self.lock_held:
                raise ValueError("forward recovery requires committed approval and held lock")
            if self.exact_rollback_verified:
                raise ValueError("forward recovery cannot report exact rollback")
        elif self.outcome is ActivationExecutionOutcomeV7.FAIL_CLOSED_LOCK_RETAINED:
            if self.failure_operation is None or not self.lock_held:
                raise ValueError("fail-closed execution requires a failure and held lock")


_EXPECTED_APPROVAL_PAYLOAD = {
    BIND_LOCK_LEASE: ProductionLockLeaseBindingReceipt,
    PUBLISH_TEMPORARY_APPROVAL: TemporaryActivationApprovalReceipt,
    REMOVE_TEMPORARY_APPROVAL: ActivationApprovalRemovalReceipt,
    PROMOTE_COMMITTED_APPROVAL: CommittedActivationApprovalReceipt,
}


def _transaction(context: ActivationExecutionContextV7):
    return context.transaction.transaction


def _invoke_install_operation(
    adapter: ProductionAdapterV7,
    operation: ProductionOperationV7,
    context: ActivationExecutionContextV7,
) -> OperationResultV7:
    transaction = _transaction(context)
    match operation:
        case ActivationApprovalLifecycleOperation.BIND_PRODUCTION_LOCK_LEASE:
            result = adapter.bind_production_lock_lease(transaction)
        case ActivationApprovalLifecycleOperation.PUBLISH_TEMPORARY_ACTIVATION_APPROVAL:
            result = adapter.publish_temporary_activation_approval(transaction)
        case AdapterOperation.START_MANAGED_STAGE_C_SERVICES:
            result = adapter.start_managed_stage_c_services(transaction)
        case AdapterOperation.VERIFY_SPLIT_BUS_HEALTH:
            result = adapter.verify_split_bus_health(transaction)
        case AdapterOperation.RUN_FINITE_MUSIC_PROBE:
            result = adapter.run_finite_music_probe(transaction)
        case AdapterOperation.RUN_FINITE_ALARM_PROBE:
            result = adapter.run_finite_alarm_probe(transaction)
        case AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES:
            result = adapter.restore_captured_application_services(
                transaction,
                context.services,
            )
        case AdapterOperation.VERIFY_DASHBOARD_HEALTH:
            result = adapter.verify_dashboard_health(transaction)
        case ActivationApprovalLifecycleOperation.PROMOTE_COMMITTED_ACTIVATION_APPROVAL:
            result = adapter.promote_committed_activation_approval(transaction)
        case AdapterOperation.RELEASE_PRODUCTION_LOCK:
            result = adapter.release_production_lock()
        case _:
            raise ValueError(
                f"operation is outside the fixed Stage C21 install suffix: {operation.value}"
            )
    return cast(OperationResultV7, result)


def _invoke_rollback_operation(
    adapter: ProductionAdapterV7,
    operation: ProductionOperationV7,
    context: ActivationExecutionContextV7,
) -> OperationResultV7:
    transaction = _transaction(context)
    match operation:
        case AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES:
            result = adapter.stop_captured_application_services(
                transaction,
                context.services,
            )
        case AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES:
            result = adapter.stop_managed_stage_c_services(transaction)
        case ActivationApprovalLifecycleOperation.REMOVE_TEMPORARY_ACTIVATION_APPROVAL:
            result = adapter.remove_temporary_activation_approval(transaction)
        case AdapterOperation.VERIFY_DAC_RELEASED:
            result = adapter.verify_dac_released(transaction)
        case AdapterOperation.RESTORE_EXACT_SNAPSHOT:
            result = adapter.restore_exact_snapshot(
                transaction,
                context.transaction.snapshot,
            )
        case AdapterOperation.RELOAD_SYSTEMD:
            result = adapter.reload_systemd(transaction)
        case AdapterOperation.RESTORE_MIXER_STATE:
            result = adapter.restore_mixer_state(transaction, context.mixer)
        case AdapterOperation.RESTORE_SERVICE_STATE:
            result = adapter.restore_service_state(transaction, context.services)
        case AdapterOperation.VERIFY_EXACT_ROLLBACK:
            result = adapter.verify_exact_rollback(
                transaction,
                context.transaction.snapshot,
            )
        case AdapterOperation.RELEASE_PRODUCTION_LOCK:
            result = adapter.release_production_lock()
        case _:
            raise ValueError(
                f"operation is outside the fixed Stage C21 exact rollback: {operation.value}"
            )
    return cast(OperationResultV7, result)


def _validate_result(
    expected_operation: ProductionOperationV7,
    result: OperationResultV7,
) -> None:
    if result.operation is not expected_operation:
        raise ValueError(
            "adapter returned a receipt for a different operation: "
            f"expected {expected_operation.value}, observed {result.operation.value}"
        )
    expected_payload = _EXPECTED_APPROVAL_PAYLOAD.get(expected_operation)
    if expected_payload is not None:
        if not isinstance(result, ActivationApprovalAdapterResult):
            raise ValueError("approval operation returned an ordinary adapter result")
        if result.status is AdapterStatus.PASS and not isinstance(
            result.payload,
            expected_payload,
        ):
            raise ValueError("successful approval operation omitted its exact typed receipt")
    else:
        if not isinstance(result, AdapterResult):
            raise ValueError("ordinary operation returned an approval adapter result")
        if result.payload is not None:
            raise ValueError("receipt-only ordinary operation returned a payload")


def _append_result_record(
    records: list[ActivationExecutionRecordV7],
    phase: ActivationExecutionPhaseV7,
    operation: ProductionOperationV7,
    result: OperationResultV7,
) -> None:
    records.append(
        ActivationExecutionRecordV7(
            sequence=len(records) + 1,
            phase=phase,
            operation=operation,
            status=result.status,
            detail=result.detail,
        )
    )


def _append_exception_record(
    records: list[ActivationExecutionRecordV7],
    phase: ActivationExecutionPhaseV7,
    operation: ProductionOperationV7,
    error: BaseException,
) -> None:
    records.append(
        ActivationExecutionRecordV7(
            sequence=len(records) + 1,
            phase=phase,
            operation=operation,
            status=AdapterStatus.FAIL,
            detail=str(error).strip() or "adapter raised without detail",
            exception_type=type(error).__name__,
        )
    )


def _fail_closed(
    *,
    records: list[ActivationExecutionRecordV7],
    failure_operation: ProductionOperationV7,
    rollback_failure_operation: ProductionOperationV7 | None,
    approval: ApprovalKnowledgeV7,
    exact_rollback_verified: bool = False,
) -> ActivationExecutionResultV7:
    return ActivationExecutionResultV7(
        outcome=ActivationExecutionOutcomeV7.FAIL_CLOSED_LOCK_RETAINED,
        records=tuple(records),
        failure_operation=failure_operation,
        rollback_failure_operation=rollback_failure_operation,
        approval=approval,
        exact_rollback_verified=exact_rollback_verified,
        lock_held=True,
    )


def _run_exact_rollback(
    adapter: ProductionAdapterV7,
    context: ActivationExecutionContextV7,
    records: list[ActivationExecutionRecordV7],
    *,
    failure_operation: ProductionOperationV7,
    approval: ApprovalKnowledgeV7,
) -> ActivationExecutionResultV7:
    exact_verified = False
    for step in ACTIVATION_EXACT_ROLLBACK_V7:
        operation = step.operation
        if (
            operation is REMOVE_TEMPORARY_APPROVAL
            and approval is ApprovalKnowledgeV7.ABSENT
        ):
            continue
        try:
            result = _invoke_rollback_operation(adapter, operation, context)
            _validate_result(operation, result)
        except BaseException as exc:
            _append_exception_record(
                records,
                ActivationExecutionPhaseV7.EXACT_ROLLBACK,
                operation,
                exc,
            )
            return _fail_closed(
                records=records,
                failure_operation=failure_operation,
                rollback_failure_operation=operation,
                approval=approval,
                exact_rollback_verified=exact_verified,
            )
        _append_result_record(
            records,
            ActivationExecutionPhaseV7.EXACT_ROLLBACK,
            operation,
            result,
        )
        if result.status is not AdapterStatus.PASS:
            return _fail_closed(
                records=records,
                failure_operation=failure_operation,
                rollback_failure_operation=operation,
                approval=approval,
                exact_rollback_verified=exact_verified,
            )
        if operation is REMOVE_TEMPORARY_APPROVAL:
            approval = ApprovalKnowledgeV7.ABSENT
        elif operation is VERIFY_EXACT_ROLLBACK:
            exact_verified = True
        elif operation is RELEASE_PRODUCTION_LOCK:
            return ActivationExecutionResultV7(
                outcome=ActivationExecutionOutcomeV7.EXACTLY_ROLLED_BACK,
                records=tuple(records),
                failure_operation=failure_operation,
                rollback_failure_operation=None,
                approval=ApprovalKnowledgeV7.ABSENT,
                exact_rollback_verified=exact_verified,
                lock_held=False,
            )
    raise RuntimeError("Stage C21 exact rollback ended without lock release")


def execute_activation_commit_v7(
    adapter: ProductionAdapterV7,
    context: ActivationExecutionContextV7,
) -> ActivationExecutionResultV7:
    """Execute only the fixed terminal suffix for an existing held transaction."""

    if not isinstance(adapter, ProductionAdapterV7):
        raise TypeError("Stage C21 terminal executor requires ProductionAdapterV7")

    records: list[ActivationExecutionRecordV7] = []
    approval = ApprovalKnowledgeV7.ABSENT
    for step in ACTIVATION_INSTALL_SUFFIX_V7:
        operation = step.operation
        try:
            result = _invoke_install_operation(adapter, operation, context)
            _validate_result(operation, result)
        except BaseException as exc:
            _append_exception_record(
                records,
                ActivationExecutionPhaseV7.INSTALL_SUFFIX,
                operation,
                exc,
            )
            if operation in {
                PUBLISH_TEMPORARY_APPROVAL,
                PROMOTE_COMMITTED_APPROVAL,
            }:
                return _fail_closed(
                    records=records,
                    failure_operation=operation,
                    rollback_failure_operation=None,
                    approval=ApprovalKnowledgeV7.INDETERMINATE,
                )
            if operation is RELEASE_PRODUCTION_LOCK and approval is ApprovalKnowledgeV7.COMMITTED:
                return ActivationExecutionResultV7(
                    outcome=ActivationExecutionOutcomeV7.FORWARD_RECOVERY_REQUIRED,
                    records=tuple(records),
                    failure_operation=operation,
                    rollback_failure_operation=None,
                    approval=approval,
                    exact_rollback_verified=False,
                    lock_held=True,
                )
            return _run_exact_rollback(
                adapter,
                context,
                records,
                failure_operation=operation,
                approval=approval,
            )

        _append_result_record(
            records,
            ActivationExecutionPhaseV7.INSTALL_SUFFIX,
            operation,
            result,
        )
        if result.status is not AdapterStatus.PASS:
            if operation is RELEASE_PRODUCTION_LOCK and approval is ApprovalKnowledgeV7.COMMITTED:
                return ActivationExecutionResultV7(
                    outcome=ActivationExecutionOutcomeV7.FORWARD_RECOVERY_REQUIRED,
                    records=tuple(records),
                    failure_operation=operation,
                    rollback_failure_operation=None,
                    approval=approval,
                    exact_rollback_verified=False,
                    lock_held=True,
                )
            return _run_exact_rollback(
                adapter,
                context,
                records,
                failure_operation=operation,
                approval=approval,
            )

        if operation is PUBLISH_TEMPORARY_APPROVAL:
            approval = ApprovalKnowledgeV7.TEMPORARY
        elif operation is PROMOTE_COMMITTED_APPROVAL:
            approval = ApprovalKnowledgeV7.COMMITTED
        elif operation is RELEASE_PRODUCTION_LOCK:
            return ActivationExecutionResultV7(
                outcome=ActivationExecutionOutcomeV7.COMMITTED,
                records=tuple(records),
                failure_operation=None,
                rollback_failure_operation=None,
                approval=approval,
                exact_rollback_verified=False,
                lock_held=False,
            )

    raise RuntimeError("Stage C21 activation suffix ended without lock release")
