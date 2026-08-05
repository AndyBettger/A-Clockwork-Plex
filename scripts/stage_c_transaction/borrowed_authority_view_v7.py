#!/usr/bin/python3
from __future__ import annotations

"""Read-only Stage C21 view of the existing C20 authority owner.

The function in this module accepts an already-created
``RouteSelectionRollbackRehearsalAdapterV2`` and re-verifies its exact held lock,
authoritative transaction, complete snapshot boundary and currently selected
split-bus route. It returns immutable identities only.

It does not acquire or release a lock, expose a file descriptor, write an
approval, create a transaction, change a route, execute a command, construct an
adapter, expose a CLI or add an operation to ``ProductionAdapterV7``.
"""

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from .production_adapter_contract import (
    AUTHORITATIVE_TRANSACTION_ROOT,
    PRODUCTION_LOCK_PATH,
    AdapterStatus,
    PackageFingerprint,
    SnapshotIdentity,
    TransactionAction,
    TransactionIdentity,
)
from .production_lock_rehearsal_adapter import (
    ProductionLockFailure,
    _descriptor_evidence,
)
from .route_selection_rollback_rehearsal_adapter import (
    RouteSelectionRollbackFailure,
    _require_identity,
)
from .route_selection_rollback_rehearsal_adapter_v2 import (
    RouteSelectionRollbackRehearsalAdapterV2,
)
from .snapshot_core import CURRENT_ALSA_DESTINATION


@dataclass(frozen=True)
class BorrowedAuthorityViewV7:
    production_lock_path: str
    lock_lease_id: str
    lock_device: int
    lock_inode: int
    transaction: TransactionIdentity
    snapshot: SnapshotIdentity
    package: PackageFingerprint
    authoritative_transaction_path: str
    transaction_device: int
    transaction_inode: int
    selected_route_path: str
    selected_route_device: int
    selected_route_inode: int
    selected_route_sha256: str
    snapshot_complete: bool
    split_bus_route_selected: bool
    exact_lock_owned: bool
    exact_transaction_verified: bool

    def __post_init__(self) -> None:
        if self.production_lock_path != PRODUCTION_LOCK_PATH:
            raise ValueError("borrowed authority must use the canonical production lock")
        if not self.lock_lease_id.strip():
            raise ValueError("borrowed authority requires the existing lock lease")
        for label, value in (
            ("lock device", self.lock_device),
            ("lock inode", self.lock_inode),
            ("transaction device", self.transaction_device),
            ("transaction inode", self.transaction_inode),
            ("route device", self.selected_route_device),
            ("route inode", self.selected_route_inode),
        ):
            if value <= 0:
                raise ValueError(f"borrowed authority {label} must be positive")
        expected_transaction_path = str(
            Path(AUTHORITATIVE_TRANSACTION_ROOT) / self.transaction.value
        )
        if self.authoritative_transaction_path != expected_transaction_path:
            raise ValueError("borrowed authority transaction path is not canonical")
        if self.selected_route_path != CURRENT_ALSA_DESTINATION:
            raise ValueError("borrowed authority selected route path changed")
        if len(self.selected_route_sha256) != 64 or any(
            character not in "0123456789abcdef"
            for character in self.selected_route_sha256
        ):
            raise ValueError("borrowed authority route digest must be lowercase SHA-256")
        if not self.snapshot_complete:
            raise ValueError("borrowed authority requires all snapshot domains")
        if not self.split_bus_route_selected:
            raise ValueError("borrowed authority requires the currently selected split route")
        if not self.exact_lock_owned or not self.exact_transaction_verified:
            raise ValueError("borrowed authority requires exact current ownership proof")


@dataclass(frozen=True)
class BorrowedAuthorityViewResultV7:
    status: AdapterStatus
    detail: str
    payload: BorrowedAuthorityViewV7 | None = None

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("borrowed authority result detail must not be empty")
        if self.status is AdapterStatus.PASS and self.payload is None:
            raise ValueError("successful borrowed authority result requires a view")
        if self.status is not AdapterStatus.PASS and self.payload is not None:
            raise ValueError("failed borrowed authority result cannot carry a view")


def _fail(detail: str) -> BorrowedAuthorityViewResultV7:
    return BorrowedAuthorityViewResultV7(
        status=AdapterStatus.FAIL,
        detail=detail,
    )


def inspect_borrowed_authority_v7(
    owner: RouteSelectionRollbackRehearsalAdapterV2,
) -> BorrowedAuthorityViewResultV7:
    """Return identities from the existing owner without transferring authority."""

    if not isinstance(owner, RouteSelectionRollbackRehearsalAdapterV2):
        raise TypeError(
            "borrowed authority inspection requires the existing C20 owner lineage"
        )

    lock_fd = owner._lock_fd
    lease = owner.lease
    original_lock_evidence = owner.held_lock_evidence
    transaction = owner.authoritative_transaction
    transaction_path = owner.transaction_path
    transaction_device = owner._transaction_device
    transaction_inode = owner._transaction_inode
    route_candidate = owner._route_candidate

    if lock_fd is None or lease is None or original_lock_evidence is None:
        return _fail("the existing owner does not hold the production lock")
    if transaction is None or transaction_path is None:
        return _fail("the existing owner has no authoritative transaction")
    if transaction_device is None or transaction_inode is None:
        return _fail("authoritative transaction identity is incomplete")
    if transaction.action is not TransactionAction.INSTALL:
        return _fail("borrowed authority requires the authoritative install transaction")
    if transaction.package != owner.package:
        return _fail("authoritative transaction package no longer matches its owner")
    if transaction_path != Path(AUTHORITATIVE_TRANSACTION_ROOT) / transaction.transaction.value:
        return _fail("authoritative transaction path is not canonical")

    snapshot_complete = all(
        (
            owner._filesystem_captured,
            owner._service_captured,
            owner._mixer_captured,
            owner._loopback_captured,
            owner._dac_captured,
        )
    )
    if not snapshot_complete:
        return _fail("all five authoritative snapshot domains are required")
    if (
        not owner._route_selected
        or not owner._route_selected_once
        or owner._route_restored
        or owner._route_selection_count != 1
        or route_candidate is None
    ):
        return _fail("the split-bus route is not currently selected exactly once")

    try:
        current_lock_evidence = _descriptor_evidence(lock_fd)
        lock_stat = os.fstat(lock_fd)
        transaction_stat = transaction_path.lstat()
        selected_route = _require_identity(
            Path(CURRENT_ALSA_DESTINATION),
            route_candidate,
            "selected active route",
        )
    except (OSError, ProductionLockFailure, RouteSelectionRollbackFailure) as exc:
        return _fail(str(exc))

    if current_lock_evidence != original_lock_evidence:
        return _fail("held production-lock evidence changed")
    if not stat.S_ISREG(lock_stat.st_mode):
        return _fail("held production-lock descriptor is no longer a regular file")
    if lease.path != PRODUCTION_LOCK_PATH:
        return _fail("held production-lock lease path changed")
    if (
        stat.S_ISLNK(transaction_stat.st_mode)
        or not stat.S_ISDIR(transaction_stat.st_mode)
        or stat.S_IMODE(transaction_stat.st_mode) != 0o700
        or transaction_stat.st_uid != 0
        or transaction_stat.st_gid != 0
        or transaction_stat.st_dev != transaction_device
        or transaction_stat.st_ino != transaction_inode
    ):
        return _fail("authoritative transaction path identity or metadata changed")

    payload = BorrowedAuthorityViewV7(
        production_lock_path=PRODUCTION_LOCK_PATH,
        lock_lease_id=lease.lease_id,
        lock_device=lock_stat.st_dev,
        lock_inode=lock_stat.st_ino,
        transaction=transaction.transaction,
        snapshot=transaction.snapshot,
        package=transaction.package,
        authoritative_transaction_path=str(transaction_path),
        transaction_device=transaction_device,
        transaction_inode=transaction_inode,
        selected_route_path=CURRENT_ALSA_DESTINATION,
        selected_route_device=selected_route.device,
        selected_route_inode=selected_route.inode,
        selected_route_sha256=selected_route.digest,
        snapshot_complete=True,
        split_bus_route_selected=True,
        exact_lock_owned=True,
        exact_transaction_verified=True,
    )
    return BorrowedAuthorityViewResultV7(
        status=AdapterStatus.PASS,
        detail=(
            "exact existing lock, authoritative transaction and selected route "
            "re-verified without transferring authority"
        ),
        payload=payload,
    )
