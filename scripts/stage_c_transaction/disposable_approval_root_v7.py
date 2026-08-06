#!/usr/bin/python3
from __future__ import annotations

"""Disposable no-follow approval-root authority for Stage C21 proofs.

The authority creates and retains one production-shaped approval directory
beneath the already-accepted disposable C20 laboratory root. It owns only its
directory descriptors. It cannot acquire, release or mutate the owner-held lock
and it exposes no production path, command, service or audio boundary.
"""

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from .disposable_c20_lock_owner_v7 import DisposableC20LockOwnerV7
from .production_adapter_contract import AdapterStatus


DIRECTORY_MODE = 0o700
APPROVAL_MODE = 0o600
MAX_APPROVAL_BYTES = 64 * 1024
APPROVAL_DIRECTORY_PARTS = ("var", "lib", "a-clockwork-plex", "split-bus")
APPROVAL_NAME = "activation-approved"


class DisposableApprovalRootFailure(RuntimeError):
    """The disposable approval-root contract could not be proved."""


@dataclass(frozen=True)
class DisposableApprovalFileObservationV7:
    present: bool
    raw_content: bytes | None = None
    device: int | None = None
    inode: int | None = None
    mode: int | None = None
    owner_uid: int | None = None
    owner_gid: int | None = None

    def __post_init__(self) -> None:
        identity = (
            self.device,
            self.inode,
            self.mode,
            self.owner_uid,
            self.owner_gid,
        )
        if self.present:
            if self.raw_content is None or any(value is None for value in identity):
                raise ValueError("present approval observation requires exact metadata")
            assert self.device is not None and self.inode is not None
            assert self.mode is not None
            if self.device <= 0 or self.inode <= 0:
                raise ValueError("present approval observation requires positive identity")
            if self.mode != APPROVAL_MODE:
                raise ValueError("present approval observation requires mode 0600")
            if len(self.raw_content) > MAX_APPROVAL_BYTES:
                raise ValueError("approval observation exceeds the bounded size")
        elif self.raw_content is not None or any(value is not None for value in identity):
            raise ValueError("absent approval observation cannot carry file metadata")


@dataclass(frozen=True)
class DisposableApprovalObservationResultV7:
    status: AdapterStatus
    detail: str
    payload: DisposableApprovalFileObservationV7 | None = None

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("disposable approval observation detail must not be empty")
        if self.status is AdapterStatus.PASS and self.payload is None:
            raise ValueError("successful approval observation requires a payload")
        if self.status is not AdapterStatus.PASS and self.payload is not None:
            raise ValueError("failed approval observation cannot carry a payload")


def _fail(detail: str) -> DisposableApprovalObservationResultV7:
    return DisposableApprovalObservationResultV7(
        status=AdapterStatus.FAIL,
        detail=detail,
    )


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


class DisposableApprovalRootV7:
    """Owner of one disposable approval-root directory descriptor."""

    def __init__(self, owner: DisposableC20LockOwnerV7) -> None:
        if not isinstance(owner, DisposableC20LockOwnerV7):
            raise TypeError("disposable approval root requires its C20-shaped owner")
        if not owner.lock_held:
            raise DisposableApprovalRootFailure(
                "disposable approval root requires a live owner-held lock"
            )
        self._owner = owner
        self._expected_uid = os.geteuid()
        self._expected_gid = os.getegid()
        self._path = owner.root.joinpath(*APPROVAL_DIRECTORY_PARTS)
        self._dir_fd: int | None = None
        self._identity: tuple[int, int] | None = None
        self._closed = False
        self._open_directory_chain()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        del exc_type, exc, traceback
        if not self._closed:
            self.close()

    @property
    def owner(self) -> DisposableC20LockOwnerV7:
        return self._owner

    @property
    def path(self) -> Path:
        return self._path

    @property
    def approval_path(self) -> Path:
        return self._path / APPROVAL_NAME

    @property
    def closed(self) -> bool:
        return self._closed

    def _validate_directory(
        self,
        fd: int,
        *,
        parent_fd: int | None,
        name: str | None,
    ) -> tuple[int, int]:
        descriptor = os.fstat(fd)
        if not stat.S_ISDIR(descriptor.st_mode):
            raise DisposableApprovalRootFailure(
                "disposable approval ancestor descriptor is not a directory"
            )
        if (
            descriptor.st_uid != self._expected_uid
            or descriptor.st_gid != self._expected_gid
            or stat.S_IMODE(descriptor.st_mode) != DIRECTORY_MODE
        ):
            raise DisposableApprovalRootFailure(
                "disposable approval ancestor owner or mode mismatch"
            )
        if parent_fd is not None and name is not None:
            path_info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if (
                not stat.S_ISDIR(path_info.st_mode)
                or stat.S_ISLNK(path_info.st_mode)
                or path_info.st_dev != descriptor.st_dev
                or path_info.st_ino != descriptor.st_ino
                or path_info.st_uid != self._expected_uid
                or path_info.st_gid != self._expected_gid
                or stat.S_IMODE(path_info.st_mode) != DIRECTORY_MODE
            ):
                raise DisposableApprovalRootFailure(
                    "disposable approval ancestor pathname identity mismatch"
                )
        return descriptor.st_dev, descriptor.st_ino

    def _open_directory_chain(self) -> None:
        current_fd = os.open(self._owner.root, _directory_flags())
        try:
            self._validate_directory(current_fd, parent_fd=None, name=None)
            for part in APPROVAL_DIRECTORY_PARTS:
                try:
                    os.mkdir(part, DIRECTORY_MODE, dir_fd=current_fd)
                except FileExistsError:
                    pass
                next_fd = os.open(part, _directory_flags(), dir_fd=current_fd)
                try:
                    identity = self._validate_directory(
                        next_fd,
                        parent_fd=current_fd,
                        name=part,
                    )
                except BaseException:
                    os.close(next_fd)
                    raise
                os.close(current_fd)
                current_fd = next_fd
            self._dir_fd = current_fd
            self._identity = identity
        except BaseException:
            os.close(current_fd)
            raise

    def _require_open(self) -> tuple[int, tuple[int, int]]:
        if self._closed or self._dir_fd is None or self._identity is None:
            raise DisposableApprovalRootFailure(
                "disposable approval-root authority is closed"
            )
        return self._dir_fd, self._identity

    def verify_root(self) -> None:
        fd, identity = self._require_open()
        descriptor = os.fstat(fd)
        path_info = self._path.lstat()
        if (
            not stat.S_ISDIR(descriptor.st_mode)
            or stat.S_ISLNK(path_info.st_mode)
            or not stat.S_ISDIR(path_info.st_mode)
            or (descriptor.st_dev, descriptor.st_ino) != identity
            or (path_info.st_dev, path_info.st_ino) != identity
            or descriptor.st_uid != self._expected_uid
            or descriptor.st_gid != self._expected_gid
            or path_info.st_uid != self._expected_uid
            or path_info.st_gid != self._expected_gid
            or stat.S_IMODE(descriptor.st_mode) != DIRECTORY_MODE
            or stat.S_IMODE(path_info.st_mode) != DIRECTORY_MODE
        ):
            raise DisposableApprovalRootFailure(
                "disposable approval root was substituted or changed"
            )

    def observe_public(self) -> DisposableApprovalObservationResultV7:
        file_fd: int | None = None
        try:
            self.verify_root()
            dir_fd, _identity = self._require_open()
            try:
                file_fd = os.open(
                    APPROVAL_NAME,
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=dir_fd,
                )
            except FileNotFoundError:
                return DisposableApprovalObservationResultV7(
                    status=AdapterStatus.PASS,
                    detail="disposable activation approval is absent",
                    payload=DisposableApprovalFileObservationV7(present=False),
                )
            descriptor = os.fstat(file_fd)
            path_info = os.stat(
                APPROVAL_NAME,
                dir_fd=dir_fd,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISREG(descriptor.st_mode)
                or stat.S_ISLNK(path_info.st_mode)
                or not stat.S_ISREG(path_info.st_mode)
                or descriptor.st_dev != path_info.st_dev
                or descriptor.st_ino != path_info.st_ino
            ):
                raise DisposableApprovalRootFailure(
                    "disposable approval name or descriptor identity mismatch"
                )
            if (
                descriptor.st_uid != self._expected_uid
                or descriptor.st_gid != self._expected_gid
                or path_info.st_uid != self._expected_uid
                or path_info.st_gid != self._expected_gid
                or stat.S_IMODE(descriptor.st_mode) != APPROVAL_MODE
                or stat.S_IMODE(path_info.st_mode) != APPROVAL_MODE
            ):
                raise DisposableApprovalRootFailure(
                    "disposable approval owner or mode mismatch"
                )
            if descriptor.st_size < 0 or descriptor.st_size > MAX_APPROVAL_BYTES:
                raise DisposableApprovalRootFailure(
                    "disposable approval exceeds the bounded size"
                )
            raw = os.pread(file_fd, MAX_APPROVAL_BYTES + 1, 0)
            after = os.fstat(file_fd)
            after_path = os.stat(
                APPROVAL_NAME,
                dir_fd=dir_fd,
                follow_symlinks=False,
            )
            if (
                len(raw) != descriptor.st_size
                or (after.st_dev, after.st_ino, after.st_size)
                != (descriptor.st_dev, descriptor.st_ino, descriptor.st_size)
                or (after_path.st_dev, after_path.st_ino)
                != (descriptor.st_dev, descriptor.st_ino)
            ):
                raise DisposableApprovalRootFailure(
                    "disposable approval changed during observation"
                )
        except (OSError, DisposableApprovalRootFailure) as exc:
            return _fail(str(exc))
        finally:
            if file_fd is not None:
                os.close(file_fd)

        return DisposableApprovalObservationResultV7(
            status=AdapterStatus.PASS,
            detail="exact disposable approval raw bytes observed",
            payload=DisposableApprovalFileObservationV7(
                present=True,
                raw_content=raw,
                device=descriptor.st_dev,
                inode=descriptor.st_ino,
                mode=stat.S_IMODE(descriptor.st_mode),
                owner_uid=descriptor.st_uid,
                owner_gid=descriptor.st_gid,
            ),
        )

    def _borrow_directory_descriptor_for_publisher(self) -> int:
        self.verify_root()
        fd, _identity = self._require_open()
        return fd

    def close(self) -> None:
        fd, _identity = self._require_open()
        self.verify_root()
        os.close(fd)
        self._dir_fd = None
        self._identity = None
        self._closed = True
