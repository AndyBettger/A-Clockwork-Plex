#!/usr/bin/python3
from __future__ import annotations

"""Disposable non-owning Stage C21 canonical lock-lease binder.

The binder borrows one descriptor from ``DisposableC20LockOwnerV7`` and may
perform only the exact canonical lease truncate/write/fsync sequence. The owner
retains all create, flock, unlink, unlock and close authority.

This module has no production path, approval object, command, service, audio
endpoint, CLI or generic dispatch boundary.
"""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .disposable_c20_lock_owner_v7 import (
    DisposableC20LockObservationResultV7,
    DisposableC20LockOwnerV7,
)
from .production_adapter_contract import AdapterStatus


FaultHook = Callable[[str], None]


def _noop_fault_hook(_point: str) -> None:
    return None


class DisposableLeaseBindingDispositionV7(str, Enum):
    CANONICAL_BOUND = "canonical-bound"
    EMPTY_ROLLBACK_PERMITTED = "empty-rollback-permitted"
    MANUAL_RECONCILIATION = "manual-reconciliation"


@dataclass(frozen=True)
class DisposableCanonicalLeaseBindingResultV7:
    status: AdapterStatus
    disposition: DisposableLeaseBindingDispositionV7
    detail: str
    lease_id: str
    canonical_bytes: bytes
    reconciled_after_exception: bool
    ordinary_rollback_permitted: bool
    manual_reconciliation_required: bool
    owner_lock_remains_held: bool

    def __post_init__(self) -> None:
        if not self.detail.strip() or not self.lease_id:
            raise ValueError("disposable lease-binding result requires identity and detail")
        if self.canonical_bytes != (self.lease_id + "\n").encode("ascii"):
            raise ValueError("disposable lease-binding canonical bytes changed")
        if self.disposition is DisposableLeaseBindingDispositionV7.CANONICAL_BOUND:
            if self.status is not AdapterStatus.PASS:
                raise ValueError("canonical-bound disposition must pass")
            if not self.owner_lock_remains_held:
                raise ValueError("canonical binding requires retained owner authority")
            if self.ordinary_rollback_permitted or self.manual_reconciliation_required:
                raise ValueError("canonical-bound disposition cannot request recovery")
        elif self.disposition is DisposableLeaseBindingDispositionV7.EMPTY_ROLLBACK_PERMITTED:
            if self.status is AdapterStatus.PASS:
                raise ValueError("empty rollback disposition must report failure")
            if not self.owner_lock_remains_held:
                raise ValueError("empty rollback begins beneath retained owner authority")
            if not self.ordinary_rollback_permitted or self.manual_reconciliation_required:
                raise ValueError("empty disposition requires ordinary rollback only")
            if self.reconciled_after_exception:
                raise ValueError("empty disposition is not a completed reconciliation")
        elif self.disposition is DisposableLeaseBindingDispositionV7.MANUAL_RECONCILIATION:
            if self.status is AdapterStatus.PASS:
                raise ValueError("manual reconciliation disposition must fail")
            if self.ordinary_rollback_permitted or not self.manual_reconciliation_required:
                raise ValueError("manual disposition must retain uncertain authority")
            if self.reconciled_after_exception:
                raise ValueError("manual disposition cannot be reconciled")


def _result(
    *,
    owner: DisposableC20LockOwnerV7,
    status: AdapterStatus,
    disposition: DisposableLeaseBindingDispositionV7,
    detail: str,
    reconciled_after_exception: bool = False,
) -> DisposableCanonicalLeaseBindingResultV7:
    return DisposableCanonicalLeaseBindingResultV7(
        status=status,
        disposition=disposition,
        detail=detail,
        lease_id=owner.lease_id,
        canonical_bytes=owner.canonical_lease_bytes,
        reconciled_after_exception=reconciled_after_exception,
        ordinary_rollback_permitted=(
            disposition
            is DisposableLeaseBindingDispositionV7.EMPTY_ROLLBACK_PERMITTED
        ),
        manual_reconciliation_required=(
            disposition
            is DisposableLeaseBindingDispositionV7.MANUAL_RECONCILIATION
        ),
        owner_lock_remains_held=owner.lock_held,
    )


def _write_all_at(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    offset = 0
    while view:
        written = os.pwrite(fd, view, offset)
        if written <= 0:
            raise OSError("short disposable canonical lease write")
        offset += written
        view = view[written:]


def _classify_observation(
    owner: DisposableC20LockOwnerV7,
    observed: DisposableC20LockObservationResultV7,
    *,
    exception_detail: str,
) -> DisposableCanonicalLeaseBindingResultV7:
    if observed.status is not AdapterStatus.PASS or observed.payload is None:
        return _result(
            owner=owner,
            status=AdapterStatus.FAIL,
            disposition=DisposableLeaseBindingDispositionV7.MANUAL_RECONCILIATION,
            detail=(
                f"{exception_detail}; post-exception lock observation failed: "
                f"{observed.detail}"
            ),
        )
    raw = observed.payload.raw_content
    if raw == owner.canonical_lease_bytes:
        return _result(
            owner=owner,
            status=AdapterStatus.PASS,
            disposition=DisposableLeaseBindingDispositionV7.CANONICAL_BOUND,
            detail=(
                f"{exception_detail}; exact canonical lease observed, so binding "
                "completed and was reconciled without retry"
            ),
            reconciled_after_exception=True,
        )
    if raw == b"":
        return _result(
            owner=owner,
            status=AdapterStatus.FAIL,
            disposition=(
                DisposableLeaseBindingDispositionV7.EMPTY_ROLLBACK_PERMITTED
            ),
            detail=(
                f"{exception_detail}; lock remained empty, so ordinary exact "
                "rollback is permitted without a blind retry"
            ),
        )
    return _result(
        owner=owner,
        status=AdapterStatus.FAIL,
        disposition=DisposableLeaseBindingDispositionV7.MANUAL_RECONCILIATION,
        detail=(
            f"{exception_detail}; partial or different lease bytes require manual "
            "reconciliation while the owner retains its lock"
        ),
    )


class DisposableCanonicalLeaseBinderV7:
    """Borrowed-descriptor binder with no lock-lifetime authority."""

    __slots__ = ("_owner", "_fault_hook")

    def __init__(
        self,
        owner: DisposableC20LockOwnerV7,
        *,
        fault_hook: FaultHook | None = None,
    ) -> None:
        if not isinstance(owner, DisposableC20LockOwnerV7):
            raise TypeError("disposable canonical lease binder requires its C20-shaped owner")
        self._owner = owner
        self._fault_hook = fault_hook or _noop_fault_hook

    @property
    def lease_id(self) -> str:
        return self._owner.lease_id

    def bind(self) -> DisposableCanonicalLeaseBindingResultV7:
        before = self._owner.observe()
        if before.status is not AdapterStatus.PASS or before.payload is None:
            return _result(
                owner=self._owner,
                status=AdapterStatus.FAIL,
                disposition=(
                    DisposableLeaseBindingDispositionV7.MANUAL_RECONCILIATION
                ),
                detail=f"cannot establish pre-write owner authority: {before.detail}",
            )
        if before.payload.raw_content == self._owner.canonical_lease_bytes:
            return _result(
                owner=self._owner,
                status=AdapterStatus.PASS,
                disposition=DisposableLeaseBindingDispositionV7.CANONICAL_BOUND,
                detail="exact canonical lease was already bound; no write was required",
            )
        if before.payload.raw_content != b"":
            return _result(
                owner=self._owner,
                status=AdapterStatus.FAIL,
                disposition=(
                    DisposableLeaseBindingDispositionV7.MANUAL_RECONCILIATION
                ),
                detail=(
                    "pre-existing disposable lock content is neither empty nor "
                    "the exact canonical lease"
                ),
            )

        try:
            fd = self._owner._borrow_descriptor_for_lease_binder()
            self._fault_hook("before-lease-truncate")
            os.ftruncate(fd, 0)
            self._fault_hook("after-lease-truncate")
            _write_all_at(fd, self._owner.canonical_lease_bytes)
            self._fault_hook("after-lease-write")
            os.ftruncate(fd, len(self._owner.canonical_lease_bytes))
            self._fault_hook("after-lease-exact-truncate")
            os.fsync(fd)
            self._fault_hook("after-lease-fsync")
        except BaseException as exc:
            return _classify_observation(
                self._owner,
                self._owner.observe(),
                exception_detail=f"canonical lease binding raised {type(exc).__name__}: {exc}",
            )

        after = self._owner.observe()
        if after.status is not AdapterStatus.PASS or after.payload is None:
            return _result(
                owner=self._owner,
                status=AdapterStatus.FAIL,
                disposition=(
                    DisposableLeaseBindingDispositionV7.MANUAL_RECONCILIATION
                ),
                detail=f"post-write owner authority could not be proved: {after.detail}",
            )
        if after.payload.raw_content != self._owner.canonical_lease_bytes:
            return _result(
                owner=self._owner,
                status=AdapterStatus.FAIL,
                disposition=(
                    DisposableLeaseBindingDispositionV7.MANUAL_RECONCILIATION
                ),
                detail=(
                    "post-write content differs from the exact canonical lease; "
                    "owner authority must be retained"
                ),
            )
        return _result(
            owner=self._owner,
            status=AdapterStatus.PASS,
            disposition=DisposableLeaseBindingDispositionV7.CANONICAL_BOUND,
            detail="exact canonical lease truncated, written, fsynced and re-verified",
        )
