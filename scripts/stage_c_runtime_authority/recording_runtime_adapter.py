#!/usr/bin/python3
from __future__ import annotations

from dataclasses import dataclass, field

from .model import ActivationApprovalRecord, BootObservation, RuntimeAuthorityError
from .supervisor_model import PreparedRoute, SupervisorMode


@dataclass
class RecordingRuntimeHostAdapter:
    approval: ActivationApprovalRecord
    boot_observation: BootObservation
    prepared_route: PreparedRoute = PreparedRoute.SPLIT_PENDING
    child_start_succeeds: bool = True
    split_health_valid: bool = True
    fail_at: str | tuple[str, ...] | None = None
    operations: list[str] = field(default_factory=list)
    lock_held: bool = False
    lock_released: bool = False
    ready_notified: bool = False
    runtime_mode: SupervisorMode | None = None
    lease_id: str = "stage-c21-recording-lease"

    def _record(self, operation: str) -> None:
        self.operations.append(operation)
        failures = (self.fail_at,) if isinstance(self.fail_at, str) else self.fail_at or ()
        if operation in failures:
            raise RuntimeAuthorityError(f"injected failure at {operation}")

    def acquire_production_lock(self) -> str:
        self._record("acquire-production-lock")
        if self.lock_held:
            raise RuntimeAuthorityError("recording production lock already held")
        self.lock_held = True
        self.lock_released = False
        return self.lease_id

    def release_production_lock(self, lease_id: str) -> None:
        self._record("release-production-lock")
        if lease_id != self.lease_id or not self.lock_held:
            raise RuntimeAuthorityError("recording lock identity mismatch")
        self.lock_held = False
        self.lock_released = True

    def read_committed_approval(self) -> ActivationApprovalRecord:
        self._record("read-committed-approval")
        return self.approval

    def observe_boot_contract(self) -> BootObservation:
        self._record("observe-boot-contract")
        return self.boot_observation

    def select_split_bus_route(self) -> None:
        self._record("select-split-bus-route")
        self.prepared_route = PreparedRoute.SPLIT_PENDING

    def select_direct_failback_route(self) -> None:
        self._record("select-direct-failback-route")
        self.prepared_route = PreparedRoute.DIRECT_READY

    def publish_prepared_route(self, route: PreparedRoute, reason: str) -> None:
        self._record(f"publish-prepared-route:{route.value}")
        if not reason.strip() or route is not self.prepared_route:
            raise RuntimeAuthorityError("prepared route publication mismatch")

    def read_prepared_route(self) -> PreparedRoute:
        self._record("read-prepared-route")
        return self.prepared_route

    def start_camilladsp_child(self) -> bool:
        self._record("start-camilladsp-child")
        return self.child_start_succeeds

    def verify_split_bus_health(self) -> bool:
        self._record("verify-split-bus-health")
        return self.split_health_valid

    def stop_camilladsp_child(self) -> None:
        self._record("stop-camilladsp-child")

    def publish_runtime_mode(self, mode: SupervisorMode, reason: str) -> None:
        self._record(f"publish-runtime-mode:{mode.value}")
        if not reason.strip():
            raise RuntimeAuthorityError("runtime mode reason is empty")
        self.runtime_mode = mode
        if mode is SupervisorMode.DIRECT_FAILBACK:
            self.prepared_route = PreparedRoute.DIRECT_READY

    def notify_systemd_ready(self, mode: SupervisorMode, reason: str) -> None:
        self._record(f"notify-systemd-ready:{mode.value}")
        if self.lock_held:
            raise RuntimeAuthorityError("systemd readiness attempted while lock held")
        if not reason.strip():
            raise RuntimeAuthorityError("systemd readiness reason is empty")
        if mode is SupervisorMode.SPLIT_ACTIVE and self.runtime_mode is not SupervisorMode.SPLIT_ACTIVE:
            raise RuntimeAuthorityError("split readiness attempted before split-active publication")
        if mode is SupervisorMode.DIRECT_FAILBACK and self.prepared_route is not PreparedRoute.DIRECT_READY:
            raise RuntimeAuthorityError("direct readiness attempted before direct route completion")
        self.ready_notified = True
