from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts.stage_c_transaction import service_quiescence_rehearsal_adapter
from scripts.stage_c_transaction.current_package_terminal_install_adapter_v16 import (
    CurrentPackageTerminalInstallAdapterV16,
)
from scripts.stage_c_transaction.current_package_terminal_install_adapter_v17 import (
    CurrentPackageTerminalInstallAdapterV17,
)
from scripts.stage_c_transaction.production_adapter_contract import (
    AdapterStatus,
    ServiceActiveState,
    ServiceEnableState,
    ServiceLoadState,
    ServiceSnapshot,
    ServiceState,
    ServiceUnit,
    TransactionIdentity,
)
from scripts.stage_c_transaction.service_quiescence_rehearsal_adapter import (
    APPLICATION_STOP_ORDER,
)


APPLICATION_UNITS = {
    ServiceUnit.PLEXAMP,
    ServiceUnit.SHAIRPORT_SYNC,
    ServiceUnit.DASHBOARD,
}


def service_snapshot(*, applications_active: bool) -> ServiceSnapshot:
    states: list[ServiceState] = []
    for unit in ServiceUnit:
        if unit in APPLICATION_UNITS:
            states.append(
                ServiceState(
                    unit=unit,
                    load=ServiceLoadState.LOADED,
                    active=(
                        ServiceActiveState.ACTIVE
                        if applications_active
                        else ServiceActiveState.INACTIVE
                    ),
                    enabled=ServiceEnableState.ENABLED,
                )
            )
        else:
            states.append(
                ServiceState(
                    unit=unit,
                    load=ServiceLoadState.NOT_FOUND,
                    active=ServiceActiveState.INACTIVE,
                    enabled=ServiceEnableState.NOT_FOUND,
                )
            )
    return ServiceSnapshot(tuple(states))


class StageCTerminalQuiescenceV17Tests(unittest.TestCase):
    def test_first_stop_sets_reload_quiescence_state(self) -> None:
        captured = service_snapshot(applications_active=True)
        stopped = service_snapshot(applications_active=False)
        transaction = TransactionIdentity("stage-c-terminal-test-transaction")

        adapter = object.__new__(CurrentPackageTerminalInstallAdapterV17)
        adapter._mutation_started = False
        adapter._services_stopped = False
        adapter._captured_services_exact = captured
        adapter._stopped_services = []
        adapter._candidate_ready_for_mutation = lambda operation, identity: None
        adapter._validate_captured_application_boundary = lambda services: None
        adapter._run_systemctl = lambda action, unit: None
        adapter._wait_for_active = lambda unit, expected: None
        adapter._record_service_action = lambda action, unit, result, detail: None

        with patch.object(
            service_quiescence_rehearsal_adapter,
            "_observe_service_snapshot",
            side_effect=(captured, stopped),
        ):
            result = adapter.stop_captured_application_services(
                transaction,
                captured,
            )

        self.assertIs(result.status, AdapterStatus.PASS)
        self.assertTrue(adapter._mutation_started)
        self.assertTrue(adapter._services_stopped)
        self.assertEqual(tuple(adapter._stopped_services), APPLICATION_STOP_ORDER)

    def test_later_restop_keeps_terminal_override(self) -> None:
        adapter = object.__new__(CurrentPackageTerminalInstallAdapterV17)
        adapter._mutation_started = True
        transaction = TransactionIdentity("stage-c-terminal-test-transaction")
        services = service_snapshot(applications_active=True)
        sentinel = object()

        with patch.object(
            CurrentPackageTerminalInstallAdapterV16,
            "stop_captured_application_services",
            return_value=sentinel,
        ) as terminal_stop:
            result = adapter.stop_captured_application_services(
                transaction,
                services,
            )

        self.assertIs(result, sentinel)
        terminal_stop.assert_called_once_with(transaction, services)


if __name__ == "__main__":
    unittest.main()
