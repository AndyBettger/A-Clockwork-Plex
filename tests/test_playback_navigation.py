from __future__ import annotations

import subprocess
import sys
import unittest

from app.playback_navigation import NavigationTransportPlaybackCoordinator


class NavigationTransportPlaybackCoordinatorTests(unittest.TestCase):
    def coordinator(
        self,
        *,
        remote: dict | None = None,
        commands: list[str] | None = None,
        command_ok: bool = True,
    ) -> NavigationTransportPlaybackCoordinator:
        remote_state = remote if remote is not None else {
            "available": True,
            "playback_status": "Playing",
            "can_control": True,
            "can_play": True,
            "can_pause": True,
        }
        command_log = commands if commands is not None else []

        def send(action: str):
            command_log.append(action)
            return command_ok, None if command_ok else "adapter failed"

        return NavigationTransportPlaybackCoordinator(
            load_config=lambda: {"dashboard": {"default_mode": "clock"}},
            load_state=lambda _config: {
                "mode": "airplay",
                "airplay": {
                    "active": True,
                    "started_at": "2026-07-26T18:00:00+00:00",
                    "ended_at": None,
                    "metadata": {},
                },
            },
            plexamp_status=lambda: {"available": True, "playback_state": "paused"},
            airplay_status=lambda: remote_state,
            alarm_status=lambda: {"screen_required": False},
            alarm_audio_status=lambda: {"playback_active": False},
            airplay_command=send,
            airplay_hold_seconds=600,
            reconcile_seconds=0.05,
            command_verify_seconds=20,
        )

    def test_previous_and_next_use_adapter_acceptance_without_fake_state_confirmation(self):
        commands: list[str] = []
        coordinator = self.coordinator(commands=commands)

        previous = coordinator.command("airplay", "previous")
        following = coordinator.command("airplay", "next")

        self.assertEqual(commands, ["previous", "next"])
        self.assertEqual(previous["command"]["status"], "accepted")
        self.assertEqual(following["command"]["status"], "accepted")
        self.assertEqual(following["command"]["completion_policy"], "adapter-acceptance")
        self.assertEqual(following["command"]["observed_source"], "mpris-adapter")
        self.assertNotIn("target_state", following["command"])
        self.assertEqual(following["playback"]["sources"]["airplay"]["state"], "playing")
        self.assertFalse(following["playback"]["sources"]["airplay"]["hold"]["active"])

    def test_navigation_has_separate_command_record_and_capabilities(self):
        coordinator = self.coordinator()
        coordinator.command("airplay", "next")
        snapshot = coordinator.snapshot()

        self.assertIn("airplay", snapshot["commands"])
        self.assertIn("airplay_navigation", snapshot["commands"])
        self.assertEqual(snapshot["commands"]["airplay"]["status"], "idle")
        self.assertEqual(snapshot["commands"]["airplay_navigation"]["action"], "next")
        self.assertTrue(snapshot["command_capabilities"]["airplay_navigation"])
        self.assertEqual(
            snapshot["command_capabilities"]["airplay_actions"],
            ["play", "pause", "previous", "next"],
        )

    def test_navigation_rejects_disconnected_or_uncontrollable_sender(self):
        disconnected = self.coordinator(
            remote={
                "available": False,
                "playback_status": "Stopped",
                "can_control": False,
            }
        )
        with self.assertRaisesRegex(ValueError, "sender is connected"):
            disconnected.command("airplay", "next")

        uncontrollable = self.coordinator(
            remote={
                "available": True,
                "playback_status": "Playing",
                "can_control": False,
            }
        )
        with self.assertRaisesRegex(ValueError, "does not currently expose"):
            uncontrollable.command("airplay", "previous")

    def test_navigation_adapter_failure_is_reported(self):
        coordinator = self.coordinator(command_ok=False)
        with self.assertRaisesRegex(RuntimeError, "adapter failed"):
            coordinator.command("airplay", "next")
        command = coordinator.navigation_snapshot()
        self.assertEqual(command["status"], "failed")
        self.assertEqual(command["observed_source"], "mpris-adapter")

    def test_real_runner_promotes_navigation_before_registering_command_api(self):
        code = (
            "from app.runner import app, application_state_hub; "
            "from app.playback_navigation import NavigationTransportPlaybackCoordinator; "
            "routes={rule.rule for rule in app.url_map.iter_rules()}; "
            "coordinator=application_state_hub.service('playback'); "
            "assert '/api/playback/command' in routes, sorted(routes); "
            "assert isinstance(coordinator, NavigationTransportPlaybackCoordinator); "
            "assert coordinator.snapshot()['command_capabilities']['airplay_navigation'] is True"
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
