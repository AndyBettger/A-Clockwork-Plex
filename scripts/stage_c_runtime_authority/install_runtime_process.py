#!/usr/bin/python3
from __future__ import annotations

from pathlib import Path
from typing import Callable

from .approval_store import ApprovalStore
from .linux_runtime_process import ChildProcess, LinuxRuntimeProcess
from .model import ActivationApprovalRecord, ApprovalPhase, RuntimeAuthorityError


class InstallRuntimeProcess(LinuxRuntimeProcess):
    """CamillaDSP process boundary for a temporary transaction-bound first start."""

    @classmethod
    def _for_test(
        cls,
        root: Path,
        *,
        process_factory: Callable[..., ChildProcess],
        notifier: object,
        monotonic: Callable[[], float],
        sleep: Callable[[float], None],
    ) -> "InstallRuntimeProcess":
        instance = super()._for_test(
            root,
            process_factory=process_factory,
            notifier=notifier,
            monotonic=monotonic,
            sleep=sleep,
        )
        instance.__class__ = cls
        return instance

    def _approval(self) -> ActivationApprovalRecord:
        record = ApprovalStore(self._paths.state_root).read()
        if record.phase is not ApprovalPhase.TEMPORARY:
            raise RuntimeAuthorityError(
                "install CamillaDSP process authority requires a temporary transaction-bound approval"
            )
        return record
