#!/usr/bin/python3
from __future__ import annotations

"""Pure Stage C21 approval-authority binding and reconciliation policy.

This module consumes one immutable ``BorrowedAuthorityViewV7`` and one reviewed
hardware contract, then produces immutable pre-write binding metadata. It does
not create an approval record or a lease-binding receipt because those receipts
assert that durable host publication has actually completed.

The module also freezes the only permitted recovery disposition for known and
indeterminate approval-publication states. It contains no filesystem access,
path mutation, command execution, adapter construction, entrypoint or generic
dispatch boundary.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .borrowed_authority_view_v7 import BorrowedAuthorityViewV7
from .production_adapter_contract import (
    AdapterStatus,
    PackageFingerprint,
    SnapshotIdentity,
    TransactionIdentity,
)


SHA256_RE = re.compile(r"[0-9a-f]{64}")
TOKEN_RE = re.compile(r"[A-Za-z0-9_.:@+-]{1,160}")


def _require_sha256(label: str, value: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _require_token(label: str, value: str) -> str:
    if not isinstance(value, str) or not TOKEN_RE.fullmatch(value):
        raise ValueError(f"{label} must be a non-empty bounded token")
    return value


@dataclass(frozen=True)
class ApprovalHardwareContractV7:
    package: PackageFingerprint
    split_route_sha256: str
    direct_route_sha256: str
    camilladsp_config_sha256: str
    camilladsp_binary_version: str
    camilladsp_binary_sha256: str
    loopback_index: int
    loopback_id: str
    loopback_pcm_substreams: int
    loopback_pcm_notify: int
    dac_card: str
    dac_device: int
    sample_rate: int
    sample_format: str
    period_size: int
    buffer_size: int

    def __post_init__(self) -> None:
        for label, value in (
            ("split route", self.split_route_sha256),
            ("direct route", self.direct_route_sha256),
            ("CamillaDSP configuration", self.camilladsp_config_sha256),
            ("CamillaDSP binary", self.camilladsp_binary_sha256),
        ):
            _require_sha256(label, value)
        for label, value in (
            ("CamillaDSP binary version", self.camilladsp_binary_version),
            ("loopback id", self.loopback_id),
            ("DAC card", self.dac_card),
            ("sample format", self.sample_format),
        ):
            _require_token(label, value)
        for label, value, minimum in (
            ("loopback index", self.loopback_index, 0),
            ("loopback substreams", self.loopback_pcm_substreams, 1),
            ("loopback notify", self.loopback_pcm_notify, 0),
            ("DAC device", self.dac_device, 0),
            ("sample rate", self.sample_rate, 1),
            ("period size", self.period_size, 1),
            ("buffer size", self.buffer_size, 1),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
                raise ValueError(f"invalid {label}: {value!r}")
        if self.buffer_size < self.period_size:
            raise ValueError("buffer size must be at least one period")

    def as_dict(self) -> dict[str, Any]:
        return {
            "package_fingerprint": self.package.sha256,
            "split_route_sha256": self.split_route_sha256,
            "direct_route_sha256": self.direct_route_sha256,
            "camilladsp_config_sha256": self.camilladsp_config_sha256,
            "camilladsp_binary_version": self.camilladsp_binary_version,
            "camilladsp_binary_sha256": self.camilladsp_binary_sha256,
            "loopback_index": self.loopback_index,
            "loopback_id": self.loopback_id,
            "loopback_pcm_substreams": self.loopback_pcm_substreams,
            "loopback_pcm_notify": self.loopback_pcm_notify,
            "dac_card": self.dac_card,
            "dac_device": self.dac_device,
            "sample_rate": self.sample_rate,
            "sample_format": self.sample_format,
            "period_size": self.period_size,
            "buffer_size": self.buffer_size,
        }


@dataclass(frozen=True)
class ApprovalAuthorityBindingV7:
    transaction: TransactionIdentity
    snapshot: SnapshotIdentity
    package: PackageFingerprint
    production_lock_path: str
    lock_lease_id: str
    lock_device: int
    lock_inode: int
    authoritative_transaction_path: str
    transaction_device: int
    transaction_inode: int
    selected_route_path: str
    selected_route_device: int
    selected_route_inode: int
    selected_route_sha256: str
    hardware: ApprovalHardwareContractV7
    source_snapshot_complete: bool
    source_split_route_selected: bool
    source_exact_lock_owned: bool
    source_exact_transaction_verified: bool

    def __post_init__(self) -> None:
        _require_token("lock lease", self.lock_lease_id)
        _require_sha256("selected route", self.selected_route_sha256)
        for label, value in (
            ("lock device", self.lock_device),
            ("lock inode", self.lock_inode),
            ("transaction device", self.transaction_device),
            ("transaction inode", self.transaction_inode),
            ("selected route device", self.selected_route_device),
            ("selected route inode", self.selected_route_inode),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{label} must be a positive integer")
        if self.hardware.package != self.package:
            raise ValueError("hardware contract package differs from authority package")
        if self.hardware.split_route_sha256 != self.selected_route_sha256:
            raise ValueError("hardware split-route digest differs from selected route")
        if not all(
            (
                self.source_snapshot_complete,
                self.source_split_route_selected,
                self.source_exact_lock_owned,
                self.source_exact_transaction_verified,
            )
        ):
            raise ValueError("approval binding requires every borrowed-authority proof")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "transaction_id": self.transaction.value,
            "snapshot_id": self.snapshot.value,
            "package_fingerprint": self.package.sha256,
            "production_lock_path": self.production_lock_path,
            "lock_lease_id": self.lock_lease_id,
            "lock_device": self.lock_device,
            "lock_inode": self.lock_inode,
            "authoritative_transaction_path": self.authoritative_transaction_path,
            "transaction_device": self.transaction_device,
            "transaction_inode": self.transaction_inode,
            "selected_route_path": self.selected_route_path,
            "selected_route_device": self.selected_route_device,
            "selected_route_inode": self.selected_route_inode,
            "selected_route_sha256": self.selected_route_sha256,
            "hardware": self.hardware.as_dict(),
            "source_snapshot_complete": self.source_snapshot_complete,
            "source_split_route_selected": self.source_split_route_selected,
            "source_exact_lock_owned": self.source_exact_lock_owned,
            "source_exact_transaction_verified": (
                self.source_exact_transaction_verified
            ),
        }

    @property
    def binding_sha256(self) -> str:
        payload = json.dumps(
            self.as_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ApprovalAuthorityBindingResultV7:
    status: AdapterStatus
    detail: str
    payload: ApprovalAuthorityBindingV7 | None = None

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("approval-authority binding detail must not be empty")
        if self.status is AdapterStatus.PASS and self.payload is None:
            raise ValueError("successful approval binding requires metadata")
        if self.status is not AdapterStatus.PASS and self.payload is not None:
            raise ValueError("failed approval binding cannot carry metadata")


def bind_approval_authority_v7(
    authority: BorrowedAuthorityViewV7,
    hardware: ApprovalHardwareContractV7,
) -> ApprovalAuthorityBindingResultV7:
    """Bind reviewed hardware metadata to immutable borrowed authority values."""

    if not isinstance(authority, BorrowedAuthorityViewV7):
        raise TypeError("approval binding requires BorrowedAuthorityViewV7")
    if not isinstance(hardware, ApprovalHardwareContractV7):
        raise TypeError("approval binding requires ApprovalHardwareContractV7")
    if hardware.package != authority.package:
        return ApprovalAuthorityBindingResultV7(
            status=AdapterStatus.FAIL,
            detail="hardware contract package differs from borrowed authority",
        )
    if hardware.split_route_sha256 != authority.selected_route_sha256:
        return ApprovalAuthorityBindingResultV7(
            status=AdapterStatus.FAIL,
            detail="hardware split-route digest differs from borrowed authority",
        )

    binding = ApprovalAuthorityBindingV7(
        transaction=authority.transaction,
        snapshot=authority.snapshot,
        package=authority.package,
        production_lock_path=authority.production_lock_path,
        lock_lease_id=authority.lock_lease_id,
        lock_device=authority.lock_device,
        lock_inode=authority.lock_inode,
        authoritative_transaction_path=authority.authoritative_transaction_path,
        transaction_device=authority.transaction_device,
        transaction_inode=authority.transaction_inode,
        selected_route_path=authority.selected_route_path,
        selected_route_device=authority.selected_route_device,
        selected_route_inode=authority.selected_route_inode,
        selected_route_sha256=authority.selected_route_sha256,
        hardware=hardware,
        source_snapshot_complete=authority.snapshot_complete,
        source_split_route_selected=authority.split_bus_route_selected,
        source_exact_lock_owned=authority.exact_lock_owned,
        source_exact_transaction_verified=authority.exact_transaction_verified,
    )
    return ApprovalAuthorityBindingResultV7(
        status=AdapterStatus.PASS,
        detail=(
            "borrowed authority and reviewed hardware metadata bound without "
            "publishing host state"
        ),
        payload=binding,
    )


class ApprovalPublicationKnowledgeV7(str, Enum):
    ABSENT_CONFIRMED = "absent-confirmed"
    TEMPORARY_CONFIRMED = "temporary-confirmed"
    COMMITTED_CONFIRMED = "committed-confirmed"
    TEMPORARY_PUBLICATION_INDETERMINATE = (
        "temporary-publication-indeterminate"
    )
    COMMITTED_PROMOTION_INDETERMINATE = (
        "committed-promotion-indeterminate"
    )


class ApprovalRecoveryActionV7(str, Enum):
    PUBLISH_TEMPORARY = "publish-temporary"
    CONTINUE_TEMPORARY_INSTALL = "continue-temporary-install"
    REMOVE_EXACT_TEMPORARY_DURING_ROLLBACK = (
        "remove-exact-temporary-during-rollback"
    )
    FORWARD_RECOVERY_ONLY = "forward-recovery-only"
    RECONCILE_EXACT_RECORD_RETAIN_LOCK = (
        "reconcile-exact-record-retain-lock"
    )


@dataclass(frozen=True)
class ApprovalReconciliationPolicyV7:
    knowledge: ApprovalPublicationKnowledgeV7
    permitted_actions: tuple[ApprovalRecoveryActionV7, ...]
    lock_must_remain_held: bool
    blind_rollback_permitted: bool
    forward_recovery_permitted: bool
    exact_record_reconciliation_required: bool
    detail: str

    def __post_init__(self) -> None:
        if not self.permitted_actions or not self.detail.strip():
            raise ValueError("approval reconciliation policy must be explicit")
        if not self.lock_must_remain_held:
            raise ValueError("approval reconciliation always begins under the held lock")
        if self.blind_rollback_permitted:
            raise ValueError("Stage C21 never permits blind approval rollback")
        if self.exact_record_reconciliation_required:
            if self.permitted_actions != (
                ApprovalRecoveryActionV7.RECONCILE_EXACT_RECORD_RETAIN_LOCK,
            ):
                raise ValueError("indeterminate publication has one reconciliation action")
            if self.forward_recovery_permitted:
                raise ValueError("indeterminate publication cannot recover forward yet")
        if self.knowledge is ApprovalPublicationKnowledgeV7.COMMITTED_CONFIRMED:
            if self.permitted_actions != (
                ApprovalRecoveryActionV7.FORWARD_RECOVERY_ONLY,
            ) or not self.forward_recovery_permitted:
                raise ValueError("confirmed commit requires forward recovery only")


RECONCILIATION_POLICY_V7 = {
    ApprovalPublicationKnowledgeV7.ABSENT_CONFIRMED:
        ApprovalReconciliationPolicyV7(
            knowledge=ApprovalPublicationKnowledgeV7.ABSENT_CONFIRMED,
            permitted_actions=(ApprovalRecoveryActionV7.PUBLISH_TEMPORARY,),
            lock_must_remain_held=True,
            blind_rollback_permitted=False,
            forward_recovery_permitted=False,
            exact_record_reconciliation_required=False,
            detail="confirmed absence permits one temporary publication attempt",
        ),
    ApprovalPublicationKnowledgeV7.TEMPORARY_CONFIRMED:
        ApprovalReconciliationPolicyV7(
            knowledge=ApprovalPublicationKnowledgeV7.TEMPORARY_CONFIRMED,
            permitted_actions=(
                ApprovalRecoveryActionV7.CONTINUE_TEMPORARY_INSTALL,
                ApprovalRecoveryActionV7.REMOVE_EXACT_TEMPORARY_DURING_ROLLBACK,
            ),
            lock_must_remain_held=True,
            blind_rollback_permitted=False,
            forward_recovery_permitted=False,
            exact_record_reconciliation_required=False,
            detail=(
                "confirmed temporary state may continue install or remove only "
                "the exact verified record during rollback"
            ),
        ),
    ApprovalPublicationKnowledgeV7.COMMITTED_CONFIRMED:
        ApprovalReconciliationPolicyV7(
            knowledge=ApprovalPublicationKnowledgeV7.COMMITTED_CONFIRMED,
            permitted_actions=(ApprovalRecoveryActionV7.FORWARD_RECOVERY_ONLY,),
            lock_must_remain_held=True,
            blind_rollback_permitted=False,
            forward_recovery_permitted=True,
            exact_record_reconciliation_required=False,
            detail="confirmed committed approval forbids exact install rollback",
        ),
    ApprovalPublicationKnowledgeV7.TEMPORARY_PUBLICATION_INDETERMINATE:
        ApprovalReconciliationPolicyV7(
            knowledge=(
                ApprovalPublicationKnowledgeV7.
                TEMPORARY_PUBLICATION_INDETERMINATE
            ),
            permitted_actions=(
                ApprovalRecoveryActionV7.RECONCILE_EXACT_RECORD_RETAIN_LOCK,
            ),
            lock_must_remain_held=True,
            blind_rollback_permitted=False,
            forward_recovery_permitted=False,
            exact_record_reconciliation_required=True,
            detail=(
                "temporary publication uncertainty must inspect the exact bound "
                "record before any rollback or retry"
            ),
        ),
    ApprovalPublicationKnowledgeV7.COMMITTED_PROMOTION_INDETERMINATE:
        ApprovalReconciliationPolicyV7(
            knowledge=(
                ApprovalPublicationKnowledgeV7.
                COMMITTED_PROMOTION_INDETERMINATE
            ),
            permitted_actions=(
                ApprovalRecoveryActionV7.RECONCILE_EXACT_RECORD_RETAIN_LOCK,
            ),
            lock_must_remain_held=True,
            blind_rollback_permitted=False,
            forward_recovery_permitted=False,
            exact_record_reconciliation_required=True,
            detail=(
                "commit promotion uncertainty must distinguish temporary from "
                "committed state before choosing rollback or forward recovery"
            ),
        ),
}


def reconciliation_policy_v7(
    knowledge: ApprovalPublicationKnowledgeV7,
) -> ApprovalReconciliationPolicyV7:
    if not isinstance(knowledge, ApprovalPublicationKnowledgeV7):
        raise TypeError("approval reconciliation requires typed publication knowledge")
    return RECONCILIATION_POLICY_V7[knowledge]


if set(RECONCILIATION_POLICY_V7) != set(ApprovalPublicationKnowledgeV7):
    raise RuntimeError("Stage C21 approval reconciliation policy is incomplete")
