#!/usr/bin/python3
from __future__ import annotations

"""Stage C14 production-lock-only typed adapter.

The adapter extends the six Stage C13 observations with exact acquisition and
release of the one fixed production route lock. Every transaction or audio
operation remains inherited from BlockedProductionAdapter and is still blocked.
"""

import errno
import fcntl
import os
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from .production_adapter_contract import (
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    PRODUCTION_LOCK_PATH,
    ProductionLockLease,
    ProductionLockObservation,
)
from .read_only_host_adapter import (
    PERMITTED_OPERATIONS as READ_ONLY_OPERATIONS,
    ObservationFailure,
    ReadOnlyHostProductionAdapter,
    _fail,
    _observe_production_lock,
)


LOCK_PATH = Path(PRODUCTION_LOCK_PATH)
LOCK_MODE = 0o600
LEASE_PREFIX = "stage-c14-lock-"
PERMITTED_OPERATIONS = (
    AdapterOperation.INSPECT_HOST_CONTRACT,
    AdapterOperation.INSPECT_PRODUCTION_LOCK,
    AdapterOperation.ACQUIRE_PRODUCTION_LOCK,
    AdapterOperation.RELEASE_PRODUCTION_LOCK,
    AdapterOperation.CAPTURE_SERVICE_STATE,
    AdapterOperation.CAPTURE_MIXER_STATE,
    AdapterOperation.CAPTURE_LOOPBACK_STATE,
    AdapterOperation.CAPTURE_DAC_STATE,
)

if set(PERMITTED_OPERATIONS) != set(READ_ONLY_OPERATIONS).union(
    {
        AdapterOperation.ACQUIRE_PRODUCTION_LOCK,
        AdapterOperation.RELEASE_PRODUCTION_LOCK,
    }
):
    raise RuntimeError("Stage C14 permitted-operation boundary is inconsistent")


class ProductionLockFailure(RuntimeError):
    """The exact production-lock contract could not be established."""


@dataclass(frozen=True)
class HeldLockEvidence:
    inode: int
    mode: int
    owner_uid: int
    owner_gid: int
    contention_proved: bool

    def __post_init__(self) -> None:
        if self.inode <= 0:
            raise ValueError("held lock inode must be positive")
        if self.mode != LOCK_MODE:
            raise ValueError("held lock mode must be 0600")
        if self.owner_uid != 0 or self.owner_gid != 0:
            raise ValueError("held lock must be root:root")
        if not self.contention_proved:
            raise ValueError("held lock must include contention proof")


def _open_flags(*, create: bool) -> int:
    flags = os.O_RDWR
    if create:
        flags |= os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def _validate_parent() -> None:
    try:
        info = LOCK_PATH.parent.lstat()
    except OSError as exc:
        raise ProductionLockFailure(f"cannot inspect production-lock parent: {exc}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise ProductionLockFailure("production-lock parent is not a real directory")
    if info.st_uid != 0 or info.st_gid != 0:
        raise ProductionLockFailure("production-lock parent is not root-owned")


def _descriptor_evidence(fd: int) -> HeldLockEvidence:
    try:
        descriptor = os.fstat(fd)
        path = LOCK_PATH.lstat()
    except OSError as exc:
        raise ProductionLockFailure(f"cannot verify held production lock: {exc}") from exc
    if not stat.S_ISREG(descriptor.st_mode) or not stat.S_ISREG(path.st_mode):
        raise ProductionLockFailure("production lock is not a regular file")
    if descriptor.st_ino != path.st_ino or descriptor.st_dev != path.st_dev:
        raise ProductionLockFailure("production-lock pathname no longer matches held descriptor")
    mode = stat.S_IMODE(descriptor.st_mode)
    if mode != LOCK_MODE or stat.S_IMODE(path.st_mode) != LOCK_MODE:
        raise ProductionLockFailure("production-lock mode differs from 0600")
    if (
        descriptor.st_uid != 0
        or descriptor.st_gid != 0
        or path.st_uid != 0
        or path.st_gid != 0
    ):
        raise ProductionLockFailure("production lock differs from root:root")
    return HeldLockEvidence(
        inode=descriptor.st_ino,
        mode=mode,
        owner_uid=descriptor.st_uid,
        owner_gid=descriptor.st_gid,
        contention_proved=True,
    )


def _prove_contention() -> None:
    try:
        second_fd = os.open(LOCK_PATH, _open_flags(create=False))
    except OSError as exc:
        raise ProductionLockFailure(f"cannot open independent contention descriptor: {exc}") from exc
    try:
        try:
            fcntl.flock(second_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                return
            raise ProductionLockFailure(f"contention proof failed: {exc}") from exc
        else:
            fcntl.flock(second_fd, fcntl.LOCK_UN)
            raise ProductionLockFailure(
                "independent descriptor unexpectedly acquired the production lock"
            )
    finally:
        os.close(second_fd)


def _safe_unlink_exact(fd: int) -> None:
    descriptor = os.fstat(fd)
    try:
        path = LOCK_PATH.lstat()
    except FileNotFoundError:
        return
    if descriptor.st_ino != path.st_ino or descriptor.st_dev != path.st_dev:
        raise ProductionLockFailure(
            "refusing to unlink a production-lock pathname with a substituted inode"
        )
    if not stat.S_ISREG(path.st_mode):
        raise ProductionLockFailure("refusing to unlink a non-regular production lock")
    LOCK_PATH.unlink()


class ProductionLockRehearsalAdapter(ReadOnlyHostProductionAdapter):
    """Eight-operation adapter: six observations plus exact lock acquire/release."""

    def __init__(self) -> None:
        super().__init__()
        self._lock_fd: int | None = None
        self._lease: ProductionLockLease | None = None
        self._evidence: HeldLockEvidence | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        del exc_type, exc, traceback
        self._best_effort_cleanup()

    @property
    def lock_held(self) -> bool:
        return self._lock_fd is not None and self._lease is not None

    @property
    def held_lock_evidence(self) -> HeldLockEvidence | None:
        return self._evidence

    @property
    def lease(self) -> ProductionLockLease | None:
        return self._lease

    def _best_effort_cleanup(self) -> None:
        fd = self._lock_fd
        if fd is None:
            return
        try:
            _safe_unlink_exact(fd)
        except (OSError, ProductionLockFailure):
            pass
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(fd)
        except OSError:
            pass
        self._lock_fd = None
        self._lease = None
        self._evidence = None

    def inspect_production_lock(self) -> AdapterResult[ProductionLockObservation]:
        operation = AdapterOperation.INSPECT_PRODUCTION_LOCK
        if not self.lock_held:
            return super().inspect_production_lock()
        assert self._lock_fd is not None
        try:
            evidence = _descriptor_evidence(self._lock_fd)
        except ProductionLockFailure as exc:
            return _fail(operation, str(exc))
        payload = ProductionLockObservation(
            path=PRODUCTION_LOCK_PATH,
            exists=True,
            held_by_caller=True,
            owner_uid=evidence.owner_uid,
            owner_gid=evidence.owner_gid,
            mode=evidence.mode,
        )
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="exact production lock is held by this adapter",
            payload=payload,
            evidence=(("inode", str(evidence.inode)),),
        )

    def acquire_production_lock(self) -> AdapterResult[ProductionLockLease]:
        operation = AdapterOperation.ACQUIRE_PRODUCTION_LOCK
        if self.lock_held:
            return _fail(operation, "production lock is already held by this adapter")
        if os.geteuid() != 0:
            return _fail(operation, "production-lock rehearsal requires root")

        fd: int | None = None
        try:
            _validate_parent()
            preflight = _observe_production_lock()
            if preflight.exists:
                raise ProductionLockFailure(
                    "production-lock path already exists; refusing replacement"
                )
            fd = os.open(LOCK_PATH, _open_flags(create=True), LOCK_MODE)
            os.fchmod(fd, LOCK_MODE)
            os.fchown(fd, 0, 0)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            preliminary = _descriptor_evidence(fd)
            _prove_contention()
            evidence = HeldLockEvidence(
                inode=preliminary.inode,
                mode=preliminary.mode,
                owner_uid=preliminary.owner_uid,
                owner_gid=preliminary.owner_gid,
                contention_proved=True,
            )
            lease = ProductionLockLease(
                path=PRODUCTION_LOCK_PATH,
                lease_id=f"{LEASE_PREFIX}{secrets.token_hex(12)}",
            )
        except (OSError, ObservationFailure, ProductionLockFailure) as exc:
            if fd is not None:
                try:
                    _safe_unlink_exact(fd)
                except (OSError, ProductionLockFailure):
                    pass
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
                try:
                    os.close(fd)
                except OSError:
                    pass
            return _fail(operation, str(exc))

        self._lock_fd = fd
        self._lease = lease
        self._evidence = evidence
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="exclusive production lock acquired and contention proved",
            payload=lease,
            evidence=(
                ("inode", str(evidence.inode)),
                ("mode", f"{evidence.mode:o}"),
                ("owner", f"{evidence.owner_uid}:{evidence.owner_gid}"),
                ("contention", "proved"),
            ),
        )

    def release_production_lock(self) -> AdapterResult[None]:
        operation = AdapterOperation.RELEASE_PRODUCTION_LOCK
        fd = self._lock_fd
        lease = self._lease
        evidence = self._evidence
        if fd is None or lease is None or evidence is None:
            return _fail(operation, "no adapter-held production lock exists")

        try:
            verified = _descriptor_evidence(fd)
            if verified.inode != evidence.inode:
                raise ProductionLockFailure("held production-lock inode changed")
            _safe_unlink_exact(fd)
            try:
                LOCK_PATH.lstat()
            except FileNotFoundError:
                pass
            else:
                raise ProductionLockFailure(
                    "production-lock pathname still exists after exact unlink"
                )
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        except (OSError, ProductionLockFailure) as exc:
            return _fail(operation, str(exc))

        self._lock_fd = None
        self._lease = None
        self._evidence = None
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="exact production-lock inode unlinked, unlocked and closed",
            evidence=(
                ("lease_id", lease.lease_id),
                ("inode", str(evidence.inode)),
                ("path_absent", "true"),
            ),
        )