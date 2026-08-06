#!/usr/bin/python3
from __future__ import annotations

"""Non-owning Stage C21 capability for the already-held C20 lock.

The capability retains the existing C20 owner and repeatedly re-runs the
reviewed borrowed-authority inspection before returning immutable proof. It
never exposes, duplicates, closes, locks, unlocks, writes, truncates, renames or
unlinks the borrowed descriptor.

This is an authority-gate slice only. It has no approval writer, production
entrypoint, generic path, command execution or adapter operation.
"""

import os
import stat
from dataclasses import dataclass
from enum import Enum

from .approval_authority_binding_v7 import ApprovalAuthorityBindingV7
from .borrowed_authority_view_v7 import (
    BorrowedAuthorityViewV7,
    inspect_borrowed_authority_v7,
)
from .production_adapter_contract import AdapterStatus
from .route_selection_rollback_rehearsal_adapter_v2 import (
    RouteSelectionRollbackRehearsalAdapterV2,
)


LOCK_MODE = 0o600
MAX_LOCK_CONTENT_BYTES = 512
_CAPABILITY_FACTORY_TOKEN = object()


class BorrowedLeaseContentStateV7(str, Enum):
    EMPTY = "empty"
    EXACT_CANONICAL = "exact-canonical"


@dataclass(frozen=True)
class BorrowedLockAuthorityGateV7:
    binding_sha256: str
    lock_device: int
    lock_inode: int
    lock_lease_id: str
    lease_content_state: BorrowedLeaseContentStateV7
    canonical_lease_bytes: bytes
    authority: BorrowedAuthorityViewV7

    def __post_init__(self) -> None:
        if self.binding_sha256 != self.binding_sha256.lower() or (
            len(self.binding_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.binding_sha256)
        ):
            raise ValueError("borrowed-lock gate requires a lowercase binding SHA-256")
        if self.lock_device <= 0 or self.lock_inode <= 0:
            raise ValueError("borrowed-lock gate requires a positive lock identity")
        if not self.lock_lease_id:
            raise ValueError("borrowed-lock gate requires a lock lease")
        expected = (self.lock_lease_id + "\n").encode("ascii")
        if self.canonical_lease_bytes != expected:
            raise ValueError("borrowed-lock gate canonical lease bytes changed")
        if (
            self.authority.lock_device != self.lock_device
            or self.authority.lock_inode != self.lock_inode
            or self.authority.lock_lease_id != self.lock_lease_id
        ):
            raise ValueError("borrowed-lock gate authority identity changed")


@dataclass(frozen=True)
class BorrowedLockCapabilityResultV7:
    status: AdapterStatus
    detail: str
    payload: BorrowedLockAuthorityGateV7 | None = None

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("borrowed-lock capability result requires detail")
        if self.status is AdapterStatus.PASS and self.payload is None:
            raise ValueError("successful borrowed-lock result requires proof")
        if self.status is not AdapterStatus.PASS and self.payload is not None:
            raise ValueError("failed borrowed-lock result cannot carry proof")


def _fail(detail: str) -> BorrowedLockCapabilityResultV7:
    return BorrowedLockCapabilityResultV7(
        status=AdapterStatus.FAIL,
        detail=detail,
    )


def _view_matches_binding(
    view: BorrowedAuthorityViewV7,
    binding: ApprovalAuthorityBindingV7,
) -> bool:
    return all(
        (
            view.transaction == binding.transaction,
            view.snapshot == binding.snapshot,
            view.package == binding.package,
            view.production_lock_path == binding.production_lock_path,
            view.lock_lease_id == binding.lock_lease_id,
            view.lock_device == binding.lock_device,
            view.lock_inode == binding.lock_inode,
            view.authoritative_transaction_path == binding.authoritative_transaction_path,
            view.transaction_device == binding.transaction_device,
            view.transaction_inode == binding.transaction_inode,
            view.selected_route_path == binding.selected_route_path,
            view.selected_route_device == binding.selected_route_device,
            view.selected_route_inode == binding.selected_route_inode,
            view.selected_route_sha256 == binding.selected_route_sha256,
            view.snapshot_complete == binding.source_snapshot_complete,
            view.split_bus_route_selected == binding.source_split_route_selected,
            view.exact_lock_owned == binding.source_exact_lock_owned,
            view.exact_transaction_verified == binding.source_exact_transaction_verified,
        )
    )


class BorrowedProductionLockCapabilityV7:
    """Re-verifiable read-only access to one owner-held production lock."""

    __slots__ = ("_owner", "_binding", "_borrowed_fd")

    def __init__(
        self,
        owner: RouteSelectionRollbackRehearsalAdapterV2,
        binding: ApprovalAuthorityBindingV7,
        borrowed_fd: int,
        *,
        _factory_token: object,
    ) -> None:
        if _factory_token is not _CAPABILITY_FACTORY_TOKEN:
            raise TypeError("borrowed production-lock capability must use its factory")
        self._owner = owner
        self._binding = binding
        self._borrowed_fd = borrowed_fd

    @property
    def binding(self) -> ApprovalAuthorityBindingV7:
        return self._binding

    def reverify(
        self,
        *,
        require_bound_lease: bool,
    ) -> BorrowedLockCapabilityResultV7:
        current_fd = self._owner._lock_fd
        if current_fd is None or current_fd != self._borrowed_fd:
            return _fail("C20 owner no longer exposes the original borrowed descriptor")

        inspected = inspect_borrowed_authority_v7(self._owner)
        if inspected.status is not AdapterStatus.PASS or inspected.payload is None:
            return _fail(f"borrowed authority re-verification failed: {inspected.detail}")
        view = inspected.payload
        if not _view_matches_binding(view, self._binding):
            return _fail("borrowed authority no longer matches the immutable binding")

        try:
            descriptor = os.fstat(self._borrowed_fd)
            if not stat.S_ISREG(descriptor.st_mode):
                return _fail("borrowed production-lock descriptor is not a regular file")
            if stat.S_IMODE(descriptor.st_mode) != LOCK_MODE:
                return _fail("borrowed production-lock descriptor mode changed")
            if descriptor.st_uid != 0 or descriptor.st_gid != 0:
                return _fail("borrowed production-lock descriptor owner changed")
            if (
                descriptor.st_dev != self._binding.lock_device
                or descriptor.st_ino != self._binding.lock_inode
            ):
                return _fail("borrowed production-lock descriptor identity changed")
            if descriptor.st_size < 0 or descriptor.st_size > MAX_LOCK_CONTENT_BYTES:
                return _fail("borrowed production-lock content is too large")
            raw = os.pread(
                self._borrowed_fd,
                MAX_LOCK_CONTENT_BYTES + 1,
                0,
            )
        except OSError as exc:
            return _fail(f"cannot observe borrowed production lock: {exc}")

        if len(raw) != descriptor.st_size:
            return _fail("borrowed production-lock content changed during observation")
        canonical = (self._binding.lock_lease_id + "\n").encode("ascii")
        if raw == b"":
            state = BorrowedLeaseContentStateV7.EMPTY
        elif raw == canonical:
            state = BorrowedLeaseContentStateV7.EXACT_CANONICAL
        else:
            return _fail("borrowed production-lock lease content is not canonical")
        if require_bound_lease and state is not BorrowedLeaseContentStateV7.EXACT_CANONICAL:
            return _fail("borrowed production-lock lease has not been canonically bound")

        return BorrowedLockCapabilityResultV7(
            status=AdapterStatus.PASS,
            detail=(
                "exact borrowed C20 authority and canonical lease re-verified"
                if state is BorrowedLeaseContentStateV7.EXACT_CANONICAL
                else "exact borrowed C20 authority re-verified with an empty lease file"
            ),
            payload=BorrowedLockAuthorityGateV7(
                binding_sha256=self._binding.binding_sha256,
                lock_device=descriptor.st_dev,
                lock_inode=descriptor.st_ino,
                lock_lease_id=self._binding.lock_lease_id,
                lease_content_state=state,
                canonical_lease_bytes=canonical,
                authority=view,
            ),
        )


def borrow_production_lock_capability_v7(
    owner: RouteSelectionRollbackRehearsalAdapterV2,
    binding: ApprovalAuthorityBindingV7,
) -> tuple[BorrowedProductionLockCapabilityV7 | None, BorrowedLockCapabilityResultV7]:
    """Borrow the existing descriptor without transferring lifetime ownership."""

    if not isinstance(owner, RouteSelectionRollbackRehearsalAdapterV2):
        raise TypeError("borrowed lock capability requires the existing C20 owner lineage")
    if not isinstance(binding, ApprovalAuthorityBindingV7):
        raise TypeError("borrowed lock capability requires ApprovalAuthorityBindingV7")
    borrowed_fd = owner._lock_fd
    if borrowed_fd is None or not isinstance(borrowed_fd, int) or borrowed_fd < 0:
        result = _fail("C20 owner has no descriptor available to borrow")
        return None, result

    capability = BorrowedProductionLockCapabilityV7(
        owner,
        binding,
        borrowed_fd,
        _factory_token=_CAPABILITY_FACTORY_TOKEN,
    )
    result = capability.reverify(require_bound_lease=False)
    if result.status is not AdapterStatus.PASS:
        return None, result
    return capability, result
