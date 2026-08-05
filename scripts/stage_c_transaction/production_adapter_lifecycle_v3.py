#!/usr/bin/python3
from __future__ import annotations

"""Stage C17 versioned restored-rehearsal transaction closure contract.

Stage C10's thirty-three-operation v1 contract and Stage C15A's thirty-four-
operation v2 view remain historically unchanged. This v3 view adds one typed
lifecycle operation for a transaction that crossed a rehearsal-only mutation
boundary, restored the captured application state exactly, retained audit
evidence and removed its authoritative transaction before lock release.

The module contains no host access, entrypoint, executable command or generic
dispatch boundary.
"""

from dataclasses import dataclass
from enum import Enum
from typing import NoReturn, Protocol, runtime_checkable

from .production_adapter_contract import (
    AdapterOperation,
    AdapterStatus,
    ServiceUnit,
    TransactionIdentity,
)
from .production_adapter_lifecycle_v2 import (
    ALL_OPERATIONS_V2,
    MUTATING_OPERATIONS_V2,
    ProductionAdapterV2,
    READ_ONLY_OPERATIONS_V2,
    BlockedProductionAdapterV2,
    TransactionLifecycleOperation,
)


class RestoredRehearsalLifecycleOperation(str, Enum):
    CLOSE_RESTORED_REHEARSAL_TRANSACTION = (
        "close-restored-rehearsal-transaction"
    )


ProductionOperationV3 = (
    AdapterOperation
    | TransactionLifecycleOperation
    | RestoredRehearsalLifecycleOperation
)

ALL_OPERATIONS_V3: tuple[ProductionOperationV3, ...] = (
    *ALL_OPERATIONS_V2,
    *tuple(RestoredRehearsalLifecycleOperation),
)
READ_ONLY_OPERATIONS_V3: tuple[ProductionOperationV3, ...] = tuple(
    READ_ONLY_OPERATIONS_V2
)
MUTATING_OPERATIONS_V3: tuple[ProductionOperationV3, ...] = (
    *MUTATING_OPERATIONS_V2,
    RestoredRehearsalLifecycleOperation.CLOSE_RESTORED_REHEARSAL_TRANSACTION,
)


@dataclass(frozen=True)
class RestoredRehearsalTransactionReceipt:
    transaction: TransactionIdentity
    state: str
    mutation_started: bool
    restored: bool
    committed: bool
    transaction_path_absent: bool
    parents_restored: bool
    restored_services: tuple[ServiceUnit, ...]
    audit_evidence: str

    def __post_init__(self) -> None:
        if self.state != "rehearsal-restored-and-closed":
            raise ValueError(
                "restored rehearsal receipt must use the exact closed state"
            )
        if not self.mutation_started:
            raise ValueError(
                "restored rehearsal closure requires a crossed mutation boundary"
            )
        if not self.restored:
            raise ValueError(
                "restored rehearsal closure must prove exact restoration"
            )
        if self.committed:
            raise ValueError(
                "a restored rehearsal must not claim an installation commit"
            )
        if not self.transaction_path_absent:
            raise ValueError(
                "restored rehearsal receipt must prove transaction-path absence"
            )
        if not self.parents_restored:
            raise ValueError(
                "restored rehearsal receipt must prove exact parent restoration"
            )
        if not self.restored_services:
            raise ValueError(
                "restored rehearsal receipt requires restored application services"
            )
        if len(self.restored_services) != len(set(self.restored_services)):
            raise ValueError(
                "restored rehearsal receipt contains duplicate services"
            )
        if any(
            service
            not in {
                ServiceUnit.PLEXAMP,
                ServiceUnit.SHAIRPORT_SYNC,
                ServiceUnit.DASHBOARD,
            }
            for service in self.restored_services
        ):
            raise ValueError(
                "restored rehearsal receipt may name only application services"
            )
        if not isinstance(self.audit_evidence, str) or not self.audit_evidence.strip():
            raise ValueError(
                "restored rehearsal receipt requires adapter-owned audit evidence"
            )


@dataclass(frozen=True)
class RestoredRehearsalAdapterResult:
    operation: RestoredRehearsalLifecycleOperation
    status: AdapterStatus
    detail: str
    payload: RestoredRehearsalTransactionReceipt | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ValueError("restored rehearsal result detail must not be empty")
        if self.status is not AdapterStatus.PASS and self.payload is not None:
            raise ValueError(
                "failed or blocked restored rehearsal result must not carry a receipt"
            )


class ProductionRestoredRehearsalAdapterBlocked(RuntimeError):
    """Raised while the v3 restored-rehearsal lifecycle remains blocked."""

    def __init__(self, operation: RestoredRehearsalLifecycleOperation) -> None:
        self.operation = operation
        super().__init__(
            "Stage C production restored-rehearsal adapter is blocked: "
            f"{operation.value}"
        )


@runtime_checkable
class ProductionAdapterV3(ProductionAdapterV2, Protocol):
    def close_restored_rehearsal_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> RestoredRehearsalAdapterResult: ...


class BlockedProductionAdapterV3(BlockedProductionAdapterV2):
    """Blocked v3 adapter: all v1, v2 and v3 methods remain unavailable."""

    @staticmethod
    def _restored_rehearsal_blocked(
        operation: RestoredRehearsalLifecycleOperation,
    ) -> NoReturn:
        raise ProductionRestoredRehearsalAdapterBlocked(operation)

    def close_restored_rehearsal_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> RestoredRehearsalAdapterResult:
        del transaction
        return self._restored_rehearsal_blocked(
            RestoredRehearsalLifecycleOperation.
            CLOSE_RESTORED_REHEARSAL_TRANSACTION
        )


@dataclass(frozen=True)
class VersionedStageBoundaryV3:
    stage: str
    permitted: int
    blocked: int

    def __post_init__(self) -> None:
        if not self.stage.strip():
            raise ValueError("stage boundary requires a stage name")
        if self.permitted < 0 or self.blocked < 0:
            raise ValueError("stage boundary counts cannot be negative")
        if self.permitted + self.blocked != len(ALL_OPERATIONS_V3):
            raise ValueError(
                "stage boundary must cover every v3 operation exactly"
            )


STAGE_BOUNDARIES_V3 = (
    VersionedStageBoundaryV3("C17", permitted=21, blocked=14),
)


def contract_snapshot_v3() -> tuple[tuple[str, str], ...]:
    """Return immutable v3 review metadata without touching the host."""

    return (
        ("version", "3"),
        ("v2_operation_count", str(len(ALL_OPERATIONS_V2))),
        ("operation_count", str(len(ALL_OPERATIONS_V3))),
        ("read_only_count", str(len(READ_ONLY_OPERATIONS_V3))),
        ("mutating_count", str(len(MUTATING_OPERATIONS_V3))),
        (
            "operations",
            ",".join(operation.value for operation in ALL_OPERATIONS_V3),
        ),
        (
            "restored_rehearsal_operation",
            RestoredRehearsalLifecycleOperation.
            CLOSE_RESTORED_REHEARSAL_TRANSACTION.value,
        ),
        ("activation_interface", "absent"),
    )


def _validate_contract() -> None:
    if len(ALL_OPERATIONS_V2) != 34:
        raise RuntimeError("Stage C15A v2 operation history changed unexpectedly")
    if len(ALL_OPERATIONS_V3) != 35:
        raise RuntimeError("Stage C17 v3 must contain exactly thirty-five operations")
    values = tuple(operation.value for operation in ALL_OPERATIONS_V3)
    if len(values) != len(set(values)):
        raise RuntimeError("Stage C17 v3 contains a duplicate operation value")
    if len(READ_ONLY_OPERATIONS_V3) != 17:
        raise RuntimeError(
            "Stage C17 v3 read-only partition must contain seventeen operations"
        )
    if len(MUTATING_OPERATIONS_V3) != 18:
        raise RuntimeError(
            "Stage C17 v3 mutating partition must contain eighteen operations"
        )
    if set(READ_ONLY_OPERATIONS_V3).intersection(MUTATING_OPERATIONS_V3):
        raise RuntimeError("Stage C17 v3 operation partitions overlap")
    if set(READ_ONLY_OPERATIONS_V3).union(MUTATING_OPERATIONS_V3) != set(
        ALL_OPERATIONS_V3
    ):
        raise RuntimeError("Stage C17 v3 operation partitions are incomplete")


_validate_contract()
