#!/usr/bin/python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .model import ActivationApprovalRecord, RuntimeAuthorityError
from .supervisor_model import (
    PreparedRoute,
    SupervisorDecision,
    SupervisorMode,
    SupervisorStartupObservation,
    start_supervisor,
)


class InstallRuntimeExecutionError(RuntimeAuthorityError):
    """A temporary first-start failure that must return to transaction rollback."""


@runtime_checkable
class InstallRuntimeHostAdapter(Protocol):
    def read_temporary_approval(self) -> ActivationApprovalRecord: ...
    def assert_borrowed_transaction_lock(self) -> str: ...
    def release_borrowed_transaction_lock_assertion(self, lease_id: str) -> None: ...
    def validate_install_prepared_contract(self) -> ActivationApprovalRecord: ...
    def publish_install_prepared_route(self, reason: str) -> None: ...
    def read_install_prepared_route(self) -> PreparedRoute: ...
    def start_camilladsp_child(self) -> bool: ...
    def verify_split_bus_health(self) -> bool: ...
    def stop_camilladsp_child(self) -> None: ...
    def publish_install_split_active(self, reason: str) -> None: ...
    def notify_systemd_ready(self, mode: SupervisorMode, reason: str) -> None: ...


@dataclass(frozen=True)
class InstallRuntimeReceipt:
    phase: str
    lease_id: str
    prepared_route: PreparedRoute
    split_bus_healthy: bool
    borrowed_assertion_closed: bool
    systemd_ready: bool

    def __post_init__(self) -> None:
        if self.phase not in {"install-route-entry", "install-supervisor-startup"}:
            raise InstallRuntimeExecutionError(f"unsupported install runtime phase: {self.phase}")
        if not self.lease_id:
            raise InstallRuntimeExecutionError("install runtime receipt has no lease identity")
        if self.systemd_ready and not (
            self.split_bus_healthy and self.borrowed_assertion_closed
        ):
            raise InstallRuntimeExecutionError(
                "install readiness requires health and a closed borrowed-lock assertion"
            )


def _close_assertion_or_fail(adapter: InstallRuntimeHostAdapter, lease_id: str) -> None:
    try:
        adapter.release_borrowed_transaction_lock_assertion(lease_id)
    except BaseException as exc:
        raise InstallRuntimeExecutionError(
            "could not close the transaction-held lease assertion; readiness withheld"
        ) from exc


def run_install_route_entry(
    adapter: InstallRuntimeHostAdapter,
) -> InstallRuntimeReceipt:
    lease_id = adapter.assert_borrowed_transaction_lock()
    try:
        approval = adapter.validate_install_prepared_contract()
        if approval.lock_lease_id != lease_id:
            raise InstallRuntimeExecutionError("install route entry lease identity mismatch")
        adapter.publish_install_prepared_route(
            "transaction-selected split-bus route accepted for supervised first start"
        )
    except BaseException:
        _close_assertion_or_fail(adapter, lease_id)
        raise
    _close_assertion_or_fail(adapter, lease_id)
    return InstallRuntimeReceipt(
        phase="install-route-entry",
        lease_id=lease_id,
        prepared_route=PreparedRoute.SPLIT_PENDING,
        split_bus_healthy=False,
        borrowed_assertion_closed=True,
        systemd_ready=False,
    )


def run_install_supervisor_startup(
    adapter: InstallRuntimeHostAdapter,
) -> tuple[SupervisorDecision, InstallRuntimeReceipt]:
    lease_id = adapter.assert_borrowed_transaction_lock()
    child_started = False
    try:
        approval = adapter.validate_install_prepared_contract()
        if approval.lock_lease_id != lease_id:
            raise InstallRuntimeExecutionError("install supervisor lease identity mismatch")
        if adapter.read_install_prepared_route() is not PreparedRoute.SPLIT_PENDING:
            raise InstallRuntimeExecutionError("install route entry did not prepare split-bus")
        child_started = adapter.start_camilladsp_child()
        if not child_started:
            raise InstallRuntimeExecutionError("CamillaDSP child did not remain running")
        if not adapter.verify_split_bus_health():
            raise InstallRuntimeExecutionError("strict split-bus first-start health failed")
        decision = start_supervisor(
            SupervisorStartupObservation(
                prepared_route=PreparedRoute.SPLIT_PENDING,
                production_lock_held=True,
                camilladsp_child_started=True,
                split_bus_health_valid=True,
            )
        )
        if decision.mode is not SupervisorMode.SPLIT_ACTIVE:
            raise InstallRuntimeExecutionError("healthy install supervisor did not select split-bus")
        adapter.publish_install_split_active(decision.reason)
        _close_assertion_or_fail(adapter, lease_id)
        adapter.notify_systemd_ready(decision.mode, decision.reason)
    except BaseException as exc:
        try:
            adapter.stop_camilladsp_child()
        except BaseException as stop_exc:
            raise InstallRuntimeExecutionError(
                "first-start failure and CamillaDSP stop both failed; readiness withheld"
            ) from stop_exc
        try:
            _close_assertion_or_fail(adapter, lease_id)
        except InstallRuntimeExecutionError as close_exc:
            raise InstallRuntimeExecutionError(
                "first-start failure left the borrowed lease assertion unresolved; transaction rollback required"
            ) from close_exc
        if isinstance(exc, InstallRuntimeExecutionError):
            raise
        raise InstallRuntimeExecutionError(
            "first-start exception; readiness withheld and transaction rollback required"
        ) from exc
    return decision, InstallRuntimeReceipt(
        phase="install-supervisor-startup",
        lease_id=lease_id,
        prepared_route=PreparedRoute.SPLIT_PENDING,
        split_bus_healthy=True,
        borrowed_assertion_closed=True,
        systemd_ready=True,
    )
