from __future__ import annotations

import subprocess
import sys
import unittest

from app.playback_handoff import BidirectionalHandoffPlaybackCoordinator


class BidirectionalHandoffPlaybackCoordinatorTests(unittest.TestCase):
    def coordinator(
        self,
        *,
        remote: dict | None = None,
        plexamp: dict | None = None,
        airplay_commands: list[str] | None = None,
        mutate_remote_on_pause: bool = True,
        command_ok: bool = True,
    ) -> BidirectionalHandoffPlaybackCoordinator:
        remote_state = remote if remote is not None else {
            "available": True,
            "playback_status": "Playing",
            "can_control": True,
            "can_play": True,
            "can_pause": True,
        }
        plexamp_state = plexamp if plexamp is not None else {
            "available": True,
            "playback_state": "paused",
            "percent": 75,
        }
        commands = airplay_commands if airplay_commands is not None else []

        def airplay_command(action: str):
            commands.append(action)
            if not command_ok:
                return False, "adapter failed"
            if action == "pause" and mutate_remote_on_pause:
                remote_state["playback_status"] = "Paused"
            return True, None

        def pause_plexamp():
            plexamp_state["playback_state"] = "paused"
            return True, None

        return BidirectionalHandoffPlaybackCoordinator(
            load_config=lambda: {"dashboard": {"default_mode": "clock"}},
            load_state=lambda _config: {
                "mode": "plexamp",
                "airplay": {
                    "active": remote_state.get("available") is True,
                    "started_at": "2026-07-28T20:00:00+01:00",
                    "ended_at": None,
                    "metadata": {},
                },
            },
            plexamp_status=lambda: dict(plexamp_state),
            airplay_status=lambda: dict(remote_state),
            alarm_status=lambda: {"screen_required": False},
            alarm_audio_status=lambda: {"playback_active": False},
            airplay_command=airplay_command,
            plexamp_pause=pause_plexamp,
            airplay_hold_seconds=600,
            reconcile_seconds=0.05,
            command_verify_seconds=20,
        )

    def test_plexamp_transition_pauses_airplay_once_and_cedes_ownership(self):
        commands: list[str] = []
        plexamp = {"available": True, "playback_state": "paused", "percent": 75}
        coordinator = self.coordinator(plexamp=plexamp, airplay_commands=commands)

        coordinator.snapshot()  # Prime the observed paused state.
        plexamp["playback_state"] = "playing"
        first = coordinator.snapshot()
        second = coordinator.snapshot()

        self.assertEqual(commands, ["pause"])
        self.assertEqual(first["active_source"], "plexamp")
        self.assertEqual(first["decision_reason"], "plexamp-takeover")
        self.assertEqual(first["recommended_screen"], "plexamp")
        self.assertTrue(first["screen_in_sync"])
        self.assertEqual(first["sources"]["airplay"]["ownership"], "ceded-to-plexamp")
        self.assertEqual(first["sources"]["airplay"]["hold"]["phase"], "ceded-to-plexamp")
        self.assertFalse(first["sources"]["airplay"]["hold"]["active"])
        handoff = first["handoffs"]["plexamp_to_airplay"]
        self.assertEqual(handoff["status"], "confirmed")
        self.assertEqual(handoff["command_count"], 1)
        self.assertEqual(second["handoffs"]["plexamp_to_airplay"]["command_count"], 1)

    def test_current_playing_state_on_startup_is_primed_not_treated_as_new_intent(self):
        commands: list[str] = []
        plexamp = {"available": True, "playback_state": "playing", "percent": 75}
        coordinator = self.coordinator(plexamp=plexamp, airplay_commands=commands)

        coordinator.snapshot()

        self.assertEqual(commands, [])
        self.assertEqual(coordinator.reverse_handoff_snapshot()["status"], "idle")

    def test_starting_plexamp_during_airplay_hold_cedes_without_redundant_pause(self):
        commands: list[str] = []
        remote = {
            "available": True,
            "playback_status": "Paused",
            "can_control": True,
            "can_play": True,
            "can_pause": True,
        }
        plexamp = {"available": True, "playback_state": "paused", "percent": 75}
        coordinator = self.coordinator(remote=remote, plexamp=plexamp, airplay_commands=commands)

        coordinator.snapshot()
        coordinator.record_event("airplay", "paused", {"origin": "iphone-pause"})
        self.assertTrue(coordinator.snapshot()["sources"]["airplay"]["hold"]["active"])

        plexamp["playback_state"] = "playing"
        snapshot = coordinator.snapshot()

        self.assertEqual(commands, [])
        self.assertEqual(snapshot["active_source"], "plexamp")
        self.assertFalse(snapshot["sources"]["airplay"]["hold"]["active"])
        self.assertEqual(snapshot["sources"]["airplay"]["hold"]["phase"], "ceded-to-plexamp")
        self.assertEqual(snapshot["handoffs"]["plexamp_to_airplay"]["status"], "not-needed")

    def test_late_shairport_pause_confirms_without_rearming_hold(self):
        commands: list[str] = []
        plexamp = {"available": True, "playback_state": "paused", "percent": 75}
        coordinator = self.coordinator(
            plexamp=plexamp,
            airplay_commands=commands,
            mutate_remote_on_pause=False,
        )

        coordinator.snapshot()
        plexamp["playback_state"] = "playing"
        awaiting = coordinator.snapshot()
        self.assertEqual(awaiting["handoffs"]["plexamp_to_airplay"]["status"], "accepted-awaiting-observation")
        self.assertEqual(awaiting["sources"]["airplay"]["hold"]["phase"], "ceded-to-plexamp")

        coordinator.record_event("airplay", "paused", {"origin": "shairport-end-wrapper"})
        confirmed = coordinator.snapshot()

        self.assertEqual(confirmed["handoffs"]["plexamp_to_airplay"]["status"], "confirmed")
        self.assertEqual(confirmed["sources"]["airplay"]["hold"]["phase"], "ceded-to-plexamp")
        self.assertFalse(confirmed["sources"]["airplay"]["hold"]["active"])

    def test_failed_pause_is_reported_and_not_retried_in_same_plexamp_episode(self):
        commands: list[str] = []
        plexamp = {"available": True, "playback_state": "paused", "percent": 75}
        coordinator = self.coordinator(
            plexamp=plexamp,
            airplay_commands=commands,
            command_ok=False,
        )

        coordinator.snapshot()
        plexamp["playback_state"] = "playing"
        first = coordinator.snapshot()
        second = coordinator.snapshot()

        self.assertEqual(commands, ["pause"])
        self.assertEqual(first["handoffs"]["plexamp_to_airplay"]["status"], "failed")
        self.assertEqual(second["handoffs"]["plexamp_to_airplay"]["command_count"], 0)
        self.assertEqual(first["active_source"], "airplay")

    def test_real_runner_promotes_bidirectional_handoff_before_apis(self):
        code = (
            "from app.runner import app, application_state_hub; "
            "from app.playback_handoff import BidirectionalHandoffPlaybackCoordinator; "
            "coordinator=application_state_hub.service('playback'); "
            "assert isinstance(coordinator, BidirectionalHandoffPlaybackCoordinator); "
            "state=coordinator.snapshot(); "
            "assert state['command_capabilities']['plexamp_to_airplay_handoff'] is True; "
            "assert state['command_capabilities']['automatic_arbitration'] is True"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
