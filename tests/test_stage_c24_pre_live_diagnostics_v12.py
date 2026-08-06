from __future__ import annotations

import sys
import unittest
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

ENTRY_PATH = (
    ROOT
    / "scripts/stage_c_transaction/"
    "current_package_systemd_reload_rollback_rehearsal_v12.py"
)
WRAPPER_PATH = (
    ROOT / "scripts/test-stage-c24-current-package-systemd-reload-rollback.sh"
)

from scripts.stage_c_transaction import (  # noqa: E402
    current_package_systemd_reload_rollback_rehearsal_v10 as base_rehearsal,
)
from scripts.stage_c_transaction import (  # noqa: E402
    current_package_systemd_reload_rollback_rehearsal_v12 as entry,
)
from scripts.stage_c_transaction.current_package_contract_v7 import (  # noqa: E402
    validate_prepare_only_report_against_accepted_v7,
)
from scripts.stage_c_transaction.current_package_systemd_reload_rollback_adapter_v10 import (  # noqa: E402
    CurrentPackageSystemdReloadRollbackAdapterV10,
)
from scripts.stage_c_transaction.current_package_systemd_reload_rollback_adapter_v11 import (  # noqa: E402
    CurrentPackageSystemdReloadRollbackAdapterV11,
)


class StageC24PreLiveDiagnosticsV12Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.entry_source = ENTRY_PATH.read_text(encoding="utf-8")
        self.wrapper_source = WRAPPER_PATH.read_text(encoding="utf-8")

    @staticmethod
    def enum(value: str) -> SimpleNamespace:
        return SimpleNamespace(value=value)

    @classmethod
    def result(
        cls,
        *,
        status: str,
        operation: str,
        detail: str,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            status=cls.enum(status),
            operation=cls.enum(operation),
            detail=detail,
        )

    @classmethod
    def report(cls) -> SimpleNamespace:
        return SimpleNamespace(
            status=cls.enum("fail"),
            disposition=cls.enum("host-observation-failed"),
            detail="one or more fixed\nhost observations failed",
            host_contract=cls.result(
                status="pass",
                operation="inspect-host-contract",
                detail="fixed read-only host observation completed",
            ),
            production_lock=cls.result(
                status="pass",
                operation="inspect-production-lock",
                detail="fixed read-only host observation completed",
            ),
            services=cls.result(
                status="pass",
                operation="capture-service-state",
                detail="fixed read-only host observation completed",
            ),
            mixer=cls.result(
                status="pass",
                operation="capture-mixer-state",
                detail="fixed read-only host observation completed",
            ),
            loopback=cls.result(
                status="fail",
                operation="capture-loopback-state",
                detail="cannot read snd_aloop index",
            ),
            dac=cls.result(
                status="pass",
                operation="capture-dac-state",
                detail="fixed read-only host observation completed",
            ),
            approval=SimpleNamespace(
                state=cls.enum("absent"),
                detail="fixed production approval ancestor is absent: split-bus",
            ),
        )

    def test_diagnostics_print_the_fixed_report_in_stable_order(self) -> None:
        output = StringIO()
        entry.emit_pre_live_diagnostics_v12(self.report(), stream=output)
        lines = output.getvalue().splitlines()

        self.assertEqual(len(lines), 8)
        self.assertEqual(
            lines[0],
            "STAGE_C24_PRE_LIVE status=fail "
            "disposition=host-observation-failed "
            "detail=one or more fixed host observations failed",
        )
        self.assertEqual(
            [line.split("name=", 1)[1].split(" ", 1)[0] for line in lines[1:7]],
            list(entry.PRE_LIVE_OBSERVATION_ORDER_V12),
        )
        self.assertIn(
            "name=loopback status=fail "
            "operation=capture-loopback-state "
            "detail=cannot read snd_aloop index",
            lines[5],
        )
        self.assertEqual(
            lines[7],
            "STAGE_C24_PRE_LIVE_APPROVAL state=absent "
            "detail=fixed production approval ancestor is absent: split-bus",
        )

    def test_diagnostic_validator_delegates_to_the_exact_accepted_validator(
        self,
    ) -> None:
        report = self.report()
        package = object()
        output = StringIO()

        with patch.object(
            entry,
            "ORIGINAL_PRE_LIVE_VALIDATOR_V12",
            autospec=True,
        ) as delegated:
            with patch.object(entry.sys, "stderr", output):
                entry.validate_prepare_only_report_with_diagnostics_v12(
                    report,
                    package,
                )

        delegated.assert_called_once_with(report, package)
        self.assertIn("STAGE_C24_PRE_LIVE", output.getvalue())

    def test_entry_temporarily_binds_v11_and_diagnostics_then_restores(self) -> None:
        observed: list[tuple[type, object]] = []

        def inspect_bindings(argv: list[str] | None = None) -> int:
            observed.append(
                (
                    base_rehearsal.CurrentPackageSystemdReloadRollbackAdapterV10,
                    base_rehearsal.validate_prepare_only_report_against_accepted_v7,
                )
            )
            self.assertEqual(argv, ["--example"])
            return 0

        with patch.object(base_rehearsal, "main", side_effect=inspect_bindings):
            self.assertEqual(entry.main(["--example"]), 0)

        self.assertEqual(
            observed,
            [
                (
                    CurrentPackageSystemdReloadRollbackAdapterV11,
                    entry.validate_prepare_only_report_with_diagnostics_v12,
                )
            ],
        )
        self.assertIs(
            base_rehearsal.CurrentPackageSystemdReloadRollbackAdapterV10,
            CurrentPackageSystemdReloadRollbackAdapterV10,
        )
        self.assertIs(
            base_rehearsal.validate_prepare_only_report_against_accepted_v7,
            validate_prepare_only_report_against_accepted_v7,
        )

    def test_entry_preserves_the_complete_c24_contract(self) -> None:
        self.assertEqual(
            entry.REQUIRED_CONFIRMATION,
            "STAGE-C24-CURRENT-PACKAGE-SYSTEMD-RELOAD-EXACT-ROLLBACK",
        )
        self.assertEqual(
            entry.EVIDENCE_PREFIX,
            "a-clockwork-plex-stage-c24-current-package-systemd-reload-rollback.",
        )
        self.assertEqual(len(entry.EXPECTED_CHECKS), 54)
        self.assertIn(
            "CurrentPackageSystemdReloadRollbackAdapterV11",
            self.entry_source,
        )
        self.assertIn("return base.main(argv)", self.entry_source)

    def test_entry_adds_no_host_or_mutation_implementation(self) -> None:
        for forbidden in (
            "subprocess",
            "host_run(",
            "systemctl",
            "daemon-reload",
            "modprobe",
            "os.system",
            "Popen(",
        ):
            self.assertNotIn(forbidden, self.entry_source)

    def test_wrapper_selects_v12_without_bypassing_the_v11_guard(self) -> None:
        self.assertIn(
            "python3 -B -m stage_c_transaction."
            "current_package_systemd_reload_rollback_rehearsal_v12",
            self.wrapper_source,
        )
        self.assertNotIn(
            "python3 -B -m stage_c_transaction."
            "current_package_systemd_reload_rollback_rehearsal_v11",
            self.wrapper_source,
        )
        self.assertEqual(self.wrapper_source.count("exec sudo env"), 1)


if __name__ == "__main__":
    unittest.main()
