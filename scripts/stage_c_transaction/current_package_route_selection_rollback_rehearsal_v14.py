#!/usr/bin/python3
from __future__ import annotations

"""Idempotent entry binding for the integrated current-package route rehearsal.

The v13 engine and adapter own the complete physical transaction.  This narrow
compatibility entry corrects only repeated in-process identity binding: it
returns immediately when the C25 prefixes are already installed, otherwise it
first establishes the accepted C24 prefixes and then advances them exactly
once.  It adds no host observation, lock, file, service, systemd, route, audio,
approval or commit operation.
"""

from . import current_package_candidate_rehearsal_adapter_v7 as current_v7
from . import current_package_route_selection_rollback_rehearsal_v13 as base
from .current_package_route_selection_rollback_adapter_v13 import (
    CURRENT_ROUTE_SNAPSHOT_PREFIX_V13,
    CURRENT_ROUTE_TRANSACTION_PREFIX_V13,
)
from .current_package_systemd_reload_rollback_adapter_v10 import (
    CURRENT_SYSTEMD_SNAPSHOT_PREFIX_V10,
    CURRENT_SYSTEMD_TRANSACTION_PREFIX_V10,
    apply_current_systemd_reload_identity_contract_v10,
)


REQUIRED_CONFIRMATION = base.REQUIRED_CONFIRMATION
EVIDENCE_PREFIX = base.EVIDENCE_PREFIX
EXPECTED_CHECKS = base.EXPECTED_CHECKS


def apply_current_route_identity_contract_v14() -> None:
    """Advance C24 identities to C25 exactly once and tolerate repeat binding."""

    target = (
        CURRENT_ROUTE_TRANSACTION_PREFIX_V13,
        CURRENT_ROUTE_SNAPSHOT_PREFIX_V13,
    )
    current = (
        current_v7.CURRENT_TRANSACTION_PREFIX,
        current_v7.CURRENT_SNAPSHOT_PREFIX,
    )
    if current == target:
        return

    apply_current_systemd_reload_identity_contract_v10()
    current = (
        current_v7.CURRENT_TRANSACTION_PREFIX,
        current_v7.CURRENT_SNAPSHOT_PREFIX,
    )
    expected = (
        CURRENT_SYSTEMD_TRANSACTION_PREFIX_V10,
        CURRENT_SYSTEMD_SNAPSHOT_PREFIX_V10,
    )
    if current != expected:
        raise SystemExit(
            "Stage C24 transaction identity contract changed; refusing the "
            "idempotent current-package route binding"
        )
    current_v7.CURRENT_TRANSACTION_PREFIX = CURRENT_ROUTE_TRANSACTION_PREFIX_V13
    current_v7.CURRENT_SNAPSHOT_PREFIX = CURRENT_ROUTE_SNAPSHOT_PREFIX_V13


def main(argv: list[str] | None = None) -> int:
    observed = base.apply_current_route_identity_contract_v13
    base.apply_current_route_identity_contract_v13 = (
        apply_current_route_identity_contract_v14
    )
    try:
        return base.main(argv)
    finally:
        base.apply_current_route_identity_contract_v13 = observed


if __name__ == "__main__":
    raise SystemExit(main())
