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
    "current_package_systemd_reload_rollback_adapter_v11.py"
)
ENTRY_PATH = (
    ROOT
    / "scripts/stage_c_transaction/"
    "current_package_systemd_reload_rollback_rehearsal_v11.py"
)
WRAPPER_PATH = (
    ROOT / "scripts/test-stage-c24-current-package-systemd-reload-rollback.sh"
)

from scripts.stage_c_transaction import (  # noqa: E402
    current_package_systemd_reload_rollback_rehearsal_v10 as base_rehearsal,
)
from scripts.stage_c_transaction.current_package_systemd_reload_rollback_adapter_v10 import (  # noqa: E402
    CurrentPackageSystemdReloadRollbackAdapterV10,
)
from scripts.stage_c_transaction.current_package_systemd_reload_rollback_adapter_v11 import (  # noqa: E402
    MAX_DAEMON_RELOAD_ATTEMPTS_V11,
    CurrentPackageSystemdReloadRollbackAdapterV11,
)
from scripts.stage_c_transaction.current_package_systemd_reload_rollback_rehearsal_v11 import (  # noqa: E402
    EVIDENCE_PREFIX,
    EXPECTED_CHECKS,
    REQUIRED_CONFIRMATION,
    main,
)
from scripts.stage_c_transaction.systemd_reload_rollback_rehearsal_adapter import (  # noqa: E402
    SystemdReloadRollbackFailure,
    SystemdReloadRollbackRehearsalAdapter,
)


class StageC24DaemonReloadAttemptGuardV11Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter_source = ADAPTER_PATH.read_text(encoding="utf-8")
        self.entry_source = ENTRY_PATH.read_text(encoding="utf-8")
        self.wrapper_source = WRAPPER_PATH.read_text(encoding="utf-8")

    @staticmethod
    def bare_adapter() -> CurrentPackageSystemdReloadRollbackAdapterV11:
        adapter = object.__new__(CurrentPackageSystemdReloadRollbackAdapterV11)
        adapter._systemd_reload_attempt_count = 0
        return adapter

    def test_guard_extends_the_complete_v10_adapter(self) -> None:
        self.assertTrue(
            issubclass(
                CurrentPackageSystemdReloadRollbackAdapterV11,
                CurrentPackageSystemdReloadRollbackAdapterV10,
            )
        )
        self.assertEqual(MAX_DAEMON_RELOAD_ATTEMPTS_V11, 2)

    def test_exactly_two_attempts_delegate_to_the_exercised_c19_primitive(
        self,
    ) -> None:
        adapter = self.bare_adapter()
        with patch.object(
            SystemdReloadRollbackRehearsalAdapter,
            "_run_daemon_reload",
            autospec=True,
        ) as delegated:
            adapter._run_daemon_reload("candidate-files-installed")
            adapter._run_daemon_reload("rollback-files-absent")
            with self.assertRaisesRegex(
                SystemdReloadRollbackFailure,
                "unapproved third",
            ):
                adapter._run_daemon_reload("forbidden-third-attempt")

        self.assertEqual(adapter.systemd_reload_attempt_count, 2)
        self.assertEqual(delegated.call_count, 2)
        self.assertEqual(
            delegated.call_args_list[0].args[1],
            "candidate-files-installed",
        )
        self.assertEqual(
            delegated.call_args_list[1].args[1],
            "rollback-files-absent",
        )

    def test_failed_command_consumes_one_attempt(self) -> None:
        adapter = self.bare_adapter()
        with patch.object(
            SystemdReloadRollbackRehearsalAdapter,
            "_run_daemon_reload",
            autospec=True,
            side_effect=(
                SystemdReloadRollbackFailure("first command failed"),
                None,
            ),
        ) as delegated:
            with self.assertRaisesRegex(
                SystemdReloadRollbackFailure,
                "first command failed",
            ):
                adapter._run_daemon_reload("candidate-files-installed")
            adapter._run_daemon_reload("rollback-files-absent")
            with self.assertRaisesRegex(
                SystemdReloadRollbackFailure,
                "attempt budget is exhausted",
            ):
                adapter._run_daemon_reload("forbidden-third-attempt")

        self.assertEqual(adapter.systemd_reload_attempt_count, 2)
        self.assertEqual(delegated.call_count, 2)

    def test_guard_contains_no_second_host_command_implementation(self) -> None:
        for forbidden in (
            "host_run(",
            "subprocess",
            "os.system",
            "Popen(",
        ):
            self.assertNotIn(forbidden, self.adapter_source)
        self.assertIn(
            "SystemdReloadRollbackRehearsalAdapter._run_daemon_reload",
            self.adapter_source,
        )

    def test_entry_point_temporarily_binds_v11_and_restores_v10(self) -> None:
        observed: list[type] = []

        def inspect_binding(argv: list[str] | None = None) -> int:
            observed.append(
                base_rehearsal.CurrentPackageSystemdReloadRollbackAdapterV10
            )
            self.assertEqual(argv, ["--example"])
            return 0

        with patch.object(base_rehearsal, "main", side_effect=inspect_binding):
            self.assertEqual(main(["--example"]), 0)

        self.assertEqual(observed, [CurrentPackageSystemdReloadRollbackAdapterV11])
        self.assertIs(
            base_rehearsal.CurrentPackageSystemdReloadRollbackAdapterV10,
            CurrentPackageSystemdReloadRollbackAdapterV10,
        )

    def test_entry_point_preserves_c24_contract(self) -> None:
        self.assertEqual(
            REQUIRED_CONFIRMATION,
            "STAGE-C24-CURRENT-PACKAGE-SYSTEMD-RELOAD-EXACT-ROLLBACK",
        )
        self.assertEqual(
            EVIDENCE_PREFIX,
            "a-clockwork-plex-stage-c24-current-package-systemd-reload-rollback.",
        )
        self.assertEqual(len(EXPECTED_CHECKS), 54)
        self.assertIn("base.main(argv)", self.entry_source)

    def test_wrapper_uses_only_the_bounded_entry_point(self) -> None:
        self.assertIn(
            "current_package_systemd_reload_rollback_rehearsal_v11",
            self.wrapper_source,
        )
        self.assertNotIn(
            "python3 -B -m stage_c_transaction."
            "current_package_systemd_reload_rollback_rehearsal_v10",
            self.wrapper_source,
        )
        self.assertIn("hard budget of two", self.wrapper_source)
        self.assertEqual(self.wrapper_source.count("exec sudo env"), 1)


if __name__ == "__main__":
    unittest.main()
