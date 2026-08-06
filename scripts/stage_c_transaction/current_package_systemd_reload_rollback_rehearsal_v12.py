#!/usr/bin/python3
from __future__ import annotations

"""Stage C24 entry point with bounded reloads and explicit pre-live diagnostics.

The failed first physical invocation after a reboot proved that the inherited
prepare-only validator reports only the combined ``host-observation-failed``
disposition when one read-only observation differs. This compatibility entry
point prints the already collected immutable report fields before delegating to
the unchanged accepted validator. It adds no host observation, lock, mutation,
service, systemd, audio or approval operation.
"""

import sys
from typing import TextIO

from . import current_package_systemd_reload_rollback_rehearsal_v10 as base
from .current_package_contract_v7 import (
    validate_prepare_only_report_against_accepted_v7 as ORIGINAL_PRE_LIVE_VALIDATOR_V12,
)
from .current_package_systemd_reload_rollback_adapter_v10 import (
    CurrentPackageSystemdReloadRollbackAdapterV10,
)
from .current_package_systemd_reload_rollback_adapter_v11 import (
    CurrentPackageSystemdReloadRollbackAdapterV11,
)
from .production_prepare_only_inspector_v7 import ProductionPrepareOnlyReportV7
from .production_adapter_contract import PackageFingerprint


REQUIRED_CONFIRMATION = base.REQUIRED_CONFIRMATION
EVIDENCE_PREFIX = base.EVIDENCE_PREFIX
EXPECTED_CHECKS = base.EXPECTED_CHECKS
PRE_LIVE_OBSERVATION_ORDER_V12 = (
    "host_contract",
    "production_lock",
    "services",
    "mixer",
    "loopback",
    "dac",
)


def _field(value: object) -> str:
    raw = getattr(value, "value", value)
    return " ".join(str(raw).split())


def emit_pre_live_diagnostics_v12(
    report: ProductionPrepareOnlyReportV7,
    *,
    stream: TextIO | None = None,
) -> None:
    """Print only fields already frozen in the read-only pre-live report."""

    output = sys.stderr if stream is None else stream
    print(
        "STAGE_C24_PRE_LIVE "
        f"status={_field(report.status)} "
        f"disposition={_field(report.disposition)} "
        f"detail={_field(report.detail)}",
        file=output,
        flush=True,
    )
    for name in PRE_LIVE_OBSERVATION_ORDER_V12:
        result = getattr(report, name)
        print(
            "STAGE_C24_PRE_LIVE_OBSERVATION "
            f"name={name} "
            f"status={_field(result.status)} "
            f"operation={_field(result.operation)} "
            f"detail={_field(result.detail)}",
            file=output,
            flush=True,
        )
    print(
        "STAGE_C24_PRE_LIVE_APPROVAL "
        f"state={_field(report.approval.state)} "
        f"detail={_field(report.approval.detail)}",
        file=output,
        flush=True,
    )


def validate_prepare_only_report_with_diagnostics_v12(
    report: ProductionPrepareOnlyReportV7,
    package: PackageFingerprint,
) -> None:
    """Expose the frozen report, then preserve the exact accepted validator."""

    emit_pre_live_diagnostics_v12(report)
    ORIGINAL_PRE_LIVE_VALIDATOR_V12(report, package)


def main(argv: list[str] | None = None) -> int:
    observed_adapter = base.CurrentPackageSystemdReloadRollbackAdapterV10
    if observed_adapter is not CurrentPackageSystemdReloadRollbackAdapterV10:
        raise SystemExit(
            "Stage C24 base adapter binding changed; refusing the diagnostic "
            "bounded-attempt entry point"
        )

    observed_validator = base.validate_prepare_only_report_against_accepted_v7
    if observed_validator is not ORIGINAL_PRE_LIVE_VALIDATOR_V12:
        raise SystemExit(
            "Stage C24 pre-live validator binding changed; refusing the "
            "diagnostic compatibility entry point"
        )

    base.CurrentPackageSystemdReloadRollbackAdapterV10 = (
        CurrentPackageSystemdReloadRollbackAdapterV11
    )
    base.validate_prepare_only_report_against_accepted_v7 = (
        validate_prepare_only_report_with_diagnostics_v12
    )
    try:
        return base.main(argv)
    finally:
        base.validate_prepare_only_report_against_accepted_v7 = observed_validator
        base.CurrentPackageSystemdReloadRollbackAdapterV10 = observed_adapter


if __name__ == "__main__":
    raise SystemExit(main())
