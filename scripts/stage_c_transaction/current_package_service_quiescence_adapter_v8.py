#!/usr/bin/python3
from __future__ import annotations

"""Current-package binding for the physically exercised service rehearsal.

Stage C22 intentionally composes two existing owners:

* the Stage C21 adapter owns the accepted 28-file package, canonical lock,
  authoritative transaction, five snapshots and private candidate validation;
* the corrected Stage C17 v2 adapter owns the reversible application-service
  stop/restore sequence, DAC-release proof and bounded restoration readiness.

The composition adds no installer, route, mixer, approval or audio operation.
"""

from . import current_package_candidate_rehearsal_adapter_v7 as current_v7
from .current_package_candidate_rehearsal_adapter_v7 import (
    CurrentPackageCandidateValidationAdapterV7,
)
from .service_quiescence_rehearsal_adapter_v2 import (
    ServiceQuiescenceRehearsalAdapterV2,
)


LEGACY_CURRENT_TRANSACTION_PREFIX_V8 = "stage-c21-prepare-install-"
LEGACY_CURRENT_SNAPSHOT_PREFIX_V8 = "stage-c21-prepare-snapshot-"
CURRENT_SERVICE_TRANSACTION_PREFIX_V8 = "stage-c22-service-rehearsal-install-"
CURRENT_SERVICE_SNAPSHOT_PREFIX_V8 = "stage-c22-service-rehearsal-snapshot-"


def apply_current_service_identity_contract_v8() -> None:
    """Bind current-package transaction identities to the Stage C22 rehearsal."""

    if (
        current_v7.CURRENT_TRANSACTION_PREFIX
        != LEGACY_CURRENT_TRANSACTION_PREFIX_V8
        or current_v7.CURRENT_SNAPSHOT_PREFIX
        != LEGACY_CURRENT_SNAPSHOT_PREFIX_V8
    ):
        raise SystemExit(
            "Stage C21 transaction identity contract changed; refusing the "
            "Stage C22 service-rehearsal binding"
        )
    current_v7.CURRENT_TRANSACTION_PREFIX = (
        CURRENT_SERVICE_TRANSACTION_PREFIX_V8
    )
    current_v7.CURRENT_SNAPSHOT_PREFIX = CURRENT_SERVICE_SNAPSHOT_PREFIX_V8


class CurrentPackageServiceQuiescenceAdapterV8(
    ServiceQuiescenceRehearsalAdapterV2,
    CurrentPackageCandidateValidationAdapterV7,
):
    """Accepted current package plus one reversible service mutation prefix."""

    pass
