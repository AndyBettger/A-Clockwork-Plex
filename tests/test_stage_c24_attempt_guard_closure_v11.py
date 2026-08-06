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

from scripts.stage_c_transaction.current_package_systemd_reload_rollback_adapter_v10 import (  # noqa: E402
    CurrentPackageSystemdReloadRollbackAdapterV10,
)
from scripts.stage_c_transaction.current_package_systemd_reload_rollback_adapter_v11 import (  # noqa: E402
    CurrentPackageSystemdReloadRollbackAdapterV11,
)
from scripts.stage_c_transaction.production_adapter_contract import (  # noqa: E402
    AdapterStatus,
    TransactionIdentity,
)


class StageC24AttemptGuardClosureV11Tests(unittest.TestCase):
    @staticmethod
    def adapter_with_attempts(
        attempts: int,
    ) -> CurrentPackageSystemdReloadRollbackAdapterV11:
        adapter = object.__new__(CurrentPackageSystemdReloadRollbackAdapterV11)
        adapter._systemd_reload_attempt_count = attempts
        return adapter

    def test_closure_refuses_any_attempt_count_other_than_two(self) -> None:
        transaction = TransactionIdentity("stage-c24-test")
        for attempts in (0, 1, 3):
            adapter = self.adapter_with_attempts(attempts)
            result = (
                adapter.close_current_package_systemd_reload_rollback_rehearsal(
                    transaction
                )
            )
            self.assertIs(result.status, AdapterStatus.FAIL)
            self.assertIn("exactly two attempted", result.detail)

    def test_exactly_two_attempts_delegate_to_complete_v10_closure(self) -> None:
        transaction = TransactionIdentity("stage-c24-test")
        adapter = self.adapter_with_attempts(2)
        sentinel = object()
        with patch.object(
            CurrentPackageSystemdReloadRollbackAdapterV10,
            "close_current_package_systemd_reload_rollback_rehearsal",
            autospec=True,
            return_value=sentinel,
        ) as delegated:
            observed = (
                adapter.close_current_package_systemd_reload_rollback_rehearsal(
                    transaction
                )
            )
        self.assertIs(observed, sentinel)
        delegated.assert_called_once_with(adapter, transaction)


if __name__ == "__main__":
    unittest.main()
