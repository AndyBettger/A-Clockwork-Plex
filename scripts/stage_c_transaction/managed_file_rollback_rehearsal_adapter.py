#!/usr/bin/python3
from __future__ import annotations

"""Stage C18 managed-file installation and exact-filesystem rollback adapter."""

import csv
import grp
import os
import pwd
import secrets
import stat
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Self

from .authoritative_snapshot_rehearsal_adapter import _atomic_text
from .candidate_validation_rehearsal_adapter import CandidateValidationFailure
from .package_review import EXPECTED_PACKAGE_FILES, ManifestEntry, sha256
from .production_adapter_contract import (
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    SnapshotIdentity,
    TransactionIdentity,
)
from .production_adapter_lifecycle_v3 import (
    RestoredRehearsalAdapterResult,
    RestoredRehearsalLifecycleOperation,
)
from .production_adapter_lifecycle_v4 import (
    ExactRollbackRehearsalAdapterResult,
    ExactRollbackRehearsalLifecycleOperation,
    ExactRollbackRehearsalTransactionReceipt,
    ProductionAdapterV4,
)
from .read_only_host_adapter import (
    ObservationFailure,
    _fail,
    _observe_dac_snapshot,
    _observe_host_contract,
    _observe_loopback_snapshot,
    _observe_mixer_snapshot,
    _observe_service_snapshot,
)
from .service_quiescence_rehearsal_adapter import ServiceQuiescenceFailure
from .service_quiescence_rehearsal_adapter_v2 import (
    ServiceQuiescenceRehearsalAdapterV2,
)
from .snapshot_core import CURRENT_ALSA_DESTINATION, write_evidence_manifest


MANAGED_FILE_ACTIONS_NAME = "managed-file-actions.tsv"
MANAGED_FILE_ROLLBACK_NAME = "managed-file-rollback.tsv"
PERMITTED_V1_OPERATIONS = (
    AdapterOperation.INSPECT_HOST_CONTRACT,
    AdapterOperation.INSPECT_PRODUCTION_LOCK,
    AdapterOperation.ACQUIRE_PRODUCTION_LOCK,
    AdapterOperation.RELEASE_PRODUCTION_LOCK,
    AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION,
    AdapterOperation.CAPTURE_FILESYSTEM_STATE,
    AdapterOperation.CAPTURE_SERVICE_STATE,
    AdapterOperation.CAPTURE_MIXER_STATE,
    AdapterOperation.CAPTURE_LOOPBACK_STATE,
    AdapterOperation.CAPTURE_DAC_STATE,
    AdapterOperation.STAGE_CANDIDATE_FILES,
    AdapterOperation.VALIDATE_CANDIDATE_ALSA,
    AdapterOperation.VALIDATE_CANDIDATE_SUDOERS,
    AdapterOperation.VALIDATE_CANDIDATE_UNITS,
    AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP,
    AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES,
    AdapterOperation.VERIFY_DAC_RELEASED,
    AdapterOperation.INSTALL_MANAGED_FILES,
    AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES,
    AdapterOperation.VERIFY_DASHBOARD_HEALTH,
    AdapterOperation.RESTORE_EXACT_SNAPSHOT,
    AdapterOperation.VERIFY_EXACT_ROLLBACK,
)
PERMITTED_V4_COUNT = len(PERMITTED_V1_OPERATIONS) + 3
BLOCKED_V4_COUNT = 36 - PERMITTED_V4_COUNT

if PERMITTED_V4_COUNT != 25 or BLOCKED_V4_COUNT != 11:
    raise RuntimeError("Stage C18 operation partition changed unexpectedly")


class ManagedFileRollbackFailure(RuntimeError):
    """The production managed-file install or exact rollback could not be proved."""


@dataclass(frozen=True)
class SnapshotRow:
    kind: str
    destination: str
    state: str
    mode: str
    owner: str
    digest: str
    snapshot: str


@dataclass(frozen=True)
class InstalledObject:
    destination: str
    kind: str
    device: int
    inode: int
    mode: int
    uid: int
    gid: int
    digest: str | None


def _safe_destination(raw: str) -> Path:
    pure = PurePosixPath(raw)
    if not pure.is_absolute() or raw == "/" or ".." in pure.parts:
        raise ManagedFileRollbackFailure(f"unsafe production destination: {raw}")
    return Path(str(pure))


def _owner_ids(raw: str) -> tuple[int, int]:
    try:
        user, group = raw.split(":", 1)
    except ValueError as exc:
        raise ManagedFileRollbackFailure(f"invalid captured owner: {raw}") from exc
    try:
        uid = int(user) if user.isdigit() else pwd.getpwnam(user).pw_uid
        gid = int(group) if group.isdigit() else grp.getgrnam(group).gr_gid
    except (KeyError, ValueError) as exc:
        raise ManagedFileRollbackFailure(f"unresolvable captured owner: {raw}") from exc
    return uid, gid


def _real_directory(path: Path) -> os.stat_result:
    try:
        info = path.lstat()
    except OSError as exc:
        raise ManagedFileRollbackFailure(f"required directory is unavailable: {path}: {exc}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise ManagedFileRollbackFailure(f"path is not a real directory: {path}")
    return info


def _verify_ancestors(path: Path) -> None:
    cursor = Path("/")
    for component in path.parts[1:]:
        cursor = cursor / component
        if not cursor.exists() and not cursor.is_symlink():
            break
        _real_directory(cursor)


def _write_all(fd: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        written = os.write(fd, data[offset:])
        if written <= 0:
            raise ManagedFileRollbackFailure("short write during atomic install")
        offset += written


class ManagedFileRollbackRehearsalAdapter(
    ServiceQuiescenceRehearsalAdapterV2,
    ProductionAdapterV4,
):
    """C17 plus one production file mutation and exact rollback."""

    def __init__(
        self,
        package_root: Path,
        invoking_user: str,
        evidence_root: Path,
    ) -> None:
        super().__init__(package_root, invoking_user, evidence_root)
        self._managed_file_actions = (
            self._evidence_root / MANAGED_FILE_ACTIONS_NAME
        )
        self._managed_file_actions.write_text(
            "order\tmonotonic_ns\taction\tdestination\tresult\tdetail\n",
            encoding="utf-8",
        )
        os.chown(self._managed_file_actions, 0, 0)
        self._managed_file_actions.chmod(0o600)
        self._managed_action_order = 0
        self._managed_file_mutation_started = False
        self._managed_files_installed = False
        self._managed_files_installed_once = False
        self._filesystem_restored = False
        self._exact_rollback_verified = False
        self._installed_files: list[InstalledObject] = []
        self._created_directories: list[InstalledObject] = []
        self._snapshot_rows_cache: dict[str, SnapshotRow] | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._managed_files_installed and not self._filesystem_restored:
            try:
                self._restore_managed_files_exact()
            except ManagedFileRollbackFailure as rollback_exc:
                raise ManagedFileRollbackFailure(
                    "mandatory Stage C18 filesystem rollback failed; the "
                    "production lock and transaction are intentionally retained: "
                    f"{rollback_exc}"
                ) from exc
        super().__exit__(exc_type, exc, traceback)

    @property
    def managed_files_installed_once(self) -> bool:
        return self._managed_files_installed_once

    @property
    def filesystem_restored(self) -> bool:
        return self._filesystem_restored

    @property
    def exact_rollback_verified(self) -> bool:
        return self._exact_rollback_verified

    def _record_managed_action(
        self,
        action: str,
        destination: str,
        result: str,
        detail: str,
    ) -> None:
        self._managed_action_order += 1
        clean = detail.replace("\t", " ").replace("\n", " ").strip()
        with self._managed_file_actions.open("a", encoding="utf-8") as output:
            output.write(
                f"{self._managed_action_order}\t{time.monotonic_ns()}\t"
                f"{action}\t{destination}\t{result}\t{clean}\n"
            )

    def _snapshot_rows(self) -> dict[str, SnapshotRow]:
        if self._snapshot_rows_cache is not None:
            return self._snapshot_rows_cache
        path = self.transaction_path
        if path is None:
            raise ManagedFileRollbackFailure("authoritative transaction is unavailable")
        source = path / "snapshot/filesystem-state.tsv"
        if source.is_symlink() or not source.is_file():
            raise ManagedFileRollbackFailure("authoritative filesystem state is unavailable")
        with source.open("r", encoding="utf-8", newline="") as handle:
            raw_rows = list(csv.DictReader(handle, delimiter="\t"))
        rows: dict[str, SnapshotRow] = {}
        for raw in raw_rows:
            row = SnapshotRow(
                kind=raw.get("kind", ""),
                destination=raw.get("destination", ""),
                state=raw.get("preinstall_state", ""),
                mode=raw.get("mode", ""),
                owner=raw.get("owner", ""),
                digest=raw.get("sha256", ""),
                snapshot=raw.get("snapshot", ""),
            )
            if not row.destination or row.destination in rows:
                raise ManagedFileRollbackFailure(
                    "authoritative filesystem state contains invalid destinations"
                )
            rows[row.destination] = row
        expected = {entry.destination for entry in self._entries}
        expected.add(CURRENT_ALSA_DESTINATION)
        if set(rows) != expected:
            raise ManagedFileRollbackFailure(
                "authoritative filesystem state does not cover the exact managed set"
            )
        for entry in (item for item in self._entries if item.kind == "file"):
            row = rows[entry.destination]
            if row.kind != "file" or row.state != "absent":
                raise ManagedFileRollbackFailure(
                    f"managed file no longer has an authoritative absence marker: {entry.destination}"
                )
        self._snapshot_rows_cache = rows
        return rows

    @staticmethod
    def _verify_directory_snapshot(path: Path, row: SnapshotRow) -> None:
        if row.state == "absent":
            if path.exists() or path.is_symlink():
                raise ManagedFileRollbackFailure(
                    f"captured-absent directory unexpectedly exists: {path}"
                )
            return
        if row.state != "present":
            raise ManagedFileRollbackFailure(
                f"unsupported directory snapshot state: {row.destination}={row.state}"
            )
        info = _real_directory(path)
        uid, gid = _owner_ids(row.owner)
        if (
            stat.S_IMODE(info.st_mode) != int(row.mode, 8)
            or info.st_uid != uid
            or info.st_gid != gid
        ):
            raise ManagedFileRollbackFailure(
                f"captured directory metadata changed: {row.destination}"
            )

    @staticmethod
    def _open_parent(path: Path) -> tuple[int, os.stat_result]:
        _verify_ancestors(path.parent)
        before = _real_directory(path.parent)
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(path.parent, flags)
        opened = os.fstat(fd)
        if opened.st_dev != before.st_dev or opened.st_ino != before.st_ino:
            os.close(fd)
            raise ManagedFileRollbackFailure(
                f"destination parent changed while opening: {path.parent}"
            )
        return fd, before

    def _create_directory(self, entry: ManifestEntry) -> InstalledObject:
        destination = _safe_destination(entry.destination)
        parent_fd, _parent = self._open_parent(destination)
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
            os.mkdir(destination.name, mode=0o700, dir_fd=parent_fd)
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
            os.fsync(parent_fd)
        except BaseException:
            try:
                os.rmdir(destination.name, dir_fd=parent_fd)
            except OSError:
                pass
            raise
        finally:
            os.close(parent_fd)
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
            info = destination.lstat()
            if (
                stat.S_ISLNK(info.st_mode)
                or not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
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
        installed = InstalledObject(
            destination=entry.destination,
            kind="file",
            device=info.st_dev,
            inode=info.st_ino,
            mode=int(entry.mode, 8),
            uid=0,
            gid=0,
            digest=entry.digest,
        )
        self._record_managed_action(
            "install-file",
            entry.destination,
            "PASS",
            f"inode={info.st_ino} sha256={entry.digest}",
        )
        return installed

    @staticmethod
    def _verify_installed_object(record: InstalledObject) -> Path:
        path = _safe_destination(record.destination)
        try:
            info = path.lstat()
        except OSError as exc:
            raise ManagedFileRollbackFailure(
                f"installed object disappeared: {record.destination}: {exc}"
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
            or stat.S_IMODE(info.st_mode) != record.mode
            or info.st_uid != record.uid
            or info.st_gid != record.gid
        ):
            raise ManagedFileRollbackFailure(
                f"installed object identity changed: {record.destination}"
            )
        if record.digest is not None and sha256(path) != record.digest:
            raise ManagedFileRollbackFailure(
                f"installed file digest changed: {record.destination}"
            )
        return path

    def _verify_current_alsa(self) -> None:
        row = self._snapshot_rows()[CURRENT_ALSA_DESTINATION]
        path = _safe_destination(CURRENT_ALSA_DESTINATION)
        info = path.lstat()
        uid, gid = _owner_ids(row.owner)
        if (
            row.state != "present"
            or stat.S_ISLNK(info.st_mode)
            or not stat.S_ISREG(info.st_mode)
            or stat.S_IMODE(info.st_mode) != int(row.mode, 8)
            or info.st_uid != uid
            or info.st_gid != gid
            or sha256(path) != row.digest
        ):
            raise ManagedFileRollbackFailure(
                "active ALSA route differs from the authoritative snapshot"
            )

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
                    self._created_directories.append(
                        self._create_directory(entry)
                    )
                else:
                    raise ManagedFileRollbackFailure(
                        f"unsupported managed directory state: {entry.destination}={row.state}"
                    )
            self._managed_file_mutation_started = True
            for entry in (item for item in self._entries if item.kind == "file"):
                self._installed_files.append(self._atomic_install_file(entry))
            if len(self._installed_files) != EXPECTED_PACKAGE_FILES:
                raise ManagedFileRollbackFailure(
                    "managed install did not produce exactly twelve files"
                )
            for record in self._installed_files:
                self._verify_installed_object(record)
            self._verify_current_alsa()
            assert self.transaction_path is not None
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
        except (
            OSError,
            CandidateValidationFailure,
            ManagedFileRollbackFailure,
        ) as exc:
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

    def _restore_managed_files_exact(self) -> None:
        if not self._managed_files_installed:
            raise ManagedFileRollbackFailure("managed files are not installed")
        for record in reversed(self._installed_files):
            path = self._verify_installed_object(record)
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
            path = self._verify_installed_object(record)
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

    def restore_exact_snapshot(
        self,
        transaction: TransactionIdentity,
        snapshot: SnapshotIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.RESTORE_EXACT_SNAPSHOT
        invalid = self._require_candidate(operation, transaction)
        if invalid is not None:
            return invalid
        current = self.authoritative_transaction
        if current is None or snapshot != current.snapshot:
            return _fail(operation, "snapshot identity is not adapter-authoritative")
        if not self._managed_files_installed or not self._managed_files_installed_once:
            return _fail(operation, "managed-file mutation has not completed")
        if self._filesystem_restored:
            return _fail(operation, "authoritative filesystem was already restored")
        if not self._services_stopped or not self._dac_release_verified:
            return _fail(operation, "filesystem rollback requires continued service quiescence")
        try:
            self._restore_managed_files_exact()
        except (OSError, ManagedFileRollbackFailure) as exc:
            return _fail(operation, str(exc))
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="managed files and created directories restored to the exact snapshot",
            evidence=(
                ("removed_file_count", str(len(self._installed_files))),
                ("removed_directory_count", str(len(self._created_directories))),
                ("active_route_restored", "unchanged"),
            ),
        )

    def verify_exact_rollback(
        self,
        transaction: TransactionIdentity,
        snapshot: SnapshotIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.VERIFY_EXACT_ROLLBACK
        invalid = self._require_candidate(operation, transaction)
        if invalid is not None:
            return invalid
        current = self.authoritative_transaction
        if current is None or snapshot != current.snapshot:
            return _fail(operation, "snapshot identity is not adapter-authoritative")
        if not all(
            (
                self._managed_files_installed_once,
                self._filesystem_restored,
                self._services_restored,
                self._dashboard_verified,
            )
        ):
            return _fail(
                operation,
                "filesystem, service and dashboard restoration must complete before verification",
            )
        if self._exact_rollback_verified:
            return _fail(operation, "exact rollback was already verified")
        try:
            rows = self._snapshot_rows()
            for entry in self._entries:
                path = _safe_destination(entry.destination)
                row = rows[entry.destination]
                if entry.kind == "file":
                    if path.exists() or path.is_symlink():
                        raise ManagedFileRollbackFailure(
                            f"managed file exists after exact rollback: {entry.destination}"
                        )
                else:
                    self._verify_directory_snapshot(path, row)
            self._verify_current_alsa()
            if _observe_service_snapshot() != self._captured_services_exact:
                raise ManagedFileRollbackFailure(
                    "service state differs from the authoritative snapshot"
                )
            _observe_host_contract()
            if _observe_mixer_snapshot() != self._captured_mixer_exact:
                raise ManagedFileRollbackFailure(
                    "mixer state differs from the authoritative snapshot"
                )
            if _observe_loopback_snapshot() != self._captured_loopback_exact:
                raise ManagedFileRollbackFailure(
                    "loopback state differs from the authoritative snapshot"
                )
            dac = _observe_dac_snapshot()
            if dac.released or not dac.owners:
                raise ManagedFileRollbackFailure(
                    "DAC ownership did not return after exact rollback"
                )
        except (
            OSError,
            ObservationFailure,
            ManagedFileRollbackFailure,
        ) as exc:
            return _fail(operation, str(exc))
        self._exact_rollback_verified = True
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="filesystem, services, route, mixer, loopback and DAC match the snapshot",
            evidence=(
                ("filesystem_mismatches", "0"),
                ("service_mismatches", "0"),
                ("mixer_mismatches", "0"),
                ("loopback_mismatches", "0"),
                ("dac_owner_count", str(len(dac.owners))),
            ),
        )

    def close_restored_rehearsal_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> RestoredRehearsalAdapterResult:
        if self._managed_file_mutation_started:
            return RestoredRehearsalAdapterResult(
                operation=(
                    RestoredRehearsalLifecycleOperation.
                    CLOSE_RESTORED_REHEARSAL_TRANSACTION
                ),
                status=AdapterStatus.FAIL,
                detail=(
                    "v3 service-only closure is unavailable after managed-file "
                    "mutation; use v4 exact-rollback rehearsal closure"
                ),
            )
        return super().close_restored_rehearsal_transaction(transaction)

    def close_exact_rollback_rehearsal_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> ExactRollbackRehearsalAdapterResult:
        operation = (
            ExactRollbackRehearsalLifecycleOperation.
            CLOSE_EXACT_ROLLBACK_REHEARSAL_TRANSACTION
        )
        current = self.authoritative_transaction
        if current is None or transaction != current.transaction:
            return ExactRollbackRehearsalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail="rejected non-authoritative transaction identity",
            )
        if not all(
            (
                self._managed_file_mutation_started,
                self._managed_files_installed_once,
                self._filesystem_restored,
                self._exact_rollback_verified,
                self._services_restored,
                self._dashboard_verified,
            )
        ):
            return ExactRollbackRehearsalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=(
                    "managed install, exact filesystem rollback, service restoration "
                    "and exact verification must complete before v4 closure"
                ),
            )
        assert self.transaction_path is not None
        try:
            _atomic_text(
                self.transaction_path / "lifecycle-v4.tsv",
                "item\tvalue\n"
                "operation\tclose-exact-rollback-rehearsal-transaction\n"
                "managed_files_installed\ttrue\n"
                "filesystem_restored\ttrue\n"
                "services_restored\ttrue\n"
                "committed\tfalse\n",
            )
            base_result = super().close_restored_rehearsal_transaction(
                transaction
            )
            if (
                base_result.status is not AdapterStatus.PASS
                or base_result.payload is None
            ):
                return ExactRollbackRehearsalAdapterResult(
                    operation=operation,
                    status=AdapterStatus.FAIL,
                    detail=f"underlying exact cleanup failed: {base_result.detail}",
                )
            transaction_copy = self._restored_transaction_copy
            if transaction_copy is None or not transaction_copy.is_dir():
                raise ManagedFileRollbackFailure(
                    "v4 transaction audit copy is unavailable"
                )
            _atomic_text(
                transaction_copy / "state.tsv",
                "item\tvalue\n"
                "state\tmanaged-files-rolled-back-and-closed\n"
                "mutation_started\ttrue\n"
                "managed_files_installed\ttrue\n"
                "filesystem_restored\ttrue\n"
                "services_restored\ttrue\n"
                "committed\tfalse\n",
            )
            write_evidence_manifest(transaction_copy)
        except (
            OSError,
            SystemExit,
            ManagedFileRollbackFailure,
            ServiceQuiescenceFailure,
        ) as exc:
            return ExactRollbackRehearsalAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=str(exc),
            )
        receipt = ExactRollbackRehearsalTransactionReceipt(
            transaction=transaction,
            state="managed-files-rolled-back-and-closed",
            mutation_started=True,
            managed_files_installed=True,
            filesystem_restored=True,
            services_restored=True,
            committed=False,
            transaction_path_absent=True,
            parents_restored=base_result.payload.parents_restored,
            installed_file_count=EXPECTED_PACKAGE_FILES,
            audit_evidence=str(self._evidence_root),
        )
        return ExactRollbackRehearsalAdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="managed-file exact-rollback rehearsal closed and removed exactly",
            payload=receipt,
        )
