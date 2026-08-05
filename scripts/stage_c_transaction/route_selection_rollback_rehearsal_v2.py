#!/usr/bin/python3
from __future__ import annotations

"""Stage C20 corrected physical entry point.

The accepted C20 orchestration remains unchanged. This explicit entry point
substitutes only the atomic-exchange reconciliation adapter so rollback follows
the exact on-disk inode arrangement even if interruption occurs immediately
after either exchange syscall.
"""

from . import route_selection_rollback_rehearsal as rehearsal
from .route_selection_rollback_rehearsal_adapter_v2 import (
    RouteSelectionRollbackRehearsalAdapterV2,
)


def main() -> None:
    rehearsal.RouteSelectionRollbackRehearsalAdapter = (
        RouteSelectionRollbackRehearsalAdapterV2
    )
    rehearsal.main()


if __name__ == "__main__":
    main()
