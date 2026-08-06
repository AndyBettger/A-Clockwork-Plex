#!/usr/bin/python3
from __future__ import annotations

"""Current-package managed-file installation and exact-rollback adapter.

Stage C23 composes the accepted current-package transaction/service owner with
only the physically exercised Stage C18 managed-file mutation primitives.  The
new layer changes the historical twelve-file success boundary to the accepted
28-file package contract and adds no daemon reload, route, mixer, approval,
CamillaDSP, audio, commit or activation operation.
"""

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Self

from stage_c_activation_package.core import EXPECTED_FILES

from . import current_package_candidate_rehearsal_adapter_v7 as current_v7
from .authoritative_snapshot_rehearsal_adapter import _atomic_text
from .candidate_validation_rehearsal_adapter import CandidateValidationFailure
from .current_package_service_quiescence_adapter_v8 import (
    CurrentPackageServiceQuiescenceAdapterV8,
)
from .managed_file_rollback_rehearsal_adapter import (
    MANAGED_FILE_ACTIONS_NAME,
    InstalledObject,
    ManagedFileRollbackFailure,
    ManagedFileRollbackRehearsalAdapter,
    SnapshotRow,
    _safe_destination,
)
from .managed_file_rollback_rehearsal_adapter_v2 import (
    ManagedFileRollbackRehearsalAdapterV2,
)
from .managed_file_rollback_rehearsal_adapter_v3 import (
    ManagedFileRollbackRehearsalAdapterV3,
)
from .managed_file_rollback_rehearsal_adapter_v4 import (
    ManagedFileRollbackRehearsalAdapterV4,
)
from .production_adapter_contract import (
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    TransactionIdentity,
)
from .production_adapter_lifecycle_v2 import LifecycleAdapterResult
from .production_adapter_lifecycle_v3 import (
    RestoredRehearsalAdapterResult,
    RestoredRehearsalLifecycleOperation,
)
from .read_only_host_adapter import _fail
from .service_quiescence_rehearsal_adapter import (
    ServiceQuiescenceFailure,
    ServiceQuiescenceRehearsalAdapter,
)
from .snapshot_core import write_evidence_manifest


LEGACY_CURRENT_TRANSACTION_PREFIX_V9 = "stage-c21-prepare-install-"
LEGACY_CURRENT_SNAPSHOT_PREFIX_V9 = "stage-c21-prepare-snapshot-"
CURRENT_MANAGED_TRANSACTION_PREFIX_V9 = "stage-c23-managed-file-rollback-install-"
CURRENT_MANAGED_SNAPSHOT_PREFIX_V9 = "stage-c23-managed-file-rollback-snapshot-"
CURRENT_PACKAGE_FILE_COUNT_V9 = EXPECTED_FILES
CURRENT_PACKAGE_PAYLOAD_COUNT_V9 = EXPECTED_FILES - 1

if CURRENT_PACKAGE_FILE_COUNT_V9 != 28 or CURRENT_PACKAGE_PAYLOAD_COUNT_V9 != 27:
    raise RuntimeError("Stage C23 current-package file-count contract changed")


def apply_current_managed_file_identity_contract_v9() -> None:
    """Bind fresh current-package transaction identities to Stage C23."""

    if (
        current_v7.CURRENT_TRANSACTION_PREFIX
        != LEGACY_CURRENT_TRANSACTION_PREFIX_V9
        or current_v7.CURRENT_SNAPSHOT_PREFIX
        != LEGACY_CURRENT_SNAPSHOT_PREFIX_V9
    ):
        raise SystemExit(
            "Stage C21 transaction identity contract changed; refusing the "
            "Stage C23 managed-file binding"
        )
    current_v7.CURRENT_TRANSACTION_PREFIX = CURRENT_MANAGED_TRANSACTION_PREFIX_V9
    current_v7.CURRENT_SNAPSHOT_PREFIX = CURRENT_MANAGED_SNAPSHOT_PREFIX_V9


class CurrentPackageExactRollbackLifecycleOperationV9(str, Enum):
    CLOSE_CURRENT_PACKAGE_EXACT_ROLLBACK_REHEARSAL = (
        "close-current-package-exact-rollback-rehearsal"
    )


@dataclass(frozen=True)
class CurrentPackageExactRollbackReceiptV9:
    transaction: TransactionIdentity
    state: str
    mutation_started: bool
    managed_files_installed: bool
    filesystem_restored: bool
    services_restored: bool
    committed: bool
    transaction_path_absent: bool
    parents_restored: bool
    installed_file_count: int
    payload_file_count: int
    audit_evidence: str

    def __post_init__(self) -> None:
        if self.state != "current-package-managed-files-rolled-back-and-closed":
            raise ValueError("Stage C23 exact-rollback receipt state changed")
        if not all(
            (
                self.mutation_started,
                self.managed_files_installed,
                self.filesystem_restored,
                self.services_restored,
                self.transaction_path_absent,
                self.parents_restored,
            )
        ):
            raise ValueError("Stage C23 receipt requires complete exact restoration")
        if self.committed:
            raise ValueError("Stage C23 exact-rollback receipt cannot be committed")
        if self.installed_file_count != CURRENT_PACKAGE_FILE_COUNT_V9:
            raise ValueError("Stage C23 receipt must cover exactly 28 files")
        if self.payload_file_count != CURRENT_PACKAGE_PAYLOAD_COUNT_V9:
            raise ValueError("Stage C23 receipt must bind exactly 27 payload files")
        if not self.audit_evidence.strip():
            raise ValueError("Stage C23 receipt requires adapter-owned audit evidence")


@dataclass(frozen=True)
class CurrentPackageExactRollbackResultV9:
    operation: CurrentPackageExactRollbackLifecycleOperationV9
    status: AdapterStatus
    detail: str
    payload: CurrentPackageExactRollbackReceiptV9 | None = None

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("Stage C23 closure detail must not be empty")
        if self.status is not AdapterStatus.PASS and self.payload is not None:
            raise ValueError("failed Stage C23 closure cannot carry a receipt")


class CurrentPackageManagedFileRollbackAdapterV9(
    CurrentPackageServiceQuiescenceAdapterV8
):
    """Accepted 28-file package plus Stage C18 exact inode-ledger rollback."""

    # Reuse the physically exercised C18 implementation objects directly.  The
    # current-package layer supplies the transaction, snapshots, entries,
    # candidate root and validation state; these methods own only file mutation
    # and exact restoration.
    _record_managed_action = ManagedFileRollbackRehearsalAdapter._record_managed_action
    _snapshot_rows = ManagedFileRollbackRehearsalAdapter._snapshot_rows
    _verify_directory_snapshot = staticmethod(
        ManagedFileRollbackRehearsalAdapter._verify_directory_snapshot
    )
    _open_parent = staticmethod(ManagedFileRollbackRehearsalAdapter._open_parent)
    _verify_installed_object = staticmethod(
        ManagedFileRollbackRehearsalAdapter._verify_installed_object
    )
    _verify_current_alsa = ManagedFileRollbackRehearsalAdapter._verify_current_alsa
    _arm_managed_rollback = ManagedFileRollbackRehearsalAdapterV2._arm_managed_rollback
    _create_directory = ManagedFileRollbackRehearsalAdapterV3._create_directory
    _cleanup_temporary = ManagedFileRollbackRehearsalAdapterV3._cleanup_temporary
    _atomic_install_file = ManagedFileRollbackRehearsalAdapterV3._atomic_install_file
    _verify_rollback_identity = staticmethod(
        ManagedFileRollbackRehearsalAdapterV4._verify_rollback_identity
    )
    _remove_exact_file_if_present = (
        ManagedFileRollbackRehearsalAdapterV4._remove_exact_file_if_present
    )
    _restore_managed_files_exact = (
        ManagedFileRollbackRehearsalAdapterV4._restore_managed_files_exact
    )
    restore_exact_snapshot = ManagedFileRollbackRehearsalAdapter.restore_exact_snapshot
    verify_exact_rollback = ManagedFileRollbackRehearsalAdapter.verify_exact_rollback

    def __init__(
        self,
        package_root: Path,
        invoking_user: str,
        evidence_root: Path,
    ) -> None:
        super().__init__(package_root, invoking_user, evidence_root)
        self._managed_file_actions = self._evidence_root / MANAGED_FILE_ACTIONS_NAME
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
        self._temporary_files: list[InstalledObject] = []
        self._pending_publication: InstalledObject | None = None
        self._publication_failed_cleanly = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._managed_files_installed and not self._filesystem_restored:
            try:
                self._restore_managed_files_exact()
            except ManagedFileRollbackFailure as rollback_exc:
                raise ManagedFileRollbackFailure(
                    "mandatory Stage C23 filesystem rollback failed; the "
                    "production lock and transaction are intentionally retained: "
                    f"{rollback_exc}"
                ) from exc
        CurrentPackageServiceQuiescenceAdapterV8.__exit__(
            self, exc_type, exc, traceback
        )

    @property
    def managed_files_installed_once(self) -> bool:
        return self._managed_files_installed_once

    @property
    def filesystem_restored(self) -> bool:
        return self._filesystem_restored

    @property
    def exact_rollback_verified(self) -> bool:
        return self._exact_rollback_verified

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

        files = tuple(item for item in self._entries if item.kind == "file")
        if len(files) != CURRENT_PACKAGE_FILE_COUNT_V9:
            return _fail(
                operation,
                "current package no longer contains exactly 28 managed files",
            )

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
                        "unsupported managed directory state: "
                        f"{entry.destination}={row.state}"
                    )

            for entry in files:
                self._atomic_install_file(entry)

            if len(self._installed_files) != CURRENT_PACKAGE_FILE_COUNT_V9:
                raise ManagedFileRollbackFailure(
                    "managed install did not produce exactly 28 files"
                )
            for record in self._installed_files:
                self._verify_installed_object(record)
            self._verify_current_alsa()

            assert self.transaction_path is not None
            _atomic_text(
                self.transaction_path / "managed-files-installed.tsv",
                "item\tvalue\n"
                "state\tcurrent-package-managed-files-installed\n"
                f"file_count\t{len(self._installed_files)}\n"
                f"payload_file_count\t{CURRENT_PACKAGE_PAYLOAD_COUNT_V9}\n"
                f"created_directory_count\t{len(self._created_directories)}\n"
                "systemd_reloaded\tfalse\n"
                "route_selected\tfalse\n"
                "committed\tfalse\n",
            )
            _atomic_text(
                self.transaction_path / "state.tsv",
                "item\tvalue\n"
                "state\tcurrent-package-managed-files-installed-rehearsal\n"
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
            detail=(
                "28 current-package files installed atomically with no reload "
                "or route change"
            ),
            evidence=(
                ("installed_file_count", str(len(self._installed_files))),
                ("payload_file_count", str(CURRENT_PACKAGE_PAYLOAD_COUNT_V9)),
                ("created_directory_count", str(len(self._created_directories))),
                ("systemd_reloaded", "false"),
                ("route_selected", "false"),
            ),
        )

    def abort_uncommitted_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> LifecycleAdapterResult:
        return ServiceQuiescenceRehearsalAdapter.abort_uncommitted_transaction(
            self, transaction
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
                    "service-only closure is unavailable after current-package "
                    "managed-file mutation; use the Stage C23 exact-rollback closure"
                ),
            )
        return ServiceQuiescenceRehearsalAdapter.close_restored_rehearsal_transaction(
            self, transaction
        )

    def close_current_package_exact_rollback_rehearsal(
        self,
        transaction: TransactionIdentity,
    ) -> CurrentPackageExactRollbackResultV9:
        operation = (
            CurrentPackageExactRollbackLifecycleOperationV9.
            CLOSE_CURRENT_PACKAGE_EXACT_ROLLBACK_REHEARSAL
        )
        current = self.authoritative_transaction
        if current is None or transaction != current.transaction:
            return CurrentPackageExactRollbackResultV9(
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
            return CurrentPackageExactRollbackResultV9(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=(
                    "28-file install, exact filesystem rollback, service "
                    "restoration and exact verification must complete before closure"
                ),
            )

        assert self.transaction_path is not None
        try:
            _atomic_text(
                self.transaction_path / "lifecycle-c23.tsv",
                "item\tvalue\n"
                "operation\tclose-current-package-exact-rollback-rehearsal\n"
                "managed_files_installed\ttrue\n"
                "installed_file_count\t28\n"
                "filesystem_restored\ttrue\n"
                "services_restored\ttrue\n"
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
                return CurrentPackageExactRollbackResultV9(
                    operation=operation,
                    status=AdapterStatus.FAIL,
                    detail=f"underlying exact cleanup failed: {base_result.detail}",
                )
            transaction_copy = self._restored_transaction_copy
            if transaction_copy is None or not transaction_copy.is_dir():
                raise ManagedFileRollbackFailure(
                    "Stage C23 transaction audit copy is unavailable"
                )
            _atomic_text(
                transaction_copy / "state.tsv",
                "item\tvalue\n"
                "state\tcurrent-package-managed-files-rolled-back-and-closed\n"
                "mutation_started\ttrue\n"
                "managed_files_installed\ttrue\n"
                "installed_file_count\t28\n"
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
            return CurrentPackageExactRollbackResultV9(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=str(exc),
            )

        receipt = CurrentPackageExactRollbackReceiptV9(
            transaction=transaction,
            state="current-package-managed-files-rolled-back-and-closed",
            mutation_started=True,
            managed_files_installed=True,
            filesystem_restored=True,
            services_restored=True,
            committed=False,
            transaction_path_absent=True,
            parents_restored=base_result.payload.parents_restored,
            installed_file_count=CURRENT_PACKAGE_FILE_COUNT_V9,
            payload_file_count=CURRENT_PACKAGE_PAYLOAD_COUNT_V9,
            audit_evidence=str(self._evidence_root),
        )
        return CurrentPackageExactRollbackResultV9(
            operation=operation,
            status=AdapterStatus.PASS,
            detail=(
                "current-package managed-file exact-rollback rehearsal closed "
                "and removed exactly"
            ),
            payload=receipt,
        )
