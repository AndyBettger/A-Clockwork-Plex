#!/usr/bin/python3
from __future__ import annotations

"""Stage C19 systemd daemon-reload and exact manager rollback adapter."""

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from .authoritative_snapshot_rehearsal_adapter import _atomic_text
from .host_review import run as host_run
from .managed_file_rollback_rehearsal_adapter import (
    MANAGED_FILE_ROLLBACK_NAME,
    PERMITTED_V1_OPERATIONS as C18_PERMITTED_V1_OPERATIONS,
    ManagedFileRollbackFailure,
)
from .managed_file_rollback_rehearsal_adapter_v4 import (
    ManagedFileRollbackRehearsalAdapterV4,
)
from .package_review import EXPECTED_PACKAGE_FILES
from .production_adapter_contract import (
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    ServiceSnapshot,
    ServiceUnit,
    SnapshotIdentity,
    TransactionIdentity,
)
from .production_adapter_lifecycle_v4 import (
    ExactRollbackRehearsalAdapterResult,
    ExactRollbackRehearsalLifecycleOperation,
)
from .production_adapter_lifecycle_v5 import (
    ProductionAdapterV5,
    SystemdReloadRollbackAdapterResult,
    SystemdReloadRollbackLifecycleOperation,
    SystemdReloadRollbackTransactionReceipt,
)
from .read_only_host_adapter import STAGE_C_SERVICE_UNITS, _fail
from .service_quiescence_rehearsal_adapter import (
    ServiceQuiescenceFailure,
    ServiceQuiescenceRehearsalAdapter,
)
from .snapshot_core import write_evidence_manifest


SYSTEMD_RELOAD_ACTIONS_NAME = "systemd-reload-actions.tsv"
SYSTEMD_UNIT_OBSERVATIONS_NAME = "systemd-unit-observations.tsv"
SYSTEMD_PROPERTIES = (
    "LoadState",
    "ActiveState",
    "SubState",
    "UnitFileState",
    "FragmentPath",
)
EXPECTED_INSTALLED_UNIT_FILE_STATE = {
    ServiceUnit.ROUTE_AUTHORITY: "disabled",
    ServiceUnit.CAMILLADSP: "disabled",
    ServiceUnit.AUDIO_FAILBACK: "static",
}
EXPECTED_FRAGMENT_PATH = {
    unit: f"/etc/systemd/system/{unit.value}"
    for unit in STAGE_C_SERVICE_UNITS
}
PERMITTED_V1_OPERATIONS = (
    *C18_PERMITTED_V1_OPERATIONS[:18],
    AdapterOperation.RELOAD_SYSTEMD,
    *C18_PERMITTED_V1_OPERATIONS[18:],
)
PERMITTED_V5_COUNT = len(PERMITTED_V1_OPERATIONS) + 4
BLOCKED_V5_COUNT = 37 - PERMITTED_V5_COUNT

if PERMITTED_V5_COUNT != 27 or BLOCKED_V5_COUNT != 10:
    raise RuntimeError("Stage C19 operation partition changed unexpectedly")


class SystemdReloadRollbackFailure(RuntimeError):
    """The systemd manager mutation or exact rollback could not be proved."""


@dataclass(frozen=True)
class ManagedUnitObservation:
    phase: str
    unit: ServiceUnit
    load_state: str
    active_state: str
    sub_state: str
    unit_file_state: str
    fragment_path: str


class SystemdReloadRollbackRehearsalAdapter(
    ManagedFileRollbackRehearsalAdapterV4,
    ProductionAdapterV5,
):
    """C18 plus two bounded daemon reloads and exact manager-state rollback."""

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
                        "managed-files-rolled-back-manager-pending"
                    )
                if not self._systemd_manager_restored:
                    self._restore_systemd_manager_exact()
            except (
                OSError,
                ManagedFileRollbackFailure,
                SystemdReloadRollbackFailure,
            ) as rollback_exc:
                raise SystemdReloadRollbackFailure(
                    "mandatory Stage C19 filesystem and systemd-manager rollback "
                    "failed; the production lock and transaction are intentionally "
                    f"retained: {rollback_exc}"
                ) from exc
        super().__exit__(exc_type, exc, traceback)

    @property
    def systemd_reload_count(self) -> int:
        return self._systemd_reload_count

    @property
    def systemd_candidate_visible(self) -> bool:
        return self._systemd_candidate_visible

    @property
    def systemd_manager_restored(self) -> bool:
        return self._systemd_manager_restored

    def _record_systemd_action(
        self,
        phase: str,
        action: str,
        result: str,
        detail: str,
    ) -> None:
        self._systemd_action_order += 1
        clean = detail.replace("\t", " ").replace("\n", " ").strip()
        with self._systemd_reload_actions.open("a", encoding="utf-8") as output:
            output.write(
                f"{self._systemd_action_order}\t{time.monotonic_ns()}\t"
                f"{phase}\t{action}\t{result}\t{clean}\n"
            )

    @staticmethod
    def _parse_systemctl_show(raw: str) -> dict[str, str]:
        values: dict[str, str] = {}
        for line in raw.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key in values:
                raise SystemdReloadRollbackFailure(
                    f"duplicate systemd property: {key}"
                )
            values[key] = value.strip()
        if set(values) != set(SYSTEMD_PROPERTIES):
            raise SystemdReloadRollbackFailure(
                "systemd unit observation did not return the exact property set"
            )
        return values

    def _observe_managed_units(
        self,
        phase: str,
        *,
        installed: bool,
    ) -> tuple[ManagedUnitObservation, ...]:
        observations: list[ManagedUnitObservation] = []
        for unit in STAGE_C_SERVICE_UNITS:
            command = [
                "systemctl",
                "show",
                unit.value,
                *(f"--property={name}" for name in SYSTEMD_PROPERTIES),
                "--no-pager",
            ]
            result = host_run(command)
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip()
                raise SystemdReloadRollbackFailure(
                    f"systemctl show failed for {unit.value}: {detail}"
                )
            values = self._parse_systemctl_show(result.stdout)
            unit_file_state = values["UnitFileState"] or "not-found"
            observation = ManagedUnitObservation(
                phase=phase,
                unit=unit,
                load_state=values["LoadState"] or "not-found",
                active_state=values["ActiveState"] or "inactive",
                sub_state=values["SubState"] or "dead",
                unit_file_state=unit_file_state,
                fragment_path=values["FragmentPath"],
            )
            if installed:
                expected = (
                    "loaded",
                    "inactive",
                    "dead",
                    EXPECTED_INSTALLED_UNIT_FILE_STATE[unit],
                    EXPECTED_FRAGMENT_PATH[unit],
                )
            else:
                expected = (
                    "not-found",
                    "inactive",
                    "dead",
                    "not-found",
                    "",
                )
            observed = (
                observation.load_state,
                observation.active_state,
                observation.sub_state,
                observation.unit_file_state,
                observation.fragment_path,
            )
            if observed != expected:
                raise SystemdReloadRollbackFailure(
                    f"managed unit state mismatch during {phase}: "
                    f"{unit.value}: expected={expected!r} observed={observed!r}"
                )
            observations.append(observation)
            with self._systemd_unit_observations.open(
                "a", encoding="utf-8"
            ) as output:
                output.write(
                    f"{phase}\t{time.monotonic_ns()}\t{unit.value}\t"
                    f"{observation.load_state}\t{observation.active_state}\t"
                    f"{observation.sub_state}\t{observation.unit_file_state}\t"
                    f"{observation.fragment_path}\n"
                )
        return tuple(observations)

    def _run_daemon_reload(self, phase: str) -> None:
        result = host_run(["systemctl", "daemon-reload"])
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip() or str(result.returncode)
            self._record_systemd_action(
                phase,
                "daemon-reload",
                "FAIL",
                detail,
            )
            raise SystemdReloadRollbackFailure(
                f"systemctl daemon-reload failed during {phase}: {detail}"
            )
        self._systemd_reload_count += 1
        self._record_systemd_action(
            phase,
            "daemon-reload",
            "PASS",
            f"reload_count={self._systemd_reload_count}",
        )

    def _write_systemd_transaction_state(self, state: str) -> None:
        if self.transaction_path is None:
            raise SystemdReloadRollbackFailure(
                "authoritative transaction is unavailable for systemd state"
            )
        _atomic_text(
            self.transaction_path / "systemd-reload-rollback.tsv",
            "item\tvalue\n"
            f"state\t{state}\n"
            f"daemon_reload_count\t{self._systemd_reload_count}\n"
            f"candidate_visible\t{str(self._systemd_candidate_visible).lower()}\n"
            f"filesystem_restored\t{str(self._filesystem_restored).lower()}\n"
            f"systemd_manager_restored\t{str(self._systemd_manager_restored).lower()}\n"
            "route_selected\tfalse\n"
            "committed\tfalse\n",
        )
        _atomic_text(
            self.transaction_path / MANAGED_FILE_ROLLBACK_NAME,
            "item\tvalue\n"
            f"state\t{state}\n"
            f"installed_file_count\t{len(self._installed_files)}\n"
            f"removed_file_count\t{len(self._installed_files) if self._filesystem_restored else 0}\n"
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
        self._observe_managed_units(
            "rollback-files-absent",
            installed=False,
        )
        self._systemd_manager_restored = True
        self._write_systemd_transaction_state(
            "systemd-manager-restored"
        )

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
                    "candidate-files-installed",
                    installed=True,
                )
                self._systemd_candidate_visible = True
                self._write_systemd_transaction_state(
                    "systemd-candidate-visible"
                )
                detail = (
                    "systemd reloaded the installed candidate; all three managed "
                    "units are loaded and inactive"
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
                    "systemd reloaded after file rollback; all three managed units "
                    "are not-found"
                )
                phase = "rollback-files-absent"
            else:
                raise SystemdReloadRollbackFailure(
                    "Stage C19 permits exactly two daemon reloads"
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
                    "managed-files-rolled-back-manager-pending"
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
            not self._systemd_manager_restored
            or self._systemd_reload_count != 2
        ):
            return _fail(
                operation,
                "exact verification requires two reloads and restored manager state",
            )
        return super().verify_exact_rollback(transaction, snapshot)

    def close_exact_rollback_rehearsal_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> ExactRollbackRehearsalAdapterResult:
        if self._systemd_mutation_started:
            return ExactRollbackRehearsalAdapterResult(
                operation=(
                    ExactRollbackRehearsalLifecycleOperation.
                    CLOSE_EXACT_ROLLBACK_REHEARSAL_TRANSACTION
                ),
                status=AdapterStatus.FAIL,
                detail=(
                    "v4 file-only closure is unavailable after systemd-manager "
                    "mutation; use v5 systemd-reload rollback closure"
                ),
            )
        return super().close_exact_rollback_rehearsal_transaction(transaction)

    def close_systemd_reload_rollback_rehearsal_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> SystemdReloadRollbackAdapterResult:
        operation = (
            SystemdReloadRollbackLifecycleOperation.
            CLOSE_SYSTEMD_RELOAD_ROLLBACK_REHEARSAL_TRANSACTION
        )
        current = self.authoritative_transaction
        if current is None or transaction != current.transaction:
            return SystemdReloadRollbackAdapterResult(
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
            return SystemdReloadRollbackAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=(
                    "installed-unit visibility, exact filesystem and manager "
                    "rollback, service restoration and exact verification must "
                    "complete before v5 closure"
                ),
            )
        assert self.transaction_path is not None
        try:
            _atomic_text(
                self.transaction_path / "lifecycle-v5.tsv",
                "item\tvalue\n"
                "operation\tclose-systemd-reload-rollback-rehearsal-transaction\n"
                "managed_files_installed\ttrue\n"
                "systemd_reloaded\ttrue\n"
                "filesystem_restored\ttrue\n"
                "systemd_manager_restored\ttrue\n"
                "services_restored\ttrue\n"
                "daemon_reload_count\t2\n"
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
                return SystemdReloadRollbackAdapterResult(
                    operation=operation,
                    status=AdapterStatus.FAIL,
                    detail=f"underlying exact cleanup failed: {base_result.detail}",
                )
            transaction_copy = self._restored_transaction_copy
            if transaction_copy is None or not transaction_copy.is_dir():
                raise SystemdReloadRollbackFailure(
                    "v5 transaction audit copy is unavailable"
                )
            _atomic_text(
                transaction_copy / "state.tsv",
                "item\tvalue\n"
                "state\tsystemd-reload-rolled-back-and-closed\n"
                "mutation_started\ttrue\n"
                "managed_files_installed\ttrue\n"
                "systemd_reloaded\ttrue\n"
                "filesystem_restored\ttrue\n"
                "systemd_manager_restored\ttrue\n"
                "services_restored\ttrue\n"
                "daemon_reload_count\t2\n"
                "route_selected\tfalse\n"
                "committed\tfalse\n",
            )
            _atomic_text(
                transaction_copy / "lifecycle-v5.tsv",
                "item\tvalue\n"
                "operation\tclose-systemd-reload-rollback-rehearsal-transaction\n"
                "managed_files_installed\ttrue\n"
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
            return SystemdReloadRollbackAdapterResult(
                operation=operation,
                status=AdapterStatus.FAIL,
                detail=str(exc),
            )
        receipt = SystemdReloadRollbackTransactionReceipt(
            transaction=transaction,
            state="systemd-reload-rolled-back-and-closed",
            mutation_started=True,
            managed_files_installed=True,
            systemd_reloaded=True,
            filesystem_restored=True,
            systemd_manager_restored=True,
            services_restored=True,
            committed=False,
            transaction_path_absent=True,
            parents_restored=base_result.payload.parents_restored,
            installed_file_count=EXPECTED_PACKAGE_FILES,
            daemon_reload_count=self._systemd_reload_count,
            audit_evidence=str(self._evidence_root),
        )
        return SystemdReloadRollbackAdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail=(
                "systemd-reload exact-rollback rehearsal closed and removed exactly"
            ),
            payload=receipt,
        )
