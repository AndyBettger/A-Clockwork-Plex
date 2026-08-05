from __future__ import annotations

import hashlib
import sys
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from stage_c_runtime_authority.model import (  # noqa: E402
    ApprovalPhase,
    BootObservation,
    CommitObservation,
    HardwareContract,
    InstallHandoffObservation,
    RuntimeAction,
    RuntimeAuthorityError,
    RuntimeMode,
    UnitObservation,
)
from stage_c_runtime_authority.state_machine import (  # noqa: E402
    accept_install_handoff,
    decide_boot,
    fixed_runtime_action_vocabulary,
    promote_committed_approval,
)


def digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def contract() -> HardwareContract:
    return HardwareContract(
        package_fingerprint=digest("package"),
        split_route_sha256=digest("split"),
        direct_route_sha256=digest("direct"),
        camilladsp_config_sha256=digest("config"),
        camilladsp_binary_version="4.1.3",
        camilladsp_binary_sha256=digest("binary"),
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
    )


def units() -> tuple[UnitObservation, ...]:
    return (
        UnitObservation("a-clockwork-plex-audio-route.service", "loaded", "inactive", "dead", "disabled"),
        UnitObservation("a-clockwork-plex-camilladsp.service", "loaded", "inactive", "dead", "disabled"),
        UnitObservation("a-clockwork-plex-audio-failback.service", "loaded", "inactive", "dead", "static"),
    )


def handoff(c: HardwareContract) -> InstallHandoffObservation:
    return InstallHandoffObservation(
        transaction_id="stage-c21-transaction",
        lock_lease_id="stage-c21-lease",
        production_lock_held=True,
        candidate_validated=True,
        package_fingerprint=c.package_fingerprint,
        active_route_sha256=c.split_route_sha256,
        installed_file_count=12,
        managed_units=units(),
        dac_released=True,
        loopback_playback_released=True,
    )


def boot(c: HardwareContract, *, start: bool, health: bool) -> BootObservation:
    return BootObservation(
        **c.as_dict(),
        managed_files_valid=True,
        split_route_valid=True,
        direct_route_valid=True,
        loopback_valid=True,
        dac_valid=True,
        camilladsp_start_succeeded=start,
        split_bus_health_valid=health,
    )


def committed_record(c: HardwareContract):
    temporary, _ = accept_install_handoff(handoff(c), c, created_at="2026-08-05T19:30:00Z")
    return temporary.promote(commit_manifest_sha256=digest("commit"), committed_at="2026-08-05T19:31:00Z")


class StageCRuntimeAuthorityCoreTests(unittest.TestCase):
    def test_install_handoff_uses_existing_lock_and_does_not_reselect_route(self):
        c = contract()
        record, decision = accept_install_handoff(handoff(c), c, created_at="2026-08-05T19:30:00Z")
        self.assertEqual(record.phase, ApprovalPhase.TEMPORARY)
        self.assertEqual(decision.actions, (RuntimeAction.ACCEPT_INSTALL_HANDOFF, RuntimeAction.PUBLISH_TEMPORARY_APPROVAL))
        self.assertNotIn(RuntimeAction.ACQUIRE_PRODUCTION_LOCK, decision.actions)
        self.assertNotIn(RuntimeAction.SELECT_SPLIT_BUS_ROUTE, decision.actions)
        self.assertNotIn(RuntimeAction.START_CAMILLADSP, decision.actions)

    def test_install_handoff_fails_closed_on_each_critical_gate(self):
        c = contract()
        base = handoff(c)
        mutations = (
            {"production_lock_held": False},
            {"candidate_validated": False},
            {"package_fingerprint": digest("wrong")},
            {"active_route_sha256": digest("wrong-route")},
            {"installed_file_count": 11},
            {"dac_released": False},
            {"loopback_playback_released": False},
            {"managed_units": tuple(reversed(units()))},
        )
        for values in mutations:
            with self.subTest(values=values), self.assertRaises(RuntimeAuthorityError):
                accept_install_handoff(replace(base, **values), c, created_at="2026-08-05T19:30:00Z")

    def test_temporary_approval_promotes_only_after_commit_and_health(self):
        c = contract()
        temporary, _ = accept_install_handoff(handoff(c), c, created_at="2026-08-05T19:30:00Z")
        observation = CommitObservation(
            transaction_id=temporary.transaction_id,
            lock_lease_id=temporary.lock_lease_id,
            production_lock_held=True,
            install_committed=True,
            split_bus_healthy=True,
            active_route_sha256=c.split_route_sha256,
            commit_manifest_sha256=digest("commit"),
        )
        committed, decision = promote_committed_approval(temporary, observation, committed_at="2026-08-05T19:31:00Z")
        self.assertEqual(committed.phase, ApprovalPhase.COMMITTED)
        self.assertEqual(decision.actions, (RuntimeAction.PROMOTE_COMMITTED_APPROVAL,))

    def test_boot_success_has_fixed_split_bus_sequence(self):
        decision = decide_boot(committed_record(contract()), boot(contract(), start=True, health=True))
        self.assertEqual(decision.mode, RuntimeMode.SPLIT_BUS_ACTIVE)
        self.assertEqual(decision.actions[0], RuntimeAction.ACQUIRE_PRODUCTION_LOCK)
        self.assertEqual(decision.actions[-1], RuntimeAction.RELEASE_PRODUCTION_LOCK)
        self.assertIn(RuntimeAction.PUBLISH_SPLIT_BUS_ACTIVE, decision.actions)
        self.assertNotIn(RuntimeAction.SELECT_DIRECT_FAILBACK_ROUTE, decision.actions)

    def test_boot_camilladsp_failure_selects_direct_failback(self):
        c = contract()
        decision = decide_boot(committed_record(c), boot(c, start=False, health=False))
        self.assertEqual(decision.mode, RuntimeMode.DIRECT_FAILBACK)
        self.assertIn(RuntimeAction.STOP_CAMILLADSP, decision.actions)
        self.assertIn(RuntimeAction.SELECT_DIRECT_FAILBACK_ROUTE, decision.actions)
        self.assertIn(RuntimeAction.PUBLISH_DIRECT_FAILBACK, decision.actions)

    def test_boot_loopback_or_binary_failure_uses_alarm_safe_direct_route(self):
        c = contract()
        committed = committed_record(c)
        observations = (
            replace(boot(c, start=True, health=True), loopback_valid=False),
            replace(boot(c, start=True, health=True), camilladsp_binary_sha256=digest("changed-binary")),
        )
        for observation in observations:
            with self.subTest(observation=observation):
                decision = decide_boot(committed, observation)
                self.assertEqual(decision.mode, RuntimeMode.DIRECT_FAILBACK)
                self.assertIn(RuntimeAction.SELECT_DIRECT_FAILBACK_ROUTE, decision.actions)

    def test_boot_refuses_temporary_approval_and_direct_contract_mismatch(self):
        c = contract()
        temporary, _ = accept_install_handoff(handoff(c), c, created_at="2026-08-05T19:30:00Z")
        with self.assertRaises(RuntimeAuthorityError):
            decide_boot(temporary, boot(c, start=True, health=True))
        with self.assertRaises(RuntimeAuthorityError):
            decide_boot(committed_record(c), replace(boot(c, start=True, health=True), package_fingerprint=digest("other")))

    def test_approval_timestamps_are_canonical_utc(self):
        c = contract()
        with self.assertRaises(RuntimeAuthorityError):
            accept_install_handoff(handoff(c), c, created_at="2026-08-05 19:30:00")
        temporary, _ = accept_install_handoff(handoff(c), c, created_at="2026-08-05T19:30:00Z")
        with self.assertRaises(RuntimeAuthorityError):
            temporary.promote(commit_manifest_sha256=digest("commit"), committed_at="2026-08-05T20:31:00+01:00")

    def test_action_vocabulary_is_fixed_and_contains_no_arbitrary_dispatch(self):
        values = fixed_runtime_action_vocabulary()
        self.assertEqual(values, tuple(action.value for action in RuntimeAction))
        self.assertEqual(len(values), len(set(values)))
        for forbidden in ("run-command", "write-path", "start-unit", "dispatch"):
            self.assertNotIn(forbidden, values)


if __name__ == "__main__":
    unittest.main()
