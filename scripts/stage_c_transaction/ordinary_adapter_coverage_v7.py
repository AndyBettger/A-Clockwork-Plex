#!/usr/bin/python3
from __future__ import annotations

"""Static Stage C21 ordinary-adapter ownership and readiness audit.

This module records the exact implementation boundary at the end of Stage C20:
29 v1-v6 operations exist in the physically exercised mandatory-rollback
rehearsal chain, nine ordinary operations remain blocked on that adapter, and
the four Stage C21 approval operations exist only in the disposable laboratory
adapter.

No operation is marked production-terminal-ready. Similar Linux mechanics in
the separate runtime-authority protocol are recorded only as related evidence;
they are not treated as implementations of ``ProductionAdapterV6``.

The module contains no host access, filesystem operation, command execution,
entrypoint, adapter construction or generic dispatch boundary.
"""

from dataclasses import dataclass
from enum import Enum

from .activation_commit_program_v7 import (
    ACTIVATION_EXACT_ROLLBACK_V7,
    ACTIVATION_INSTALL_SUFFIX_V7,
)
from .production_adapter_contract import (
    AUTHORITATIVE_TRANSACTION_ROOT,
    PRODUCTION_LOCK_PATH,
    AdapterOperation,
)
from .production_adapter_lifecycle_v2 import TransactionLifecycleOperation
from .production_adapter_lifecycle_v3 import (
    RestoredRehearsalLifecycleOperation,
)
from .production_adapter_lifecycle_v4 import (
    ExactRollbackRehearsalLifecycleOperation,
)
from .production_adapter_lifecycle_v5 import (
    SystemdReloadRollbackLifecycleOperation,
)
from .production_adapter_lifecycle_v6 import (
    ALL_OPERATIONS_V6,
    RouteSelectionRollbackLifecycleOperation,
)
from .production_adapter_lifecycle_v7 import (
    ALL_OPERATIONS_V7,
    ActivationApprovalLifecycleOperation,
    ProductionOperationV7,
)
from .route_selection_rollback_rehearsal_adapter import (
    PERMITTED_V1_OPERATIONS as C20_PERMITTED_V1_OPERATIONS,
)


class AdapterEvidenceV7(str, Enum):
    C20_MANDATORY_ROLLBACK_REHEARSAL = (
        "c20-mandatory-rollback-rehearsal"
    )
    BLOCKED_ORDINARY_CONTRACT = "blocked-ordinary-contract"
    DISPOSABLE_APPROVAL_LABORATORY = "disposable-approval-laboratory"


class RelatedRuntimeMechanicsV7(str, Enum):
    NONE = "none"
    SEPARATE_RUNTIME_AUTHORITY_PROTOCOL = (
        "separate-runtime-authority-protocol"
    )


@dataclass(frozen=True)
class OperationCoverageV7:
    operation: ProductionOperationV7
    evidence: AdapterEvidenceV7
    owner: str
    physically_rehearsed_on_appliance: bool
    disposable_filesystem_proved: bool
    related_runtime_mechanics: RelatedRuntimeMechanicsV7
    production_terminal_ready: bool
    detail: str

    def __post_init__(self) -> None:
        if not self.owner.strip() or not self.detail.strip():
            raise ValueError("operation coverage owner and detail must not be empty")
        if self.production_terminal_ready:
            raise ValueError(
                "Stage C21 audit must not claim a production-terminal-ready operation"
            )
        if (
            self.evidence
            is AdapterEvidenceV7.C20_MANDATORY_ROLLBACK_REHEARSAL
            and not self.physically_rehearsed_on_appliance
        ):
            raise ValueError("C20 rehearsal evidence must record physical rehearsal")
        if (
            self.evidence
            is AdapterEvidenceV7.DISPOSABLE_APPROVAL_LABORATORY
            and not self.disposable_filesystem_proved
        ):
            raise ValueError("approval laboratory evidence requires disposable proof")
        if self.physically_rehearsed_on_appliance and self.disposable_filesystem_proved:
            raise ValueError("one coverage record cannot claim both evidence domains")


C20_CLOSURE_OPERATIONS = (
    TransactionLifecycleOperation.ABORT_UNCOMMITTED_TRANSACTION,
    RestoredRehearsalLifecycleOperation.CLOSE_RESTORED_REHEARSAL_TRANSACTION,
    ExactRollbackRehearsalLifecycleOperation.
    CLOSE_EXACT_ROLLBACK_REHEARSAL_TRANSACTION,
    SystemdReloadRollbackLifecycleOperation.
    CLOSE_SYSTEMD_RELOAD_ROLLBACK_REHEARSAL_TRANSACTION,
    RouteSelectionRollbackLifecycleOperation.
    CLOSE_ROUTE_SELECTION_ROLLBACK_REHEARSAL_TRANSACTION,
)

C20_REHEARSAL_OPERATIONS: tuple[ProductionOperationV7, ...] = (
    *C20_PERMITTED_V1_OPERATIONS,
    *C20_CLOSURE_OPERATIONS,
)
_C20_REHEARSAL_SET = frozenset(C20_REHEARSAL_OPERATIONS)

C20_BLOCKED_ORDINARY_OPERATIONS: tuple[ProductionOperationV7, ...] = tuple(
    operation
    for operation in ALL_OPERATIONS_V6
    if operation not in _C20_REHEARSAL_SET
)
_C20_BLOCKED_SET = frozenset(C20_BLOCKED_ORDINARY_OPERATIONS)

DISPOSABLE_APPROVAL_OPERATIONS: tuple[ProductionOperationV7, ...] = tuple(
    ActivationApprovalLifecycleOperation
)
_DISPOSABLE_APPROVAL_SET = frozenset(DISPOSABLE_APPROVAL_OPERATIONS)

RUNTIME_AUTHORITY_RELATED_OPERATIONS: tuple[ProductionOperationV7, ...] = (
    AdapterOperation.START_MANAGED_STAGE_C_SERVICES,
    AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES,
    AdapterOperation.VERIFY_SPLIT_BUS_HEALTH,
    AdapterOperation.SELECT_DIRECT_FAILBACK_ROUTE,
)
_RUNTIME_RELATED_SET = frozenset(RUNTIME_AUTHORITY_RELATED_OPERATIONS)


_BLOCKED_DETAILS = {
    AdapterOperation.START_MANAGED_STAGE_C_SERVICES:
        "C20 stops before managed runtime start; temporary first-start mechanics exist only in the separate runtime-authority protocol",
    AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES:
        "C20 never starts managed runtime; child stop mechanics exist only in the separate runtime-authority protocol",
    AdapterOperation.VERIFY_SPLIT_BUS_HEALTH:
        "strict health mechanics exist in runtime authority but are not a ProductionAdapterV6 implementation",
    AdapterOperation.RUN_FINITE_MUSIC_PROBE:
        "no ordinary adapter implementation opens the finite music probe",
    AdapterOperation.RUN_FINITE_ALARM_PROBE:
        "no ordinary adapter implementation opens the finite alarm probe",
    AdapterOperation.WRITE_COMMIT_MANIFEST:
        "historical operation remains blocked and is not a second Stage C21 commit marker",
    AdapterOperation.SELECT_DIRECT_FAILBACK_ROUTE:
        "direct-route mechanics exist in runtime authority but not as this ordinary transaction operation",
    AdapterOperation.RESTORE_MIXER_STATE:
        "component mixer restoration remains blocked on the furthest C20 adapter",
    AdapterOperation.RESTORE_SERVICE_STATE:
        "component service restoration remains blocked on the furthest C20 adapter",
}


def _coverage(operation: ProductionOperationV7) -> OperationCoverageV7:
    if operation in _C20_REHEARSAL_SET:
        return OperationCoverageV7(
            operation=operation,
            evidence=AdapterEvidenceV7.C20_MANDATORY_ROLLBACK_REHEARSAL,
            owner="RouteSelectionRollbackRehearsalAdapterV2 lineage",
            physically_rehearsed_on_appliance=True,
            disposable_filesystem_proved=False,
            related_runtime_mechanics=RelatedRuntimeMechanicsV7.NONE,
            production_terminal_ready=False,
            detail=(
                "implemented only inside the physically exercised C20 "
                "mandatory-rollback rehearsal chain"
            ),
        )
    if operation in _C20_BLOCKED_SET:
        return OperationCoverageV7(
            operation=operation,
            evidence=AdapterEvidenceV7.BLOCKED_ORDINARY_CONTRACT,
            owner="BlockedProductionAdapterV6 boundary",
            physically_rehearsed_on_appliance=False,
            disposable_filesystem_proved=False,
            related_runtime_mechanics=(
                RelatedRuntimeMechanicsV7.SEPARATE_RUNTIME_AUTHORITY_PROTOCOL
                if operation in _RUNTIME_RELATED_SET
                else RelatedRuntimeMechanicsV7.NONE
            ),
            production_terminal_ready=False,
            detail=_BLOCKED_DETAILS[operation],
        )
    if operation in _DISPOSABLE_APPROVAL_SET:
        return OperationCoverageV7(
            operation=operation,
            evidence=AdapterEvidenceV7.DISPOSABLE_APPROVAL_LABORATORY,
            owner="DisposableActivationApprovalLifecycleAdapter",
            physically_rehearsed_on_appliance=False,
            disposable_filesystem_proved=True,
            related_runtime_mechanics=RelatedRuntimeMechanicsV7.NONE,
            production_terminal_ready=False,
            detail=(
                "proved beneath a fresh disposable root; no production path, "
                "lock binding or appliance approval writer exists"
            ),
        )
    raise RuntimeError(f"unclassified Stage C21 operation: {operation.value}")


OPERATION_COVERAGE_V7: tuple[OperationCoverageV7, ...] = tuple(
    _coverage(operation) for operation in ALL_OPERATIONS_V7
)
COVERAGE_BY_OPERATION_V7 = {
    item.operation: item for item in OPERATION_COVERAGE_V7
}


@dataclass(frozen=True)
class AuthorityOwnershipSnapshotV7:
    production_lock_path: str
    authoritative_transaction_root: str
    current_lock_owner: str
    current_transaction_owner: str
    approval_must_bind_existing_lock: bool
    second_production_lock_authority_forbidden: bool
    detail: str

    def __post_init__(self) -> None:
        if not self.production_lock_path.startswith("/"):
            raise ValueError("production lock path must be absolute")
        if not self.authoritative_transaction_root.startswith("/"):
            raise ValueError("authoritative transaction root must be absolute")
        if not self.current_lock_owner.strip() or not self.current_transaction_owner.strip():
            raise ValueError("authority owners must not be empty")
        if not self.approval_must_bind_existing_lock:
            raise ValueError("Stage C21 approval must bind the existing held lock")
        if not self.second_production_lock_authority_forbidden:
            raise ValueError("a second production lock authority must remain forbidden")
        if not self.detail.strip():
            raise ValueError("authority ownership detail must not be empty")


AUTHORITY_OWNERSHIP_V7 = AuthorityOwnershipSnapshotV7(
    production_lock_path=PRODUCTION_LOCK_PATH,
    authoritative_transaction_root=AUTHORITATIVE_TRANSACTION_ROOT,
    current_lock_owner="ProductionLockRehearsalAdapter lineage",
    current_transaction_owner="AuthoritativeSnapshotRehearsalAdapter lineage",
    approval_must_bind_existing_lock=True,
    second_production_lock_authority_forbidden=True,
    detail=(
        "future approval operations must extend the exact held lock inode and "
        "authoritative transaction; they must not acquire a parallel lock"
    ),
)


@dataclass(frozen=True)
class TerminalReadinessSnapshotV7:
    total_operations: int
    c20_rehearsal_operations: int
    blocked_ordinary_operations: int
    disposable_approval_operations: int
    activation_suffix_operations: int
    exact_rollback_operations: int
    production_ready_operations: int
    production_activation_ready: bool
    production_exact_rollback_ready: bool
    smallest_safe_next_increment: str

    def __post_init__(self) -> None:
        if self.total_operations != 42:
            raise ValueError("Stage C21 operation count changed")
        if (
            self.c20_rehearsal_operations
            + self.blocked_ordinary_operations
            + self.disposable_approval_operations
            != self.total_operations
        ):
            raise ValueError("Stage C21 coverage partition is incomplete")
        if self.production_ready_operations != 0:
            raise ValueError("audit must not claim production-ready operations")
        if self.production_activation_ready or self.production_exact_rollback_ready:
            raise ValueError("Stage C21 terminal execution is not production ready")
        if not self.smallest_safe_next_increment.strip():
            raise ValueError("readiness snapshot requires one next increment")


TERMINAL_READINESS_V7 = TerminalReadinessSnapshotV7(
    total_operations=len(OPERATION_COVERAGE_V7),
    c20_rehearsal_operations=len(C20_REHEARSAL_OPERATIONS),
    blocked_ordinary_operations=len(C20_BLOCKED_ORDINARY_OPERATIONS),
    disposable_approval_operations=len(DISPOSABLE_APPROVAL_OPERATIONS),
    activation_suffix_operations=len(ACTIVATION_INSTALL_SUFFIX_V7),
    exact_rollback_operations=len(ACTIVATION_EXACT_ROLLBACK_V7),
    production_ready_operations=sum(
        item.production_terminal_ready for item in OPERATION_COVERAGE_V7
    ),
    production_activation_ready=False,
    production_exact_rollback_ready=False,
    smallest_safe_next_increment=(
        "add a read-only typed view of the existing held lock and authoritative "
        "transaction identities before designing any production approval writer"
    ),
)


def _validate_coverage() -> None:
    if len(OPERATION_COVERAGE_V7) != len(ALL_OPERATIONS_V7) != 42:
        raise RuntimeError("Stage C21 coverage count changed")
    if tuple(item.operation for item in OPERATION_COVERAGE_V7) != ALL_OPERATIONS_V7:
        raise RuntimeError("Stage C21 coverage order changed")
    if len(COVERAGE_BY_OPERATION_V7) != 42:
        raise RuntimeError("Stage C21 coverage contains duplicate operations")
    if len(C20_REHEARSAL_OPERATIONS) != 29:
        raise RuntimeError("C20 rehearsal operation count changed")
    if len(C20_BLOCKED_ORDINARY_OPERATIONS) != 9:
        raise RuntimeError("C20 blocked operation count changed")
    if len(DISPOSABLE_APPROVAL_OPERATIONS) != 4:
        raise RuntimeError("Stage C21 approval operation count changed")
    if _C20_REHEARSAL_SET.intersection(_C20_BLOCKED_SET):
        raise RuntimeError("C20 rehearsal and blocked sets overlap")
    if _C20_REHEARSAL_SET.union(_C20_BLOCKED_SET) != frozenset(ALL_OPERATIONS_V6):
        raise RuntimeError("C20 ordinary operation partition changed")
    if _C20_REHEARSAL_SET.union(_C20_BLOCKED_SET).intersection(
        _DISPOSABLE_APPROVAL_SET
    ):
        raise RuntimeError("ordinary and approval ownership overlap")
    if any(item.production_terminal_ready for item in OPERATION_COVERAGE_V7):
        raise RuntimeError("Stage C21 audit accidentally marks production readiness")
    if not _RUNTIME_RELATED_SET.issubset(_C20_BLOCKED_SET):
        raise RuntimeError("related runtime mechanics must remain blocked ordinary ops")


_validate_coverage()
