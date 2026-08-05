#!/usr/bin/python3
from __future__ import annotations

"""Stage C20 atomic-exchange reconciliation correction.

The accepted C20 operation boundary and orchestration remain unchanged. This
narrow adapter override makes active-route rollback derive the exchange phase
from the two exact device/inode identities on disk rather than trusting the
in-memory Boolean written immediately after ``renameat2(RENAME_EXCHANGE)``.

That closes both interruption windows:

- the first exchange completed but Python had not yet recorded completion;
- the reverse exchange completed but Python had not yet cleared completion.
"""

import os
from pathlib import Path

from .managed_file_rollback_rehearsal_adapter import _safe_destination
from .route_selection_rollback_rehearsal_adapter import (
    RouteIdentity,
    RouteSelectionRollbackFailure,
    RouteSelectionRollbackRehearsalAdapter,
    _identity,
    _rename_exchange,
    _require_identity,
)
from .snapshot_core import CURRENT_ALSA_DESTINATION


def _optional_identity(path: Path) -> RouteIdentity | None:
    try:
        return _identity(path)
    except FileNotFoundError:
        return None


class RouteSelectionRollbackRehearsalAdapterV2(
    RouteSelectionRollbackRehearsalAdapter
):
    """Infer the real exchange state from exact on-disk identities."""

    def _restore_active_route_exact(self) -> None:
        rollback_name = self._route_rollback_name
        original = self._route_original
        candidate = self._route_candidate
        if rollback_name is None or original is None:
            raise RouteSelectionRollbackFailure(
                "active-route rollback ledger is incomplete"
            )

        active = _safe_destination(CURRENT_ALSA_DESTINATION)
        rollback_path = active.parent / rollback_name
        active_identity = _identity(active)
        rollback_identity = _optional_identity(rollback_path)

        if candidate is None:
            if active_identity == original and rollback_identity is None:
                self._route_exchange_completed = False
                self._route_selected = False
                self._route_rollback_name = None
                return
            raise RouteSelectionRollbackFailure(
                "active-route candidate identity was not adopted before an "
                "on-disk private route object appeared"
            )

        selected_arrangement = (
            active_identity == candidate and rollback_identity == original
        )
        original_arrangement = (
            active_identity == original and rollback_identity == candidate
        )
        if not selected_arrangement and not original_arrangement:
            raise RouteSelectionRollbackFailure(
                "active-route exchange arrangement does not match either exact "
                "transaction-owned inode layout"
            )

        parent_fd, _parent = self._open_parent(active)
        try:
            if selected_arrangement:
                if self._route_selection_count not in (0, 1):
                    raise RouteSelectionRollbackFailure(
                        "route-selection count changed before reconciliation"
                    )
                self._route_selected_once = True
                self._route_selection_count = 1
                _rename_exchange(parent_fd, active.name, rollback_name)
                os.fsync(parent_fd)

            _require_identity(active, original, "restored active route")
            _require_identity(
                rollback_path,
                candidate,
                "parked candidate route",
            )
            self._unlink_partial_candidate(
                parent_fd,
                rollback_name,
                candidate.device,
                candidate.inode,
            )
        finally:
            os.close(parent_fd)

        if rollback_path.exists() or rollback_path.is_symlink():
            raise RouteSelectionRollbackFailure(
                "private route rollback pathname remains after cleanup"
            )

        self._route_exchange_completed = False
        self._route_selected = False
        if self._route_selected_once:
            self._route_restored = True
            self._record_route_action(
                "restore-active-route",
                "PASS",
                (
                    f"original_inode={original.inode} "
                    f"original_sha256={original.digest} "
                    f"removed_candidate_inode={candidate.inode} "
                    f"reconciled_from={'selected' if selected_arrangement else 'restored'}"
                ),
            )
        else:
            self._record_route_action(
                "remove-unselected-route-candidate",
                "PASS",
                f"removed_candidate_inode={candidate.inode}",
            )
        self._route_rollback_name = None
        if self._route_selected_once:
            self._write_route_transaction_state(
                "split-bus-route-restored-files-pending"
            )
