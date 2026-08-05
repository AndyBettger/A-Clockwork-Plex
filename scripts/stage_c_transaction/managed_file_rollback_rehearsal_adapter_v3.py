#!/usr/bin/python3
from __future__ import annotations

"""Final pre-physical Stage C18 write-boundary hardening.

The rollback ledger adopts a created directory immediately after mkdir and an
installed file immediately after atomic rename, before any later fsync or
verification can fail.
"""

import os
import secrets
import stat

from .managed_file_rollback_rehearsal_adapter import (
    InstalledObject,
    ManagedFileRollbackFailure,
    _safe_destination,
    _write_all,
)
from .managed_file_rollback_rehearsal_adapter_v2 import (
    ManagedFileRollbackRehearsalAdapterV2,
)
from .package_review import ManifestEntry, sha256


class ManagedFileRollbackRehearsalAdapterV3(
    ManagedFileRollbackRehearsalAdapterV2
):
    """Stage C18 with ledger ownership at the first durable pathname mutation."""

    def _create_directory(self, entry: ManifestEntry) -> InstalledObject:
        destination = _safe_destination(entry.destination)
        parent_fd, _parent = self._open_parent(destination)
        created = False
        recorded = False
        try:
            try:
                os.stat(
                    destination.name,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                pass
            else:
                raise ManagedFileRollbackFailure(
                    f"managed directory unexpectedly exists: {entry.destination}"
                )
            self._arm_managed_rollback()
            os.mkdir(destination.name, mode=0o700, dir_fd=parent_fd)
            created = True
            child_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            if hasattr(os, "O_CLOEXEC"):
                child_flags |= os.O_CLOEXEC
            if hasattr(os, "O_NOFOLLOW"):
                child_flags |= os.O_NOFOLLOW
            child_fd = os.open(destination.name, child_flags, dir_fd=parent_fd)
            try:
                info = os.fstat(child_fd)
                installed = InstalledObject(
                    destination=entry.destination,
                    kind="directory",
                    device=info.st_dev,
                    inode=info.st_ino,
                    mode=int(entry.mode, 8),
                    uid=0,
                    gid=0,
                    digest=None,
                )
                self._created_directories.append(installed)
                recorded = True
                os.fchmod(child_fd, int(entry.mode, 8))
                os.fchown(child_fd, 0, 0)
                os.fsync(child_fd)
                info = os.fstat(child_fd)
            finally:
                os.close(child_fd)
            os.fsync(parent_fd)
            if (
                not stat.S_ISDIR(info.st_mode)
                or info.st_dev != installed.device
                or info.st_ino != installed.inode
                or stat.S_IMODE(info.st_mode) != int(entry.mode, 8)
                or info.st_uid != 0
                or info.st_gid != 0
            ):
                raise ManagedFileRollbackFailure(
                    f"created directory verification failed: {entry.destination}"
                )
        except BaseException:
            if created and not recorded:
                try:
                    os.rmdir(destination.name, dir_fd=parent_fd)
                except OSError:
                    pass
            raise
        finally:
            os.close(parent_fd)
        self._record_managed_action(
            "create-directory",
            entry.destination,
            "PASS",
            f"inode={installed.inode} mode={entry.mode} owner=0:0",
        )
        return installed

    def _atomic_install_file(self, entry: ManifestEntry) -> InstalledObject:
        destination = _safe_destination(entry.destination)
        assert self._candidate_root is not None
        source = self._candidate_root / entry.destination.lstrip("/")
        source_info = source.lstat()
        if (
            stat.S_ISLNK(source_info.st_mode)
            or not stat.S_ISREG(source_info.st_mode)
            or source_info.st_nlink != 1
            or sha256(source) != entry.digest
        ):
            raise ManagedFileRollbackFailure(
                f"transaction candidate changed before install: {entry.destination}"
            )
        parent_fd, _parent = self._open_parent(destination)
        temporary = f".{destination.name}.stage-c18-{secrets.token_hex(8)}.tmp"
        fd: int | None = None
        record: InstalledObject | None = None
        try:
            try:
                os.stat(
                    destination.name,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                pass
            else:
                raise ManagedFileRollbackFailure(
                    f"managed destination is no longer absent: {entry.destination}"
                )
            self._arm_managed_rollback()
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_CLOEXEC"):
                flags |= os.O_CLOEXEC
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(temporary, flags, 0o600, dir_fd=parent_fd)
            with source.open("rb") as reader:
                for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                    _write_all(fd, chunk)
            os.fchmod(fd, int(entry.mode, 8))
            os.fchown(fd, 0, 0)
            os.fsync(fd)
            temporary_info = os.fstat(fd)
            os.close(fd)
            fd = None
            temporary_path = destination.parent / temporary
            if sha256(source) != entry.digest or sha256(temporary_path) != entry.digest:
                raise ManagedFileRollbackFailure(
                    f"atomic install digest verification failed: {entry.destination}"
                )
            os.replace(
                temporary,
                destination.name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
            record = InstalledObject(
                destination=entry.destination,
                kind="file",
                device=temporary_info.st_dev,
                inode=temporary_info.st_ino,
                mode=int(entry.mode, 8),
                uid=0,
                gid=0,
                digest=entry.digest,
            )
            self._installed_files.append(record)
            os.fsync(parent_fd)
            info = destination.lstat()
            if (
                stat.S_ISLNK(info.st_mode)
                or not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_dev != record.device
                or info.st_ino != record.inode
                or stat.S_IMODE(info.st_mode) != int(entry.mode, 8)
                or info.st_uid != 0
                or info.st_gid != 0
                or sha256(destination) != entry.digest
            ):
                raise ManagedFileRollbackFailure(
                    f"installed file verification failed: {entry.destination}"
                )
        finally:
            if fd is not None:
                os.close(fd)
            try:
                os.unlink(temporary, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
            os.close(parent_fd)
        assert record is not None
        self._record_managed_action(
            "install-file",
            entry.destination,
            "PASS",
            f"inode={record.inode} sha256={entry.digest}",
        )
        return record
