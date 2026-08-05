#!/usr/bin/python3
from __future__ import annotations

"""Final Stage C18 rollback identity boundary.

Installation acceptance remains strict about type, mode, owner and digest.
Mandatory rollback deliberately requires only the exact device/inode and object
type that the adapter itself recorded at mkdir or rename time. This lets the
adapter remove its own partial object even when a later chmod, chown, fsync or
post-install verification failed, without weakening successful-install proof.
"""

import os
import stat
from pathlib import Path

from .managed_file_rollback_rehearsal_adapter import (
    InstalledObject,
    ManagedFileRollbackFailure,
    _safe_destination,
)
from .managed_file_rollback_rehearsal_adapter_v3 import (
    ManagedFileRollbackRehearsalAdapterV3,
)
from .snapshot_core import CURRENT_ALSA_DESTINATION


class ManagedFileRollbackRehearsalAdapterV4(
    ManagedFileRollbackRehearsalAdapterV3
):
    """Stage C18 physical adapter with exact identity-only rollback removal."""

    @staticmethod
    def _verify_rollback_identity(record: InstalledObject) -> Path:
        path = _safe_destination(record.destination)
        try:
            info = path.lstat()
        except OSError as exc:
            raise ManagedFileRollbackFailure(
                f"recorded rollback object is unavailable: {record.destination}: {exc}"
            ) from exc
        expected_type = (
            stat.S_ISREG(info.st_mode)
            if record.kind == "file"
            else stat.S_ISDIR(info.st_mode)
        )
        if (
            stat.S_ISLNK(info.st_mode)
            or not expected_type
            or info.st_dev != record.device
            or info.st_ino != record.inode
        ):
            raise ManagedFileRollbackFailure(
                f"refusing rollback after pathname substitution: {record.destination}"
            )
        return path

    def _restore_managed_files_exact(self) -> None:
        if not self._managed_files_installed:
            raise ManagedFileRollbackFailure(
                "managed-file rollback was not armed"
            )
        for record in reversed(self._installed_files):
            path = self._verify_rollback_identity(record)
            parent_fd, _parent = self._open_parent(path)
            try:
                current = os.stat(
                    path.name,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
                if current.st_dev != record.device or current.st_ino != record.inode:
                    raise ManagedFileRollbackFailure(
                        f"refusing removal after pathname substitution: {record.destination}"
                    )
                os.unlink(path.name, dir_fd=parent_fd)
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
            self._record_managed_action(
                "remove-file",
                record.destination,
                "PASS",
                f"removed exact inode={record.inode}",
            )
        for record in reversed(self._created_directories):
            path = self._verify_rollback_identity(record)
            parent_fd, _parent = self._open_parent(path)
            try:
                current = os.stat(
                    path.name,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
                if current.st_dev != record.device or current.st_ino != record.inode:
                    raise ManagedFileRollbackFailure(
                        f"refusing directory removal after substitution: {record.destination}"
                    )
                os.rmdir(path.name, dir_fd=parent_fd)
                os.fsync(parent_fd)
            except OSError as exc:
                raise ManagedFileRollbackFailure(
                    f"managed directory is not exactly removable: {record.destination}: {exc}"
                ) from exc
            finally:
                os.close(parent_fd)
            self._record_managed_action(
                "remove-directory",
                record.destination,
                "PASS",
                f"removed exact inode={record.inode}",
            )

        rows = self._snapshot_rows()
        for entry in self._entries:
            path = _safe_destination(entry.destination)
            row = rows[entry.destination]
            if entry.kind == "file":
                if path.exists() or path.is_symlink():
                    raise ManagedFileRollbackFailure(
                        f"managed file remains after rollback: {entry.destination}"
                    )
            else:
                self._verify_directory_snapshot(path, row)
        self._verify_current_alsa()

        assert self.transaction_path is not None
        from .authoritative_snapshot_rehearsal_adapter import _atomic_text
        from .managed_file_rollback_rehearsal_adapter import (
            MANAGED_FILE_ROLLBACK_NAME,
        )

        _atomic_text(
            self.transaction_path / MANAGED_FILE_ROLLBACK_NAME,
            "item\tvalue\n"
            "state\tmanaged-files-rolled-back\n"
            f"installed_file_count\t{len(self._installed_files)}\n"
            f"removed_file_count\t{len(self._installed_files)}\n"
            f"removed_directory_count\t{len(self._created_directories)}\n"
            "systemd_reloaded\tfalse\n"
            "route_selected\tfalse\n"
            "committed\tfalse\n",
        )
        _atomic_text(
            self.transaction_path / "state.tsv",
            "item\tvalue\n"
            "state\tmanaged-files-rolled-back\n"
            "mutation_started\ttrue\n"
            "managed_files_installed\ttrue\n"
            "filesystem_restored\ttrue\n"
            "systemd_reloaded\tfalse\n"
            "route_selected\tfalse\n"
            "committed\tfalse\n",
        )
        self._managed_files_installed = False
        self._filesystem_restored = True
