#!/usr/bin/python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .model import ActivationApprovalRecord, BootObservation, RuntimeAuthorityError
from .supervisor_model import (
    BootPreparationDecision,
    PreparedRoute,
    SupervisorAction,
    SupervisorDecision,
    SupervisorMode,
    SupervisorStartupObservation,
    child_failure_failback,
    prepare_boot,
    start_supervisor,
)


class RuntimeExecutionError(RuntimeAuthorityError):
    """A fail-closed error while applying one fixed runtime decision."""


@runtime_checkable
class RuntimeHostAdapter(Protocol):
    def acquire_production_lock(self) -> str: ...
    def release_production_lock(self, lease_id: str) -> None: ...
    def read_committed_approval(self) -> ActivationApprovalRecord: ...
    def observe_boot_contract(self) -> BootObservation: ...
    def select_split_bus_route(self) -> None: ...
    def select_direct_failback_route(self) -> None: ...
    def publish_prepared_route(self, route: PreparedRoute, reason: str) -> None: ...
    def read_prepared_route(self) -> PreparedRoute: ...
    def start_camilladsp_child(self) -> bool: ...
    def verify_split_bus_health(self) -> bool: ...
    def stop_camilladsp_child(self) -> None: ...
    def publish_runtime_mode(self, mode: SupervisorMode, reason: str) -> None: ...
    def notify_systemd_ready(self, mode: SupervisorMode, reason: str) -> None: ...


@dataclass(frozen=True)
class RuntimeExecutionReceipt:
    phase: str
    mode: str
    reason: str
    lease_id: str
    lock_released: bool
    systemd_ready: bool

    def __post_init__(self) -> None:
        if self.phase not in {"boot-preparation", "supervisor-startup", "runtime-child-failure"}:
            raise RuntimeExecutionError(f"unsupported execution phase: {self.phase}")
        if not self.mode or not self.reason or not self.lease_id:
            raise RuntimeExecutionError("runtime execution receipt is incomplete")
        if self.systemd_ready and not self.lock_released:
            raise RuntimeExecutionError("systemd readiness cannot be published while the production lock is retained")


def _complete_direct_failback(
    adapter: RuntimeHostAdapter,
    *,
    reason: str,
    stop_child: bool,
) -> None:
    if stop_child:
        adapter.stop_camilladsp_child()
    adapter.select_direct_failback_route()
    adapter.publish_runtime_mode(SupervisorMode.DIRECT_FAILBACK, reason)


def run_boot_preparation(adapter: RuntimeHostAdapter) -> tuple[BootPreparationDecision, RuntimeExecutionReceipt]:
    lease_id = adapter.acquire_production_lock()
    route_mutation_started = False
    try:
        approval = adapter.read_committed_approval()
        observation = adapter.observe_boot_contract()
        decision = prepare_boot(approval, observation)
        route_mutation_started = True
        if decision.prepared_route is PreparedRoute.SPLIT_PENDING:
            adapter.select_split_bus_route()
        else:
            adapter.select_direct_failback_route()
        adapter.publish_prepared_route(decision.prepared_route, decision.reason)
    except BaseException:
        if route_mutation_started:
            fallback_reason = "boot preparation exception forced direct failback"
            try:
                _complete_direct_failback(
                    adapter,
                    reason=fallback_reason,
                    stop_child=False,
                )
            except BaseException as failback_exc:
                raise RuntimeExecutionError(
                    "boot preparation and mandatory direct failback failed; production lock retained"
                ) from failback_exc
            adapter.release_production_lock(lease_id)
            fallback = BootPreparationDecision(
                prepared_route=PreparedRoute.DIRECT_READY,
                reason=fallback_reason,
                actions=(
                    SupervisorAction.ACQUIRE_PRODUCTION_LOCK,
                    SupervisorAction.VALIDATE_COMMITTED_STATE,
                    SupervisorAction.SELECT_DIRECT_FAILBACK_ROUTE,
                    SupervisorAction.PUBLISH_DIRECT_FAILBACK,
                    SupervisorAction.RELEASE_PRODUCTION_LOCK,
                ),
            )
            return fallback, RuntimeExecutionReceipt(
                phase="boot-preparation",
                mode=PreparedRoute.DIRECT_READY.value,
                reason=fallback_reason,
                lease_id=lease_id,
                lock_released=True,
                systemd_ready=False,
            )
        adapter.release_production_lock(lease_id)
        raise
    adapter.release_production_lock(lease_id)
    return decision, RuntimeExecutionReceipt(
        phase="boot-preparation",
        mode=decision.prepared_route.value,
        reason=decision.reason,
        lease_id=lease_id,
        lock_released=True,
        systemd_ready=False,
    )


def run_supervisor_startup(adapter: RuntimeHostAdapter) -> tuple[SupervisorDecision, RuntimeExecutionReceipt]:
    lease_id = adapter.acquire_production_lock()
    ready = False
    try:
        prepared = adapter.read_prepared_route()
        child_started = False
        health_valid = False
        if prepared is PreparedRoute.SPLIT_PENDING:
            child_started = adapter.start_camilladsp_child()
            if child_started:
                health_valid = adapter.verify_split_bus_health()
        decision = start_supervisor(
            SupervisorStartupObservation(
                prepared_route=prepared,
                production_lock_held=True,
                camilladsp_child_started=child_started,
                split_bus_health_valid=health_valid,
            )
        )
        if decision.mode is SupervisorMode.SPLIT_ACTIVE:
            adapter.publish_runtime_mode(decision.mode, decision.reason)
        elif prepared is PreparedRoute.SPLIT_PENDING:
            _complete_direct_failback(
                adapter,
                reason=decision.reason,
                stop_child=True,
            )
        else:
            # Boot preparation already published the completed direct route.
            pass
        adapter.release_production_lock(lease_id)
        adapter.notify_systemd_ready(decision.mode, decision.reason)
        ready = True
    except BaseException:
        if not ready:
            try:
                fallback_reason = "supervisor startup exception forced direct failback"
                _complete_direct_failback(
                    adapter,
                    reason=fallback_reason,
                    stop_child=True,
                )
                adapter.release_production_lock(lease_id)
                adapter.notify_systemd_ready(
                    SupervisorMode.DIRECT_FAILBACK,
                    fallback_reason,
                )
                decision = start_supervisor(
                    SupervisorStartupObservation(
                        prepared_route=PreparedRoute.DIRECT_READY,
                        production_lock_held=True,
                        camilladsp_child_started=False,
                        split_bus_health_valid=False,
                    )
                )
                return decision, RuntimeExecutionReceipt(
                    phase="supervisor-startup",
                    mode=SupervisorMode.DIRECT_FAILBACK.value,
                    reason=fallback_reason,
                    lease_id=lease_id,
                    lock_released=True,
                    systemd_ready=True,
                )
            except BaseException as failback_exc:
                raise RuntimeExecutionError(
                    "supervisor startup and mandatory direct failback failed; readiness withheld and lock retained"
                ) from failback_exc
        raise
    return decision, RuntimeExecutionReceipt(
        phase="supervisor-startup",
        mode=decision.mode.value,
        reason=decision.reason,
        lease_id=lease_id,
        lock_released=True,
        systemd_ready=True,
    )


def run_runtime_child_failure(adapter: RuntimeHostAdapter) -> tuple[SupervisorDecision, RuntimeExecutionReceipt]:
    lease_id = adapter.acquire_production_lock()
    try:
        decision = child_failure_failback(production_lock_held=True)
        _complete_direct_failback(adapter, reason=decision.reason, stop_child=True)
        adapter.release_production_lock(lease_id)
    except BaseException as exc:
        raise RuntimeExecutionError(
            "runtime child failure could not complete direct failback; production lock retained"
        ) from exc
    return decision, RuntimeExecutionReceipt(
        phase="runtime-child-failure",
        mode=decision.mode.value,
        reason=decision.reason,
        lease_id=lease_id,
        lock_released=True,
        systemd_ready=True,
    )
