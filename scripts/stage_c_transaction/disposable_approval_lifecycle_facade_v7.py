#!/usr/bin/python3
from __future__ import annotations

"""Thin disposable Stage C21 approval lifecycle coordinator.

This module performs no filesystem mutation. It only restricts the order in
which the already-proved disposable lease binder, temporary publisher,
temporary remover and committed promoter may be invoked. Every underlying
result is returned unchanged inside a frozen lifecycle event.
"""

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

from .approval_record_plan_v7 import (
    CommittedApprovalRecordPlanV7,
    TemporaryApprovalRecordPlanV7,
)
from .disposable_approval_root_v7 import DisposableApprovalRootV7
from .disposable_c20_lock_owner_v7 import DisposableC20LockOwnerV7
from .disposable_canonical_lease_binder_v7 import (
    DisposableCanonicalLeaseBinderV7,
    DisposableCanonicalLeaseBindingResultV7,
    DisposableLeaseBindingDispositionV7,
)
from .disposable_committed_approval_promoter_v7 import (
    DisposableCommittedApprovalPromoterV7,
    DisposableCommittedApprovalPromotionResultV7,
    DisposableCommittedPromotionDispositionV7,
)
from .disposable_temporary_approval_publisher_v7 import (
    DisposableTemporaryApprovalPublicationResultV7,
    DisposableTemporaryApprovalPublisherV7,
    DisposableTemporaryPublicationDispositionV7,
)
from .disposable_temporary_approval_remover_v7 import (
    DisposableTemporaryApprovalRemovalResultV7,
    DisposableTemporaryApprovalRemoverV7,
    DisposableTemporaryRemovalDispositionV7,
)
from .production_adapter_contract import AdapterStatus


LifecycleUnderlyingResultV7: TypeAlias = (
    DisposableCanonicalLeaseBindingResultV7
    | DisposableTemporaryApprovalPublicationResultV7
    | DisposableTemporaryApprovalRemovalResultV7
    | DisposableCommittedApprovalPromotionResultV7
)


class DisposableApprovalLifecycleOrderError(RuntimeError):
    """An operation was requested outside its single permitted phase."""


class DisposableApprovalLifecycleOperationV7(str, Enum):
    BIND_CANONICAL_LEASE = "bind-canonical-lease"
    PUBLISH_TEMPORARY = "publish-temporary"
    REMOVE_TEMPORARY = "remove-temporary"
    PROMOTE_COMMITTED = "promote-committed"


class DisposableApprovalLifecyclePhaseV7(str, Enum):
    OWNER_HELD_EMPTY = "owner-held-empty"
    LEASE_BOUND = "lease-bound"
    TEMPORARY_PUBLISHED = "temporary-published"
    TEMPORARY_REMOVED = "temporary-removed"
    COMMITTED = "committed"
    RECOVERY_REQUIRED = "recovery-required"


_EXPECTED_RESULT_TYPES = {
    DisposableApprovalLifecycleOperationV7.BIND_CANONICAL_LEASE: (
        DisposableCanonicalLeaseBindingResultV7
    ),
    DisposableApprovalLifecycleOperationV7.PUBLISH_TEMPORARY: (
        DisposableTemporaryApprovalPublicationResultV7
    ),
    DisposableApprovalLifecycleOperationV7.REMOVE_TEMPORARY: (
        DisposableTemporaryApprovalRemovalResultV7
    ),
    DisposableApprovalLifecycleOperationV7.PROMOTE_COMMITTED: (
        DisposableCommittedApprovalPromotionResultV7
    ),
}


_ALLOWED_BEFORE = {
    DisposableApprovalLifecycleOperationV7.BIND_CANONICAL_LEASE: (
        DisposableApprovalLifecyclePhaseV7.OWNER_HELD_EMPTY
    ),
    DisposableApprovalLifecycleOperationV7.PUBLISH_TEMPORARY: (
        DisposableApprovalLifecyclePhaseV7.LEASE_BOUND
    ),
    DisposableApprovalLifecycleOperationV7.REMOVE_TEMPORARY: (
        DisposableApprovalLifecyclePhaseV7.TEMPORARY_PUBLISHED
    ),
    DisposableApprovalLifecycleOperationV7.PROMOTE_COMMITTED: (
        DisposableApprovalLifecyclePhaseV7.TEMPORARY_PUBLISHED
    ),
}


_SUCCESS_AFTER = {
    DisposableApprovalLifecycleOperationV7.BIND_CANONICAL_LEASE: (
        DisposableApprovalLifecyclePhaseV7.LEASE_BOUND
    ),
    DisposableApprovalLifecycleOperationV7.PUBLISH_TEMPORARY: (
        DisposableApprovalLifecyclePhaseV7.TEMPORARY_PUBLISHED
    ),
    DisposableApprovalLifecycleOperationV7.REMOVE_TEMPORARY: (
        DisposableApprovalLifecyclePhaseV7.TEMPORARY_REMOVED
    ),
    DisposableApprovalLifecycleOperationV7.PROMOTE_COMMITTED: (
        DisposableApprovalLifecyclePhaseV7.COMMITTED
    ),
}


_SUCCESS_DISPOSITIONS = {
    DisposableApprovalLifecycleOperationV7.BIND_CANONICAL_LEASE: (
        DisposableLeaseBindingDispositionV7.CANONICAL_BOUND
    ),
    DisposableApprovalLifecycleOperationV7.PUBLISH_TEMPORARY: (
        DisposableTemporaryPublicationDispositionV7.TEMPORARY_PUBLISHED
    ),
    DisposableApprovalLifecycleOperationV7.REMOVE_TEMPORARY: (
        DisposableTemporaryRemovalDispositionV7.TEMPORARY_REMOVED
    ),
    DisposableApprovalLifecycleOperationV7.PROMOTE_COMMITTED: (
        DisposableCommittedPromotionDispositionV7.COMMITTED_PROMOTED
    ),
}


def _reviewed_follow_up_permitted(result: LifecycleUnderlyingResultV7) -> bool:
    if isinstance(result, DisposableCanonicalLeaseBindingResultV7):
        return result.ordinary_rollback_permitted
    if isinstance(result, DisposableTemporaryApprovalPublicationResultV7):
        return result.ordinary_rollback_permitted
    if isinstance(result, DisposableTemporaryApprovalRemovalResultV7):
        return result.reviewed_recovery_permitted
    if isinstance(result, DisposableCommittedApprovalPromotionResultV7):
        return result.reviewed_retry_permitted
    raise TypeError("unsupported disposable lifecycle result")


def _forward_recovery_required(result: LifecycleUnderlyingResultV7) -> bool:
    return bool(
        isinstance(result, DisposableCommittedApprovalPromotionResultV7)
        and result.forward_recovery_required
    )


def _manual_reconciliation_required(result: LifecycleUnderlyingResultV7) -> bool:
    return result.manual_reconciliation_required


def _owner_lock_remains_held(result: LifecycleUnderlyingResultV7) -> bool:
    return result.owner_lock_remains_held


def _disposition(result: LifecycleUnderlyingResultV7) -> Enum:
    return result.disposition


@dataclass(frozen=True)
class DisposableApprovalLifecycleEventV7:
    operation: DisposableApprovalLifecycleOperationV7
    phase_before: DisposableApprovalLifecyclePhaseV7
    phase_after: DisposableApprovalLifecyclePhaseV7
    result: LifecycleUnderlyingResultV7
    successful_terminal_state: bool
    reviewed_follow_up_permitted: bool
    forward_recovery_required: bool
    manual_reconciliation_required: bool
    owner_lock_remains_held: bool

    def __post_init__(self) -> None:
        expected_type = _EXPECTED_RESULT_TYPES.get(self.operation)
        if expected_type is None or not isinstance(self.result, expected_type):
            raise ValueError("lifecycle operation and underlying result type differ")
        if self.phase_before is not _ALLOWED_BEFORE[self.operation]:
            raise ValueError("lifecycle event starts from an invalid phase")

        succeeded = (
            self.result.status is AdapterStatus.PASS
            and _disposition(self.result) is _SUCCESS_DISPOSITIONS[self.operation]
        )
        expected_after = (
            _SUCCESS_AFTER[self.operation]
            if succeeded
            else DisposableApprovalLifecyclePhaseV7.RECOVERY_REQUIRED
        )
        if self.phase_after is not expected_after:
            raise ValueError("lifecycle event ends in an invalid phase")

        expected_terminal = succeeded and self.phase_after in {
            DisposableApprovalLifecyclePhaseV7.TEMPORARY_REMOVED,
            DisposableApprovalLifecyclePhaseV7.COMMITTED,
        }
        if self.successful_terminal_state is not expected_terminal:
            raise ValueError("lifecycle terminal-state flag is inconsistent")
        if self.reviewed_follow_up_permitted is not _reviewed_follow_up_permitted(
            self.result
        ):
            raise ValueError("lifecycle reviewed-follow-up flag is inconsistent")
        if self.forward_recovery_required is not _forward_recovery_required(
            self.result
        ):
            raise ValueError("lifecycle forward-recovery flag is inconsistent")
        if self.manual_reconciliation_required is not _manual_reconciliation_required(
            self.result
        ):
            raise ValueError("lifecycle manual-reconciliation flag is inconsistent")
        if self.owner_lock_remains_held is not _owner_lock_remains_held(self.result):
            raise ValueError("lifecycle owner-lock flag is inconsistent")
        if succeeded and (
            self.reviewed_follow_up_permitted
            or self.forward_recovery_required
            or self.manual_reconciliation_required
        ):
            raise ValueError("successful lifecycle event cannot request recovery")
        if not succeeded and self.successful_terminal_state:
            raise ValueError("failed lifecycle event cannot be terminal success")


def _event(
    operation: DisposableApprovalLifecycleOperationV7,
    before: DisposableApprovalLifecyclePhaseV7,
    result: LifecycleUnderlyingResultV7,
) -> DisposableApprovalLifecycleEventV7:
    succeeded = (
        result.status is AdapterStatus.PASS
        and _disposition(result) is _SUCCESS_DISPOSITIONS[operation]
    )
    after = (
        _SUCCESS_AFTER[operation]
        if succeeded
        else DisposableApprovalLifecyclePhaseV7.RECOVERY_REQUIRED
    )
    return DisposableApprovalLifecycleEventV7(
        operation=operation,
        phase_before=before,
        phase_after=after,
        result=result,
        successful_terminal_state=(
            succeeded
            and after
            in {
                DisposableApprovalLifecyclePhaseV7.TEMPORARY_REMOVED,
                DisposableApprovalLifecyclePhaseV7.COMMITTED,
            }
        ),
        reviewed_follow_up_permitted=_reviewed_follow_up_permitted(result),
        forward_recovery_required=_forward_recovery_required(result),
        manual_reconciliation_required=_manual_reconciliation_required(result),
        owner_lock_remains_held=_owner_lock_remains_held(result),
    )


class DisposableApprovalLifecycleFacadeV7:
    """Order-only coordinator for the four disposable approval authorities."""

    __slots__ = (
        "_owner",
        "_approval_root",
        "_temporary",
        "_committed",
        "_phase",
    )

    def __init__(
        self,
        owner: DisposableC20LockOwnerV7,
        approval_root: DisposableApprovalRootV7,
        temporary: TemporaryApprovalRecordPlanV7,
        committed: CommittedApprovalRecordPlanV7,
    ) -> None:
        if not isinstance(owner, DisposableC20LockOwnerV7):
            raise TypeError("lifecycle facade requires DisposableC20LockOwnerV7")
        if not isinstance(approval_root, DisposableApprovalRootV7):
            raise TypeError("lifecycle facade requires DisposableApprovalRootV7")
        if approval_root.owner is not owner:
            raise ValueError("lifecycle facade authorities use different owners")
        if approval_root.path.parent.parent.parent.parent != owner.root:
            raise ValueError("lifecycle facade authorities use different roots")
        if not owner.lock_held:
            raise ValueError("lifecycle facade requires retained owner authority")
        if approval_root.closed:
            raise ValueError("lifecycle facade requires an open approval root")
        approval_root.verify_root()
        if not isinstance(temporary, TemporaryApprovalRecordPlanV7):
            raise TypeError("lifecycle facade requires TemporaryApprovalRecordPlanV7")
        if not isinstance(committed, CommittedApprovalRecordPlanV7):
            raise TypeError("lifecycle facade requires CommittedApprovalRecordPlanV7")
        if temporary.binding_sha256 != committed.binding_sha256:
            raise ValueError("lifecycle plans use different authority bindings")
        if temporary.record_sha256 != committed.temporary_record_sha256:
            raise ValueError("committed lifecycle plan does not derive from temporary plan")
        if temporary.record.lock_lease_id != owner.lease_id:
            raise ValueError("temporary lifecycle plan uses a different owner lease")
        if committed.record.lock_lease_id != owner.lease_id:
            raise ValueError("committed lifecycle plan uses a different owner lease")
        self._owner = owner
        self._approval_root = approval_root
        self._temporary = temporary
        self._committed = committed
        self._phase = DisposableApprovalLifecyclePhaseV7.OWNER_HELD_EMPTY

    @property
    def phase(self) -> DisposableApprovalLifecyclePhaseV7:
        return self._phase

    @property
    def temporary_plan(self) -> TemporaryApprovalRecordPlanV7:
        return self._temporary

    @property
    def committed_plan(self) -> CommittedApprovalRecordPlanV7:
        return self._committed

    def _require_phase(
        self,
        operation: DisposableApprovalLifecycleOperationV7,
    ) -> DisposableApprovalLifecyclePhaseV7:
        expected = _ALLOWED_BEFORE[operation]
        if self._phase is not expected:
            raise DisposableApprovalLifecycleOrderError(
                f"{operation.value} requires {expected.value}, current phase is {self._phase.value}"
            )
        return self._phase

    def _accept(
        self,
        operation: DisposableApprovalLifecycleOperationV7,
        before: DisposableApprovalLifecyclePhaseV7,
        result: LifecycleUnderlyingResultV7,
    ) -> DisposableApprovalLifecycleEventV7:
        event = _event(operation, before, result)
        self._phase = event.phase_after
        return event

    def bind_canonical_lease(self) -> DisposableApprovalLifecycleEventV7:
        operation = DisposableApprovalLifecycleOperationV7.BIND_CANONICAL_LEASE
        before = self._require_phase(operation)
        result = DisposableCanonicalLeaseBinderV7(self._owner).bind()
        return self._accept(operation, before, result)

    def publish_temporary(self) -> DisposableApprovalLifecycleEventV7:
        operation = DisposableApprovalLifecycleOperationV7.PUBLISH_TEMPORARY
        before = self._require_phase(operation)
        result = DisposableTemporaryApprovalPublisherV7(
            self._owner,
            self._approval_root,
            self._temporary,
            self._committed,
        ).publish()
        return self._accept(operation, before, result)

    def remove_temporary(self) -> DisposableApprovalLifecycleEventV7:
        operation = DisposableApprovalLifecycleOperationV7.REMOVE_TEMPORARY
        before = self._require_phase(operation)
        result = DisposableTemporaryApprovalRemoverV7(
            self._owner,
            self._approval_root,
            self._temporary,
            self._committed,
        ).remove()
        return self._accept(operation, before, result)

    def promote_committed(self) -> DisposableApprovalLifecycleEventV7:
        operation = DisposableApprovalLifecycleOperationV7.PROMOTE_COMMITTED
        before = self._require_phase(operation)
        result = DisposableCommittedApprovalPromoterV7(
            self._owner,
            self._approval_root,
            self._temporary,
            self._committed,
        ).promote()
        return self._accept(operation, before, result)
