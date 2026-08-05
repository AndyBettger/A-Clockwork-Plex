#!/usr/bin/python3
from __future__ import annotations

"""Stage C18 versioned managed-file exact-rollback rehearsal closure.

The frozen v1, v2 and v3 operation histories remain unchanged. This v4 view
adds one typed lifecycle operation for a transaction that installed the reviewed
managed files, restored the authoritative filesystem snapshot exactly, restored
the captured application state, retained audit evidence and removed the
transaction before lock release.

The module contains no host access, entrypoint, executable command or generic
dispatch boundary.
"""

from dataclasses import dataclass
from enum import Enum
from typing import NoReturn, Protocol, runtime_checkable

from .production_adapter_contract import AdapterStatus, TransactionIdentity
from .production_adapter_lifecycle_v3 import (
    ALL_OPERATIONS_V3,
    MUTATING_OPERATIONS_V3,
    READ_ONLY_OPERATIONS_V3,
    BlockedProductionAdapterV3,
    ProductionAdapterV3,
    ProductionOperationV3,
)


class ExactRollbackRehearsalLifecycleOperation(str, Enum):
    CLOSE_EXACT_ROLLBACK_REHEARSAL_TRANSACTION = (
        "close-exact-rollback-rehearsal-transaction"
    )


ProductionOperationV4 = (
    ProductionOperationV3 | ExactRollbackRehearsalLifecycleOperation
)

ALL_OPERATIONS_V4: tuple[ProductionOperationV4, ...] = (
    *ALL_OPERATIONS_V3,
    *tuple(ExactRollbackRehearsalLifecycleOperation),
)
READ_ONLY_OPERATIONS_V4: tuple[ProductionOperationV4, ...] = tuple(
    READ_ONLY_OPERATIONS_V3
)
MUTATING_OPERATIONS_V4: tuple[ProductionOperationV4, ...] = (
    *MUTATING_OPERATIONS_V3,
    ExactRollbackRehearsalLifecycleOperation.
    CLOSE_EXACT_ROLLBACK_REHEARSAL_TRANSACTION,
)


@dataclass(frozen=True)
class ExactRollbackRehearsalTransactionReceipt:
    transaction: TransactionIdentity
    state: str
    mutation_started: bool
    managed_files_installed: bool
    filesystem_restored: bool
    services_restored: bool
    committed: bool
    transaction_path_absent: bool
    parents_restored: bool
    installed_file_count: int
    audit_evidence: str

    def __post_init__(self) -> None:
        if self.state != "managed-files-rolled-back-and-closed":
            raise ValueError(
                "exact rollback rehearsal receipt must use the closed state"
            )
        if not self.mutation_started:
            raise ValueError(
                "exact rollback rehearsal requires a crossed mutation boundary"
            )
        if not self.managed_files_installed:
            raise ValueError(
                "exact rollback rehearsal must prove managed files were installed"
            )
        if not self.filesystem_restored:
            raise ValueError(
                "exact rollback rehearsal must prove filesystem restoration"
            )
        if not self.services_restored:
            raise ValueError(
                "exact rollback rehearsal must prove service restoration"
            )
        if self.committed:
            raise ValueError(
                "exact rollback rehearsal must not claim an installation commit"
            )
        if not self.transaction_path_absent or not self.parents_restored:
            raise ValueError(
                "exact rollback rehearsal receipt requires exact cleanup"
            )
        if self.installed_file_count != 12:
            raise ValueError(
                "exact rollback rehearsal must cover exactly twelve files"
            )
        if not isinstance(self.audit_evidence, str) or not self.audit_evidence.strip():
            raise ValueError(
                "exact rollback rehearsal requires adapter-owned audit evidence"
            )


@dataclass(frozen=True)
class ExactRollbackRehearsalAdapterResult:
    operation: ExactRollbackRehearsalLifecycleOperation
    status: AdapterStatus
    detail: str
    payload: ExactRollbackRehearsalTransactionReceipt | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ValueError(
                "exact rollback rehearsal result detail must not be empty"
            )
        if self.status is not AdapterStatus.PASS and self.payload is not None:
            raise ValueError(
                "failed exact rollback rehearsal result must not carry a receipt"
            )


class ProductionExactRollbackRehearsalAdapterBlocked(RuntimeError):
    """Raised while the v4 exact-rollback lifecycle remains blocked."""

    def __init__(
        self,
        operation: ExactRollbackRehearsalLifecycleOperation,
    ) -> None:
        self.operation = operation
        super().__init__(
            "Stage C production exact-rollback rehearsal adapter is blocked: "
            f"{operation.value}"
        )


@runtime_checkable
class ProductionAdapterV4(ProductionAdapterV3, Protocol):
    def close_exact_rollback_rehearsal_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> ExactRollbackRehearsalAdapterResult: ...


class BlockedProductionAdapterV4(BlockedProductionAdapterV3):
    """Blocked v4 adapter: all v1 through v4 methods remain unavailable."""

    @staticmethod
    def _exact_rollback_rehearsal_blocked(
        operation: ExactRollbackRehearsalLifecycleOperation,
    ) -> NoReturn:
        raise ProductionExactRollbackRehearsalAdapterBlocked(operation)

    def close_exact_rollback_rehearsal_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> ExactRollbackRehearsalAdapterResult:
        del transaction
        return self._exact_rollback_rehearsal_blocked(
            ExactRollbackRehearsalLifecycleOperation.
            CLOSE_EXACT_ROLLBACK_REHEARSAL_TRANSACTION
        )


@dataclass(frozen=True)
class VersionedStageBoundaryV4:
    stage: str
    permitted: int
    blocked: int

    def __post_init__(self) -> None:
        if not self.stage.strip():
            raise ValueError("stage boundary requires a stage name")
        if self.permitted < 0 or self.blocked < 0:
            raise ValueError("stage boundary counts cannot be negative")
        if self.permitted + self.blocked != len(ALL_OPERATIONS_V4):
            raise ValueError(
                "stage boundary must cover every v4 operation exactly"
            )


STAGE_BOUNDARIES_V4 = (
    VersionedStageBoundaryV4("C18", permitted=25, blocked=11),
)


def contract_snapshot_v4() -> tuple[tuple[str, str], ...]:
    """Return immutable v4 review metadata without touching the host."""

    return (
        ("version", "4"),
        ("v3_operation_count", str(len(ALL_OPERATIONS_V3))),
        ("operation_count", str(len(ALL_OPERATIONS_V4))),
        ("read_only_count", str(len(READ_ONLY_OPERATIONS_V4))),
        ("mutating_count", str(len(MUTATING_OPERATIONS_V4))),
        (
            "operations",
            ",".join(operation.value for operation in ALL_OPERATIONS_V4),
        ),
        (
            "exact_rollback_rehearsal_operation",
            ExactRollbackRehearsalLifecycleOperation.
            CLOSE_EXACT_ROLLBACK_REHEARSAL_TRANSACTION.value,
        ),
        ("activation_interface", "absent"),
    )


def _validate_contract() -> None:
    if len(ALL_OPERATIONS_V3) != 35:
        raise RuntimeError("Stage C17 v3 operation history changed unexpectedly")
    if len(ALL_OPERATIONS_V4) != 36:
        raise RuntimeError("Stage C18 v4 must contain exactly thirty-six operations")
    values = tuple(operation.value for operation in ALL_OPERATIONS_V4)
    if len(values) != len(set(values)):
        raise RuntimeError("Stage C18 v4 contains a duplicate operation value")
    if len(READ_ONLY_OPERATIONS_V4) != 17:
        raise RuntimeError(
            "Stage C18 v4 read-only partition must contain seventeen operations"
        )
    if len(MUTATING_OPERATIONS_V4) != 19:
        raise RuntimeError(
            "Stage C18 v4 mutating partition must contain nineteen operations"
        )
    if set(READ_ONLY_OPERATIONS_V4).intersection(MUTATING_OPERATIONS_V4):
        raise RuntimeError("Stage C18 v4 operation partitions overlap")
    if set(READ_ONLY_OPERATIONS_V4).union(MUTATING_OPERATIONS_V4) != set(
        ALL_OPERATIONS_V4
    ):
        raise RuntimeError("Stage C18 v4 operation partitions are incomplete")


_validate_contract()
