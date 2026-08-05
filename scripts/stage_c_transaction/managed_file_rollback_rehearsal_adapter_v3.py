#!/usr/bin/python3
from __future__ import annotations

"""Final pre-physical Stage C18 write-boundary hardening.

The rollback ledger adopts a created directory immediately after mkdir. File
publication uses an atomic no-overwrite hard link from a private temporary inode;
the destination inode is pre-bound in the rollback ledger before publication and
adopted immediately after the link succeeds.
"""

import os
import secrets
import stat
from pathlib import Path

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


def _publish_noreplace(parent_fd: int, temporary: str, destination: str) -> None:
    """Atomically publish one inode and refuse an existing destination."""

    os.link(
        temporary,
        destination,
        src_dir_fd=parent_fd,
        dst_dir_fd=parent_fd,
        follow_symlinks=False,
    )


class ManagedFileRollbackRehearsalAdapterV3(
    ManagedFileRollbackRehearsalAdapterV2
):
    """Stage C18 with complete temporary and publication rollback ledgers."""

    def __init__(
        self,
        package_root: Path,
        invoking_user: str,
        evidence_root: Path,
    ) -> None:
        super().__init__(package_root, invoking_user, evidence_root)
        self._temporary_files: list[InstalledObject] = []
        self._pending_publication: InstalledObject | None = None
        self._publication_failed_cleanly = False

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

    def _cleanup_temporary(
        self,
        parent_fd: int,
        temporary: str,
        record: InstalledObject,
    ) -> None:
        try:
            info = os.stat(
                temporary,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            if record in self._temporary_files:
                self._temporary_files.remove(record)
            return
        if (
            stat.S_ISLNK(info.st_mode)
            or not stat.S_ISREG(info.st_mode)
            or info.st_dev != record.device
            or info.st_ino != record.inode
        ):
            raise ManagedFileRollbackFailure(
                f"refusing temporary cleanup after substitution: {record.destination}"
            )
        os.unlink(temporary, dir_fd=parent_fd)
        os.fsync(parent_fd)
        self._temporary_files.remove(record)

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
        temporary_path = destination.parent / temporary
        fd: int | None = None
        temporary_record: InstalledObject | None = None
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
            temporary_info = os.fstat(fd)
            temporary_record = InstalledObject(
                destination=str(temporary_path),
                kind="file",
                device=temporary_info.st_dev,
                inode=temporary_info.st_ino,
                mode=0o600,
                uid=0,
                gid=0,
                digest=None,
            )
            self._temporary_files.append(temporary_record)
            with source.open("rb") as reader:
                for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                    _write_all(fd, chunk)
            os.fchmod(fd, int(entry.mode, 8))
            os.fchown(fd, 0, 0)
            os.fsync(fd)
            temporary_info = os.fstat(fd)
            os.close(fd)
            fd = None
            if sha256(source) != entry.digest or sha256(temporary_path) != entry.digest:
                raise ManagedFileRollbackFailure(
                    f"atomic install digest verification failed: {entry.destination}"
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
            self._pending_publication = record
            self._publication_failed_cleanly = False
            try:
                _publish_noreplace(
                    parent_fd,
                    temporary,
                    destination.name,
                )
            except OSError:
                self._publication_failed_cleanly = True
                raise
            self._installed_files.append(record)
            self._pending_publication = None
            self._publication_failed_cleanly = False
            self._cleanup_temporary(
                parent_fd,
                temporary,
                temporary_record,
            )
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
            if temporary_record is not None and temporary_record in self._temporary_files:
                self._cleanup_temporary(
                    parent_fd,
                    temporary,
                    temporary_record,
                )
            os.close(parent_fd)
        assert record is not None
        self._record_managed_action(
            "install-file",
            entry.destination,
            "PASS",
            f"inode={record.inode} sha256={entry.digest}",
        )
        return record
