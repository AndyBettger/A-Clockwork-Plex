from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from stage_c_runtime_authority.model import (
    ActivationApprovalRecord,
    ApprovalPhase,
    BootObservation,
    RuntimeAuthorityError,
)
from stage_c_runtime_authority.recording_runtime_adapter import RecordingRuntimeHostAdapter
from stage_c_runtime_authority.runtime_executor import (
    RuntimeExecutionError,
    RuntimeHostAdapter,
    run_boot_preparation,
    run_runtime_child_failure,
    run_supervisor_startup,
)
from stage_c_runtime_authority.supervisor_model import PreparedRoute, SupervisorMode


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
HASH_E = "e" * 64
HASH_F = "f" * 64


def committed_record() -> ActivationApprovalRecord:
    return ActivationApprovalRecord(
        schema_version=1,
        phase=ApprovalPhase.COMMITTED,
        transaction_id="stage-c21-install-transaction",
        lock_lease_id="stage-c21-production-lock",
        package_fingerprint=HASH_A,
        commit_manifest_sha256=HASH_F,
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
        committed_at="2026-08-05T20:01:00Z",
    )


def boot_observation(**changes: object) -> BootObservation:
    values: dict[str, object] = {
        "package_fingerprint": HASH_A,
        "split_route_sha256": HASH_B,
        "direct_route_sha256": HASH_C,
        "camilladsp_config_sha256": HASH_D,
        "camilladsp_binary_version": "4.1.3",
        "camilladsp_binary_sha256": HASH_E,
        "loopback_index": 7,
        "loopback_id": "ACP_Loopback",
        "loopback_pcm_substreams": 2,
        "loopback_pcm_notify": 1,
        "dac_card": "Pro",
        "dac_device": 0,
        "sample_rate": 44100,
        "sample_format": "S16_LE",
        "period_size": 1024,
        "buffer_size": 8192,
        "managed_files_valid": True,
        "split_route_valid": True,
        "direct_route_valid": True,
        "loopback_valid": True,
        "dac_valid": True,
        "camilladsp_start_succeeded": False,
        "split_bus_health_valid": False,
    }
    values.update(changes)
    return BootObservation(**values)


def adapter(**changes: object) -> RecordingRuntimeHostAdapter:
    values: dict[str, object] = {
        "approval": committed_record(),
        "boot_observation": boot_observation(),
    }
    values.update(changes)
    return RecordingRuntimeHostAdapter(**values)


class StageCRuntimeExecutorTests(unittest.TestCase):
    def test_recording_adapter_conforms_to_fixed_protocol(self):
        self.assertIsInstance(adapter(), RuntimeHostAdapter)

    def test_healthy_boot_preparation_selects_split_without_readiness(self):
        host = adapter()
        decision, receipt = run_boot_preparation(host)
        self.assertIs(decision.prepared_route, PreparedRoute.SPLIT_PENDING)
        self.assertEqual(
            host.operations,
            [
                "acquire-production-lock",
                "read-committed-approval",
                "observe-boot-contract",
                "select-split-bus-route",
                "publish-prepared-route:split-bus-pending-health",
                "release-production-lock",
            ],
        )
        self.assertTrue(receipt.lock_released)
        self.assertFalse(receipt.systemd_ready)
        self.assertFalse(host.ready_notified)

    def test_preflight_failure_prepares_direct_route_without_child(self):
        host = adapter(boot_observation=boot_observation(loopback_valid=False))
        decision, receipt = run_boot_preparation(host)
        self.assertIs(decision.prepared_route, PreparedRoute.DIRECT_READY)
        self.assertIn("select-direct-failback-route", host.operations)
        self.assertNotIn("start-camilladsp-child", host.operations)
        self.assertFalse(receipt.systemd_ready)

    def test_boot_publication_failure_completes_direct_failback_and_returns_safe_success(self):
        host = adapter(fail_at="publish-prepared-route:split-bus-pending-health")
        decision, receipt = run_boot_preparation(host)
        self.assertIs(decision.prepared_route, PreparedRoute.DIRECT_READY)
        self.assertEqual(host.runtime_mode, SupervisorMode.DIRECT_FAILBACK)
        self.assertTrue(host.lock_released)
        self.assertIn("select-direct-failback-route", host.operations)
        self.assertIn("publish-runtime-mode:direct-failback", host.operations)
        self.assertFalse(receipt.systemd_ready)

    def test_pre_mutation_observation_failure_releases_lock_and_raises(self):
        host = adapter(fail_at="read-committed-approval")
        with self.assertRaises(RuntimeAuthorityError):
            run_boot_preparation(host)
        self.assertFalse(host.lock_held)
        self.assertTrue(host.lock_released)
        self.assertNotIn("select-direct-failback-route", host.operations)

    def test_boot_failure_and_failed_direct_recovery_retain_lock(self):
        host = adapter(
            fail_at=(
                "publish-prepared-route:split-bus-pending-health",
                "select-direct-failback-route",
            )
        )
        with self.assertRaisesRegex(RuntimeExecutionError, "lock retained"):
            run_boot_preparation(host)
        self.assertTrue(host.lock_held)
        self.assertFalse(host.lock_released)

    def test_healthy_supervisor_publishes_split_before_ready(self):
        host = adapter(prepared_route=PreparedRoute.SPLIT_PENDING)
        decision, receipt = run_supervisor_startup(host)
        self.assertIs(decision.mode, SupervisorMode.SPLIT_ACTIVE)
        self.assertTrue(receipt.systemd_ready)
        self.assertLess(
            host.operations.index("publish-runtime-mode:split-bus-active"),
            host.operations.index("notify-systemd-ready:split-bus-active"),
        )
        self.assertLess(
            host.operations.index("release-production-lock"),
            host.operations.index("notify-systemd-ready:split-bus-active"),
        )

    def test_child_start_failure_completes_direct_route_before_ready(self):
        host = adapter(
            prepared_route=PreparedRoute.SPLIT_PENDING,
            child_start_succeeds=False,
        )
        decision, receipt = run_supervisor_startup(host)
        self.assertIs(decision.mode, SupervisorMode.DIRECT_FAILBACK)
        self.assertTrue(receipt.systemd_ready)
        self.assertLess(
            host.operations.index("publish-runtime-mode:direct-failback"),
            host.operations.index("notify-systemd-ready:direct-failback"),
        )
        self.assertTrue(host.ready_notified)

    def test_prepared_direct_supervisor_does_not_reselect_or_republish(self):
        host = adapter(prepared_route=PreparedRoute.DIRECT_READY)
        decision, receipt = run_supervisor_startup(host)
        self.assertIs(decision.mode, SupervisorMode.DIRECT_FAILBACK)
        self.assertTrue(receipt.systemd_ready)
        self.assertNotIn("start-camilladsp-child", host.operations)
        self.assertNotIn("select-direct-failback-route", host.operations)
        self.assertNotIn("publish-runtime-mode:direct-failback", host.operations)
        self.assertIn("notify-systemd-ready:direct-failback", host.operations)

    def test_supervisor_exception_recovers_to_direct_and_notifies_ready(self):
        host = adapter(
            prepared_route=PreparedRoute.SPLIT_PENDING,
            fail_at="verify-split-bus-health",
        )
        decision, receipt = run_supervisor_startup(host)
        self.assertIs(decision.mode, SupervisorMode.DIRECT_FAILBACK)
        self.assertTrue(receipt.systemd_ready)
        self.assertTrue(host.lock_released)
        self.assertTrue(host.ready_notified)

    def test_failed_supervisor_recovery_withholds_ready_and_retains_lock(self):
        host = adapter(
            prepared_route=PreparedRoute.SPLIT_PENDING,
            fail_at=("verify-split-bus-health", "select-direct-failback-route"),
        )
        with self.assertRaisesRegex(RuntimeExecutionError, "readiness withheld and lock retained"):
            run_supervisor_startup(host)
        self.assertTrue(host.lock_held)
        self.assertFalse(host.ready_notified)

    def test_runtime_child_failure_switches_direct_without_application_restart(self):
        host = adapter(prepared_route=PreparedRoute.SPLIT_PENDING)
        decision, receipt = run_runtime_child_failure(host)
        self.assertIs(decision.mode, SupervisorMode.DIRECT_FAILBACK)
        self.assertTrue(receipt.lock_released)
        self.assertIn("stop-camilladsp-child", host.operations)
        self.assertIn("select-direct-failback-route", host.operations)
        self.assertIn("publish-runtime-mode:direct-failback", host.operations)
        self.assertFalse(any("plexamp" in operation for operation in host.operations))
        self.assertFalse(any("shairport" in operation for operation in host.operations))

    def test_runtime_failback_failure_retains_lock(self):
        host = adapter(fail_at="publish-runtime-mode:direct-failback")
        with self.assertRaisesRegex(RuntimeExecutionError, "lock retained"):
            run_runtime_child_failure(host)
        self.assertTrue(host.lock_held)

    def test_executor_and_recording_adapter_have_no_host_command_boundary(self):
        combined = "\n".join(
            (SCRIPTS / f"stage_c_runtime_authority/{name}").read_text(encoding="utf-8")
            for name in ("runtime_executor.py", "recording_runtime_adapter.py")
        )
        for forbidden in (
            "subprocess",
            "systemctl",
            "aplay",
            "amixer",
            "NOTIFY_SOCKET",
            "os.exec",
            "shell=True",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
