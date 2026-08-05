#!/usr/bin/python3
from __future__ import annotations

"""Pure Stage C21 approval-record planning and exact reconciliation.

This module derives canonical temporary and committed approval records from one
``ApprovalAuthorityBindingV7`` by using the existing runtime-authority schema
and canonical encoder. It plans bytes and digests only; it does not open or
write the approval store.

Observed records are classified by exact canonical bytes. Semantically similar
or non-canonical JSON is deliberately treated as mismatched state.
"""

from dataclasses import dataclass
from enum import Enum

from stage_c_runtime_authority.approval_store import decode_record, encode_record
from stage_c_runtime_authority.model import (
    ActivationApprovalRecord,
    ApprovalPhase,
    HardwareContract,
    RuntimeAuthorityError,
)

from .approval_authority_binding_v7 import (
    ApprovalAuthorityBindingV7,
    ApprovalPublicationKnowledgeV7,
    ApprovalRecoveryActionV7,
    _require_sha256,
)


@dataclass(frozen=True)
class TemporaryApprovalRecordPlanV7:
    binding_sha256: str
    record: ActivationApprovalRecord
    encoded_bytes: bytes
    record_sha256: str
    encoded_sha256: str

    def __post_init__(self) -> None:
        _require_sha256("authority binding", self.binding_sha256)
        _require_sha256("temporary record", self.record_sha256)
        _require_sha256("temporary encoded record", self.encoded_sha256)
        if self.record.phase is not ApprovalPhase.TEMPORARY:
            raise ValueError("temporary plan requires a temporary approval record")
        if self.record.record_sha256 != self.record_sha256:
            raise ValueError("temporary record digest changed")
        if encode_record(self.record) != self.encoded_bytes:
            raise ValueError("temporary encoded bytes are not canonical")
        import hashlib

        if hashlib.sha256(self.encoded_bytes).hexdigest() != self.encoded_sha256:
            raise ValueError("temporary encoded-byte digest changed")


@dataclass(frozen=True)
class CommittedApprovalRecordPlanV7:
    binding_sha256: str
    temporary_record_sha256: str
    record: ActivationApprovalRecord
    encoded_bytes: bytes
    record_sha256: str
    encoded_sha256: str
    commit_manifest_sha256: str

    def __post_init__(self) -> None:
        for label, value in (
            ("authority binding", self.binding_sha256),
            ("temporary record", self.temporary_record_sha256),
            ("committed record", self.record_sha256),
            ("committed encoded record", self.encoded_sha256),
            ("commit manifest", self.commit_manifest_sha256),
        ):
            _require_sha256(label, value)
        if self.record.phase is not ApprovalPhase.COMMITTED:
            raise ValueError("committed plan requires a committed approval record")
        if self.record.commit_manifest_sha256 != self.commit_manifest_sha256:
            raise ValueError("committed record manifest digest changed")
        if self.record.record_sha256 != self.record_sha256:
            raise ValueError("committed record digest changed")
        if self.record_sha256 == self.temporary_record_sha256:
            raise ValueError("approval promotion must change the record digest")
        if encode_record(self.record) != self.encoded_bytes:
            raise ValueError("committed encoded bytes are not canonical")
        import hashlib

        if hashlib.sha256(self.encoded_bytes).hexdigest() != self.encoded_sha256:
            raise ValueError("committed encoded-byte digest changed")


def _hardware_contract(binding: ApprovalAuthorityBindingV7) -> HardwareContract:
    hardware = binding.hardware
    return HardwareContract(
        package_fingerprint=hardware.package.sha256,
        split_route_sha256=hardware.split_route_sha256,
        direct_route_sha256=hardware.direct_route_sha256,
        camilladsp_config_sha256=hardware.camilladsp_config_sha256,
        camilladsp_binary_version=hardware.camilladsp_binary_version,
        camilladsp_binary_sha256=hardware.camilladsp_binary_sha256,
        loopback_index=hardware.loopback_index,
        loopback_id=hardware.loopback_id,
        loopback_pcm_substreams=hardware.loopback_pcm_substreams,
        loopback_pcm_notify=hardware.loopback_pcm_notify,
        dac_card=hardware.dac_card,
        dac_device=hardware.dac_device,
        sample_rate=hardware.sample_rate,
        sample_format=hardware.sample_format,
        period_size=hardware.period_size,
        buffer_size=hardware.buffer_size,
    )


def plan_temporary_approval_v7(
    binding: ApprovalAuthorityBindingV7,
    *,
    created_at: str,
) -> TemporaryApprovalRecordPlanV7:
    if not isinstance(binding, ApprovalAuthorityBindingV7):
        raise TypeError("temporary approval planning requires ApprovalAuthorityBindingV7")
    record = ActivationApprovalRecord.temporary(
        transaction_id=binding.transaction.value,
        lock_lease_id=binding.lock_lease_id,
        contract=_hardware_contract(binding),
        created_at=created_at,
    )
    encoded = encode_record(record)
    import hashlib

    return TemporaryApprovalRecordPlanV7(
        binding_sha256=binding.binding_sha256,
        record=record,
        encoded_bytes=encoded,
        record_sha256=record.record_sha256,
        encoded_sha256=hashlib.sha256(encoded).hexdigest(),
    )


def plan_committed_approval_v7(
    temporary: TemporaryApprovalRecordPlanV7,
    *,
    commit_manifest_sha256: str,
    committed_at: str,
) -> CommittedApprovalRecordPlanV7:
    if not isinstance(temporary, TemporaryApprovalRecordPlanV7):
        raise TypeError("committed approval planning requires a temporary plan")
    _require_sha256("commit manifest", commit_manifest_sha256)
    record = temporary.record.promote(
        commit_manifest_sha256=commit_manifest_sha256,
        committed_at=committed_at,
    )
    encoded = encode_record(record)
    import hashlib

    return CommittedApprovalRecordPlanV7(
        binding_sha256=temporary.binding_sha256,
        temporary_record_sha256=temporary.record_sha256,
        record=record,
        encoded_bytes=encoded,
        record_sha256=record.record_sha256,
        encoded_sha256=hashlib.sha256(encoded).hexdigest(),
        commit_manifest_sha256=commit_manifest_sha256,
    )


class ApprovalObservedStateV7(str, Enum):
    ABSENT = "absent"
    EXACT_TEMPORARY = "exact-temporary"
    EXACT_COMMITTED = "exact-committed"
    MISMATCHED = "mismatched"
    OBSERVATION_FAILURE = "observation-failure"


@dataclass(frozen=True)
class ApprovalRecordClassificationV7:
    state: ApprovalObservedStateV7
    detail: str
    observed_record_sha256: str | None = None
    observed_encoded_sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("approval classification detail must not be empty")
        for label, value in (
            ("observed record", self.observed_record_sha256),
            ("observed encoded record", self.observed_encoded_sha256),
        ):
            if value is not None:
                _require_sha256(label, value)
        if self.state in {
            ApprovalObservedStateV7.EXACT_TEMPORARY,
            ApprovalObservedStateV7.EXACT_COMMITTED,
        } and (
            self.observed_record_sha256 is None
            or self.observed_encoded_sha256 is None
        ):
            raise ValueError("exact classification requires both observed digests")
        if self.state in {
            ApprovalObservedStateV7.ABSENT,
            ApprovalObservedStateV7.OBSERVATION_FAILURE,
        } and (
            self.observed_record_sha256 is not None
            or self.observed_encoded_sha256 is not None
        ):
            raise ValueError("absent/failure classification cannot carry digests")


def classify_approval_record_v7(
    temporary: TemporaryApprovalRecordPlanV7,
    committed: CommittedApprovalRecordPlanV7,
    *,
    observed_raw: bytes | None,
    observation_error: str | None = None,
) -> ApprovalRecordClassificationV7:
    if not isinstance(temporary, TemporaryApprovalRecordPlanV7):
        raise TypeError("classification requires a temporary approval plan")
    if not isinstance(committed, CommittedApprovalRecordPlanV7):
        raise TypeError("classification requires a committed approval plan")
    if temporary.binding_sha256 != committed.binding_sha256:
        raise ValueError("temporary and committed plans use different authority bindings")
    if temporary.record_sha256 != committed.temporary_record_sha256:
        raise ValueError("committed plan does not derive from the supplied temporary plan")
    if observation_error is not None:
        if not observation_error.strip():
            raise ValueError("observation error must not be empty")
        if observed_raw is not None:
            raise ValueError("observation failure cannot also carry observed bytes")
        return ApprovalRecordClassificationV7(
            state=ApprovalObservedStateV7.OBSERVATION_FAILURE,
            detail=observation_error,
        )
    if observed_raw is None:
        return ApprovalRecordClassificationV7(
            state=ApprovalObservedStateV7.ABSENT,
            detail="activation approval is absent",
        )
    if not isinstance(observed_raw, bytes):
        raise TypeError("observed approval bytes must be bytes or None")

    import hashlib

    encoded_sha256 = hashlib.sha256(observed_raw).hexdigest()
    try:
        observed_record = decode_record(observed_raw)
    except RuntimeAuthorityError as exc:
        return ApprovalRecordClassificationV7(
            state=ApprovalObservedStateV7.MISMATCHED,
            detail=f"observed approval is invalid: {exc}",
            observed_encoded_sha256=encoded_sha256,
        )

    record_sha256 = observed_record.record_sha256
    if observed_raw == temporary.encoded_bytes:
        return ApprovalRecordClassificationV7(
            state=ApprovalObservedStateV7.EXACT_TEMPORARY,
            detail="observed bytes exactly match the planned temporary approval",
            observed_record_sha256=record_sha256,
            observed_encoded_sha256=encoded_sha256,
        )
    if observed_raw == committed.encoded_bytes:
        return ApprovalRecordClassificationV7(
            state=ApprovalObservedStateV7.EXACT_COMMITTED,
            detail="observed bytes exactly match the planned committed approval",
            observed_record_sha256=record_sha256,
            observed_encoded_sha256=encoded_sha256,
        )
    return ApprovalRecordClassificationV7(
        state=ApprovalObservedStateV7.MISMATCHED,
        detail="observed approval is valid but not one of the exact planned records",
        observed_record_sha256=record_sha256,
        observed_encoded_sha256=encoded_sha256,
    )


class IndeterminateResolutionActionV7(str, Enum):
    CONTINUE_TEMPORARY_INSTALL = "continue-temporary-install"
    EXACT_ROLLBACK_APPROVAL_ABSENT = "exact-rollback-approval-absent"
    EXACT_ROLLBACK_REMOVE_TEMPORARY = "exact-rollback-remove-temporary"
    FORWARD_RECOVERY_ONLY = "forward-recovery-only"
    RETAIN_LOCK_MANUAL_RECONCILIATION = "retain-lock-manual-reconciliation"


@dataclass(frozen=True)
class IndeterminateApprovalResolutionV7:
    knowledge: ApprovalPublicationKnowledgeV7
    observed_state: ApprovalObservedStateV7
    action: IndeterminateResolutionActionV7
    lock_must_remain_held: bool
    exact_rollback_permitted: bool
    forward_recovery_permitted: bool
    detail: str

    def __post_init__(self) -> None:
        if self.knowledge not in {
            ApprovalPublicationKnowledgeV7.TEMPORARY_PUBLICATION_INDETERMINATE,
            ApprovalPublicationKnowledgeV7.COMMITTED_PROMOTION_INDETERMINATE,
        }:
            raise ValueError("resolution requires indeterminate publication knowledge")
        if not self.lock_must_remain_held or not self.detail.strip():
            raise ValueError("indeterminate resolution must retain the lock and explain itself")
        if self.exact_rollback_permitted and self.forward_recovery_permitted:
            raise ValueError("one resolution cannot permit rollback and forward recovery")
        if self.action is IndeterminateResolutionActionV7.FORWARD_RECOVERY_ONLY:
            if not self.forward_recovery_permitted or self.exact_rollback_permitted:
                raise ValueError("forward recovery action has inconsistent permissions")
        if self.action in {
            IndeterminateResolutionActionV7.EXACT_ROLLBACK_APPROVAL_ABSENT,
            IndeterminateResolutionActionV7.EXACT_ROLLBACK_REMOVE_TEMPORARY,
        } and not self.exact_rollback_permitted:
            raise ValueError("rollback action must permit exact rollback")
        if self.action is IndeterminateResolutionActionV7.RETAIN_LOCK_MANUAL_RECONCILIATION:
            if self.exact_rollback_permitted or self.forward_recovery_permitted:
                raise ValueError("manual reconciliation cannot pre-authorise recovery")


def resolve_indeterminate_approval_v7(
    knowledge: ApprovalPublicationKnowledgeV7,
    classification: ApprovalRecordClassificationV7,
) -> IndeterminateApprovalResolutionV7:
    if not isinstance(knowledge, ApprovalPublicationKnowledgeV7):
        raise TypeError("resolution requires typed publication knowledge")
    if not isinstance(classification, ApprovalRecordClassificationV7):
        raise TypeError("resolution requires typed approval classification")

    state = classification.state
    if knowledge is ApprovalPublicationKnowledgeV7.TEMPORARY_PUBLICATION_INDETERMINATE:
        if state is ApprovalObservedStateV7.ABSENT:
            return IndeterminateApprovalResolutionV7(
                knowledge=knowledge,
                observed_state=state,
                action=IndeterminateResolutionActionV7.EXACT_ROLLBACK_APPROVAL_ABSENT,
                lock_must_remain_held=True,
                exact_rollback_permitted=True,
                forward_recovery_permitted=False,
                detail="temporary publication did not become visible; exact rollback may omit approval removal",
            )
        if state is ApprovalObservedStateV7.EXACT_TEMPORARY:
            return IndeterminateApprovalResolutionV7(
                knowledge=knowledge,
                observed_state=state,
                action=IndeterminateResolutionActionV7.CONTINUE_TEMPORARY_INSTALL,
                lock_must_remain_held=True,
                exact_rollback_permitted=False,
                forward_recovery_permitted=False,
                detail="exact temporary approval is present; the held transaction may continue",
            )
    elif knowledge is ApprovalPublicationKnowledgeV7.COMMITTED_PROMOTION_INDETERMINATE:
        if state is ApprovalObservedStateV7.EXACT_TEMPORARY:
            return IndeterminateApprovalResolutionV7(
                knowledge=knowledge,
                observed_state=state,
                action=IndeterminateResolutionActionV7.EXACT_ROLLBACK_REMOVE_TEMPORARY,
                lock_must_remain_held=True,
                exact_rollback_permitted=True,
                forward_recovery_permitted=False,
                detail="promotion did not replace the exact temporary record; exact rollback may remove it",
            )
        if state is ApprovalObservedStateV7.EXACT_COMMITTED:
            return IndeterminateApprovalResolutionV7(
                knowledge=knowledge,
                observed_state=state,
                action=IndeterminateResolutionActionV7.FORWARD_RECOVERY_ONLY,
                lock_must_remain_held=True,
                exact_rollback_permitted=False,
                forward_recovery_permitted=True,
                detail="exact committed approval is authoritative; recover forward only",
            )
    else:
        raise ValueError("resolution accepts only indeterminate publication knowledge")

    return IndeterminateApprovalResolutionV7(
        knowledge=knowledge,
        observed_state=state,
        action=IndeterminateResolutionActionV7.RETAIN_LOCK_MANUAL_RECONCILIATION,
        lock_must_remain_held=True,
        exact_rollback_permitted=False,
        forward_recovery_permitted=False,
        detail=(
            "observed approval state is unexpected or unverifiable; retain the "
            "production lock without rollback, retry or forward recovery"
        ),
    )
