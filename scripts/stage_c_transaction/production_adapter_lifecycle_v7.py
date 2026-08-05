#!/usr/bin/python3
from __future__ import annotations

"""Stage C21 versioned activation-approval transaction lifecycle.

The frozen v1 through v6 operation histories remain unchanged. This v7 view
adds four transaction-owned operations needed to bridge an authoritative install
transaction into the separately reviewed Stage C21 runtime package:

- bind the already-held production-lock lease to its exact lock inode;
- publish one temporary transaction-bound activation approval;
- remove that exact temporary approval during automatic rollback;
- promote that exact temporary approval only after successful install commit.

This module contains no host access, entrypoint, filesystem primitive, command
execution or generic dispatch boundary. Every new operation remains blocked at
this contract gate.
"""

from dataclasses import dataclass
from enum import Enum
from typing import NoReturn, Protocol, runtime_checkable

from .production_adapter_contract import (
    AdapterStatus,
    PackageFingerprint,
    TransactionIdentity,
)
from .production_adapter_lifecycle_v6 import (
    ALL_OPERATIONS_V6,
    MUTATING_OPERATIONS_V6,
    READ_ONLY_OPERATIONS_V6,
    BlockedProductionAdapterV6,
    ProductionAdapterV6,
    ProductionOperationV6,
)


ACTIVATION_APPROVAL_PATH = (
    "/var/lib/a-clockwork-plex/split-bus/activation-approved"
)
PRODUCTION_LOCK_PATH = "/run/lock/a-clockwork-plex-audio-route.lock"
TEMPORARY_APPROVAL_PHASE = "temporary-transaction-bound"
COMMITTED_APPROVAL_PHASE = "committed-boot-eligible"


class ActivationApprovalLifecycleOperation(str, Enum):
    BIND_PRODUCTION_LOCK_LEASE = "bind-production-lock-lease"
    PUBLISH_TEMPORARY_ACTIVATION_APPROVAL = (
        "publish-temporary-activation-approval"
    )
    REMOVE_TEMPORARY_ACTIVATION_APPROVAL = (
        "remove-temporary-activation-approval"
    )
    PROMOTE_COMMITTED_ACTIVATION_APPROVAL = (
        "promote-committed-activation-approval"
    )


ProductionOperationV7 = (
    ProductionOperationV6 | ActivationApprovalLifecycleOperation
)

ALL_OPERATIONS_V7: tuple[ProductionOperationV7, ...] = (
    *ALL_OPERATIONS_V6,
    *tuple(ActivationApprovalLifecycleOperation),
)
READ_ONLY_OPERATIONS_V7: tuple[ProductionOperationV7, ...] = tuple(
    READ_ONLY_OPERATIONS_V6
)
MUTATING_OPERATIONS_V7: tuple[ProductionOperationV7, ...] = (
    *MUTATING_OPERATIONS_V6,
    *tuple(ActivationApprovalLifecycleOperation),
)


def _require_token(label: str, value: str) -> None:
    if (
        not isinstance(value, str)
        or not value.strip()
        or any(character.isspace() for character in value)
    ):
        raise ValueError(f"{label} must be a non-empty token without whitespace")


def _require_sha256(label: str, value: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


@dataclass(frozen=True)
class ProductionLockLeaseBindingReceipt:
    transaction: TransactionIdentity
    lock_path: str
    lease_id: str
    lock_device: int
    lock_inode: int
    transaction_owns_lock: bool
    canonical_content_written: bool
    exact_inode_verified: bool
    external_observer_ready: bool

    def __post_init__(self) -> None:
        if self.lock_path != PRODUCTION_LOCK_PATH:
            raise ValueError("lock-lease binding receipt uses the wrong path")
        _require_token("lock lease", self.lease_id)
        if self.lock_device < 0 or self.lock_inode <= 0:
            raise ValueError("lock-lease binding requires a valid inode identity")
        if not self.transaction_owns_lock:
            raise ValueError("lock lease may be bound only by the owning transaction")
        if not self.canonical_content_written:
            raise ValueError("lock lease binding requires canonical file content")
        if not self.exact_inode_verified:
            raise ValueError("lock lease binding requires exact inode verification")
        if not self.external_observer_ready:
            raise ValueError("lock lease must be observable by the service process")


@dataclass(frozen=True)
class TemporaryActivationApprovalReceipt:
    transaction: TransactionIdentity
    approval_path: str
    phase: str
    package: PackageFingerprint
    lock_lease_id: str
    record_sha256: str
    active_route_sha256: str
    boot_eligible: bool
    atomically_published: bool
    exact_record_verified: bool

    def __post_init__(self) -> None:
        if self.approval_path != ACTIVATION_APPROVAL_PATH:
            raise ValueError("temporary approval receipt uses the wrong path")
        if self.phase != TEMPORARY_APPROVAL_PHASE:
            raise ValueError("temporary approval receipt uses the wrong phase")
        _require_token("temporary approval lock lease", self.lock_lease_id)
        _require_sha256("temporary approval record", self.record_sha256)
        _require_sha256("temporary approval active route", self.active_route_sha256)
        if self.boot_eligible:
            raise ValueError("temporary activation approval must not be boot eligible")
        if not self.atomically_published or not self.exact_record_verified:
            raise ValueError("temporary approval must be atomically published and verified")


@dataclass(frozen=True)
class ActivationApprovalRemovalReceipt:
    transaction: TransactionIdentity
    approval_path: str
    expected_record_sha256: str
    exact_record_removed: bool
    approval_absent: bool
    rollback_owned: bool

    def __post_init__(self) -> None:
        if self.approval_path != ACTIVATION_APPROVAL_PATH:
            raise ValueError("approval-removal receipt uses the wrong path")
        _require_sha256("removed temporary approval", self.expected_record_sha256)
        if not self.exact_record_removed:
            raise ValueError("rollback must remove the exact temporary approval")
        if not self.approval_absent:
            raise ValueError("temporary approval must be absent after rollback removal")
        if not self.rollback_owned:
            raise ValueError("temporary approval removal must be owned by rollback")


@dataclass(frozen=True)
class CommittedActivationApprovalReceipt:
    transaction: TransactionIdentity
    approval_path: str
    phase: str
    package: PackageFingerprint
    lock_lease_id: str
    temporary_record_sha256: str
    committed_record_sha256: str
    commit_manifest_sha256: str
    boot_eligible: bool
    atomically_promoted: bool
    exact_record_verified: bool

    def __post_init__(self) -> None:
        if self.approval_path != ACTIVATION_APPROVAL_PATH:
            raise ValueError("committed approval receipt uses the wrong path")
        if self.phase != COMMITTED_APPROVAL_PHASE:
            raise ValueError("committed approval receipt uses the wrong phase")
        _require_token("committed approval lock lease", self.lock_lease_id)
        _require_sha256("temporary approval record", self.temporary_record_sha256)
        _require_sha256("committed approval record", self.committed_record_sha256)
        _require_sha256("commit manifest", self.commit_manifest_sha256)
        if self.temporary_record_sha256 == self.committed_record_sha256:
            raise ValueError("approval promotion must change the exact record identity")
        if not self.boot_eligible:
            raise ValueError("committed activation approval must be boot eligible")
        if not self.atomically_promoted or not self.exact_record_verified:
            raise ValueError("committed approval must be atomically promoted and verified")


ApprovalLifecyclePayload = (
    ProductionLockLeaseBindingReceipt
    | TemporaryActivationApprovalReceipt
    | ActivationApprovalRemovalReceipt
    | CommittedActivationApprovalReceipt
)


@dataclass(frozen=True)
class ActivationApprovalAdapterResult:
    operation: ActivationApprovalLifecycleOperation
    status: AdapterStatus
    detail: str
    payload: ApprovalLifecyclePayload | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ValueError("activation-approval result detail must not be empty")
        if self.status is not AdapterStatus.PASS and self.payload is not None:
            raise ValueError("failed activation-approval result must not carry a receipt")
        expected_payload = {
            ActivationApprovalLifecycleOperation.BIND_PRODUCTION_LOCK_LEASE:
                ProductionLockLeaseBindingReceipt,
            ActivationApprovalLifecycleOperation.PUBLISH_TEMPORARY_ACTIVATION_APPROVAL:
                TemporaryActivationApprovalReceipt,
            ActivationApprovalLifecycleOperation.REMOVE_TEMPORARY_ACTIVATION_APPROVAL:
                ActivationApprovalRemovalReceipt,
            ActivationApprovalLifecycleOperation.PROMOTE_COMMITTED_ACTIVATION_APPROVAL:
                CommittedActivationApprovalReceipt,
        }[self.operation]
        if self.payload is not None and not isinstance(self.payload, expected_payload):
            raise ValueError("activation-approval result carries the wrong receipt type")


class ProductionActivationApprovalAdapterBlocked(RuntimeError):
    """Raised while every v7 approval-lifecycle operation remains blocked."""

    def __init__(self, operation: ActivationApprovalLifecycleOperation) -> None:
        self.operation = operation
        super().__init__(
            "Stage C production activation-approval adapter is blocked: "
            f"{operation.value}"
        )


@runtime_checkable
class ProductionAdapterV7(ProductionAdapterV6, Protocol):
    def bind_production_lock_lease(
        self,
        transaction: TransactionIdentity,
    ) -> ActivationApprovalAdapterResult: ...

    def publish_temporary_activation_approval(
        self,
        transaction: TransactionIdentity,
    ) -> ActivationApprovalAdapterResult: ...

    def remove_temporary_activation_approval(
        self,
        transaction: TransactionIdentity,
    ) -> ActivationApprovalAdapterResult: ...

    def promote_committed_activation_approval(
        self,
        transaction: TransactionIdentity,
    ) -> ActivationApprovalAdapterResult: ...


class BlockedProductionAdapterV7(BlockedProductionAdapterV6):
    """Blocked v7 adapter: all v1 through v7 methods remain unavailable."""

    @staticmethod
    def _activation_approval_blocked(
        operation: ActivationApprovalLifecycleOperation,
    ) -> NoReturn:
        raise ProductionActivationApprovalAdapterBlocked(operation)

    def bind_production_lock_lease(
        self,
        transaction: TransactionIdentity,
    ) -> ActivationApprovalAdapterResult:
        del transaction
        return self._activation_approval_blocked(
            ActivationApprovalLifecycleOperation.BIND_PRODUCTION_LOCK_LEASE
        )

    def publish_temporary_activation_approval(
        self,
        transaction: TransactionIdentity,
    ) -> ActivationApprovalAdapterResult:
        del transaction
        return self._activation_approval_blocked(
            ActivationApprovalLifecycleOperation.
            PUBLISH_TEMPORARY_ACTIVATION_APPROVAL
        )

    def remove_temporary_activation_approval(
        self,
        transaction: TransactionIdentity,
    ) -> ActivationApprovalAdapterResult:
        del transaction
        return self._activation_approval_blocked(
            ActivationApprovalLifecycleOperation.
            REMOVE_TEMPORARY_ACTIVATION_APPROVAL
        )

    def promote_committed_activation_approval(
        self,
        transaction: TransactionIdentity,
    ) -> ActivationApprovalAdapterResult:
        del transaction
        return self._activation_approval_blocked(
            ActivationApprovalLifecycleOperation.
            PROMOTE_COMMITTED_ACTIVATION_APPROVAL
        )


@dataclass(frozen=True)
class ActivationApprovalStageBoundaryV7:
    stage: str
    new_operations_permitted: int
    new_operations_blocked: int

    def __post_init__(self) -> None:
        if not self.stage.strip():
            raise ValueError("approval stage boundary requires a stage name")
        if self.new_operations_permitted < 0 or self.new_operations_blocked < 0:
            raise ValueError("approval stage boundary counts cannot be negative")
        if (
            self.new_operations_permitted + self.new_operations_blocked
            != len(ActivationApprovalLifecycleOperation)
        ):
            raise ValueError("approval stage boundary must cover all four new operations")


STAGE_BOUNDARIES_V7 = (
    ActivationApprovalStageBoundaryV7(
        "C21-approval-bridge-contract",
        new_operations_permitted=0,
        new_operations_blocked=4,
    ),
)


def contract_snapshot_v7() -> tuple[tuple[str, str], ...]:
    """Return immutable v7 review metadata without touching the host."""

    return (
        ("version", "7"),
        ("v6_operation_count", str(len(ALL_OPERATIONS_V6))),
        ("operation_count", str(len(ALL_OPERATIONS_V7))),
        ("read_only_count", str(len(READ_ONLY_OPERATIONS_V7))),
        ("mutating_count", str(len(MUTATING_OPERATIONS_V7))),
        (
            "operations",
            ",".join(operation.value for operation in ALL_OPERATIONS_V7),
        ),
        ("approval_path", ACTIVATION_APPROVAL_PATH),
        ("lock_path", PRODUCTION_LOCK_PATH),
        ("new_operations_permitted", "0"),
        ("new_operations_blocked", "4"),
        ("service_helper_approval_interface", "absent"),
    )


def _validate_contract() -> None:
    if len(ALL_OPERATIONS_V6) != 38:
        raise RuntimeError("Stage C20 v6 operation history changed unexpectedly")
    if len(ALL_OPERATIONS_V7) != 42:
        raise RuntimeError("Stage C21 v7 must contain exactly forty-two operations")
    values = tuple(operation.value for operation in ALL_OPERATIONS_V7)
    if len(values) != len(set(values)):
        raise RuntimeError("Stage C21 v7 contains a duplicate operation value")
    if len(READ_ONLY_OPERATIONS_V7) != 17:
        raise RuntimeError("Stage C21 v7 read-only partition must contain seventeen operations")
    if len(MUTATING_OPERATIONS_V7) != 25:
        raise RuntimeError("Stage C21 v7 mutating partition must contain twenty-five operations")
    if set(READ_ONLY_OPERATIONS_V7).intersection(MUTATING_OPERATIONS_V7):
        raise RuntimeError("Stage C21 v7 operation partitions overlap")
    if set(READ_ONLY_OPERATIONS_V7).union(MUTATING_OPERATIONS_V7) != set(
        ALL_OPERATIONS_V7
    ):
        raise RuntimeError("Stage C21 v7 operation partitions are incomplete")


_validate_contract()
