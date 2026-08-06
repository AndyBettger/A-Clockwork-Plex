#!/usr/bin/python3
from __future__ import annotations

"""Bounded-attempt hardening for the Stage C24 systemd rollback adapter.

The v10 adapter already constrains successful completion to exactly two daemon
reloads. This final C24 layer also constrains *attempted* daemon reloads to two,
including failed commands or failed post-reload unit observations. A cleanup
path therefore cannot issue an unapproved third daemon-reload; instead the
canonical production lock and authoritative transaction remain retained for
inspection.
"""

from .current_package_systemd_reload_rollback_adapter_v10 import (
    CurrentPackageSystemdReloadRollbackAdapterV10,
)
from .systemd_reload_rollback_rehearsal_adapter import (
    SystemdReloadRollbackFailure,
    SystemdReloadRollbackRehearsalAdapter,
)


MAX_DAEMON_RELOAD_ATTEMPTS_V11 = 2


class CurrentPackageSystemdReloadRollbackAdapterV11(
    CurrentPackageSystemdReloadRollbackAdapterV10
):
    """C24 adapter with a hard two-attempt daemon-reload budget."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._systemd_reload_attempt_count = 0

    @property
    def systemd_reload_attempt_count(self) -> int:
        return self._systemd_reload_attempt_count

    def _run_daemon_reload(self, phase: str) -> None:
        if self._systemd_reload_attempt_count >= MAX_DAEMON_RELOAD_ATTEMPTS_V11:
            raise SystemdReloadRollbackFailure(
                "Stage C24 daemon-reload attempt budget is exhausted; refusing "
                "an unapproved third daemon-reload and retaining authority state"
            )
        self._systemd_reload_attempt_count += 1
        SystemdReloadRollbackRehearsalAdapter._run_daemon_reload(self, phase)
