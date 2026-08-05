#!/usr/bin/python3
from __future__ import annotations

"""Stage C20 split-bus route selection and exact active-route rollback adapter."""

import ctypes
import os
import secrets
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from .authoritative_snapshot_rehearsal_adapter import _atomic_text
from .managed_file_rollback_rehearsal_adapter import (
    _open_parent,
    _owner_ids,
    _safe_destination,
    _write_all,
)
from .package_review import EXPECTED_PACKAGE_FILES, sha256
from .production_adapter_contract import (
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    ServiceSnapshot,
    SnapshotIdentity,
    TransactionIdentity,
)
from .production_adapter_lifecycle_v5 import (
    SystemdReloadRollbackAdapterResult,
    SystemdReloadRollbackLifecycleOperation,
)
from .production_adapter_lifecycle_v6 import (
    ProductionAdapterV6,
    RouteSelectionRollbackAdapterResult,
    RouteSelectionRollbackLifecycleOperation,
    RouteSelectionRollbackTransactionReceipt,
)
from .read_only_host_adapter import _fail
from .service_quiescence_rehearsal_adapter import (
    ServiceQuiescenceFailure,
    ServiceQuiescenceRehearsalAdapter,
)
from .snapshot_core import CURRENT_ALSA_DESTINATION, write_evidence_manifest
from .systemd_reload_rollback_rehearsal_adapter import (
    PERMITTED_V1_OPERATIONS as C19_PERMITTED_V1_OPERATIONS,
    SystemdReloadRollbackFailure,
    SystemdReloadRollbackRehearsalAdapter,
)


SPLIT_ROUTE_SOURCE = "/etc/a-clockwork-plex/audio-routes/split-bus.conf"
ROUTE_ACTIONS_NAME = "route-selection-actions.tsv"
ROUTE_TRANSACTION_STATE_NAME = "route-selection-rollback.tsv"
RENAME_EXCHANGE = 2

_reload_index = C19_PERMITTED_V1_OPERATIONS.index(AdapterOperation.RELOAD_SYSTEMD)
PERMITTED_V1_OPERATIONS = (
    *C19_PERMITTED_V1_OPERATIONS[: _reload_index + 1],
    AdapterOperation.SELECT_SPLIT_BUS_ROUTE,
    *C19_PERMITTED_V1_OPERATIONS[_reload_index + 1 :],
)
PERMITTED_V6_COUNT = len(PERMITTED_V1_OPERATIONS) + 5
BLOCKED_V6_COUNT = 38 - PERMITTED_V6_COUNT

if PERMITTED_V6_COUNT != 29 or BLOCKED_V6_COUNT != 9:
    raise RuntimeError("Stage C20 operation partition changed unexpectedly")


class RouteSelectionRollbackFailure(RuntimeError):
    """The active ALSA route selection or exact rollback could not be proved."""


@dataclass(frozen=True)
class RouteIdentity:
    device: int
    inode: int
    mode: int
    uid: int
    gid: int
    digest: str


def _rename_exchange(parent_fd: int, left: str, right: str) -> None:
    """Atomically exchange two names in one already-open real directory."""

    libc = ctypes.CDLL(None, use_errno=True)
    function = getattr(libc, "renameat2", None)
    if function is None:
        raise RouteSelectionRollbackFailure(
            "libc does not expose renameat2 for atomic route exchange"
        )
    function.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    function.restype = ctypes.c_int
    result = function(
        parent_fd,
        os.fsencode(left),
        parent_fd,
        os.fsencode(right),
        RENAME_EXCHANGE,
    )
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(
            error,
            os.strerror(error),
            f"{left}<->{right}",
        )


def _identity(path: Path) -> RouteIdentity:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise RouteSelectionRollbackFailure(
            f"route object is not a real regular file: {path}"
        )
    return RouteIdentity(
        device=info.st_dev,
        inode=info.st_ino,
        mode=stat.S_IMODE(info.st_mode),
        uid=info.st_uid,
        gid=info.st_gid,
        digest=sha256(path),
    )


def _require_identity(
    path: Path,
    expected: RouteIdentity,
    label: str,
) -> RouteIdentity:
    try:
        observed = _identity(path)
    except OSError as exc:
        raise RouteSelectionRollbackFailure(
            f"{label} is unavailable: {path}: {exc}"
        ) from exc
    if observed != expected:
        raise RouteSelectionRollbackFailure(
            f"{label} identity changed: {path}: "
            f"expected={expected!r} observed={observed!r}"
        )
    return observed


class RouteSelectionRollbackRehearsalAdapter(
    SystemdReloadRollbackRehearsalAdapter,
    ProductionAdapterV6,
):
    """C19 plus one atomic split-bus route exchange and exact reversal."""

    def __init__(
        self,
        package_root: Path,
        invoking_user: str,
        evidence_root: Path,
    ) -> None:
        super().__init__(package_root, invoking_user, evidence_root)
        self._route_actions = self._evidence_root / ROUTE_ACTIONS_NAME
        self._route_actions.write_text(
            "order\tmonotonic_ns\taction\tactive_path\tresult\tdetail\n",
            encoding="utf-8",
        )
        os.chown(self._route_actions, 0, 0)
        self._route_actions.chmod(0o600)
        self._route_action_order = 0
        self._route_mutation_started = False
        self._route_selected = False
        self._route_selected_once = False
        self._route_restored = False
        self._route_selection_count = 0
        self._route_exchange_completed = False
        self._route_rollback_name: str | None = None
        self._route_original: RouteIdentity | None = None
        self._route_candidate: RouteIdentity | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._route_mutation_started and self._route_rollback_name is not None:
            try:
                self._restore_active_route_exact()
            except (OSError, RouteSelectionRollbackFailure) as rollback_exc:
                raise RouteSelectionRollbackFailure(
                    "mandatory Stage C20 active-route rollback failed; the "
                    "production lock and transaction are intentionally retained: "
                    f"{rollback_exc}"
                ) from exc
        super().__exit__(exc_type, exc, traceback)

    @property
    def route_selected_once(self) -> bool:
        return self._route_selected_once

    @property
    def route_restored(self) -> bool:
        return self._route_restored

    @property
    def route_selection_count(self) -> int:
        return self._route_selection_count

    def _record_route_action(
        self,
        action: str,
        result: str,
        detail: str,
    ) -> None:
        self._route_action_order += 1
        clean = detail.replace("\t", " ").replace("\n", " ").strip()
        with self._route_actions.open("a", encoding="utf-8") as output:
            output.write(
                f"{self._route_action_order}\t{time.monotonic_ns()}\t{action}\t"
                f"{CURRENT_ALSA_DESTINATION}\t{result}\t{clean}\n"
            )

    def _write_route_transaction_state(self, state: str) -> None:
        if self.transaction_path is None:
            raise RouteSelectionRollbackFailure(
                "authoritative transaction is unavailable for route state"
            )
        original = self._route_original
        candidate = self._route_candidate
        _atomic_text(
            self.transaction_path / ROUTE_TRANSACTION_STATE_NAME,
            "item\tvalue\n"
            f"state\t{state}\n"
            f"route_mutation_started\t{str(self._route_mutation_started).lower()}\n"
            f"split_bus_route_selected\t{str(self._route_selected_once).lower()}\n"
            f"active_route_restored\t{str(self._route_restored).lower()}\n"
            f"route_selection_count\t{self._route_selection_count}\n"
            f"original_inode\t{original.inode if original else '-'}\n"
            f"original_sha256\t{original.digest if original else '-'}\n"
            f"candidate_inode\t{candidate.inode if candidate else '-'}\n"
            f"candidate_sha256\t{candidate.digest if candidate else '-'}\n"
            "managed_stage_c_services_started\tfalse\n"
            "audio_probe_opened\tfalse\n"
            "committed\tfalse\n",
        )
        _atomic_text(
            self.transaction_path / "state.tsv",
            "item\tvalue\n"
            f"state\t{state}\n"
            "mutation_started\ttrue\n"
            "managed_files_installed\ttrue\n"
            "systemd_reloaded\ttrue\n"
            f"route_selected\t{str(self._route_selected).lower()}\n"
            f"route_selected_once\t{str(self._route_selected_once).lower()}\n"
            f"route_restored\t{str(self._route_restored).lower()}\n"
            f"filesystem_restored\t{str(self._filesystem_restored).lower()}\n"
            f"systemd_manager_restored\t{str(self._systemd_manager_restored).lower()}\n"
            "managed_stage_c_services_started\tfalse\n"
            "committed\tfalse\n",
        )

    def _original_route_identity(self) -> RouteIdentity:
        row = self._snapshot_rows()[CURRENT_ALSA_DESTINATION]
        if row.kind != "file" or row.state != "present":
            raise RouteSelectionRollbackFailure(
                "authoritative active-route snapshot is not a present file"
            )
        path = _safe_destination(CURRENT_ALSA_DESTINATION)
        uid, gid = _owner_ids(row.owner)
        identity = _identity(path)
        expected = RouteIdentity(
            device=identity.device,
            inode=identity.inode,
            mode=int(row.mode, 8),
            uid=uid,
            gid=gid,
            digest=row.digest,
        )
        if identity != expected:
            raise RouteSelectionRollbackFailure(
                "active ALSA route differs from the authoritative snapshot before selection"
            )
        snapshot = Path(row.snapshot)
        assert self.transaction_path is not None
        snapshot_root = self.transaction_path / "snapshot/rootfs"
        try:
            snapshot.relative_to(snapshot_root)
        except ValueError as exc:
            raise RouteSelectionRollbackFailure(
                "active-route snapshot path escaped the authoritative transaction"
            ) from exc
        snapshot_info = snapshot.lstat()
        if (
            stat.S_ISLNK(snapshot_info.st_mode)
            or not stat.S_ISREG(snapshot_info.st_mode)
            or sha256(snapshot) != row.digest
        ):
            raise RouteSelectionRollbackFailure(
                "authoritative active-route snapshot bytes changed"
            )
        return identity

    def _installed_split_route(self) -> tuple[Path, RouteIdentity]:
        records = [
            record
            for record in self._installed_files
            if record.destination == SPLIT_ROUTE_SOURCE
        ]
        if len(records) != 1:
            raise RouteSelectionRollbackFailure(
                "installed split-bus route is not uniquely transaction-bound"
            )
        source = self._verify_installed_object(records[0])
        identity = _identity(source)
        if records[0].digest is None or identity.digest != records[0].digest:
            raise RouteSelectionRollbackFailure(
                "installed split-bus route digest changed before selection"
            )
        return source, identity

    def _restore_active_route_exact(self) -> None:
        rollback_name = self._route_rollback_name
        original = self._route_original
        candidate = self._route_candidate
        if rollback_name is None or original is None or candidate is None:
            raise RouteSelectionRollbackFailure(
                "active-route rollback ledger is incomplete"
            )
        active = _safe_destination(CURRENT_ALSA_DESTINATION)
        rollback_path = active.parent / rollback_name
        parent_fd, _parent = _open_parent(active)
        try:
            if self._route_exchange_completed:
                _require_identity(active, candidate, "selected active route")
                _require_identity(rollback_path, original, "parked original route")
                _rename_exchange(parent_fd, active.name, rollback_name)
                self._route_exchange_completed = False
                os.fsync(parent_fd)
                _require_identity(active, original, "restored active route")
                _require_identity(rollback_path, candidate, "parked candidate route")
                current = os.stat(
                    rollback_name,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
                if (
                    current.st_dev != candidate.device
                    or current.st_ino != candidate.inode
                ):
                    raise RouteSelectionRollbackFailure(
                        "refusing candidate cleanup after pathname substitution"
                    )
                os.unlink(rollback_name, dir_fd=parent_fd)
                os.fsync(parent_fd)
                self._route_selected = False
                self._route_restored = True
                self._record_route_action(
                    "restore-active-route",
                    "PASS",
                    (
                        f"original_inode={original.inode} "
                        f"original_sha256={original.digest} "
                        f"removed_candidate_inode={candidate.inode}"
                    ),
                )
            else:
                try:
                    _require_identity(
                        rollback_path,
                        candidate,
                        "unexchanged candidate route",
                    )
                except OSError:
                    raise
                _require_identity(active, original, "unchanged active route")
                current = os.stat(
                    rollback_name,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
                if (
                    current.st_dev != candidate.device
                    or current.st_ino != candidate.inode
                ):
                    raise RouteSelectionRollbackFailure(
                        "refusing temporary route cleanup after substitution"
                    )
                os.unlink(rollback_name, dir_fd=parent_fd)
                os.fsync(parent_fd)
                self._record_route_action(
                    "remove-unselected-route-candidate",
                    "PASS",
                    f"removed_candidate_inode={candidate.inode}",
                )
        finally:
            os.close(parent_fd)
        if rollback_path.exists() or rollback_path.is_symlink():
            raise RouteSelectionRollbackFailure(
                "private route rollback pathname remains after cleanup"
            )
        self._route_rollback_name = None
        if self._route_selected_once:
            self._write_route_transaction_state(
                "split-bus-route-restored-files-pending"
            )

    def select_split_bus_route(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.SELECT_SPLIT_BUS_ROUTE
        invalid = self._require_candidate(operation, transaction)
        if invalid is not None:
            return invalid
        if (
            self._systemd_reload_count != 1
            or not self._systemd_candidate_visible
            or self._systemd_manager_restored
        ):
            return _fail(
                operation,
                "split-bus route selection requires the first candidate daemon reload",
            )
        if (
            not self._managed_files_installed
            or self._filesystem_restored
            or not self._services_stopped
            or self._services_restored
            or not self._dac_release_verified
        ):
            return _fail(
                operation,
                "split-bus route selection requires installed files, quiesced services and released audio endpoints",
            )
        if self._route_mutation_started or self._route_selected_once:
            return _fail(operation, "split-bus route selection already started")

        active = _safe_destination(CURRENT_ALSA_DESTINATION)
        parent_fd: int | None = None
        fd: int | None = None
        try:
            source, source_identity = self._installed_split_route()
            original = self._original_route_identity()
            rollback_name = (
                f".{active.name}.stage-c20-{secrets.token_hex(12)}.rollback"
            )
            rollback_path = active.parent / rollback_name
            parent_fd, _parent = _open_parent(active)
            try:
                os.stat(
                    rollback_name,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                pass
            else:
                raise RouteSelectionRollbackFailure(
                    "private route rollback pathname unexpectedly exists"
                )

            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_CLOEXEC"):
                flags |= os.O_CLOEXEC
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            self._route_mutation_started = True
            self._route_rollback_name = rollback_name
            self._route_original = original
            fd = os.open(rollback_name, flags, 0o600, dir_fd=parent_fd)
            created = os.fstat(fd)
            uid, gid = _owner_ids(
                self._snapshot_rows()[CURRENT_ALSA_DESTINATION].owner
            )
            with source.open("rb") as reader:
                for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                    _write_all(fd, chunk)
            os.fchmod(fd, original.mode)
            os.fchown(fd, uid, gid)
            os.fsync(fd)
            candidate_info = os.fstat(fd)
            os.close(fd)
            fd = None
            candidate = RouteIdentity(
                device=candidate_info.st_dev,
                inode=candidate_info.st_ino,
                mode=original.mode,
                uid=uid,
                gid=gid,
                digest=source_identity.digest,
            )
            self._route_candidate = candidate
            _require_identity(
                rollback_path,
                candidate,
                "prepared split-bus route candidate",
            )
            _require_identity(active, original, "pre-exchange active route")
            if sha256(source) != source_identity.digest:
                raise RouteSelectionRollbackFailure(
                    "installed split-bus source changed during route preparation"
                )

            _rename_exchange(parent_fd, active.name, rollback_name)
            self._route_exchange_completed = True
            self._route_selected_once = True
            self._route_selection_count = 1
            os.fsync(parent_fd)
            _require_identity(active, candidate, "selected split-bus active route")
            _require_identity(rollback_path, original, "parked original active route")
            self._route_selected = True
            self._write_route_transaction_state("split-bus-route-selected")
            self._record_route_action(
                "select-split-bus-route",
                "PASS",
                (
                    f"original_inode={original.inode} "
                    f"original_sha256={original.digest} "
                    f"candidate_inode={candidate.inode} "
                    f"candidate_sha256={candidate.digest}"
                ),
            )
        except (
            OSError,
            RouteSelectionRollbackFailure,
            SystemdReloadRollbackFailure,
        ) as exc:
            self._record_route_action(
                "select-split-bus-route",
                "FAIL",
                str(exc),
            )
            return _fail(operation, str(exc))
        finally:
            if fd is not None:
                os.close(fd)
            if parent_fd is not None:
                os.close(parent_fd)

        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail=(
                "reviewed split-bus route selected by atomic inode exchange while services remained quiesced"
            ),
            evidence=(
                ("active_path", CURRENT_ALSA_DESTINATION),
                ("source_path", SPLIT_ROUTE_SOURCE),
                ("original_inode", str(original.inode)),
                ("original_sha256", original.digest),
                ("selected_inode", str(candidate.inode)),
                ("selected_sha256", candidate.digest),
                ("route_selection_count", "1"),
                ("managed_stage_c_services_started", "false"),
                ("audio_probe_opened", "false"),
            ),
        )

    def restore_exact_snapshot(
        self,
        transaction: TransactionIdentity,
        snapshot: SnapshotIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.RESTORE_EXACT_SNAPSHOT
        if (
            not self._route_selected
            or not self._route_selected_once
            or self._route_selection_count != 1
        ):
            return _fail(
                operation,
                "exact rollback requires one proved split-bus route selection",
            )
        try:
            self._restore_active_route_exact()
        except (OSError, RouteSelectionRollbackFailure) as exc:
            return _fail(operation, str(exc))
        result = super().restore_exact_snapshot(transaction, snapshot)
        if result.status is AdapterStatus.PASS:
            try:
                self._write_route_transaction_state(
                    "active-route-and-managed-files-restored-manager-pending"
                )
            except (OSError, RouteSelectionRollbackFailure) as exc:
                return _fail(operation, str(exc))
            return AdapterResult(
                operation=operation,
                status=AdapterStatus.PASS,
                detail=(
                    "original active-route inode and authoritative managed filesystem restored exactly"
                ),
                evidence=(
                    ("active_route_restored", "true"),
                    ("original_inode", str(self._route_original.inode)),
                    ("original_sha256", self._route_original.digest),
                    ("filesystem_restored", "true"),
                ),
            )
        return result

    def restore_captured_application_services(
        self,
        transaction: TransactionIdentity,
        services: ServiceSnapshot,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES
        if self._route_mutation_started and not self._route_restored:
            return _fail(
                operation,
                "application services cannot restart before exact active-route rollback",
            )
        return super().restore_captured_application_services(
            transaction,
            services,
        )

    def verify_exact_rollback(
        self,
        transaction: TransactionIdentity,
        snapshot: SnapshotIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.VERIFY_EXACT_ROLLBACK
        if (
            not self._route_selected_once
            or not self._route_restored
            or self._route_selection_count != 1
        ):
            return _fail(
                operation,
                "exact verification requires one selected and exactly restored route",
            )
        return super().verify_exact_rollback(transaction, snapshot)

    def close_systemd_reload_rollback_rehearsal_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> SystemdReloadRollbackAdapterResult:
        if self._route_mutation_started:
            return SystemdReloadRollbackAdapterResult(
                operation=(
                    SystemdReloadRollbackLifecycleOperation.
                    CLOSE_SYSTEMD_RELOAD_ROLLBACK_REHEARSAL_TRANSACTION
                ),
                status=AdapterStatus.FAIL,
                detail=(
                    "v5 systemd-only closure is unavailable after active-route mutation; use v6 route-selection rollback closure"
                ),
            )
        return super().close_systemd_reload_rollback_rehearsal_transaction(
            transaction
        )

    def close_route_selection_rollback_rehearsal_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> RouteSelectionRollbackAdapterResult:
        operation = (
            RouteSelectionRollbackLifecycleOperation.
            CLOSE_ROUTE_SELECTION_ROLLBACK_REHEARSAL_TRANSACTION
        )
        current = self.authoritative_transaction
        if current is None or transaction != current.transaction:
            return RouteSelectionRollbackAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail="rejected non-authoritative transaction identity",
            )
        if not all(
            (
                self._route_mutation_started,
                self._route_selected_once,
                self._route_restored,
                self._systemd_candidate_visible,
                self._systemd_manager_restored,
                self._managed_files_installed_once,
                self._filesystem_restored,
                self._exact_rollback_verified,
                self._services_restored,
                self._dashboard_verified,
            )
        ) or self._route_selection_count != 1 or self._systemd_reload_count != 2:
            return RouteSelectionRollbackAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=(
                    "route selection, exact active-route/filesystem/manager rollback, service restoration and exact verification must complete before v6 closure"
                ),
            )
        assert self.transaction_path is not None
        try:
            _atomic_text(
                self.transaction_path / "lifecycle-v6.tsv",
                "item\tvalue\n"
                "operation\tclose-route-selection-rollback-rehearsal-transaction\n"
                "managed_files_installed\ttrue\n"
                "systemd_reloaded\ttrue\n"
                "split_bus_route_selected\ttrue\n"
                "active_route_restored\ttrue\n"
                "filesystem_restored\ttrue\n"
                "systemd_manager_restored\ttrue\n"
                "services_restored\ttrue\n"
                "daemon_reload_count\t2\n"
                "route_selection_count\t1\n"
                "committed\tfalse\n",
            )
            base_result = (
                ServiceQuiescenceRehearsalAdapter.
                close_restored_rehearsal_transaction(
                    self,
                    transaction,
                )
            )
            if (
                base_result.status is not AdapterStatus.PASS
                or base_result.payload is None
            ):
                return RouteSelectionRollbackAdapterResult(
                    operation=operation,
                    status=AdapterStatus.FAIL,
                    detail=f"underlying exact cleanup failed: {base_result.detail}",
                )
            transaction_copy = self._restored_transaction_copy
            if transaction_copy is None or not transaction_copy.is_dir():
                raise RouteSelectionRollbackFailure(
                    "v6 transaction audit copy is unavailable"
                )
            _atomic_text(
                transaction_copy / "state.tsv",
                "item\tvalue\n"
                "state\tsplit-bus-route-rolled-back-and-closed\n"
                "mutation_started\ttrue\n"
                "managed_files_installed\ttrue\n"
                "systemd_reloaded\ttrue\n"
                "split_bus_route_selected\ttrue\n"
                "active_route_restored\ttrue\n"
                "filesystem_restored\ttrue\n"
                "systemd_manager_restored\ttrue\n"
                "services_restored\ttrue\n"
                "daemon_reload_count\t2\n"
                "route_selection_count\t1\n"
                "route_selected\tfalse\n"
                "managed_stage_c_services_started\tfalse\n"
                "committed\tfalse\n",
            )
            _atomic_text(
                transaction_copy / "lifecycle-v6.tsv",
                "item\tvalue\n"
                "operation\tclose-route-selection-rollback-rehearsal-transaction\n"
                "managed_files_installed\ttrue\n"
                "systemd_reloaded\ttrue\n"
                "split_bus_route_selected\ttrue\n"
                "active_route_restored\ttrue\n"
                "filesystem_restored\ttrue\n"
                "systemd_manager_restored\ttrue\n"
                "services_restored\ttrue\n"
                "daemon_reload_count\t2\n"
                "route_selection_count\t1\n"
                "committed\tfalse\n",
            )
            write_evidence_manifest(transaction_copy)
        except (
            OSError,
            SystemExit,
            ServiceQuiescenceFailure,
            SystemdReloadRollbackFailure,
            RouteSelectionRollbackFailure,
        ) as exc:
            return RouteSelectionRollbackAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=str(exc),
            )
        receipt = RouteSelectionRollbackTransactionReceipt(
            transaction=transaction,
            state="split-bus-route-rolled-back-and-closed",
            mutation_started=True,
            managed_files_installed=True,
            systemd_reloaded=True,
            split_bus_route_selected=True,
            active_route_restored=True,
            filesystem_restored=True,
            systemd_manager_restored=True,
            services_restored=True,
            committed=False,
            transaction_path_absent=True,
            parents_restored=base_result.payload.parents_restored,
            installed_file_count=EXPECTED_PACKAGE_FILES,
            daemon_reload_count=self._systemd_reload_count,
            route_selection_count=self._route_selection_count,
            audit_evidence=str(self._evidence_root),
        )
        return RouteSelectionRollbackAdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail=(
                "split-bus route-selection exact-rollback rehearsal closed and removed exactly"
            ),
            payload=receipt,
        )
