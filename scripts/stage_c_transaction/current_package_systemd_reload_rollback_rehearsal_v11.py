#!/usr/bin/python3
from __future__ import annotations

"""Final Stage C24 entry point with a two-attempt daemon-reload budget."""

from . import current_package_systemd_reload_rollback_rehearsal_v10 as base
from .current_package_systemd_reload_rollback_adapter_v10 import (
    CurrentPackageSystemdReloadRollbackAdapterV10,
)
from .current_package_systemd_reload_rollback_adapter_v11 import (
    CurrentPackageSystemdReloadRollbackAdapterV11,
)


REQUIRED_CONFIRMATION = base.REQUIRED_CONFIRMATION
EVIDENCE_PREFIX = base.EVIDENCE_PREFIX
EXPECTED_CHECKS = base.EXPECTED_CHECKS


def main(argv: list[str] | None = None) -> int:
    observed = base.CurrentPackageSystemdReloadRollbackAdapterV10
    if observed is not CurrentPackageSystemdReloadRollbackAdapterV10:
        raise SystemExit(
            "Stage C24 base adapter binding changed; refusing the bounded-attempt "
            "entry point"
        )
    base.CurrentPackageSystemdReloadRollbackAdapterV10 = (
        CurrentPackageSystemdReloadRollbackAdapterV11
    )
    try:
        return base.main(argv)
    finally:
        base.CurrentPackageSystemdReloadRollbackAdapterV10 = observed


if __name__ == "__main__":
    raise SystemExit(main())
