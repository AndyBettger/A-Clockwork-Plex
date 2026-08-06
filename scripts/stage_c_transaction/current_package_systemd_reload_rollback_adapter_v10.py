#!/usr/bin/python3
from __future__ import annotations

"""Current-package systemd daemon-reload and exact rollback adapter.

Stage C24 extends the accepted Stage C23 28-file transaction owner with only the
physically exercised Stage C19 systemd-manager mutation primitives. It permits
exactly two daemon reloads: one while the three candidate units are installed
and one after exact filesystem rollback. Route selection, managed-service
startup, mixer mutation, CamillaDSP, probes, approval, commit and activation are
not added.
"""

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Self

from . import current_package_candidate_rehearsal_adapter_v7 as current_v7
from .authoritative_snapshot_rehearsal_adapter import _atomic_text
from .current_package_managed_file_rollback_adapter_v9 import (
    CURRENT_PACKAGE_FILE_COUNT_V9,
    CURRENT_PACKAGE_PAYLOAD_COUNT_V9,
    CurrentPackageExactRollbackLifecycleOperationV9,
    CurrentPackageExactRollbackResultV9,
    CurrentPackageManagedFileRollbackAdapterV9,
)
from .managed_file_rollback_rehearsal_adapter import (
    ManagedFileRollbackFailure,
)
from .production_adapter_contract import (
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    ServiceSnapshot,
    SnapshotIdentity,
    TransactionIdentity,
)
from .read_only_host_adapter import _fail
from .service_quiescence_rehearsal_adapter import (
    ServiceQuiescenceFailure,
    ServiceQuiescenceRehearsalAdapter,
)
from .snapshot_core import write_evidence_manifest
from .systemd_reload_rollback_rehearsal_adapter import (
    SYSTEMD_RELOAD_ACTIONS_NAME,
    SYSTEMD_UNIT_OBSERVATIONS_NAME,
    SystemdReloadRollbackFailure,
    SystemdReloadRollbackRehearsalAdapter,
)


LEGACY_CURRENT_TRANSACTION_PREFIX_V10 = "stage-c21-prepare-install-"
LEGACY_CURRENT_SNAPSHOT_PREFIX_V10 = "stage-c21-prepare-snapshot-"
CURRENT_SYSTEMD_TRANSACTION_PREFIX_V10 = (
    "stage-c24-systemd-reload-rollback-install-"
)
CURRENT_SYSTEMD_SNAPSHOT_PREFIX_V10 = (
    "stage-c24-systemd-reload-rollback-snapshot-"
)


def apply_current_systemd_reload_identity_contract_v10() -> None:
    """Bind fresh current-package transaction identities to Stage C24."""

    current = (
        current_v7.CURRENT_TRANSACTION_PREFIX,
        current_v7.CURRENT_SNAPSHOT_PREFIX,
    )
    target = (
        CURRENT_SYSTEMD_TRANSACTION_PREFIX_V10,
        CURRENT_SYSTEMD_SNAPSHOT_PREFIX_V10,
    )
    if current == target:
        return
    legacy = (
        LEGACY_CURRENT_TRANSACTION_PREFIX_V10,
        LEGACY_CURRENT_SNAPSHOT_PREFIX_V10,
    )
    if current != legacy:
        raise SystemExit(
            "Stage C21 transaction identity contract changed; refusing the "
            "Stage C24 systemd-reload binding"
        )
    current_v7.CURRENT_TRANSACTION_PREFIX = CURRENT_SYSTEMD_TRANSACTION_PREFIX_V10
    current_v7.CURRENT_SNAPSHOT_PREFIX = CURRENT_SYSTEMD_SNAPSHOT_PREFIX_V10


class CurrentPackageSystemdReloadLifecycleOperationV10(str, Enum):
    CLOSE_CURRENT_PACKAGE_SYSTEMD_RELOAD_ROLLBACK_REHEARSAL = (
        "close-current-package-systemd-reload-rollback-rehearsal"
    )


@dataclass(frozen=True)
class CurrentPackageSystemdReloadRollbackReceiptV10:
    transaction: TransactionIdentity
    state: str
    mutation_started: bool
    managed_files_installed: bool
    systemd_reloaded: bool
    filesystem_restored: bool
    systemd_manager_restored: bool
    services_restored: bool
    committed: bool
    transaction_path_absent: bool
    parents_restored: bool
    installed_file_count: int
    payload_file_count: int
    daemon_reload_count: int
    audit_evidence: str

    def __post_init__(self) -> None:
        if self.state != "current-package-systemd-reload-rolled-back-and-closed":
            raise ValueError("Stage C24 receipt state changed")
        if not all(
            (
                self.mutation_started,
                self.managed_files_installed,
                self.systemd_reloaded,
                self.filesystem_restored,
                self.systemd_manager_restored,
                self.services_restored,
                self.transaction_path_absent,
                self.parents_restored,
            )
        ):
            raise ValueError("Stage C24 receipt requires complete exact restoration")
        if self.committed:
            raise ValueError("Stage C24 rollback receipt cannot be committed")
        if self.installed_file_count != CURRENT_PACKAGE_FILE_COUNT_V9:
            raise ValueError("Stage C24 receipt must cover exactly 28 files")
        if self.payload_file_count != CURRENT_PACKAGE_PAYLOAD_COUNT_V9:
            raise ValueError("Stage C24 receipt must bind exactly 27 payload files")
        if self.daemon_reload_count != 2:
            raise ValueError("Stage C24 requires exactly two daemon reloads")
        if not self.audit_evidence.strip():
            raise ValueError("Stage C24 receipt requires adapter-owned audit evidence")


@dataclass(frozen=True)
class CurrentPackageSystemdReloadRollbackResultV10:
    operation: CurrentPackageSystemdReloadLifecycleOperationV10
    status: AdapterStatus
    detail: str
    payload: CurrentPackageSystemdReloadRollbackReceiptV10 | None = None

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("Stage C24 closure detail must not be empty")
        if self.status is not AdapterStatus.PASS and self.payload is not None:
            raise ValueError("failed Stage C24 closure cannot carry a receipt")


class CurrentPackageSystemdReloadRollbackAdapterV10(
    CurrentPackageManagedFileRollbackAdapterV9
):
    """Accepted 28-file package plus bounded systemd-manager rollback."""

    # These physically exercised C19 functions contain the only host command
    # owner used by C24: fixed `systemctl daemon-reload` and fixed
    # `systemctl show` observations of the three managed units.
    _record_systemd_action = (
        SystemdReloadRollbackRehearsalAdapter._record_systemd_action
    )
    _parse_systemctl_show = staticmethod(
        SystemdReloadRollbackRehearsalAdapter._parse_systemctl_show
    )
    _observe_managed_units = (
        SystemdReloadRollbackRehearsalAdapter._observe_managed_units
    )
    _run_daemon_reload = SystemdReloadRollbackRehearsalAdapter._run_daemon_reload

    def __init__(
        self,
        package_root: Path,
        invoking_user: str,
        evidence_root: Path,
    ) -> None:
        super().__init__(package_root, invoking_user, evidence_root)
        self._systemd_reload_actions = (
            self._evidence_root / SYSTEMD_RELOAD_ACTIONS_NAME
        )
        self._systemd_reload_actions.write_text(
            "order\tmonotonic_ns\tphase\taction\tresult\tdetail\n",
            encoding="utf-8",
        )
        os.chown(self._systemd_reload_actions, 0, 0)
        self._systemd_reload_actions.chmod(0o600)
        self._systemd_unit_observations = (
            self._evidence_root / SYSTEMD_UNIT_OBSERVATIONS_NAME
        )
        self._systemd_unit_observations.write_text(
            "phase\tmonotonic_ns\tunit\tload_state\tactive_state\t"
            "sub_state\tunit_file_state\tfragment_path\n",
            encoding="utf-8",
        )
        os.chown(self._systemd_unit_observations, 0, 0)
        self._systemd_unit_observations.chmod(0o600)
        self._systemd_action_order = 0
        self._systemd_mutation_started = False
        self._systemd_reload_count = 0
        self._systemd_candidate_visible = False
        self._systemd_manager_restored = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._systemd_mutation_started:
            try:
                if self._managed_files_installed and not self._filesystem_restored:
                    self._restore_managed_files_exact()
                    self._write_systemd_transaction_state(
                        "current-package-files-rolled-back-manager-pending"
                    )
                if not self._systemd_manager_restored:
                    self._restore_systemd_manager_exact()
            except (
                OSError,
                ManagedFileRollbackFailure,
                SystemdReloadRollbackFailure,
            ) as rollback_exc:
                raise SystemdReloadRollbackFailure(
                    "mandatory Stage C24 filesystem and systemd-manager rollback "
                    "failed; the production lock and transaction are intentionally "
                    f"retained: {rollback_exc}"
                ) from exc
        CurrentPackageManagedFileRollbackAdapterV9.__exit__(
            self, exc_type, exc, traceback
        )

    @property
    def systemd_reload_count(self) -> int:
        return self._systemd_reload_count

    @property
    def systemd_candidate_visible(self) -> bool:
        return self._systemd_candidate_visible

    @property
    def systemd_manager_restored(self) -> bool:
        return self._systemd_manager_restored

    def _write_systemd_transaction_state(self, state: str) -> None:
        if self.transaction_path is None:
            raise SystemdReloadRollbackFailure(
                "authoritative transaction is unavailable for systemd state"
            )
        common = (
            f"state\t{state}\n"
            f"daemon_reload_count\t{self._systemd_reload_count}\n"
            f"candidate_visible\t{str(self._systemd_candidate_visible).lower()}\n"
            f"filesystem_restored\t{str(self._filesystem_restored).lower()}\n"
            f"systemd_manager_restored\t{str(self._systemd_manager_restored).lower()}\n"
            "route_selected\tfalse\n"
            "committed\tfalse\n"
        )
        _atomic_text(
            self.transaction_path / "systemd-reload-rollback.tsv",
            "item\tvalue\n" + common,
        )
        _atomic_text(
            self.transaction_path / "managed-files-installed.tsv",
            "item\tvalue\n"
            f"state\t{state}\n"
            f"file_count\t{CURRENT_PACKAGE_FILE_COUNT_V9}\n"
            f"payload_file_count\t{CURRENT_PACKAGE_PAYLOAD_COUNT_V9}\n"
            f"removed_file_count\t{CURRENT_PACKAGE_FILE_COUNT_V9 if self._filesystem_restored else 0}\n"
            f"removed_directory_count\t{len(self._created_directories) if self._filesystem_restored else 0}\n"
            "systemd_reloaded\ttrue\n"
            f"systemd_manager_restored\t{str(self._systemd_manager_restored).lower()}\n"
            "route_selected\tfalse\n"
            "committed\tfalse\n",
        )
        _atomic_text(
            self.transaction_path / "state.tsv",
            "item\tvalue\n"
            f"state\t{state}\n"
            "mutation_started\ttrue\n"
            "managed_files_installed\ttrue\n"
            f"filesystem_restored\t{str(self._filesystem_restored).lower()}\n"
            "systemd_reloaded\ttrue\n"
            f"systemd_manager_restored\t{str(self._systemd_manager_restored).lower()}\n"
            "route_selected\tfalse\n"
            "committed\tfalse\n",
        )

    def _restore_systemd_manager_exact(self) -> None:
        if not self._filesystem_restored:
            raise SystemdReloadRollbackFailure(
                "systemd manager cannot be restored before filesystem rollback"
            )
        if not self._services_stopped or self._services_restored:
            raise SystemdReloadRollbackFailure(
                "systemd manager restoration requires continued service quiescence"
            )
        self._run_daemon_reload("rollback-files-absent")
        self._observe_managed_units("rollback-files-absent", installed=False)
        self._systemd_manager_restored = True
        self._write_systemd_transaction_state("systemd-manager-restored")

    def reload_systemd(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.RELOAD_SYSTEMD
        invalid = self._require_candidate(operation, transaction)
        if invalid is not None:
            return invalid
        if not self._mutation_started or not self._services_stopped:
            return _fail(operation, "systemd reload requires service quiescence")
        if not self._dac_release_verified:
            return _fail(operation, "systemd reload requires verified DAC release")
        try:
            if self._systemd_reload_count == 0:
                if not self._managed_files_installed or self._filesystem_restored:
                    raise SystemdReloadRollbackFailure(
                        "first daemon reload requires installed managed files"
                    )
                self._systemd_mutation_started = True
                self._run_daemon_reload("candidate-files-installed")
                self._observe_managed_units(
                    "candidate-files-installed", installed=True
                )
                self._systemd_candidate_visible = True
                self._write_systemd_transaction_state("systemd-candidate-visible")
                detail = (
                    "systemd reloaded the installed current package; all three "
                    "managed units are loaded and inactive"
                )
                phase = "candidate-files-installed"
            elif self._systemd_reload_count == 1:
                if not self._filesystem_restored:
                    raise SystemdReloadRollbackFailure(
                        "second daemon reload requires exact filesystem rollback"
                    )
                if not self._systemd_candidate_visible:
                    raise SystemdReloadRollbackFailure(
                        "candidate unit visibility was not proved"
                    )
                self._restore_systemd_manager_exact()
                detail = (
                    "systemd reloaded after current-package file rollback; all "
                    "three managed units are not-found"
                )
                phase = "rollback-files-absent"
            else:
                raise SystemdReloadRollbackFailure(
                    "Stage C24 permits exactly two daemon reloads"
                )
        except (
            OSError,
            ManagedFileRollbackFailure,
            SystemdReloadRollbackFailure,
        ) as exc:
            return _fail(operation, str(exc))
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail=detail,
            evidence=(
                ("phase", phase),
                ("daemon_reload_count", str(self._systemd_reload_count)),
                ("managed_units_active", "0"),
                ("route_selected", "false"),
            ),
        )

    def restore_exact_snapshot(
        self,
        transaction: TransactionIdentity,
        snapshot: SnapshotIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.RESTORE_EXACT_SNAPSHOT
        if self._systemd_reload_count != 1 or not self._systemd_candidate_visible:
            return _fail(
                operation,
                "filesystem rollback requires the installed units to be visible",
            )
        result = super().restore_exact_snapshot(transaction, snapshot)
        if result.status is AdapterStatus.PASS:
            try:
                self._write_systemd_transaction_state(
                    "current-package-files-rolled-back-manager-pending"
                )
            except (OSError, SystemdReloadRollbackFailure) as exc:
                return _fail(operation, str(exc))
        return result

    def restore_captured_application_services(
        self,
        transaction: TransactionIdentity,
        services: ServiceSnapshot,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES
        if self._systemd_mutation_started and not self._systemd_manager_restored:
            return _fail(
                operation,
                "application services cannot restart before systemd-manager rollback",
            )
        return super().restore_captured_application_services(transaction, services)

    def verify_exact_rollback(
        self,
        transaction: TransactionIdentity,
        snapshot: SnapshotIdentity,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.VERIFY_EXACT_ROLLBACK
        if not self._systemd_manager_restored or self._systemd_reload_count != 2:
            return _fail(
                operation,
                "exact verification requires two reloads and restored manager state",
            )
        return super().verify_exact_rollback(transaction, snapshot)

    def close_current_package_exact_rollback_rehearsal(
        self,
        transaction: TransactionIdentity,
    ) -> CurrentPackageExactRollbackResultV9:
        if self._systemd_mutation_started:
            return CurrentPackageExactRollbackResultV9(
                operation=(
                    CurrentPackageExactRollbackLifecycleOperationV9.
                    CLOSE_CURRENT_PACKAGE_EXACT_ROLLBACK_REHEARSAL
                ),
                status=AdapterStatus.FAIL,
                detail=(
                    "C23 file-only closure is unavailable after systemd-manager "
                    "mutation; use the Stage C24 closure"
                ),
            )
        return super().close_current_package_exact_rollback_rehearsal(transaction)

    def close_current_package_systemd_reload_rollback_rehearsal(
        self,
        transaction: TransactionIdentity,
    ) -> CurrentPackageSystemdReloadRollbackResultV10:
        operation = (
            CurrentPackageSystemdReloadLifecycleOperationV10.
            CLOSE_CURRENT_PACKAGE_SYSTEMD_RELOAD_ROLLBACK_REHEARSAL
        )
        current = self.authoritative_transaction
        if current is None or transaction != current.transaction:
            return CurrentPackageSystemdReloadRollbackResultV10(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail="rejected non-authoritative transaction identity",
            )
        if not all(
            (
                self._systemd_mutation_started,
                self._systemd_candidate_visible,
                self._systemd_manager_restored,
                self._managed_files_installed_once,
                self._filesystem_restored,
                self._exact_rollback_verified,
                self._services_restored,
                self._dashboard_verified,
            )
        ) or self._systemd_reload_count != 2:
            return CurrentPackageSystemdReloadRollbackResultV10(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=(
                    "installed-unit visibility, exact filesystem and manager "
                    "rollback, service restoration and exact verification must "
                    "complete before Stage C24 closure"
                ),
            )

        assert self.transaction_path is not None
        try:
            _atomic_text(
                self.transaction_path / "lifecycle-c24.tsv",
                "item\tvalue\n"
                "operation\tclose-current-package-systemd-reload-rollback-rehearsal\n"
                "managed_files_installed\ttrue\n"
                "installed_file_count\t28\n"
                "payload_file_count\t27\n"
                "systemd_reloaded\ttrue\n"
                "filesystem_restored\ttrue\n"
                "systemd_manager_restored\ttrue\n"
                "services_restored\ttrue\n"
                "daemon_reload_count\t2\n"
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
                return CurrentPackageSystemdReloadRollbackResultV10(
                    operation=operation,
                    status=AdapterStatus.FAIL,
                    detail=f"underlying exact cleanup failed: {base_result.detail}",
                )
            transaction_copy = self._restored_transaction_copy
            if transaction_copy is None or not transaction_copy.is_dir():
                raise SystemdReloadRollbackFailure(
                    "Stage C24 transaction audit copy is unavailable"
                )
            _atomic_text(
                transaction_copy / "state.tsv",
                "item\tvalue\n"
                "state\tcurrent-package-systemd-reload-rolled-back-and-closed\n"
                "mutation_started\ttrue\n"
                "managed_files_installed\ttrue\n"
                "installed_file_count\t28\n"
                "payload_file_count\t27\n"
                "systemd_reloaded\ttrue\n"
                "filesystem_restored\ttrue\n"
                "systemd_manager_restored\ttrue\n"
                "services_restored\ttrue\n"
                "daemon_reload_count\t2\n"
                "route_selected\tfalse\n"
                "committed\tfalse\n",
            )
            _atomic_text(
                transaction_copy / "lifecycle-c24.tsv",
                "item\tvalue\n"
                "operation\tclose-current-package-systemd-reload-rollback-rehearsal\n"
                "managed_files_installed\ttrue\n"
                "installed_file_count\t28\n"
                "payload_file_count\t27\n"
                "systemd_reloaded\ttrue\n"
                "filesystem_restored\ttrue\n"
                "systemd_manager_restored\ttrue\n"
                "services_restored\ttrue\n"
                "daemon_reload_count\t2\n"
                "committed\tfalse\n",
            )
            write_evidence_manifest(transaction_copy)
        except (
            OSError,
            SystemExit,
            ManagedFileRollbackFailure,
            ServiceQuiescenceFailure,
            SystemdReloadRollbackFailure,
        ) as exc:
            return CurrentPackageSystemdReloadRollbackResultV10(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=str(exc),
            )

        receipt = CurrentPackageSystemdReloadRollbackReceiptV10(
            transaction=transaction,
            state="current-package-systemd-reload-rolled-back-and-closed",
            mutation_started=True,
            managed_files_installed=True,
            systemd_reloaded=True,
            filesystem_restored=True,
            systemd_manager_restored=True,
            services_restored=True,
            committed=False,
            transaction_path_absent=True,
            parents_restored=base_result.payload.parents_restored,
            installed_file_count=CURRENT_PACKAGE_FILE_COUNT_V9,
            payload_file_count=CURRENT_PACKAGE_PAYLOAD_COUNT_V9,
            daemon_reload_count=self._systemd_reload_count,
            audit_evidence=str(self._evidence_root),
        )
        return CurrentPackageSystemdReloadRollbackResultV10(
            operation=operation,
            status=AdapterStatus.PASS,
            detail=(
                "current-package systemd-reload exact-rollback rehearsal closed "
                "and removed exactly"
            ),
            payload=receipt,
        )
