#!/usr/bin/python3
from __future__ import annotations

"""Explicit Stage C21 v7 adapter composition boundary.

This module combines one supplied v1-v6 ordinary transaction adapter with one
supplied v7 approval-lifecycle adapter. It adds no host implementation,
filesystem access, process execution, service helper, CLI or generic dispatch
boundary of its own.

Every method delegates explicitly to exactly one supplied authority. Ordinary
v1-v6 operations always use ``ordinary``; the four Stage C21 approval/lease
operations always use ``approval``.
"""

from dataclasses import dataclass

from .production_adapter_contract import (
    AdapterResult,
    AuthoritativeTransaction,
    DacSnapshot,
    FilesystemSnapshot,
    HostContractSnapshot,
    LoopbackSnapshot,
    MixerSnapshot,
    PackageFingerprint,
    ProductionLockLease,
    ProductionLockObservation,
    ServiceSnapshot,
    SnapshotIdentity,
    TransactionAction,
    TransactionIdentity,
)
from .production_adapter_lifecycle_v2 import LifecycleAdapterResult
from .production_adapter_lifecycle_v3 import RestoredRehearsalAdapterResult
from .production_adapter_lifecycle_v4 import ExactRollbackRehearsalAdapterResult
from .production_adapter_lifecycle_v5 import SystemdReloadRollbackAdapterResult
from .production_adapter_lifecycle_v6 import (
    ProductionAdapterV6,
    RouteSelectionRollbackAdapterResult,
)
from .production_adapter_lifecycle_v7 import (
    ActivationApprovalAdapterResult,
    ProductionAdapterV7,
)


@dataclass(frozen=True)
class CompositeProductionAdapterV7:
    """One explicit v7 view over separate ordinary and approval authorities."""

    ordinary: ProductionAdapterV6
    approval: ProductionAdapterV7

    def __post_init__(self) -> None:
        if not isinstance(self.ordinary, ProductionAdapterV6):
            raise TypeError("ordinary delegate must satisfy ProductionAdapterV6")
        if not isinstance(self.approval, ProductionAdapterV7):
            raise TypeError("approval delegate must satisfy ProductionAdapterV7")

    def inspect_host_contract(self) -> AdapterResult[HostContractSnapshot]:
        return self.ordinary.inspect_host_contract()

    def inspect_production_lock(self) -> AdapterResult[ProductionLockObservation]:
        return self.ordinary.inspect_production_lock()

    def acquire_production_lock(self) -> AdapterResult[ProductionLockLease]:
        return self.ordinary.acquire_production_lock()

    def release_production_lock(self) -> AdapterResult[None]:
        return self.ordinary.release_production_lock()

    def create_authoritative_transaction(
        self,
        action: TransactionAction,
        package: PackageFingerprint,
    ) -> AdapterResult[AuthoritativeTransaction]:
        return self.ordinary.create_authoritative_transaction(action, package)

    def capture_filesystem_state(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[FilesystemSnapshot]:
        return self.ordinary.capture_filesystem_state(transaction)

    def capture_service_state(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[ServiceSnapshot]:
        return self.ordinary.capture_service_state(transaction)

    def capture_mixer_state(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[MixerSnapshot]:
        return self.ordinary.capture_mixer_state(transaction)

    def capture_loopback_state(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[LoopbackSnapshot]:
        return self.ordinary.capture_loopback_state(transaction)

    def capture_dac_state(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[DacSnapshot]:
        return self.ordinary.capture_dac_state(transaction)

    def stage_candidate_files(
        self,
        transaction: TransactionIdentity,
        package: PackageFingerprint,
    ) -> AdapterResult[None]:
        return self.ordinary.stage_candidate_files(transaction, package)

    def validate_candidate_alsa(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self.ordinary.validate_candidate_alsa(transaction)

    def validate_candidate_sudoers(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self.ordinary.validate_candidate_sudoers(transaction)

    def validate_candidate_units(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self.ordinary.validate_candidate_units(transaction)

    def validate_candidate_camilladsp(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self.ordinary.validate_candidate_camilladsp(transaction)

    def stop_captured_application_services(
        self,
        transaction: TransactionIdentity,
        services: ServiceSnapshot,
    ) -> AdapterResult[None]:
        return self.ordinary.stop_captured_application_services(
            transaction,
            services,
        )

    def verify_dac_released(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self.ordinary.verify_dac_released(transaction)

    def install_managed_files(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self.ordinary.install_managed_files(transaction)

    def reload_systemd(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self.ordinary.reload_systemd(transaction)

    def select_split_bus_route(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self.ordinary.select_split_bus_route(transaction)

    def start_managed_stage_c_services(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self.ordinary.start_managed_stage_c_services(transaction)

    def stop_managed_stage_c_services(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self.ordinary.stop_managed_stage_c_services(transaction)

    def verify_split_bus_health(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self.ordinary.verify_split_bus_health(transaction)

    def run_finite_music_probe(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self.ordinary.run_finite_music_probe(transaction)

    def run_finite_alarm_probe(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self.ordinary.run_finite_alarm_probe(transaction)

    def restore_captured_application_services(
        self,
        transaction: TransactionIdentity,
        services: ServiceSnapshot,
    ) -> AdapterResult[None]:
        return self.ordinary.restore_captured_application_services(
            transaction,
            services,
        )

    def verify_dashboard_health(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self.ordinary.verify_dashboard_health(transaction)

    def write_commit_manifest(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self.ordinary.write_commit_manifest(transaction)

    def select_direct_failback_route(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        return self.ordinary.select_direct_failback_route(transaction)

    def restore_exact_snapshot(
        self,
        transaction: TransactionIdentity,
        snapshot: SnapshotIdentity,
    ) -> AdapterResult[None]:
        return self.ordinary.restore_exact_snapshot(transaction, snapshot)

    def restore_mixer_state(
        self,
        transaction: TransactionIdentity,
        mixer: MixerSnapshot,
    ) -> AdapterResult[None]:
        return self.ordinary.restore_mixer_state(transaction, mixer)

    def restore_service_state(
        self,
        transaction: TransactionIdentity,
        services: ServiceSnapshot,
    ) -> AdapterResult[None]:
        return self.ordinary.restore_service_state(transaction, services)

    def verify_exact_rollback(
        self,
        transaction: TransactionIdentity,
        snapshot: SnapshotIdentity,
    ) -> AdapterResult[None]:
        return self.ordinary.verify_exact_rollback(transaction, snapshot)

    def abort_uncommitted_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> LifecycleAdapterResult:
        return self.ordinary.abort_uncommitted_transaction(transaction)

    def close_restored_rehearsal_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> RestoredRehearsalAdapterResult:
        return self.ordinary.close_restored_rehearsal_transaction(transaction)

    def close_exact_rollback_rehearsal_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> ExactRollbackRehearsalAdapterResult:
        return self.ordinary.close_exact_rollback_rehearsal_transaction(transaction)

    def close_systemd_reload_rollback_rehearsal_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> SystemdReloadRollbackAdapterResult:
        return self.ordinary.close_systemd_reload_rollback_rehearsal_transaction(
            transaction
        )

    def close_route_selection_rollback_rehearsal_transaction(
        self,
        transaction: TransactionIdentity,
    ) -> RouteSelectionRollbackAdapterResult:
        return self.ordinary.close_route_selection_rollback_rehearsal_transaction(
            transaction
        )

    def bind_production_lock_lease(
        self,
        transaction: TransactionIdentity,
    ) -> ActivationApprovalAdapterResult:
        return self.approval.bind_production_lock_lease(transaction)

    def publish_temporary_activation_approval(
        self,
        transaction: TransactionIdentity,
    ) -> ActivationApprovalAdapterResult:
        return self.approval.publish_temporary_activation_approval(transaction)

    def remove_temporary_activation_approval(
        self,
        transaction: TransactionIdentity,
    ) -> ActivationApprovalAdapterResult:
        return self.approval.remove_temporary_activation_approval(transaction)

    def promote_committed_activation_approval(
        self,
        transaction: TransactionIdentity,
    ) -> ActivationApprovalAdapterResult:
        return self.approval.promote_committed_activation_approval(transaction)
