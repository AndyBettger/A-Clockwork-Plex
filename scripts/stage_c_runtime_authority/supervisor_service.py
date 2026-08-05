#!/usr/bin/python3
from __future__ import annotations

import signal
import threading
from dataclasses import dataclass
from typing import Callable, Protocol

from .model import ActivationApprovalRecord, ApprovalPhase, RuntimeAuthorityError
from .runtime_executor import run_runtime_child_failure
from .supervisor_model import SupervisorMode


SUPERVISOR_POLL_SECONDS = 0.25


class SupervisorAdapter(Protocol):
    @property
    def child_running(self) -> bool: ...
    def stop_camilladsp_child(self) -> None: ...


class StopEvent(Protocol):
    def wait(self, timeout: float) -> bool: ...
    def set(self) -> None: ...


@dataclass(frozen=True)
class SupervisorServiceOutcome:
    exit_code: int
    final_mode: SupervisorMode
    reason: str
    child_stopped: bool

    def __post_init__(self) -> None:
        if self.exit_code not in {0, 1}:
            raise RuntimeAuthorityError("supervisor service outcome has an unsupported exit code")
        if not self.reason.strip():
            raise RuntimeAuthorityError("supervisor service outcome reason is empty")


def supervise_lifetime(
    startup_adapter: SupervisorAdapter,
    startup_mode: SupervisorMode,
    *,
    approval_reader: Callable[[], ActivationApprovalRecord],
    ordinary_adapter_factory: Callable[[], object],
    stop_event: StopEvent,
) -> SupervisorServiceOutcome:
    mode = startup_mode
    while True:
        if stop_event.wait(SUPERVISOR_POLL_SECONDS):
            startup_adapter.stop_camilladsp_child()
            return SupervisorServiceOutcome(
                exit_code=0,
                final_mode=mode,
                reason="systemd stop requested; supervised child stopped",
                child_stopped=True,
            )
        if mode is not SupervisorMode.SPLIT_ACTIVE or startup_adapter.child_running:
            continue
        approval = approval_reader()
        if approval.phase is ApprovalPhase.TEMPORARY:
            startup_adapter.stop_camilladsp_child()
            return SupervisorServiceOutcome(
                exit_code=1,
                final_mode=SupervisorMode.SPLIT_ACTIVE,
                reason="pre-commit CamillaDSP child exited; exact install transaction rollback required",
                child_stopped=True,
            )
        ordinary = ordinary_adapter_factory()
        decision, receipt = run_runtime_child_failure(ordinary)
        if (
            decision.mode is not SupervisorMode.DIRECT_FAILBACK
            or receipt.mode != SupervisorMode.DIRECT_FAILBACK.value
            or not receipt.lock_released
        ):
            raise RuntimeAuthorityError("committed child failure did not complete exact direct failback")
        mode = SupervisorMode.DIRECT_FAILBACK


def production_stop_event() -> threading.Event:
    event = threading.Event()

    def request_stop(signum: int, frame: object) -> None:
        del signum, frame
        event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    return event
