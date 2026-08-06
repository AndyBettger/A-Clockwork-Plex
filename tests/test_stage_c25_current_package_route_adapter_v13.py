from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

ADAPTER_PATH = (
    ROOT
    / "scripts/stage_c_transaction/"
    "current_package_route_selection_rollback_adapter_v13.py"
)

from scripts.stage_c_transaction import (  # noqa: E402
    current_package_candidate_rehearsal_adapter_v7 as current_v7,
)
from scripts.stage_c_transaction.current_package_route_selection_rollback_adapter_v13 import (  # noqa: E402
    CURRENT_ROUTE_SNAPSHOT_PREFIX_V13,
    CURRENT_ROUTE_TRANSACTION_PREFIX_V13,
    CurrentPackageRouteRollbackReceiptV13,
    CurrentPackageRouteSelectionRollbackAdapterV13,
    apply_current_route_identity_contract_v13,
)
from scripts.stage_c_transaction.current_package_systemd_reload_rollback_adapter_v10 import (  # noqa: E402
    CURRENT_SYSTEMD_SNAPSHOT_PREFIX_V10,
    CURRENT_SYSTEMD_TRANSACTION_PREFIX_V10,
)
from scripts.stage_c_transaction.current_package_systemd_reload_rollback_adapter_v11 import (  # noqa: E402
    MAX_DAEMON_RELOAD_ATTEMPTS_V11,
    CurrentPackageSystemdReloadRollbackAdapterV11,
)
from scripts.stage_c_transaction.production_adapter_contract import (  # noqa: E402
    AdapterOperation,
    AdapterStatus,
    TransactionIdentity,
)


class CurrentPackageRouteAdapterV13Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = ADAPTER_PATH.read_text(encoding="utf-8")

    def test_adapter_extends_the_bounded_current_package_owner(self) -> None:
        self.assertTrue(
            issubclass(
                CurrentPackageRouteSelectionRollbackAdapterV13,
                CurrentPackageSystemdReloadRollbackAdapterV11,
            )
        )
        self.assertEqual(MAX_DAEMON_RELOAD_ATTEMPTS_V11, 2)

    def test_identity_binding_advances_c24_once_and_is_idempotent(self) -> None:
        with (
            patch.object(
                current_v7,
                "CURRENT_TRANSACTION_PREFIX",
                CURRENT_SYSTEMD_TRANSACTION_PREFIX_V10,
            ),
            patch.object(
                current_v7,
                "CURRENT_SNAPSHOT_PREFIX",
                CURRENT_SYSTEMD_SNAPSHOT_PREFIX_V10,
            ),
            patch(
                "scripts.stage_c_transaction."
                "current_package_route_selection_rollback_adapter_v13."
                "apply_current_systemd_reload_identity_contract_v10"
            ),
        ):
            apply_current_route_identity_contract_v13()
            self.assertEqual(
                current_v7.CURRENT_TRANSACTION_PREFIX,
                CURRENT_ROUTE_TRANSACTION_PREFIX_V13,
            )
            self.assertEqual(
                current_v7.CURRENT_SNAPSHOT_PREFIX,
                CURRENT_ROUTE_SNAPSHOT_PREFIX_V13,
            )
            apply_current_route_identity_contract_v13()

    def test_preconditions_refuse_route_before_the_first_reload(self) -> None:
        adapter = object.__new__(CurrentPackageRouteSelectionRollbackAdapterV13)
        adapter._systemd_reload_count = 0
        adapter._systemd_candidate_visible = False
        adapter._systemd_manager_restored = False
        adapter._managed_files_installed = True
        adapter._filesystem_restored = False
        adapter._services_stopped = True
        adapter._services_restored = False
        adapter._dac_release_verified = True
        adapter._route_mutation_started = False
        adapter._route_selected_once = False
        transaction = TransactionIdentity("stage-c25-test-transaction")
        with patch.object(adapter, "_require_candidate", return_value=None):
            result = adapter.select_split_bus_route(transaction)
        self.assertIs(result.operation, AdapterOperation.SELECT_SPLIT_BUS_ROUTE)
        self.assertIs(result.status, AdapterStatus.FAIL)
        self.assertFalse(adapter._route_mutation_started)

    def test_receipt_requires_complete_one_exchange_two_reload_rollback(self) -> None:
        receipt = CurrentPackageRouteRollbackReceiptV13(
            transaction=TransactionIdentity("stage-c25-test-transaction"),
            state="current-package-route-rolled-back-and-closed",
            managed_files_installed=True,
            systemd_reloaded=True,
            split_bus_route_selected=True,
            active_route_restored=True,
            filesystem_restored=True,
            systemd_manager_restored=True,
            services_restored=True,
            committed=False,
            transaction_path_absent=True,
            parents_restored=True,
            installed_file_count=28,
            payload_file_count=27,
            daemon_reload_count=2,
            route_selection_count=1,
            audit_evidence="/var/tmp/example",
        )
        self.assertFalse(receipt.committed)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            CurrentPackageRouteRollbackReceiptV13(
                **{**receipt.__dict__, "route_selection_count": 2}
            )

    def test_layer_adds_only_route_filesystem_mutation(self) -> None:
        self.assertIn("_rename_exchange(", self.source)
        self.assertIn("CurrentPackageSystemdReloadRollbackAdapterV11", self.source)
        self.assertNotIn("host_run(", self.source)
        self.assertNotIn("systemctl", self.source)
        self.assertNotIn("publish_temporary_activation_approval", self.source)
        self.assertNotIn("promote_committed_activation_approval", self.source)
        self.assertNotIn("PROBE_MUSIC_LANE", self.source)
        self.assertNotIn("PROBE_ALARM_LANE", self.source)
        self.assertNotIn("install-master-eq.sh", self.source)

    def test_rollback_order_is_route_before_inherited_cleanup(self) -> None:
        exit_source = self.source[
            self.source.index("    def __exit__("):
            self.source.index("    @property\n    def route_selected_once")
        ]
        self.assertLess(
            exit_source.index("self._restore_active_route_exact()"),
            exit_source.index(
                "CurrentPackageSystemdReloadRollbackAdapterV11.__exit__"
            ),
        )


if __name__ == "__main__":
    unittest.main()
