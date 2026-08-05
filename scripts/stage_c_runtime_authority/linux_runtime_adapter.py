#!/usr/bin/python3
from __future__ import annotations

from pathlib import Path
from typing import Callable

from .linux_runtime_filesystem import LinuxRuntimeFilesystem
from .linux_runtime_process import ChildProcess, LinuxRuntimeProcess
from .model import ActivationApprovalRecord, BootObservation
from .runtime_executor import RuntimeHostAdapter
from .supervisor_model import PreparedRoute, SupervisorMode


class LinuxRuntimeHostAdapter:
    """One fixed ordinary-boot/runtime adapter composed from the two reviewed Linux boundaries."""

    def __init__(self) -> None:
        self._filesystem = LinuxRuntimeFilesystem()
        self._process = LinuxRuntimeProcess()

    @classmethod
    def _for_test(
        cls,
        root: Path,
        *,
        process_factory: Callable[..., ChildProcess],
        notifier: object,
        monotonic: Callable[[], float],
        sleep: Callable[[float], None],
    ) -> "LinuxRuntimeHostAdapter":
        instance = cls.__new__(cls)
        instance._filesystem = LinuxRuntimeFilesystem._for_test(root)
        instance._process = LinuxRuntimeProcess._for_test(
            root,
            process_factory=process_factory,
            notifier=notifier,
            monotonic=monotonic,
            sleep=sleep,
        )
        return instance

    def acquire_production_lock(self) -> str:
        return self._filesystem.acquire_production_lock()

    def release_production_lock(self, lease_id: str) -> None:
        self._filesystem.release_production_lock(lease_id)

    def read_committed_approval(self) -> ActivationApprovalRecord:
        return self._filesystem.read_committed_approval()

    def observe_boot_contract(self) -> BootObservation:
        return self._filesystem.observe_boot_contract()

    def select_split_bus_route(self) -> None:
        self._filesystem.select_split_bus_route()

    def select_direct_failback_route(self) -> None:
        self._filesystem.select_direct_failback_route()

    def publish_prepared_route(self, route: PreparedRoute, reason: str) -> None:
        self._filesystem.publish_prepared_route(route, reason)

    def read_prepared_route(self) -> PreparedRoute:
        return self._filesystem.read_prepared_route()

    def start_camilladsp_child(self) -> bool:
        return self._process.start_camilladsp_child()

    def verify_split_bus_health(self) -> bool:
        return self._process.verify_split_bus_health()

    def stop_camilladsp_child(self) -> None:
        self._process.stop_camilladsp_child()

    def publish_runtime_mode(self, mode: SupervisorMode, reason: str) -> None:
        self._filesystem.publish_runtime_mode(mode, reason)

    def notify_systemd_ready(self, mode: SupervisorMode, reason: str) -> None:
        self._process.notify_systemd_ready(mode, reason)

    def wait_for_child_exit(self) -> int | None:
        return self._process.wait_for_child_exit()

    @property
    def child_running(self) -> bool:
        return self._process.child_running


assert isinstance(LinuxRuntimeHostAdapter(), RuntimeHostAdapter)
