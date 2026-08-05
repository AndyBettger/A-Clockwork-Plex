from __future__ import annotations

import signal
import sys
import unittest
from pathlib import Path
from unittest import mock


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
from stage_c_runtime_authority.supervisor_model import SupervisorMode
from stage_c_runtime_authority.supervisor_service import (
    SUPERVISOR_POLL_SECONDS,
    production_stop_event,
    supervise_lifetime,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
HASH_E = "e" * 64
HASH_F = "f" * 64


def approval(phase: ApprovalPhase) -> ActivationApprovalRecord:
    return ActivationApprovalRecord(
        schema_version=1,
        phase=phase,
        transaction_id="stage-c21-supervisor-test",
        lock_lease_id="stage-c21-supervisor-lease",
        package_fingerprint=HASH_A,
        commit_manifest_sha256=HASH_F if phase is ApprovalPhase.COMMITTED else None,
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
        committed_at="2026-08-05T20:01:00Z" if phase is ApprovalPhase.COMMITTED else None,
    )


def boot_observation() -> BootObservation:
    return BootObservation(
        package_fingerprint=HASH_A,
        split_route_sha256=HASH_B,
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
        managed_files_valid=True,
        split_route_valid=True,
        direct_route_valid=True,
        loopback_valid=True,
        dac_valid=True,
        camilladsp_start_succeeded=False,
        split_bus_health_valid=False,
    )


class SequencedEvent:
    def __init__(self, waits: list[bool]):
        self.waits = list(waits)
        self.timeouts: list[float] = []
        self.set_called = False

    def wait(self, timeout: float) -> bool:
        self.timeouts.append(timeout)
        if not self.waits:
            raise AssertionError("supervisor test exhausted its bounded event sequence")
        return self.waits.pop(0)

    def set(self) -> None:
        self.set_called = True


class StartupAdapter:
    def __init__(self, child_states: list[bool]):
        self.child_states = list(child_states)
        self.stop_count = 0

    @property
    def child_running(self) -> bool:
        if not self.child_states:
            return False
        if len(self.child_states) == 1:
            return self.child_states[0]
        return self.child_states.pop(0)

    def stop_camilladsp_child(self) -> None:
        self.stop_count += 1


class StageCSupervisorServiceTests(unittest.TestCase):
    def test_direct_mode_remains_alive_until_systemd_stop(self):
        startup = StartupAdapter([False])
        event = SequencedEvent([False, True])
        reader = mock.Mock(side_effect=AssertionError("approval should not be read in direct mode"))
        factory = mock.Mock(side_effect=AssertionError("failback adapter should not be created"))
        outcome = supervise_lifetime(
            startup,
            SupervisorMode.DIRECT_FAILBACK,
            approval_reader=reader,
            ordinary_adapter_factory=factory,
            stop_event=event,
        )
        self.assertEqual(outcome.exit_code, 0)
        self.assertIs(outcome.final_mode, SupervisorMode.DIRECT_FAILBACK)
        self.assertEqual(startup.stop_count, 1)
        self.assertEqual(event.timeouts, [SUPERVISOR_POLL_SECONDS, SUPERVISOR_POLL_SECONDS])
        reader.assert_not_called()
        factory.assert_not_called()

    def test_running_split_child_remains_alive_until_stop(self):
        startup = StartupAdapter([True, True])
        event = SequencedEvent([False, True])
        outcome = supervise_lifetime(
            startup,
            SupervisorMode.SPLIT_ACTIVE,
            approval_reader=lambda: approval(ApprovalPhase.COMMITTED),
            ordinary_adapter_factory=lambda: None,
            stop_event=event,
        )
        self.assertEqual(outcome.exit_code, 0)
        self.assertIs(outcome.final_mode, SupervisorMode.SPLIT_ACTIVE)
        self.assertEqual(startup.stop_count, 1)

    def test_precommit_child_exit_defers_to_exact_transaction_rollback(self):
        startup = StartupAdapter([False])
        event = SequencedEvent([False])
        factory = mock.Mock(side_effect=AssertionError("runtime failback must not run before commit"))
        outcome = supervise_lifetime(
            startup,
            SupervisorMode.SPLIT_ACTIVE,
            approval_reader=lambda: approval(ApprovalPhase.TEMPORARY),
            ordinary_adapter_factory=factory,
            stop_event=event,
        )
        self.assertEqual(outcome.exit_code, 1)
        self.assertIs(outcome.final_mode, SupervisorMode.SPLIT_ACTIVE)
        self.assertIn("transaction rollback required", outcome.reason)
        self.assertEqual(startup.stop_count, 1)
        factory.assert_not_called()

    def test_committed_child_exit_completes_direct_failback_then_stays_alive(self):
        startup = StartupAdapter([False])
        event = SequencedEvent([False, True])
        ordinary = RecordingRuntimeHostAdapter(
            approval=approval(ApprovalPhase.COMMITTED),
            boot_observation=boot_observation(),
        )
        outcome = supervise_lifetime(
            startup,
            SupervisorMode.SPLIT_ACTIVE,
            approval_reader=lambda: approval(ApprovalPhase.COMMITTED),
            ordinary_adapter_factory=lambda: ordinary,
            stop_event=event,
        )
        self.assertEqual(outcome.exit_code, 0)
        self.assertIs(outcome.final_mode, SupervisorMode.DIRECT_FAILBACK)
        self.assertIn("select-direct-failback-route", ordinary.operations)
        self.assertIn("publish-runtime-mode:direct-failback", ordinary.operations)
        self.assertLess(
            ordinary.operations.index("publish-runtime-mode:direct-failback"),
            ordinary.operations.index("release-production-lock"),
        )
        self.assertEqual(startup.stop_count, 1)

    def test_failed_committed_failback_raises_for_onfailure_unit(self):
        startup = StartupAdapter([False])
        event = SequencedEvent([False])
        ordinary = RecordingRuntimeHostAdapter(
            approval=approval(ApprovalPhase.COMMITTED),
            boot_observation=boot_observation(),
            fail_at="select-direct-failback-route",
        )
        with self.assertRaises(RuntimeAuthorityError):
            supervise_lifetime(
                startup,
                SupervisorMode.SPLIT_ACTIVE,
                approval_reader=lambda: approval(ApprovalPhase.COMMITTED),
                ordinary_adapter_factory=lambda: ordinary,
                stop_event=event,
            )
        self.assertTrue(ordinary.lock_held)
        self.assertNotIn("release-production-lock", ordinary.operations)

    def test_production_stop_event_installs_only_term_and_int_handlers(self):
        handlers: dict[int, object] = {}

        def record(signum: int, handler: object) -> None:
            handlers[signum] = handler

        with mock.patch("signal.signal", side_effect=record):
            event = production_stop_event()
        self.assertEqual(set(handlers), {signal.SIGTERM, signal.SIGINT})
        handlers[signal.SIGTERM](signal.SIGTERM, None)
        self.assertTrue(event.is_set())

    def test_service_policy_has_no_systemd_command_or_audio_device_boundary(self):
        source = (SCRIPTS / "stage_c_runtime_authority/supervisor_service.py").read_text(
            encoding="utf-8"
        )
        for forbidden in (
            "subprocess",
            "systemctl",
            "aplay",
            "amixer",
            "/dev/snd",
            "/etc/alsa",
            "os.replace",
            "fcntl.flock",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("ApprovalPhase.TEMPORARY", source)
        self.assertIn("run_runtime_child_failure", source)
        self.assertIn("production_stop_event", source)


if __name__ == "__main__":
    unittest.main()
