#!/usr/bin/python3
from __future__ import annotations

"""Stage C19 versioned systemd-reload exact-rollback rehearsal closure.

The frozen v1 through v4 operation histories remain unchanged. This v5 view
adds one typed lifecycle operation for a transaction that installed the reviewed
managed files, reloaded systemd, restored the authoritative filesystem and
systemd-manager state exactly, restored the captured application state, retained
audit evidence and removed the transaction before lock release.

The module contains no host access, entrypoint, executable command or generic
dispatch boundary.
"""

from dataclasses import dataclass
from enum import Enum
from typing import NoReturn, Protocol, runtime_checkable

from .production_adapter_contract import AdapterStatus, TransactionIdentity
from .production_adapter_lifecycle_v4 import (
    ALL_OPERATIONS_V4,
    MUTATING_OPERATIONS_V4,
    READ_ONLY_OPERATIONS_V4,
    BlockedProductionAdapterV4,
    ProductionAdapterV4,
    ProductionOperationV4,
)


class SystemdReloadRollbackLifecycleOperation(str, Enum):
    CLOSE_SYSTEMD_RELOAD_ROLLBACK_REHEARSAL_TRANSACTION = (
        "close-systemd-reload-rollback-rehearsal-transaction"
    )


ProductionOperationV5 = (
    ProductionOperationV4 | SystemdReloadRollbackLifecycleOperation
)

ALL_OPERATIONS_V5: tuple[ProductionOperationV5, ...] = (
    *ALL_OPERATIONS_V4,
    *tuple(SystemdReloadRollbackLifecycleOperation),
)
READ_ONLY_OPERATIONS_V5: tuple[ProductionOperationV5, ...] = tuple(
    READ_ONLY_OPERATIONS_V4
)
MUTATING_OPERATIONS_V5: tuple[ProductionOperationV5, ...] = (
    *MUTATING_OPERATIONS_V4,
    SystemdReloadRollbackLifecycleOperation.
    CLOSE_SYSTEMD_RELOAD_ROLLBACK_REHEARSAL_TRANSACTION,
)


@dataclass(frozen=True)
class SystemdReloadRollbackTransactionReceipt:
    transaction: TransactionIdentity
    state: str
    mutation_started: bool
    managed_files_installed: bool
    systemd_reloaded: bool
    filesystem_restored: bool
    systemd_manager_restored: bool
    services_restored: bool
    committed: bool
    transaction_path_absent: bool
    parents_restored: bool
    installed_file_count: int
    daemon_reload_count: int
    audit_evidence: str

    def __post_init__(self) -> None:
        if self.state != "systemd-reload-rolled-back-and-closed":
            raise ValueError(
                "systemd reload rollback receipt must use the closed state"
            )
        if not self.mutation_started:
            raise ValueError(
                "systemd reload rollback requires a crossed mutation boundary"
            )
        if not self.managed_files_installed:
            raise ValueError(
                "systemd reload rollback must prove managed files were installed"
            )
        if not self.systemd_reloaded:
            raise ValueError(
                "systemd reload rollback must prove the manager observed the units"
            )
        if not self.filesystem_restored:
            raise ValueError(
                "systemd reload rollback must prove filesystem restoration"
            )
        if not self.systemd_manager_restored:
            raise ValueError(
                "systemd reload rollback must prove manager-state restoration"
            )
        if not self.services_restored:
            raise ValueError(
                "systemd reload rollback must prove service restoration"
            )
        if self.committed:
            raise ValueError(
                "systemd reload rollback must not claim an installation commit"
            )
        if not self.transaction_path_absent or not self.parents_restored:
            raise ValueError(
                "systemd reload rollback receipt requires exact cleanup"
            )
        if self.installed_file_count != 12:
            raise ValueError(
                "systemd reload rollback must cover exactly twelve files"
            )
        if self.daemon_reload_count != 2:
            raise ValueError(
                "systemd reload rollback requires exactly two daemon reloads"
            )
        if not isinstance(self.audit_evidence, str) or not self.audit_evidence.strip():
            raise ValueError(
                "systemd reload rollback requires adapter-owned audit evidence"
            )


@dataclass(frozen=True)
class SystemdReloadRollbackAdapterResult:
    operation: SystemdReloadRollbackLifecycleOperation
    status: AdapterStatus
    detail: str
    payload: SystemdReloadRollbackTransactionReceipt | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ValueError(
                "systemd reload rollback result detail must not be empty"
            )
        if self.status is not AdapterStatus.PASS and self.payload is not None:
            raise ValueError(
                "failed systemd reload rollback result must not carry a receipt"
            )


class ProductionSystemdReloadRollbackAdapterBlocked(RuntimeError):
    """Raised while the v5 systemd-reload rollback lifecycle remains blocked."""

    def __init__(
        self,
        operation: SystemdReloadRollbackLifecycleOperation,
    ) -> None:
        self.operation = operation
        super().__init__(
            "Stage C production systemd-reload rollback adapter is blocked: "
            f"{operation.value}"
        )


@runtime_checkable
class ProductionAdapterV5(ProductionAdapterV4, Protocol):
    def close_systemd_reload_rollback_rehearsal_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> SystemdReloadRollbackAdapterResult: ...


class BlockedProductionAdapterV5(BlockedProductionAdapterV4):
    """Blocked v5 adapter: all v1 through v5 methods remain unavailable."""

    @staticmethod
    def _systemd_reload_rollback_blocked(
        operation: SystemdReloadRollbackLifecycleOperation,
    ) -> NoReturn:
        raise ProductionSystemdReloadRollbackAdapterBlocked(operation)

    def close_systemd_reload_rollback_rehearsal_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> SystemdReloadRollbackAdapterResult:
        del transaction
        return self._systemd_reload_rollback_blocked(
            SystemdReloadRollbackLifecycleOperation.
            CLOSE_SYSTEMD_RELOAD_ROLLBACK_REHEARSAL_TRANSACTION
        )


@dataclass(frozen=True)
class VersionedStageBoundaryV5:
    stage: str
    permitted: int
    blocked: int

    def __post_init__(self) -> None:
        if not self.stage.strip():
            raise ValueError("stage boundary requires a stage name")
        if self.permitted < 0 or self.blocked < 0:
            raise ValueError("stage boundary counts cannot be negative")
        if self.permitted + self.blocked != len(ALL_OPERATIONS_V5):
            raise ValueError(
                "stage boundary must cover every v5 operation exactly"
            )


STAGE_BOUNDARIES_V5 = (
    VersionedStageBoundaryV5("C19", permitted=27, blocked=10),
)


def contract_snapshot_v5() -> tuple[tuple[str, str], ...]:
    """Return immutable v5 review metadata without touching the host."""

    return (
        ("version", "5"),
        ("v4_operation_count", str(len(ALL_OPERATIONS_V4))),
        ("operation_count", str(len(ALL_OPERATIONS_V5))),
        ("read_only_count", str(len(READ_ONLY_OPERATIONS_V5))),
        ("mutating_count", str(len(MUTATING_OPERATIONS_V5))),
        (
            "operations",
            ",".join(operation.value for operation in ALL_OPERATIONS_V5),
        ),
        (
            "systemd_reload_rollback_operation",
            SystemdReloadRollbackLifecycleOperation.
            CLOSE_SYSTEMD_RELOAD_ROLLBACK_REHEARSAL_TRANSACTION.value,
        ),
        ("activation_interface", "absent"),
    )


def _validate_contract() -> None:
    if len(ALL_OPERATIONS_V4) != 36:
        raise RuntimeError("Stage C18 v4 operation history changed unexpectedly")
    if len(ALL_OPERATIONS_V5) != 37:
        raise RuntimeError("Stage C19 v5 must contain exactly thirty-seven operations")
    values = tuple(operation.value for operation in ALL_OPERATIONS_V5)
    if len(values) != len(set(values)):
        raise RuntimeError("Stage C19 v5 contains a duplicate operation value")
    if len(READ_ONLY_OPERATIONS_V5) != 17:
        raise RuntimeError(
            "Stage C19 v5 read-only partition must contain seventeen operations"
        )
    if len(MUTATING_OPERATIONS_V5) != 20:
        raise RuntimeError(
            "Stage C19 v5 mutating partition must contain twenty operations"
        )
    if set(READ_ONLY_OPERATIONS_V5).intersection(MUTATING_OPERATIONS_V5):
        raise RuntimeError("Stage C19 v5 operation partitions overlap")
    if set(READ_ONLY_OPERATIONS_V5).union(MUTATING_OPERATIONS_V5) != set(
        ALL_OPERATIONS_V5
    ):
        raise RuntimeError("Stage C19 v5 operation partitions are incomplete")


_validate_contract()
