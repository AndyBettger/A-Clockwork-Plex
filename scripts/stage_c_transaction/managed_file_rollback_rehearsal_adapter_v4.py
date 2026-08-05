#!/usr/bin/python3
from __future__ import annotations

"""Final Stage C18 rollback identity boundary.

Installation acceptance remains strict about type, mode, owner and digest.
Mandatory rollback deliberately requires only the exact device/inode and object
type that the adapter itself recorded at mkdir, temporary creation or atomic
no-overwrite publication time. This lets the adapter remove its own partial
object after a later failure without weakening successful-install proof.
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

    def _remove_exact_file_if_present(
        self,
        record: InstalledObject,
        *,
        action: str,
        allow_absent: bool,
    ) -> bool:
        path = _safe_destination(record.destination)
        try:
            info = path.lstat()
        except FileNotFoundError:
            if allow_absent:
                return False
            raise ManagedFileRollbackFailure(
                f"recorded rollback file is unavailable: {record.destination}"
            )
        if (
            stat.S_ISLNK(info.st_mode)
            or not stat.S_ISREG(info.st_mode)
            or info.st_dev != record.device
            or info.st_ino != record.inode
        ):
            raise ManagedFileRollbackFailure(
                f"refusing rollback after pathname substitution: {record.destination}"
            )
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
            action,
            record.destination,
            "PASS",
            f"removed exact inode={record.inode}",
        )
        return True

    def _restore_managed_files_exact(self) -> None:
        if not self._managed_files_installed:
            raise ManagedFileRollbackFailure(
                "managed-file rollback was not armed"
            )

        pending = self._pending_publication
        if pending is not None:
            removed = self._remove_exact_file_if_present(
                pending,
                action="remove-pending-publication",
                allow_absent=self._publication_failed_cleanly,
            )
            if not removed and not self._publication_failed_cleanly:
                raise ManagedFileRollbackFailure(
                    "managed-file publication outcome is not provably absent"
                )
            self._pending_publication = None
            self._publication_failed_cleanly = False

        for record in reversed(self._installed_files):
            self._remove_exact_file_if_present(
                record,
                action="remove-file",
                allow_absent=False,
            )

        for record in reversed(self._temporary_files):
            self._remove_exact_file_if_present(
                record,
                action="remove-temporary",
                allow_absent=True,
            )
        self._temporary_files.clear()

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
            "pending_publication_count\t0\n"
            "temporary_file_count\t0\n"
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
