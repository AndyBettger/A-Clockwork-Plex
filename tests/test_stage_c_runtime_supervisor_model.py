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
from stage_c_runtime_authority.supervisor_model import (
    PreparedRoute,
    SupervisorAction,
    SupervisorMode,
    SupervisorStartupObservation,
    child_failure_failback,
    prepare_boot,
    start_supervisor,
)


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


class StageCRuntimeSupervisorModelTests(unittest.TestCase):
    def test_boot_prepare_stops_before_camilladsp_or_systemd_readiness(self):
        decision = prepare_boot(committed_record(), boot_observation())
        self.assertIs(decision.prepared_route, PreparedRoute.SPLIT_PENDING)
        self.assertEqual(
            decision.actions,
            (
                SupervisorAction.ACQUIRE_PRODUCTION_LOCK,
                SupervisorAction.VALIDATE_COMMITTED_STATE,
                SupervisorAction.SELECT_SPLIT_BUS_ROUTE,
                SupervisorAction.PUBLISH_SPLIT_PENDING,
                SupervisorAction.RELEASE_PRODUCTION_LOCK,
            ),
        )
        self.assertNotIn(SupervisorAction.START_CAMILLADSP_CHILD, decision.actions)
        self.assertNotIn(SupervisorAction.NOTIFY_SYSTEMD_READY, decision.actions)

    def test_split_preflight_failure_prepares_direct_route_before_applications(self):
        decision = prepare_boot(
            committed_record(),
            boot_observation(loopback_valid=False),
        )
        self.assertIs(decision.prepared_route, PreparedRoute.DIRECT_READY)
        self.assertIn(SupervisorAction.SELECT_DIRECT_FAILBACK_ROUTE, decision.actions)
        self.assertIn(SupervisorAction.PUBLISH_DIRECT_FAILBACK, decision.actions)
        self.assertNotIn(SupervisorAction.NOTIFY_SYSTEMD_READY, decision.actions)

    def test_invalid_direct_contract_fails_closed(self):
        with self.assertRaisesRegex(RuntimeAuthorityError, "direct-failback contract mismatch"):
            prepare_boot(committed_record(), boot_observation(direct_route_sha256=HASH_D))

    def test_healthy_supervisor_releases_gate_only_after_health_publication(self):
        decision = start_supervisor(
            SupervisorStartupObservation(
                prepared_route=PreparedRoute.SPLIT_PENDING,
                production_lock_held=True,
                camilladsp_child_started=True,
                split_bus_health_valid=True,
            )
        )
        self.assertIs(decision.mode, SupervisorMode.SPLIT_ACTIVE)
        self.assertLess(
            decision.actions.index(SupervisorAction.PUBLISH_SPLIT_ACTIVE),
            decision.actions.index(SupervisorAction.NOTIFY_SYSTEMD_READY),
        )
        self.assertEqual(
            decision.actions[-2:],
            (SupervisorAction.NOTIFY_SYSTEMD_READY, SupervisorAction.REMAIN_RUNTIME_SUPERVISOR),
        )

    def test_startup_failure_completes_direct_failback_before_readiness(self):
        decision = start_supervisor(
            SupervisorStartupObservation(
                prepared_route=PreparedRoute.SPLIT_PENDING,
                production_lock_held=True,
                camilladsp_child_started=False,
                split_bus_health_valid=False,
            )
        )
        self.assertIs(decision.mode, SupervisorMode.DIRECT_FAILBACK)
        self.assertLess(
            decision.actions.index(SupervisorAction.PUBLISH_DIRECT_FAILBACK),
            decision.actions.index(SupervisorAction.NOTIFY_SYSTEMD_READY),
        )
        self.assertIn(SupervisorAction.STOP_CAMILLADSP_CHILD, decision.actions)

    def test_prepared_direct_route_never_starts_camilladsp_child(self):
        decision = start_supervisor(
            SupervisorStartupObservation(
                prepared_route=PreparedRoute.DIRECT_READY,
                production_lock_held=True,
                camilladsp_child_started=False,
                split_bus_health_valid=False,
            )
        )
        self.assertIs(decision.mode, SupervisorMode.DIRECT_FAILBACK)
        self.assertNotIn(SupervisorAction.START_CAMILLADSP_CHILD, decision.actions)
        self.assertNotIn(SupervisorAction.SELECT_DIRECT_FAILBACK_ROUTE, decision.actions)

    def test_runtime_child_failure_fails_back_without_dropping_supervisor(self):
        decision = child_failure_failback(production_lock_held=True)
        self.assertIs(decision.mode, SupervisorMode.DIRECT_FAILBACK)
        self.assertLess(
            decision.actions.index(SupervisorAction.PUBLISH_DIRECT_FAILBACK),
            decision.actions.index(SupervisorAction.REMAIN_RUNTIME_SUPERVISOR),
        )
        self.assertTrue(decision.systemd_ready)

    def test_supervisor_paths_refuse_unheld_lock(self):
        with self.assertRaisesRegex(RuntimeAuthorityError, "requires the production lock"):
            start_supervisor(
                SupervisorStartupObservation(
                    prepared_route=PreparedRoute.SPLIT_PENDING,
                    production_lock_held=False,
                    camilladsp_child_started=True,
                    split_bus_health_valid=True,
                )
            )
        with self.assertRaisesRegex(RuntimeAuthorityError, "requires the production lock"):
            child_failure_failback(production_lock_held=False)

    def test_model_contains_no_host_execution_boundary(self):
        source = (SCRIPTS / "stage_c_runtime_authority/supervisor_model.py").read_text(encoding="utf-8")
        for forbidden in (
            "subprocess",
            "systemctl",
            "sd_notify",
            "NOTIFY_SOCKET",
            "aplay",
            "amixer",
            "os.exec",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
