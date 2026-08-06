#!/usr/bin/python3
from __future__ import annotations

"""Current-package split-bus route selection and exact-rollback adapter.

This is the final rollback-only current-package layer.  It extends the accepted
28-file, bounded-two-reload C24 owner with the physically exercised C20 atomic
route-exchange primitives.  It adds no managed-service startup, CamillaDSP
child, audio probe, approval publication, commit or persistent activation.
"""

import os
import secrets
import stat
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Self

from . import current_package_candidate_rehearsal_adapter_v7 as current_v7
from .authoritative_snapshot_rehearsal_adapter import _atomic_text
from .current_package_managed_file_rollback_adapter_v9 import (
    CURRENT_PACKAGE_FILE_COUNT_V9,
    CURRENT_PACKAGE_PAYLOAD_COUNT_V9,
)
from .current_package_systemd_reload_rollback_adapter_v10 import (
    CURRENT_SYSTEMD_SNAPSHOT_PREFIX_V10,
    CURRENT_SYSTEMD_TRANSACTION_PREFIX_V10,
    CurrentPackageSystemdReloadLifecycleOperationV10,
    CurrentPackageSystemdReloadRollbackResultV10,
    apply_current_systemd_reload_identity_contract_v10,
)
from .current_package_systemd_reload_rollback_adapter_v11 import (
    MAX_DAEMON_RELOAD_ATTEMPTS_V11,
    CurrentPackageSystemdReloadRollbackAdapterV11,
)
from .managed_file_rollback_rehearsal_adapter import (
    ManagedFileRollbackFailure,
    _owner_ids,
    _safe_destination,
    _write_all,
)
from .package_review import sha256
from .production_adapter_contract import (
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    ServiceSnapshot,
    SnapshotIdentity,
    TransactionIdentity,
)
from .read_only_host_adapter import _fail
from .route_selection_rollback_rehearsal_adapter import (
    ROUTE_ACTIONS_NAME,
    ROUTE_TRANSACTION_STATE_NAME,
    SPLIT_ROUTE_SOURCE,
    RouteIdentity,
    RouteSelectionRollbackFailure,
    _identity,
    _rename_exchange,
    _require_identity,
)
from .service_quiescence_rehearsal_adapter import (
    ServiceQuiescenceFailure,
    ServiceQuiescenceRehearsalAdapter,
)
from .snapshot_core import CURRENT_ALSA_DESTINATION, write_evidence_manifest
from .systemd_reload_rollback_rehearsal_adapter import (
    SystemdReloadRollbackFailure,
)


CURRENT_ROUTE_TRANSACTION_PREFIX_V13 = (
    "stage-c25-current-package-route-rollback-install-"
)
CURRENT_ROUTE_SNAPSHOT_PREFIX_V13 = (
    "stage-c25-current-package-route-rollback-snapshot-"
)


def apply_current_route_identity_contract_v13() -> None:
    """Bind fresh current-package transaction identities to the route rehearsal."""

    apply_current_systemd_reload_identity_contract_v10()
    current = (
        current_v7.CURRENT_TRANSACTION_PREFIX,
        current_v7.CURRENT_SNAPSHOT_PREFIX,
    )
    target = (
        CURRENT_ROUTE_TRANSACTION_PREFIX_V13,
        CURRENT_ROUTE_SNAPSHOT_PREFIX_V13,
    )
    if current == target:
        return
    expected = (
        CURRENT_SYSTEMD_TRANSACTION_PREFIX_V10,
        CURRENT_SYSTEMD_SNAPSHOT_PREFIX_V10,
    )
    if current != expected:
        raise SystemExit(
            "Stage C24 transaction identity contract changed; refusing the "
            "current-package route binding"
        )
    current_v7.CURRENT_TRANSACTION_PREFIX = CURRENT_ROUTE_TRANSACTION_PREFIX_V13
    current_v7.CURRENT_SNAPSHOT_PREFIX = CURRENT_ROUTE_SNAPSHOT_PREFIX_V13


class CurrentPackageRouteRollbackLifecycleOperationV13(str, Enum):
    CLOSE_CURRENT_PACKAGE_ROUTE_ROLLBACK_REHEARSAL = (
        "close-current-package-route-rollback-rehearsal"
    )


@dataclass(frozen=True)
class CurrentPackageRouteRollbackReceiptV13:
    transaction: TransactionIdentity
    state: str
    managed_files_installed: bool
    systemd_reloaded: bool
    split_bus_route_selected: bool
    active_route_restored: bool
    filesystem_restored: bool
    systemd_manager_restored: bool
    services_restored: bool
    committed: bool
    transaction_path_absent: bool
    parents_restored: bool
    installed_file_count: int
    payload_file_count: int
    daemon_reload_count: int
    route_selection_count: int
    audit_evidence: str

    def __post_init__(self) -> None:
        if self.state != "current-package-route-rolled-back-and-closed":
            raise ValueError("current-package route receipt state changed")
        if not all(
            (
                self.managed_files_installed,
                self.systemd_reloaded,
                self.split_bus_route_selected,
                self.active_route_restored,
                self.filesystem_restored,
                self.systemd_manager_restored,
                self.services_restored,
                self.transaction_path_absent,
                self.parents_restored,
            )
        ):
            raise ValueError("route receipt requires complete exact restoration")
        if self.committed:
            raise ValueError("rollback-only route receipt cannot be committed")
        if self.installed_file_count != CURRENT_PACKAGE_FILE_COUNT_V9:
            raise ValueError("route receipt must cover exactly 28 files")
        if self.payload_file_count != CURRENT_PACKAGE_PAYLOAD_COUNT_V9:
            raise ValueError("route receipt must bind exactly 27 payload files")
        if self.daemon_reload_count != MAX_DAEMON_RELOAD_ATTEMPTS_V11:
            raise ValueError("route receipt requires exactly two daemon reloads")
        if self.route_selection_count != 1:
            raise ValueError("route receipt requires exactly one route selection")
        if not self.audit_evidence.strip():
            raise ValueError("route receipt requires adapter-owned audit evidence")


@dataclass(frozen=True)
class CurrentPackageRouteRollbackResultV13:
    operation: CurrentPackageRouteRollbackLifecycleOperationV13
    status: AdapterStatus
    detail: str
    payload: CurrentPackageRouteRollbackReceiptV13 | None = None

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("current-package route closure detail must not be empty")
        if self.status is AdapterStatus.PASS and self.payload is None:
            raise ValueError("successful route closure requires a receipt")
        if self.status is not AdapterStatus.PASS and self.payload is not None:
            raise ValueError("failed route closure cannot carry a receipt")


class CurrentPackageRouteSelectionRollbackAdapterV13(
    CurrentPackageSystemdReloadRollbackAdapterV11
):
    """Current 28-file package plus one atomic route exchange and exact reversal."""

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
                    "mandatory current-package active-route rollback failed; "
                    "the production lock and transaction are intentionally retained: "
                    f"{rollback_exc}"
                ) from exc
        CurrentPackageSystemdReloadRollbackAdapterV11.__exit__(
            self, exc_type, exc, traceback
        )

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
            "installed_file_count\t28\n"
            "payload_file_count\t27\n"
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

    @staticmethod
    def _unlink_partial_candidate(
        parent_fd: int,
        name: str,
        device: int,
        inode: int,
    ) -> None:
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            stat.S_ISLNK(current.st_mode)
            or not stat.S_ISREG(current.st_mode)
            or current.st_dev != device
            or current.st_ino != inode
        ):
            raise RouteSelectionRollbackFailure(
                "refusing partial route-candidate cleanup after substitution"
            )
        os.unlink(name, dir_fd=parent_fd)
        os.fsync(parent_fd)

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
        parent_fd, _parent = self._open_parent(active)
        try:
            if self._route_exchange_completed:
                _require_identity(active, candidate, "selected active route")
                _require_identity(rollback_path, original, "parked original route")
                _rename_exchange(parent_fd, active.name, rollback_name)
                self._route_exchange_completed = False
                os.fsync(parent_fd)
                _require_identity(active, original, "restored active route")
                _require_identity(rollback_path, candidate, "parked candidate route")
                self._unlink_partial_candidate(
                    parent_fd,
                    rollback_name,
                    candidate.device,
                    candidate.inode,
                )
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
                _require_identity(
                    rollback_path,
                    candidate,
                    "unexchanged candidate route",
                )
                _require_identity(active, original, "unchanged active route")
                self._unlink_partial_candidate(
                    parent_fd,
                    rollback_name,
                    candidate.device,
                    candidate.inode,
                )
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
        temporary_device: int | None = None
        temporary_inode: int | None = None
        original: RouteIdentity | None = None
        candidate: RouteIdentity | None = None
        try:
            source, source_identity = self._installed_split_route()
            original = self._original_route_identity()
            rollback_name = (
                f".{active.name}.stage-c25-{secrets.token_hex(12)}.rollback"
            )
            rollback_path = active.parent / rollback_name
            parent_fd, _parent = self._open_parent(active)
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
            temporary_device = created.st_dev
            temporary_inode = created.st_ino
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
            ManagedFileRollbackFailure,
            RouteSelectionRollbackFailure,
            SystemdReloadRollbackFailure,
        ) as exc:
            cleanup_error: BaseException | None = None
            try:
                if self._route_exchange_completed:
                    self._restore_active_route_exact()
                elif (
                    parent_fd is not None
                    and self._route_rollback_name is not None
                    and temporary_device is not None
                    and temporary_inode is not None
                ):
                    if fd is not None:
                        os.close(fd)
                        fd = None
                    self._unlink_partial_candidate(
                        parent_fd,
                        self._route_rollback_name,
                        temporary_device,
                        temporary_inode,
                    )
                    self._route_rollback_name = None
                    if original is not None:
                        _require_identity(
                            active,
                            original,
                            "unchanged active route after failed preparation",
                        )
                    self._record_route_action(
                        "remove-failed-route-candidate",
                        "PASS",
                        f"removed_candidate_inode={temporary_inode}",
                    )
            except BaseException as immediate_cleanup_exc:
                cleanup_error = immediate_cleanup_exc
            detail = str(exc)
            if cleanup_error is not None:
                detail += f"; immediate route cleanup failed: {cleanup_error}"
            self._record_route_action(
                "select-split-bus-route",
                "FAIL",
                detail,
            )
            return _fail(operation, detail)
        finally:
            if fd is not None:
                os.close(fd)
            if parent_fd is not None:
                os.close(parent_fd)

        assert original is not None
        assert candidate is not None
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
        result = CurrentPackageSystemdReloadRollbackAdapterV11.restore_exact_snapshot(
            self, transaction, snapshot
        )
        if result.status is AdapterStatus.PASS:
            try:
                self._write_route_transaction_state(
                    "active-route-and-managed-files-restored-manager-pending"
                )
            except (OSError, RouteSelectionRollbackFailure) as exc:
                return _fail(operation, str(exc))
            assert self._route_original is not None
            return AdapterResult(
                operation=operation,
                status=AdapterStatus.PASS,
                detail=(
                    "original active-route inode and authoritative 28-file managed filesystem restored exactly"
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
        return CurrentPackageSystemdReloadRollbackAdapterV11.restore_captured_application_services(
            self, transaction, services
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
        return CurrentPackageSystemdReloadRollbackAdapterV11.verify_exact_rollback(
            self, transaction, snapshot
        )

    def close_current_package_systemd_reload_rollback_rehearsal(
        self,
        transaction: TransactionIdentity,
    ) -> CurrentPackageSystemdReloadRollbackResultV10:
        if self._route_mutation_started:
            return CurrentPackageSystemdReloadRollbackResultV10(
                operation=(
                    CurrentPackageSystemdReloadLifecycleOperationV10.
                    CLOSE_CURRENT_PACKAGE_SYSTEMD_RELOAD_ROLLBACK_REHEARSAL
                ),
                status=AdapterStatus.FAIL,
                detail=(
                    "C24 systemd-only closure is unavailable after active-route "
                    "mutation; use the current-package route closure"
                ),
            )
        return CurrentPackageSystemdReloadRollbackAdapterV11.close_current_package_systemd_reload_rollback_rehearsal(
            self, transaction
        )

    def close_current_package_route_rollback_rehearsal(
        self,
        transaction: TransactionIdentity,
    ) -> CurrentPackageRouteRollbackResultV13:
        operation = (
            CurrentPackageRouteRollbackLifecycleOperationV13.
            CLOSE_CURRENT_PACKAGE_ROUTE_ROLLBACK_REHEARSAL
        )
        current = self.authoritative_transaction
        if current is None or transaction != current.transaction:
            return CurrentPackageRouteRollbackResultV13(
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
        ) or (
            self._route_selection_count != 1
            or self._systemd_reload_count != 2
            or self._systemd_reload_attempt_count != 2
        ):
            return CurrentPackageRouteRollbackResultV13(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=(
                    "one route selection, exact active-route/filesystem/manager "
                    "rollback, service restoration and exact verification must "
                    "complete before current-package route closure"
                ),
            )

        assert self.transaction_path is not None
        try:
            _atomic_text(
                self.transaction_path / "lifecycle-c25.tsv",
                "item\tvalue\n"
                "operation\tclose-current-package-route-rollback-rehearsal\n"
                "managed_files_installed\ttrue\n"
                "installed_file_count\t28\n"
                "payload_file_count\t27\n"
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
                close_restored_rehearsal_transaction(self, transaction)
            )
            if (
                base_result.status is not AdapterStatus.PASS
                or base_result.payload is None
            ):
                return CurrentPackageRouteRollbackResultV13(
                    operation=operation,
                    status=AdapterStatus.FAIL,
                    detail=f"underlying exact cleanup failed: {base_result.detail}",
                )
            transaction_copy = self._restored_transaction_copy
            if transaction_copy is None or not transaction_copy.is_dir():
                raise RouteSelectionRollbackFailure(
                    "current-package route transaction audit copy is unavailable"
                )
            _atomic_text(
                transaction_copy / "state.tsv",
                "item\tvalue\n"
                "state\tcurrent-package-route-rolled-back-and-closed\n"
                "mutation_started\ttrue\n"
                "managed_files_installed\ttrue\n"
                "installed_file_count\t28\n"
                "payload_file_count\t27\n"
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
            _atomic_text(
                transaction_copy / "lifecycle-c25.tsv",
                "item\tvalue\n"
                "operation\tclose-current-package-route-rollback-rehearsal\n"
                "managed_files_installed\ttrue\n"
                "installed_file_count\t28\n"
                "payload_file_count\t27\n"
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
            ManagedFileRollbackFailure,
            ServiceQuiescenceFailure,
            SystemdReloadRollbackFailure,
            RouteSelectionRollbackFailure,
        ) as exc:
            return CurrentPackageRouteRollbackResultV13(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=str(exc),
            )

        receipt = CurrentPackageRouteRollbackReceiptV13(
            transaction=transaction,
            state="current-package-route-rolled-back-and-closed",
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
            installed_file_count=CURRENT_PACKAGE_FILE_COUNT_V9,
            payload_file_count=CURRENT_PACKAGE_PAYLOAD_COUNT_V9,
            daemon_reload_count=self._systemd_reload_count,
            route_selection_count=self._route_selection_count,
            audit_evidence=str(self._evidence_root),
        )
        return CurrentPackageRouteRollbackResultV13(
            operation=operation,
            status=AdapterStatus.PASS,
            detail=(
                "current-package route-selection exact-rollback rehearsal closed "
                "and removed exactly"
            ),
            payload=receipt,
        )
