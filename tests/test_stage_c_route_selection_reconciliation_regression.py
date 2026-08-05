from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.stage_c_transaction.route_selection_rollback_rehearsal_adapter import (
    _identity,
    _rename_exchange,
)
from scripts.stage_c_transaction.route_selection_rollback_rehearsal_adapter_v2 import (
    RouteSelectionRollbackRehearsalAdapterV2,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_ADAPTER = (
    REPO_ROOT
    / "scripts/stage_c_transaction/route_selection_rollback_rehearsal_adapter.py"
)
CORRECTED_ADAPTER = (
    REPO_ROOT
    / "scripts/stage_c_transaction/route_selection_rollback_rehearsal_adapter_v2.py"
)
ENTRY = (
    REPO_ROOT
    / "scripts/stage_c_transaction/route_selection_rollback_rehearsal_v2.py"
)
WRAPPER = REPO_ROOT / "scripts/test-stage-c-route-selection-rollback-rehearsal.sh"


class StageCRouteSelectionReconciliationRegressionTests(unittest.TestCase):
    @staticmethod
    def _adapter(
        rollback_name: str,
        original,
        candidate,
        *,
        exchange_completed: bool,
        selected_once: bool,
        selected: bool,
        count: int,
    ) -> RouteSelectionRollbackRehearsalAdapterV2:
        adapter = object.__new__(RouteSelectionRollbackRehearsalAdapterV2)
        adapter._route_rollback_name = rollback_name
        adapter._route_original = original
        adapter._route_candidate = candidate
        adapter._route_exchange_completed = exchange_completed
        adapter._route_selected_once = selected_once
        adapter._route_selected = selected
        adapter._route_selection_count = count
        adapter._route_restored = False
        adapter._record_route_action = Mock()
        adapter._write_route_transaction_state = Mock()
        return adapter

    @staticmethod
    def _exchange(root: Path, left: str, right: str) -> None:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        parent_fd = os.open(root, flags)
        try:
            _rename_exchange(parent_fd, left, right)
        finally:
            os.close(parent_fd)

    def test_first_exchange_completed_before_flag_is_reconciled(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            active = root / "active.conf"
            rollback = root / ".active.stage-c20.rollback"
            active.write_text("direct\n", encoding="utf-8")
            rollback.write_text("split\n", encoding="utf-8")
            original = _identity(active)
            candidate = _identity(rollback)
            self._exchange(root, active.name, rollback.name)

            adapter = self._adapter(
                rollback.name,
                original,
                candidate,
                exchange_completed=False,
                selected_once=False,
                selected=False,
                count=0,
            )
            with patch(
                "scripts.stage_c_transaction."
                "route_selection_rollback_rehearsal_adapter_v2."
                "_safe_destination",
                return_value=active,
            ):
                adapter._restore_active_route_exact()

            self.assertEqual(_identity(active), original)
            self.assertFalse(rollback.exists())
            self.assertTrue(adapter._route_selected_once)
            self.assertEqual(adapter._route_selection_count, 1)
            self.assertTrue(adapter._route_restored)
            self.assertFalse(adapter._route_exchange_completed)
            self.assertIsNone(adapter._route_rollback_name)
            detail = adapter._record_route_action.call_args.args[2]
            self.assertIn("reconciled_from=selected", detail)
            adapter._write_route_transaction_state.assert_called_once_with(
                "split-bus-route-restored-files-pending"
            )

    def test_reverse_exchange_completed_before_flag_clear_is_reconciled(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            active = root / "active.conf"
            rollback = root / ".active.stage-c20.rollback"
            active.write_text("direct\n", encoding="utf-8")
            rollback.write_text("split\n", encoding="utf-8")
            original = _identity(active)
            candidate = _identity(rollback)

            adapter = self._adapter(
                rollback.name,
                original,
                candidate,
                exchange_completed=True,
                selected_once=True,
                selected=True,
                count=1,
            )
            with patch(
                "scripts.stage_c_transaction."
                "route_selection_rollback_rehearsal_adapter_v2."
                "_safe_destination",
                return_value=active,
            ):
                adapter._restore_active_route_exact()

            self.assertEqual(_identity(active), original)
            self.assertFalse(rollback.exists())
            self.assertTrue(adapter._route_selected_once)
            self.assertEqual(adapter._route_selection_count, 1)
            self.assertTrue(adapter._route_restored)
            self.assertFalse(adapter._route_exchange_completed)
            self.assertIsNone(adapter._route_rollback_name)
            detail = adapter._record_route_action.call_args.args[2]
            self.assertIn("reconciled_from=restored", detail)

    def test_corrected_adapter_is_a_narrow_subclass(self) -> None:
        source = CORRECTED_ADAPTER.read_text(encoding="utf-8")
        self.assertIn(
            "class RouteSelectionRollbackRehearsalAdapterV2(\n    RouteSelectionRollbackRehearsalAdapter\n)",
            source,
        )
        self.assertEqual(source.count("def _restore_active_route_exact"), 1)
        for forbidden in (
            "systemctl",
            "aplay",
            "speaker-test",
            "amixer",
            "subprocess",
            "shell=True",
        ):
            self.assertNotIn(forbidden, source)

    def test_entry_selection_is_explicit_and_wrapper_uses_it(self) -> None:
        entry = ENTRY.read_text(encoding="utf-8")
        wrapper = WRAPPER.read_text(encoding="utf-8")
        self.assertIn(
            "rehearsal.RouteSelectionRollbackRehearsalAdapter = (",
            entry,
        )
        self.assertIn("RouteSelectionRollbackRehearsalAdapterV2", entry)
        self.assertIn(
            "python3 -m stage_c_transaction.route_selection_rollback_rehearsal_v2",
            wrapper,
        )
        self.assertNotIn(
            "python3 -m stage_c_transaction.route_selection_rollback_rehearsal \\",
            wrapper,
        )

    def test_new_modules_and_wrapper_compile(self) -> None:
        subprocess.run(
            [
                "python3",
                "-m",
                "py_compile",
                str(BASE_ADAPTER),
                str(CORRECTED_ADAPTER),
                str(ENTRY),
            ],
            check=True,
            cwd=REPO_ROOT,
        )
        subprocess.run(
            ["bash", "-n", str(WRAPPER)],
            check=True,
            cwd=REPO_ROOT,
        )


if __name__ == "__main__":
    unittest.main()
