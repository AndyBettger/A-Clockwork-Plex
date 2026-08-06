#!/usr/bin/python3
from __future__ import annotations

"""Terminal adapter correction for the initial service-quiescence boundary.

The v15 terminal override is still required when a later activation failure must
quiesce applications again after they were restored under the managed graph.
For the first stop, however, the physically exercised service owner must run so
it sets the inherited mutation flag, records each stopped service and guarantees
partial-stop restoration.
"""

from .current_package_terminal_install_adapter_v16 import (
    ACTIVE_ROUTE,
    COMMITTED_INSTALL_ROOT,
    RUNTIME_HELPER,
    SPLIT_ROUTE,
    CurrentPackageTerminalInstallAdapterV16,
)
from .production_adapter_contract import AdapterResult, ServiceSnapshot, TransactionIdentity
from .service_quiescence_rehearsal_adapter import ServiceQuiescenceRehearsalAdapter


class CurrentPackageTerminalInstallAdapterV17(
    CurrentPackageTerminalInstallAdapterV16
):
    """v16 terminal owner with the proved first-stop state transition."""

    def stop_captured_application_services(
        self,
        transaction: TransactionIdentity,
        services: ServiceSnapshot,
    ) -> AdapterResult[None]:
        if not self._mutation_started:
            return ServiceQuiescenceRehearsalAdapter.stop_captured_application_services(
                self,
                transaction,
                services,
            )
        return super().stop_captured_application_services(transaction, services)
