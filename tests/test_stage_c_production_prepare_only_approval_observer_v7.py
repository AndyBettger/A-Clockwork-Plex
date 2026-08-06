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

from scripts.stage_c_transaction import (  # noqa: E402
    production_prepare_only_inspector_v7 as inspector_module,
)
from scripts.stage_c_transaction.production_prepare_only_inspector_v7 import (  # noqa: E402
    ProductionApprovalBaselineStateV7,
)


class StageCProductionPrepareOnlyApprovalObserverV7Tests(unittest.TestCase):
    def test_unexpected_low_level_exception_becomes_typed_observation_failure(self) -> None:
        with patch.object(
            inspector_module.os,
            "open",
            side_effect=RuntimeError("injected fixed-path observation failure"),
        ) as open_mock:
            observed = inspector_module.observe_production_approval_baseline_v7()

        open_mock.assert_called_once_with("/", inspector_module._directory_flags())
        self.assertIs(
            observed.state,
            ProductionApprovalBaselineStateV7.OBSERVATION_FAILURE,
        )
        self.assertFalse(observed.present)
        self.assertFalse(observed.canonical_record)
        self.assertIn("RuntimeError", observed.detail)
        self.assertIn("injected fixed-path observation failure", observed.detail)
        self.assertIsNone(observed.raw_sha256)
        self.assertIsNone(observed.device)
        self.assertIsNone(observed.inode)
