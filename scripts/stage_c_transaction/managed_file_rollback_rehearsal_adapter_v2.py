#!/usr/bin/python3
from __future__ import annotations

"""Pre-physical hardening for Stage C18 partial managed-file mutation.

This narrow subclass arms mandatory rollback before the first production
filesystem write and records the installed inode before post-replace validation.
Every partial directory or file install is therefore covered by the same exact
rollback path.
"""

import os
import secrets
import stat
from pathlib import PurePosixPath

from .managed_file_rollback_rehearsal_adapter import (
    InstalledObject,
    ManagedFileRollbackFailure,
    ManagedFileRollbackRehearsalAdapter,
    _real_directory,
    _safe_destination,
    _write_all,
)
from .package_review import EXPECTED_PACKAGE_FILES, ManifestEntry, sha256
from .production_adapter_contract import (
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    TransactionIdentity,
)
from .read_only_host_adapter import _fail


class ManagedFileRollbackRehearsalAdapterV2(
    ManagedFileRollbackRehearsalAdapter
):
    """Stage C18 adapter with complete partial-install rollback coverage."""

    def _arm_managed_rollback(self) -> None:
        self._managed_file_mutation_started = True
        self._managed_files_installed = True

    def _create_directory(self, entry: ManifestEntry) -> InstalledObject:
        destination = _safe_destination(entry.destination)
        parent_fd, _parent = self._open_parent(destination)
        created = False
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
                os.fchmod(child_fd, int(entry.mode, 8))
                os.fchown(child_fd, 0, 0)
                os.fsync(child_fd)
                info = os.fstat(child_fd)
            finally:
                os.close(child_fd)
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
            os.fsync(parent_fd)
            if (
                not stat.S_ISDIR(info.st_mode)
                or stat.S_IMODE(info.st_mode) != int(entry.mode, 8)
                or info.st_uid != 0
                or info.st_gid != 0
            ):
                raise ManagedFileRollbackFailure(
                    f"created directory verification failed: {entry.destination}"
                )
        except BaseException:
            if created and not self._created_directories:
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
            f"inode={info.st_ino} mode={entry.mode} owner=0:0",
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
            os.fsync(parent_fd)
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

    def install_managed_files(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.INSTALL_MANAGED_FILES
        invalid = self._candidate_ready_for_mutation(operation, transaction)
        if invalid is not None:
            return invalid
        if not self._services_stopped or not self._dac_release_verified:
            return _fail(
                operation,
                "managed-file installation requires quiesced services and proved DAC release",
            )
        if self._managed_file_mutation_started or self._managed_files_installed_once:
            return _fail(operation, "managed-file installation already started")
        try:
            rows = self._snapshot_rows()
            self._verify_current_alsa()
            for entry in sorted(
                (item for item in self._entries if item.kind == "directory"),
                key=lambda item: len(PurePosixPath(item.destination).parts),
            ):
                row = rows[entry.destination]
                path = _safe_destination(entry.destination)
                if row.state == "present":
                    self._verify_directory_snapshot(path, row)
                    self._record_managed_action(
                        "preserve-directory",
                        entry.destination,
                        "PASS",
                        f"mode={row.mode} owner={row.owner}",
                    )
                elif row.state == "absent":
                    self._create_directory(entry)
                else:
                    raise ManagedFileRollbackFailure(
                        f"unsupported managed directory state: {entry.destination}={row.state}"
                    )
            for entry in (item for item in self._entries if item.kind == "file"):
                self._atomic_install_file(entry)
            if len(self._installed_files) != EXPECTED_PACKAGE_FILES:
                raise ManagedFileRollbackFailure(
                    "managed install did not produce exactly twelve files"
                )
            for record in self._installed_files:
                self._verify_installed_object(record)
            self._verify_current_alsa()
            assert self.transaction_path is not None
            from .authoritative_snapshot_rehearsal_adapter import _atomic_text
            _atomic_text(
                self.transaction_path / "managed-files-installed.tsv",
                "item\tvalue\n"
                "state\tmanaged-files-installed\n"
                f"file_count\t{len(self._installed_files)}\n"
                f"created_directory_count\t{len(self._created_directories)}\n"
                "systemd_reloaded\tfalse\n"
                "route_selected\tfalse\n"
                "committed\tfalse\n",
            )
            _atomic_text(
                self.transaction_path / "state.tsv",
                "item\tvalue\n"
                "state\tmanaged-files-installed-rehearsal\n"
                "mutation_started\ttrue\n"
                "managed_files_installed\ttrue\n"
                "systemd_reloaded\tfalse\n"
                "route_selected\tfalse\n"
                "committed\tfalse\n",
            )
        except (OSError, ManagedFileRollbackFailure) as exc:
            return _fail(operation, str(exc))
        self._managed_files_installed = True
        self._managed_files_installed_once = True
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="twelve managed files installed atomically with no reload or route change",
            evidence=(
                ("installed_file_count", str(len(self._installed_files))),
                ("created_directory_count", str(len(self._created_directories))),
                ("systemd_reloaded", "false"),
                ("route_selected", "false"),
            ),
        )
