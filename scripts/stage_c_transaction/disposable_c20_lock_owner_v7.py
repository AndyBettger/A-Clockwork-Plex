#!/usr/bin/python3
from __future__ import annotations

"""Disposable C20-shaped owner for Stage C21 lock-lease binding proof.

The owner creates and exclusively holds one lock beneath a caller-supplied fresh
0700 laboratory root. It alone owns create, flock, exact unlink, unlock and
close. No production path, approval object, command, service or audio endpoint
is available through this module.
"""

import errno
import fcntl
import os
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from .production_adapter_contract import AdapterStatus


DIRECTORY_MODE = 0o700
LOCK_MODE = 0o600
MAX_LOCK_CONTENT_BYTES = 512
LOCK_RELATIVE = Path("run/lock/a-clockwork-plex-audio-route.lock")
LEASE_PREFIX = "stage-c21-disposable-lease-"


class DisposableC20LockOwnerFailure(RuntimeError):
    """The disposable C20-shaped ownership contract could not be proved."""


@dataclass(frozen=True)
class DisposableC20LockObservationV7:
    lock_path: str
    lease_id: str
    device: int
    inode: int
    mode: int
    owner_uid: int
    owner_gid: int
    contention_proved: bool
    raw_content: bytes

    def __post_init__(self) -> None:
        if not self.lock_path:
            raise ValueError("disposable lock observation requires a path")
        if not self.lease_id:
            raise ValueError("disposable lock observation requires a lease")
        if self.device <= 0 or self.inode <= 0:
            raise ValueError("disposable lock observation requires a positive identity")
        if self.mode != LOCK_MODE:
            raise ValueError("disposable lock observation requires mode 0600")
        if self.owner_uid < 0 or self.owner_gid < 0:
            raise ValueError("disposable lock observation requires an owner")
        if not self.contention_proved:
            raise ValueError("disposable lock observation requires contention proof")
        if len(self.raw_content) > MAX_LOCK_CONTENT_BYTES:
            raise ValueError("disposable lock observation content is too large")


@dataclass(frozen=True)
class DisposableC20LockObservationResultV7:
    status: AdapterStatus
    detail: str
    payload: DisposableC20LockObservationV7 | None = None

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("disposable lock observation detail must not be empty")
        if self.status is AdapterStatus.PASS and self.payload is None:
            raise ValueError("successful disposable lock observation requires proof")
        if self.status is not AdapterStatus.PASS and self.payload is not None:
            raise ValueError("failed disposable lock observation cannot carry proof")


def _fail(detail: str) -> DisposableC20LockObservationResultV7:
    return DisposableC20LockObservationResultV7(
        status=AdapterStatus.FAIL,
        detail=detail,
    )


def _write_all_at(fd: int, payload: bytes, offset: int = 0) -> None:
    view = memoryview(payload)
    position = offset
    while view:
        written = os.pwrite(fd, view, position)
        if written <= 0:
            raise DisposableC20LockOwnerFailure("short disposable owner write")
        position += written
        view = view[written:]


class DisposableC20LockOwnerV7:
    """Sole lifetime owner of one disposable production-shaped lock."""

    def __init__(self, root: Path) -> None:
        self._root = self._validate_fresh_root(root)
        self._expected_uid = os.geteuid()
        self._expected_gid = os.getegid()
        self._lock_path = self._root / LOCK_RELATIVE
        self._lease_id = f"{LEASE_PREFIX}{secrets.token_hex(12)}"
        self._lock_fd: int | None = None
        self._lock_identity: tuple[int, int] | None = None
        self._closed = False

        self._create_private_directory(self._lock_path.parent)
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
        fd = os.open(self._lock_path, flags, LOCK_MODE)
        try:
            os.fchmod(fd, LOCK_MODE)
            os.fchown(fd, self._expected_uid, self._expected_gid)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.fsync(fd)
            descriptor = os.fstat(fd)
            path_info = self._lock_path.lstat()
            if (
                not stat.S_ISREG(descriptor.st_mode)
                or stat.S_ISLNK(path_info.st_mode)
                or not stat.S_ISREG(path_info.st_mode)
                or descriptor.st_dev != path_info.st_dev
                or descriptor.st_ino != path_info.st_ino
            ):
                raise DisposableC20LockOwnerFailure(
                    "disposable lock descriptor identity mismatch"
                )
            self._lock_fd = fd
            self._lock_identity = (descriptor.st_dev, descriptor.st_ino)
            self._prove_contention()
        except BaseException:
            try:
                descriptor = os.fstat(fd)
                path_info = self._lock_path.lstat()
                if (
                    stat.S_ISREG(path_info.st_mode)
                    and descriptor.st_dev == path_info.st_dev
                    and descriptor.st_ino == path_info.st_ino
                ):
                    self._lock_path.unlink()
            except OSError:
                pass
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(fd)
            raise

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        del exc_type, exc, traceback
        if not self._closed:
            self.close_owner()

    @staticmethod
    def _validate_fresh_root(root: Path) -> Path:
        if not isinstance(root, Path) or not root.is_absolute():
            raise DisposableC20LockOwnerFailure(
                "disposable owner root must be an absolute Path"
            )
        try:
            info = root.lstat()
        except FileNotFoundError as exc:
            raise DisposableC20LockOwnerFailure(
                "disposable owner root must already exist"
            ) from exc
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise DisposableC20LockOwnerFailure(
                "disposable owner root must be a real directory"
            )
        if info.st_uid != os.geteuid() or info.st_gid != os.getegid():
            raise DisposableC20LockOwnerFailure(
                "disposable owner root owner mismatch"
            )
        if stat.S_IMODE(info.st_mode) != DIRECTORY_MODE:
            raise DisposableC20LockOwnerFailure(
                "disposable owner root must have mode 0700"
            )
        if any(root.iterdir()):
            raise DisposableC20LockOwnerFailure(
                "disposable owner root must be empty"
            )
        resolved = root.resolve(strict=True)
        if resolved != root:
            raise DisposableC20LockOwnerFailure(
                "disposable owner root must not traverse a symlink"
            )
        return resolved

    def _create_private_directory(self, path: Path) -> None:
        relative = path.relative_to(self._root)
        current = self._root
        for part in relative.parts:
            current = current / part
            try:
                current.mkdir(mode=DIRECTORY_MODE)
            except FileExistsError:
                pass
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise DisposableC20LockOwnerFailure(
                    f"disposable owner ancestor is not a real directory: {current}"
                )
            if info.st_uid != self._expected_uid or info.st_gid != self._expected_gid:
                raise DisposableC20LockOwnerFailure(
                    f"disposable owner ancestor owner mismatch: {current}"
                )
            if stat.S_IMODE(info.st_mode) != DIRECTORY_MODE:
                raise DisposableC20LockOwnerFailure(
                    f"disposable owner ancestor mode mismatch: {current}"
                )

    @property
    def root(self) -> Path:
        return self._root

    @property
    def lock_path(self) -> Path:
        return self._lock_path

    @property
    def lease_id(self) -> str:
        return self._lease_id

    @property
    def canonical_lease_bytes(self) -> bytes:
        return (self._lease_id + "\n").encode("ascii")

    @property
    def lock_held(self) -> bool:
        return (
            not self._closed
            and self._lock_fd is not None
            and self._lock_identity is not None
        )

    @property
    def closed(self) -> bool:
        return self._closed

    def _require_open(self) -> tuple[int, tuple[int, int]]:
        if not self.lock_held:
            raise DisposableC20LockOwnerFailure(
                "disposable C20-shaped owner no longer holds its lock"
            )
        assert self._lock_fd is not None
        assert self._lock_identity is not None
        return self._lock_fd, self._lock_identity

    def _prove_contention(self) -> None:
        self._require_open()
        second = os.open(
            self._lock_path,
            os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        try:
            try:
                fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN):
                    raise DisposableC20LockOwnerFailure(
                        f"disposable lock contention proof failed: {exc}"
                    ) from exc
            else:
                fcntl.flock(second, fcntl.LOCK_UN)
                raise DisposableC20LockOwnerFailure(
                    "independent descriptor acquired the disposable lock"
                )
        finally:
            os.close(second)

    def observe(self) -> DisposableC20LockObservationResultV7:
        try:
            fd, identity = self._require_open()
            descriptor = os.fstat(fd)
            path_info = self._lock_path.lstat()
            if (
                not stat.S_ISREG(descriptor.st_mode)
                or stat.S_ISLNK(path_info.st_mode)
                or not stat.S_ISREG(path_info.st_mode)
                or (descriptor.st_dev, descriptor.st_ino) != identity
                or (path_info.st_dev, path_info.st_ino) != identity
            ):
                raise DisposableC20LockOwnerFailure(
                    "disposable lock pathname or descriptor was substituted"
                )
            if (
                descriptor.st_uid != self._expected_uid
                or descriptor.st_gid != self._expected_gid
                or path_info.st_uid != self._expected_uid
                or path_info.st_gid != self._expected_gid
            ):
                raise DisposableC20LockOwnerFailure(
                    "disposable lock owner changed"
                )
            if (
                stat.S_IMODE(descriptor.st_mode) != LOCK_MODE
                or stat.S_IMODE(path_info.st_mode) != LOCK_MODE
            ):
                raise DisposableC20LockOwnerFailure(
                    "disposable lock mode changed"
                )
            if descriptor.st_size < 0 or descriptor.st_size > MAX_LOCK_CONTENT_BYTES:
                raise DisposableC20LockOwnerFailure(
                    "disposable lock content is too large"
                )
            self._prove_contention()
            raw = os.pread(fd, MAX_LOCK_CONTENT_BYTES + 1, 0)
            if len(raw) != descriptor.st_size:
                raise DisposableC20LockOwnerFailure(
                    "disposable lock content changed during observation"
                )
        except (OSError, DisposableC20LockOwnerFailure) as exc:
            return _fail(str(exc))

        return DisposableC20LockObservationResultV7(
            status=AdapterStatus.PASS,
            detail="exact disposable C20-shaped lock ownership re-verified",
            payload=DisposableC20LockObservationV7(
                lock_path=str(self._lock_path),
                lease_id=self._lease_id,
                device=descriptor.st_dev,
                inode=descriptor.st_ino,
                mode=stat.S_IMODE(descriptor.st_mode),
                owner_uid=descriptor.st_uid,
                owner_gid=descriptor.st_gid,
                contention_proved=True,
                raw_content=raw,
            ),
        )

    def _borrow_descriptor_for_lease_binder(self) -> int:
        fd, _identity = self._require_open()
        return fd

    def close_owner(self) -> None:
        fd, identity = self._require_open()
        observed = self.observe()
        if observed.status is not AdapterStatus.PASS or observed.payload is None:
            raise DisposableC20LockOwnerFailure(
                f"refusing disposable owner close: {observed.detail}"
            )
        if (observed.payload.device, observed.payload.inode) != identity:
            raise DisposableC20LockOwnerFailure(
                "refusing disposable owner close after identity change"
            )
        self._lock_path.unlink()
        try:
            self._lock_path.lstat()
        except FileNotFoundError:
            pass
        else:
            raise DisposableC20LockOwnerFailure(
                "disposable lock pathname remains after exact unlink"
            )
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
        self._lock_fd = None
        self._lock_identity = None
        self._closed = True
