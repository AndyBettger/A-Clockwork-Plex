#!/usr/bin/python3
from __future__ import annotations

"""Stage C15A versioned transaction-abort lifecycle contract.

The original Stage C10 contract remains historically unchanged at thirty-three
operations. This module adds one physically proved transaction-lifecycle
operation as a versioned v2 view. It contains no host-access implementation,
entrypoint or production command boundary.
"""

from dataclasses import dataclass
from enum import Enum
from typing import NoReturn, Protocol, runtime_checkable

from .production_adapter_contract import (
    AdapterOperation,
    AdapterStatus,
    BlockedProductionAdapter,
    MUTATING_OPERATIONS,
    ProductionAdapter,
    READ_ONLY_OPERATIONS,
    TransactionAction,
    TransactionIdentity,
)


class TransactionLifecycleOperation(str, Enum):
    ABORT_UNCOMMITTED_TRANSACTION = "abort-uncommitted-transaction"


ProductionOperationV2 = AdapterOperation | TransactionLifecycleOperation

ALL_OPERATIONS_V2: tuple[ProductionOperationV2, ...] = (
    *tuple(AdapterOperation),
    *tuple(TransactionLifecycleOperation),
)
READ_ONLY_OPERATIONS_V2: tuple[ProductionOperationV2, ...] = tuple(
    READ_ONLY_OPERATIONS
)
MUTATING_OPERATIONS_V2: tuple[ProductionOperationV2, ...] = (
    *tuple(MUTATING_OPERATIONS),
    TransactionLifecycleOperation.ABORT_UNCOMMITTED_TRANSACTION,
)


@dataclass(frozen=True)
class AbortUncommittedTransactionReceipt:
    transaction: TransactionIdentity
    state: str
    mutation_started: bool
    committed: bool
    transaction_path_absent: bool
    parents_restored: bool
    audit_evidence: str

    def __post_init__(self) -> None:
        if self.state != "aborted-before-mutation":
            raise ValueError(
                "abort receipt must describe the exact pre-mutation abort state"
            )
        if self.mutation_started:
            raise ValueError("pre-mutation abort cannot report mutation started")
        if self.committed:
            raise ValueError("a committed transaction cannot use pre-mutation abort")
        if not self.transaction_path_absent:
            raise ValueError("abort receipt must prove transaction-path absence")
        if not self.parents_restored:
            raise ValueError("abort receipt must prove exact parent restoration")
        if not isinstance(self.audit_evidence, str) or not self.audit_evidence.strip():
            raise ValueError("abort receipt requires adapter-owned audit evidence")


@dataclass(frozen=True)
class LifecycleAdapterResult:
    operation: TransactionLifecycleOperation
    status: AdapterStatus
    detail: str
    payload: AbortUncommittedTransactionReceipt | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ValueError("lifecycle result detail must not be empty")
        if self.status is not AdapterStatus.PASS and self.payload is not None:
            raise ValueError(
                "failed or blocked lifecycle result must not carry a receipt"
            )


class ProductionLifecycleAdapterBlocked(RuntimeError):
    """Raised when the versioned lifecycle operation remains blocked."""

    def __init__(self, operation: TransactionLifecycleOperation) -> None:
        self.operation = operation
        super().__init__(
            f"Stage C production lifecycle adapter is blocked: {operation.value}"
        )


@runtime_checkable
class ProductionAdapterV2(ProductionAdapter, Protocol):
    def abort_uncommitted_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> LifecycleAdapterResult: ...


class BlockedProductionAdapterV2(BlockedProductionAdapter):
    """Blocked v2 adapter: all v1 methods and the abort remain unavailable."""

    @staticmethod
    def _lifecycle_blocked(
        operation: TransactionLifecycleOperation,
    ) -> NoReturn:
        raise ProductionLifecycleAdapterBlocked(operation)

    def abort_uncommitted_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> LifecycleAdapterResult:
        del transaction
        return self._lifecycle_blocked(
            TransactionLifecycleOperation.ABORT_UNCOMMITTED_TRANSACTION
        )


@dataclass(frozen=True)
class VersionedStageBoundary:
    stage: str
    permitted: int
    blocked: int

    def __post_init__(self) -> None:
        if not self.stage.strip():
            raise ValueError("stage boundary requires a stage name")
        if self.permitted < 0 or self.blocked < 0:
            raise ValueError("stage boundary counts cannot be negative")
        if self.permitted + self.blocked != len(ALL_OPERATIONS_V2):
            raise ValueError("stage boundary must cover every v2 operation exactly")


STAGE_BOUNDARIES_V2 = (
    VersionedStageBoundary("C13", permitted=6, blocked=28),
    VersionedStageBoundary("C14", permitted=8, blocked=26),
    VersionedStageBoundary("C15", permitted=11, blocked=23),
)


def contract_snapshot_v2() -> tuple[tuple[str, str], ...]:
    """Return immutable v2 review metadata without touching the host."""

    return (
        ("version", "2"),
        ("v1_operation_count", str(len(AdapterOperation))),
        ("operation_count", str(len(ALL_OPERATIONS_V2))),
        ("read_only_count", str(len(READ_ONLY_OPERATIONS_V2))),
        ("mutating_count", str(len(MUTATING_OPERATIONS_V2))),
        (
            "operations",
            ",".join(operation.value for operation in ALL_OPERATIONS_V2),
        ),
        (
            "abort_operation",
            TransactionLifecycleOperation.ABORT_UNCOMMITTED_TRANSACTION.value,
        ),
        ("explicit_uninstall", TransactionAction.EXPLICIT_UNINSTALL.value),
        ("activation_interface", "absent"),
    )


def _validate_contract() -> None:
    if len(AdapterOperation) != 33:
        raise RuntimeError("Stage C10 v1 operation history changed unexpectedly")
    if len(ALL_OPERATIONS_V2) != 34:
        raise RuntimeError("Stage C15A v2 must contain exactly thirty-four operations")
    values = tuple(operation.value for operation in ALL_OPERATIONS_V2)
    if len(values) != len(set(values)):
        raise RuntimeError("Stage C15A v2 contains a duplicate operation value")
    if len(READ_ONLY_OPERATIONS_V2) != 17:
        raise RuntimeError("Stage C15A v2 read-only partition must contain seventeen operations")
    if len(MUTATING_OPERATIONS_V2) != 17:
        raise RuntimeError("Stage C15A v2 mutating partition must contain seventeen operations")
    if set(READ_ONLY_OPERATIONS_V2).intersection(MUTATING_OPERATIONS_V2):
        raise RuntimeError("Stage C15A v2 operation partitions overlap")
    if set(READ_ONLY_OPERATIONS_V2).union(MUTATING_OPERATIONS_V2) != set(
        ALL_OPERATIONS_V2
    ):
        raise RuntimeError("Stage C15A v2 operation partitions are incomplete")
    if hasattr(AdapterOperation, "EXPLICIT_UNINSTALL"):
        raise RuntimeError("explicit uninstall must remain transaction policy")


_validate_contract()
