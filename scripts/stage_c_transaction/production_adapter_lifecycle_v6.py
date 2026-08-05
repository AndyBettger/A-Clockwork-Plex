#!/usr/bin/python3
from __future__ import annotations

"""Stage C20 versioned split-bus route-selection rollback closure.

The frozen v1 through v5 operation histories remain unchanged. This v6 view
adds one typed lifecycle operation for a transaction that installed the reviewed
managed files, reloaded systemd, selected the reviewed split-bus ALSA route while
all application services and audio endpoints remained quiesced, restored the
exact original active-route inode, restored the authoritative filesystem and
systemd-manager state, restored the captured application state, retained audit
evidence and removed the transaction before lock release.

The module contains no host access, entrypoint, executable command or generic
dispatch boundary.
"""

from dataclasses import dataclass
from enum import Enum
from typing import NoReturn, Protocol, runtime_checkable

from .production_adapter_contract import AdapterStatus, TransactionIdentity
from .production_adapter_lifecycle_v5 import (
    ALL_OPERATIONS_V5,
    MUTATING_OPERATIONS_V5,
    READ_ONLY_OPERATIONS_V5,
    BlockedProductionAdapterV5,
    ProductionAdapterV5,
    ProductionOperationV5,
)


class RouteSelectionRollbackLifecycleOperation(str, Enum):
    CLOSE_ROUTE_SELECTION_ROLLBACK_REHEARSAL_TRANSACTION = (
        "close-route-selection-rollback-rehearsal-transaction"
    )


ProductionOperationV6 = (
    ProductionOperationV5 | RouteSelectionRollbackLifecycleOperation
)

ALL_OPERATIONS_V6: tuple[ProductionOperationV6, ...] = (
    *ALL_OPERATIONS_V5,
    *tuple(RouteSelectionRollbackLifecycleOperation),
)
READ_ONLY_OPERATIONS_V6: tuple[ProductionOperationV6, ...] = tuple(
    READ_ONLY_OPERATIONS_V5
)
MUTATING_OPERATIONS_V6: tuple[ProductionOperationV6, ...] = (
    *MUTATING_OPERATIONS_V5,
    RouteSelectionRollbackLifecycleOperation.
    CLOSE_ROUTE_SELECTION_ROLLBACK_REHEARSAL_TRANSACTION,
)


@dataclass(frozen=True)
class RouteSelectionRollbackTransactionReceipt:
    transaction: TransactionIdentity
    state: str
    mutation_started: bool
    managed_files_installed: bool
    systemd_reloaded: bool
    split_bus_route_selected: bool
    active_route_restored: bool
    filesystem_restored: bool
    systemd_manager_restored: bool
    services_restored: bool
    committed: bool
    transaction_path_absent: bool
    parents_restored: bool
    installed_file_count: int
    daemon_reload_count: int
    route_selection_count: int
    audit_evidence: str

    def __post_init__(self) -> None:
        if self.state != "split-bus-route-rolled-back-and-closed":
            raise ValueError(
                "route-selection rollback receipt must use the closed state"
            )
        if not self.mutation_started:
            raise ValueError(
                "route-selection rollback requires a crossed mutation boundary"
            )
        if not self.managed_files_installed:
            raise ValueError(
                "route-selection rollback must prove managed files were installed"
            )
        if not self.systemd_reloaded:
            raise ValueError(
                "route-selection rollback must prove the manager observed the units"
            )
        if not self.split_bus_route_selected:
            raise ValueError(
                "route-selection rollback must prove the split-bus route was selected"
            )
        if not self.active_route_restored:
            raise ValueError(
                "route-selection rollback must prove exact active-route restoration"
            )
        if not self.filesystem_restored:
            raise ValueError(
                "route-selection rollback must prove filesystem restoration"
            )
        if not self.systemd_manager_restored:
            raise ValueError(
                "route-selection rollback must prove manager-state restoration"
            )
        if not self.services_restored:
            raise ValueError(
                "route-selection rollback must prove service restoration"
            )
        if self.committed:
            raise ValueError(
                "route-selection rollback must not claim an installation commit"
            )
        if not self.transaction_path_absent or not self.parents_restored:
            raise ValueError(
                "route-selection rollback receipt requires exact cleanup"
            )
        if self.installed_file_count != 12:
            raise ValueError(
                "route-selection rollback must cover exactly twelve files"
            )
        if self.daemon_reload_count != 2:
            raise ValueError(
                "route-selection rollback requires exactly two daemon reloads"
            )
        if self.route_selection_count != 1:
            raise ValueError(
                "route-selection rollback requires exactly one route selection"
            )
        if not isinstance(self.audit_evidence, str) or not self.audit_evidence.strip():
            raise ValueError(
                "route-selection rollback requires adapter-owned audit evidence"
            )


@dataclass(frozen=True)
class RouteSelectionRollbackAdapterResult:
    operation: RouteSelectionRollbackLifecycleOperation
    status: AdapterStatus
    detail: str
    payload: RouteSelectionRollbackTransactionReceipt | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ValueError(
                "route-selection rollback result detail must not be empty"
            )
        if self.status is not AdapterStatus.PASS and self.payload is not None:
            raise ValueError(
                "failed route-selection rollback result must not carry a receipt"
            )


class ProductionRouteSelectionRollbackAdapterBlocked(RuntimeError):
    """Raised while the v6 route-selection rollback lifecycle remains blocked."""

    def __init__(
        self,
        operation: RouteSelectionRollbackLifecycleOperation,
    ) -> None:
        self.operation = operation
        super().__init__(
            "Stage C production route-selection rollback adapter is blocked: "
            f"{operation.value}"
        )


@runtime_checkable
class ProductionAdapterV6(ProductionAdapterV5, Protocol):
    def close_route_selection_rollback_rehearsal_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> RouteSelectionRollbackAdapterResult: ...


class BlockedProductionAdapterV6(BlockedProductionAdapterV5):
    """Blocked v6 adapter: all v1 through v6 methods remain unavailable."""

    @staticmethod
    def _route_selection_rollback_blocked(
        operation: RouteSelectionRollbackLifecycleOperation,
    ) -> NoReturn:
        raise ProductionRouteSelectionRollbackAdapterBlocked(operation)

    def close_route_selection_rollback_rehearsal_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> RouteSelectionRollbackAdapterResult:
        del transaction
        return self._route_selection_rollback_blocked(
            RouteSelectionRollbackLifecycleOperation.
            CLOSE_ROUTE_SELECTION_ROLLBACK_REHEARSAL_TRANSACTION
        )


@dataclass(frozen=True)
class VersionedStageBoundaryV6:
    stage: str
    permitted: int
    blocked: int

    def __post_init__(self) -> None:
        if not self.stage.strip():
            raise ValueError("stage boundary requires a stage name")
        if self.permitted < 0 or self.blocked < 0:
            raise ValueError("stage boundary counts cannot be negative")
        if self.permitted + self.blocked != len(ALL_OPERATIONS_V6):
            raise ValueError(
                "stage boundary must cover every v6 operation exactly"
            )


STAGE_BOUNDARIES_V6 = (
    VersionedStageBoundaryV6("C20", permitted=29, blocked=9),
)


def contract_snapshot_v6() -> tuple[tuple[str, str], ...]:
    """Return immutable v6 review metadata without touching the host."""

    return (
        ("version", "6"),
        ("v5_operation_count", str(len(ALL_OPERATIONS_V5))),
        ("operation_count", str(len(ALL_OPERATIONS_V6))),
        ("read_only_count", str(len(READ_ONLY_OPERATIONS_V6))),
        ("mutating_count", str(len(MUTATING_OPERATIONS_V6))),
        (
            "operations",
            ",".join(operation.value for operation in ALL_OPERATIONS_V6),
        ),
        (
            "route_selection_rollback_operation",
            RouteSelectionRollbackLifecycleOperation.
            CLOSE_ROUTE_SELECTION_ROLLBACK_REHEARSAL_TRANSACTION.value,
        ),
        ("activation_interface", "absent"),
    )


def _validate_contract() -> None:
    if len(ALL_OPERATIONS_V5) != 37:
        raise RuntimeError("Stage C19 v5 operation history changed unexpectedly")
    if len(ALL_OPERATIONS_V6) != 38:
        raise RuntimeError("Stage C20 v6 must contain exactly thirty-eight operations")
    values = tuple(operation.value for operation in ALL_OPERATIONS_V6)
    if len(values) != len(set(values)):
        raise RuntimeError("Stage C20 v6 contains a duplicate operation value")
    if len(READ_ONLY_OPERATIONS_V6) != 17:
        raise RuntimeError(
            "Stage C20 v6 read-only partition must contain seventeen operations"
        )
    if len(MUTATING_OPERATIONS_V6) != 21:
        raise RuntimeError(
            "Stage C20 v6 mutating partition must contain twenty-one operations"
        )
    if set(READ_ONLY_OPERATIONS_V6).intersection(MUTATING_OPERATIONS_V6):
        raise RuntimeError("Stage C20 v6 operation partitions overlap")
    if set(READ_ONLY_OPERATIONS_V6).union(MUTATING_OPERATIONS_V6) != set(
        ALL_OPERATIONS_V6
    ):
        raise RuntimeError("Stage C20 v6 operation partitions are incomplete")


_validate_contract()
