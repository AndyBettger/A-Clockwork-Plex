from __future__ import annotations

import ast
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.stage_c_transaction.production_adapter_contract import (
    DAC_CONTRACT,
    DacOwner,
    DacSnapshot,
)
from scripts.stage_c_transaction.read_only_host_adapter import ObservationFailure
from scripts.stage_c_transaction.service_quiescence_rehearsal_adapter import (
    ServiceQuiescenceRehearsalAdapter,
)
from scripts.stage_c_transaction.service_quiescence_rehearsal_adapter_v2 import (
    DAC_READY_POLL_SECONDS,
    DAC_READY_TIMEOUT_SECONDS,
    RESTORATION_READINESS_NAME,
    ServiceQuiescenceRehearsalAdapterV2,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTER = (
    REPO_ROOT
    / "scripts/stage_c_transaction/service_quiescence_rehearsal_adapter_v2.py"
)
ENTRY = (
    REPO_ROOT
    / "scripts/stage_c_transaction/service_quiescence_rehearsal_v2.py"
)
WRAPPER = REPO_ROOT / "scripts/test-stage-c-service-quiescence-rehearsal.sh"


class _ReadinessHarness:
    def __init__(self) -> None:
        self.records: list[tuple[str, str]] = []
        self._restoration_readiness = Path("/var/tmp/test-readiness.tsv")
        self._readiness_attempt = 0

    def _record_readiness(self, state: str, detail: str) -> None:
        self._readiness_attempt += 1
        self.records.append((state, detail))


class StageCServiceQuiescenceReadinessRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = ADAPTER.read_text(encoding="utf-8")
        self.entry_source = ENTRY.read_text(encoding="utf-8")
        self.wrapper_source = WRAPPER.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    def method_source(self, name: str) -> str:
        class_node = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "ServiceQuiescenceRehearsalAdapterV2"
        )
        method = next(
            node
            for node in class_node.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        )
        return ast.get_source_segment(self.source, method) or ""

    def test_corrected_adapter_is_a_narrow_subclass(self) -> None:
        self.assertTrue(
            issubclass(
                ServiceQuiescenceRehearsalAdapterV2,
                ServiceQuiescenceRehearsalAdapter,
            )
        )
        class_node = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "ServiceQuiescenceRehearsalAdapterV2"
        )
        methods = {
            node.name
            for node in class_node.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertEqual(
            methods,
            {
                "__init__",
                "_record_readiness",
                "_wait_for_restored_dac",
                "verify_dashboard_health",
            },
        )

    def test_readiness_is_bounded_and_evidenced(self) -> None:
        self.assertEqual(DAC_READY_TIMEOUT_SECONDS, 30.0)
        self.assertEqual(DAC_READY_POLL_SECONDS, 0.25)
        self.assertEqual(
            RESTORATION_READINESS_NAME,
            "restoration-readiness.tsv",
        )
        source = self.method_source("_wait_for_restored_dac")
        self.assertIn("deadline = time.monotonic() + timeout_seconds", source)
        self.assertIn("_observe_dac_snapshot()", source)
        self.assertIn("except ObservationFailure", source)
        self.assertIn("self._record_readiness", source)
        self.assertIn("time.sleep(DAC_READY_POLL_SECONDS)", source)
        self.assertNotIn("systemctl", source)

    def test_dashboard_is_awaited_before_strict_dac_poll(self) -> None:
        source = self.method_source("verify_dashboard_health")
        dashboard = source.index("self._wait_for_dashboard()")
        dac = source.index("self._wait_for_restored_dac()")
        self.assertLess(dashboard, dac)
        for marker in (
            "_observe_service_snapshot()",
            "_observe_host_contract()",
            "_observe_mixer_snapshot()",
            "_observe_loopback_snapshot()",
        ):
            self.assertIn(marker, source)

    def test_closed_then_ready_dac_is_accepted_without_blind_delay(self) -> None:
        ready = DacSnapshot(
            contract=DAC_CONTRACT,
            owners=(
                DacOwner(
                    pid=123,
                    user="andy",
                    command="node",
                    access="rw",
                ),
            ),
            released=False,
        )
        harness = _ReadinessHarness()
        with (
            patch(
                "scripts.stage_c_transaction."
                "service_quiescence_rehearsal_adapter_v2."
                "_observe_dac_snapshot",
                side_effect=(
                    ObservationFailure(
                        "physical DAC contract mismatch: fields missing"
                    ),
                    ready,
                ),
            ),
            patch(
                "scripts.stage_c_transaction."
                "service_quiescence_rehearsal_adapter_v2.time.monotonic",
                side_effect=(0.0, 0.0, 0.01),
            ),
            patch(
                "scripts.stage_c_transaction."
                "service_quiescence_rehearsal_adapter_v2.time.sleep"
            ) as sleep,
        ):
            observed = (
                ServiceQuiescenceRehearsalAdapterV2.
                _wait_for_restored_dac(harness, timeout_seconds=1.0)
            )
        self.assertEqual(observed, ready)
        self.assertEqual(harness.records[0][0], "not-ready")
        self.assertEqual(harness.records[-1], ("ready", "owner_count=1"))
        sleep.assert_called_once_with(DAC_READY_POLL_SECONDS)

    def test_entry_selection_is_explicit_and_wrapper_uses_it(self) -> None:
        self.assertIn(
            "rehearsal.ServiceQuiescenceRehearsalAdapter =",
            self.entry_source,
        )
        self.assertIn(
            "ServiceQuiescenceRehearsalAdapterV2",
            self.entry_source,
        )
        self.assertIn("rehearsal.main()", self.entry_source)
        self.assertIn(
            "python3 -m stage_c_transaction.service_quiescence_rehearsal_v2",
            self.wrapper_source,
        )
        self.assertIn(
            "polls the strict DAC runtime contract for up to 30 seconds",
            self.wrapper_source,
        )

    def test_corrected_layer_adds_no_appliance_mutation_command(self) -> None:
        combined = self.source + self.entry_source
        for forbidden in (
            "systemctl",
            "amixer",
            "modprobe",
            "rmmod",
            "aplay",
            "arecord",
            "install_managed_files(",
            "select_split_bus_route(",
            "start_managed_stage_c_services(",
        ):
            self.assertNotIn(forbidden, combined)

    def test_new_python_and_existing_wrapper_syntax(self) -> None:
        for path in (ADAPTER, ENTRY):
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        result = subprocess.run(
            ("bash", "-n", str(WRAPPER)),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout={result.stdout}\nstderr={result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
