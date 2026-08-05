from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from stage_c_runtime_authority.install_runtime_executor import (
    InstallRuntimeExecutionError,
    InstallRuntimeHostAdapter,
    run_install_route_entry,
    run_install_supervisor_startup,
)
from stage_c_runtime_authority.model import ActivationApprovalRecord, ApprovalPhase, RuntimeAuthorityError
from stage_c_runtime_authority.supervisor_model import PreparedRoute, SupervisorMode


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
HASH_E = "e" * 64


def temporary_approval() -> ActivationApprovalRecord:
    return ActivationApprovalRecord(
        schema_version=1,
        phase=ApprovalPhase.TEMPORARY,
        transaction_id="stage-c21-install-test",
        lock_lease_id="stage-c21-install-lease",
        package_fingerprint=HASH_A,
        commit_manifest_sha256=None,
        active_route_sha256=HASH_B,
        direct_route_sha256=HASH_C,
        camilladsp_config_sha256=HASH_D,
        camilladsp_binary_version="4.1.3",
        camilladsp_binary_sha256=HASH_E,
        loopback_index=7,
        loopback_id="ACP_Loopback",
        loopback_pcm_substreams=2,
        loopback_pcm_notify=1,
        dac_card="Pro",
        dac_device=0,
        sample_rate=44100,
        sample_format="S16_LE",
        period_size=1024,
        buffer_size=8192,
        created_at="2026-08-05T20:00:00Z",
        committed_at=None,
    )


@dataclass
class RecordingInstallAdapter:
    approval: ActivationApprovalRecord = field(default_factory=temporary_approval)
    fail_at: str | tuple[str, ...] | None = None
    child_start_succeeds: bool = True
    health_succeeds: bool = True
    operations: list[str] = field(default_factory=list)
    borrowed: bool = False
    prepared: bool = False
    split_active: bool = False
    ready: bool = False

    def _record(self, operation: str) -> None:
        self.operations.append(operation)
        failures = (self.fail_at,) if isinstance(self.fail_at, str) else self.fail_at or ()
        if operation in failures:
            raise RuntimeAuthorityError(f"injected failure at {operation}")

    def read_temporary_approval(self) -> ActivationApprovalRecord:
        self._record("read-temporary-approval")
        return self.approval

    def assert_borrowed_transaction_lock(self) -> str:
        self._record("assert-borrowed-transaction-lock")
        if self.borrowed:
            raise RuntimeAuthorityError("borrowed assertion already held")
        self.borrowed = True
        return self.approval.lock_lease_id

    def release_borrowed_transaction_lock_assertion(self, lease_id: str) -> None:
        self._record("release-borrowed-transaction-lock-assertion")
        if not self.borrowed or lease_id != self.approval.lock_lease_id:
            raise RuntimeAuthorityError("borrowed assertion identity mismatch")
        self.borrowed = False

    def validate_install_prepared_contract(self) -> ActivationApprovalRecord:
        self._record("validate-install-prepared-contract")
        if not self.borrowed:
            raise RuntimeAuthorityError("validation lacks borrowed assertion")
        return self.approval

    def publish_install_prepared_route(self, reason: str) -> None:
        self._record("publish-install-prepared-route")
        if not self.borrowed or not reason:
            raise RuntimeAuthorityError("invalid preparation publication")
        self.prepared = True

    def read_install_prepared_route(self) -> PreparedRoute:
        self._record("read-install-prepared-route")
        if not self.borrowed or not self.prepared:
            raise RuntimeAuthorityError("split route was not prepared")
        return PreparedRoute.SPLIT_PENDING

    def start_camilladsp_child(self) -> bool:
        self._record("start-camilladsp-child")
        return self.child_start_succeeds

    def verify_split_bus_health(self) -> bool:
        self._record("verify-split-bus-health")
        return self.health_succeeds

    def stop_camilladsp_child(self) -> None:
        self._record("stop-camilladsp-child")

    def publish_install_split_active(self, reason: str) -> None:
        self._record("publish-install-split-active")
        if not self.borrowed or not reason:
            raise RuntimeAuthorityError("invalid split-active publication")
        self.split_active = True

    def notify_systemd_ready(self, mode: SupervisorMode, reason: str) -> None:
        self._record("notify-systemd-ready")
        if self.borrowed:
            raise RuntimeAuthorityError("readiness while borrowed assertion open")
        if mode is not SupervisorMode.SPLIT_ACTIVE or not self.split_active or not reason:
            raise RuntimeAuthorityError("invalid install readiness")
        self.ready = True


class StageCInstallRuntimeExecutorTests(unittest.TestCase):
    def test_recording_adapter_conforms_to_fixed_install_protocol(self):
        self.assertIsInstance(RecordingInstallAdapter(), InstallRuntimeHostAdapter)

    def test_route_entry_only_validates_and_publishes_pending_split(self):
        adapter = RecordingInstallAdapter()
        receipt = run_install_route_entry(adapter)
        self.assertEqual(
            adapter.operations,
            [
                "assert-borrowed-transaction-lock",
                "validate-install-prepared-contract",
                "publish-install-prepared-route",
                "release-borrowed-transaction-lock-assertion",
            ],
        )
        self.assertTrue(adapter.prepared)
        self.assertFalse(adapter.borrowed)
        self.assertFalse(adapter.ready)
        self.assertFalse(receipt.systemd_ready)
        self.assertFalse(receipt.split_bus_healthy)

    def test_route_entry_failure_closes_assertion_and_withholds_readiness(self):
        adapter = RecordingInstallAdapter(fail_at="publish-install-prepared-route")
        with self.assertRaises(RuntimeAuthorityError):
            run_install_route_entry(adapter)
        self.assertFalse(adapter.borrowed)
        self.assertFalse(adapter.ready)
        self.assertEqual(
            adapter.operations[-1],
            "release-borrowed-transaction-lock-assertion",
        )

    def test_healthy_first_start_publishes_health_closes_assertion_then_notifies(self):
        adapter = RecordingInstallAdapter(prepared=True)
        decision, receipt = run_install_supervisor_startup(adapter)
        self.assertIs(decision.mode, SupervisorMode.SPLIT_ACTIVE)
        self.assertTrue(receipt.systemd_ready)
        self.assertTrue(receipt.split_bus_healthy)
        self.assertTrue(adapter.ready)
        self.assertFalse(adapter.borrowed)
        self.assertLess(
            adapter.operations.index("publish-install-split-active"),
            adapter.operations.index("release-borrowed-transaction-lock-assertion"),
        )
        self.assertLess(
            adapter.operations.index("release-borrowed-transaction-lock-assertion"),
            adapter.operations.index("notify-systemd-ready"),
        )
        self.assertNotIn("stop-camilladsp-child", adapter.operations)

    def test_child_start_or_health_failure_stops_child_and_returns_to_transaction(self):
        for changes in (
            {"child_start_succeeds": False},
            {"health_succeeds": False},
        ):
            with self.subTest(changes=changes):
                adapter = RecordingInstallAdapter(prepared=True, **changes)
                with self.assertRaises(InstallRuntimeExecutionError):
                    run_install_supervisor_startup(adapter)
                self.assertIn("stop-camilladsp-child", adapter.operations)
                self.assertFalse(adapter.borrowed)
                self.assertFalse(adapter.ready)
                self.assertFalse(adapter.split_active)
                self.assertFalse(any("direct" in item for item in adapter.operations))

    def test_health_publication_failure_stops_child_and_withholds_ready(self):
        adapter = RecordingInstallAdapter(
            prepared=True,
            fail_at="publish-install-split-active",
        )
        with self.assertRaises(InstallRuntimeExecutionError):
            run_install_supervisor_startup(adapter)
        self.assertIn("stop-camilladsp-child", adapter.operations)
        self.assertFalse(adapter.borrowed)
        self.assertFalse(adapter.ready)

    def test_notify_failure_does_not_double_close_borrowed_assertion(self):
        adapter = RecordingInstallAdapter(
            prepared=True,
            fail_at="notify-systemd-ready",
        )
        with self.assertRaises(InstallRuntimeExecutionError):
            run_install_supervisor_startup(adapter)
        self.assertEqual(
            adapter.operations.count("release-borrowed-transaction-lock-assertion"),
            1,
        )
        self.assertFalse(adapter.borrowed)
        self.assertIn("stop-camilladsp-child", adapter.operations)

    def test_failed_cleanup_reports_stop_or_assertion_failure_without_ready(self):
        stop_failure = RecordingInstallAdapter(
            prepared=True,
            health_succeeds=False,
            fail_at="stop-camilladsp-child",
        )
        with self.assertRaisesRegex(InstallRuntimeExecutionError, "stop both failed"):
            run_install_supervisor_startup(stop_failure)
        self.assertFalse(stop_failure.ready)

        close_failure = RecordingInstallAdapter(
            prepared=True,
            health_succeeds=False,
            fail_at="release-borrowed-transaction-lock-assertion",
        )
        with self.assertRaisesRegex(InstallRuntimeExecutionError, "assertion unresolved"):
            run_install_supervisor_startup(close_failure)
        self.assertFalse(close_failure.ready)
        self.assertTrue(close_failure.borrowed)

    def test_executor_contains_no_direct_failback_or_lock_acquisition(self):
        source = (SCRIPTS / "stage_c_runtime_authority/install_runtime_executor.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("select_direct_failback_route", source)
        self.assertNotIn("acquire_production_lock", source)
        self.assertNotIn("release_production_lock", source)
        self.assertNotIn("run_runtime_child_failure", source)
        self.assertIn("readiness withheld", source)
        self.assertIn("transaction rollback required", source)


if __name__ == "__main__":
    unittest.main()
