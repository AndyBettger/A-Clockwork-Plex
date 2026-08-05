#!/usr/bin/python3
from __future__ import annotations

from pathlib import Path
from typing import Callable

from .install_runtime_executor import InstallRuntimeHostAdapter
from .install_runtime_filesystem import InstallRuntimeFilesystem
from .install_runtime_process import InstallRuntimeProcess
from .linux_runtime_process import ChildProcess
from .model import ActivationApprovalRecord
from .supervisor_model import PreparedRoute, SupervisorMode


class InstallLinuxRuntimeHostAdapter:
    """Temporary first-start composition under the authoritative transaction's held lease."""

    def __init__(self) -> None:
        self._filesystem = InstallRuntimeFilesystem()
        self._process = InstallRuntimeProcess()

    @classmethod
    def _for_test(
        cls,
        root: Path,
        *,
        process_factory: Callable[..., ChildProcess],
        notifier: object,
        monotonic: Callable[[], float],
        sleep: Callable[[float], None],
    ) -> "InstallLinuxRuntimeHostAdapter":
        instance = cls.__new__(cls)
        instance._filesystem = InstallRuntimeFilesystem._for_test(root)
        instance._process = InstallRuntimeProcess._for_test(
            root,
            process_factory=process_factory,
            notifier=notifier,
            monotonic=monotonic,
            sleep=sleep,
        )
        return instance

    def read_temporary_approval(self) -> ActivationApprovalRecord:
        return self._filesystem.read_temporary_approval()

    def assert_borrowed_transaction_lock(self) -> str:
        return self._filesystem.assert_borrowed_transaction_lock()

    def release_borrowed_transaction_lock_assertion(self, lease_id: str) -> None:
        self._filesystem.release_borrowed_transaction_lock_assertion(lease_id)

    def validate_install_prepared_contract(self) -> ActivationApprovalRecord:
        return self._filesystem.validate_install_prepared_contract()

    def publish_install_prepared_route(self, reason: str) -> None:
        self._filesystem.publish_install_prepared_route(reason)

    def read_install_prepared_route(self) -> PreparedRoute:
        return self._filesystem.read_install_prepared_route()

    def start_camilladsp_child(self) -> bool:
        return self._process.start_camilladsp_child()

    def verify_split_bus_health(self) -> bool:
        return self._process.verify_split_bus_health()

    def stop_camilladsp_child(self) -> None:
        self._process.stop_camilladsp_child()

    def publish_install_split_active(self, reason: str) -> None:
        self._filesystem.publish_install_split_active(reason)

    def notify_systemd_ready(self, mode: SupervisorMode, reason: str) -> None:
        self._process.notify_systemd_ready(mode, reason)

    def wait_for_child_exit(self) -> int | None:
        return self._process.wait_for_child_exit()

    @property
    def child_running(self) -> bool:
        return self._process.child_running


assert isinstance(InstallLinuxRuntimeHostAdapter(), InstallRuntimeHostAdapter)
