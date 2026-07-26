from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask

from app.application_state import ApplicationStateHub
from app.playback_transport import (
    TransportPlaybackCoordinator,
    register_playback_command_api,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 26, 18, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


class TransportPlaybackCoordinatorTests(unittest.TestCase):
    def coordinator(
        self,
        *,
        remote: dict | None = None,
        commands: list[str] | None = None,
        clock: FakeClock | None = None,
        runtime_path: Path | None = None,
        command_ok: bool = True,
    ) -> TransportPlaybackCoordinator:
        remote_state = remote if remote is not None else {
            "available": True,
            "playback_status": "Playing",
            "can_control": True,
            "can_play": True,
            "can_pause": True,
        }
        command_log = commands if commands is not None else []
        fake_clock = clock or FakeClock()

        def send(action: str):
            command_log.append(action)
            return (command_ok, None if command_ok else "adapter failed")

        return TransportPlaybackCoordinator(
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
            runtime_path=runtime_path,
            airplay_hold_seconds=600,
            reconcile_seconds=0.05,
            now_provider=fake_clock.now,
            airplay_command=send,
            command_verify_seconds=20,
        )

    def test_pause_command_is_explicit_and_arms_hold_immediately(self):
        commands: list[str] = []
        coordinator = self.coordinator(commands=commands)

        result = coordinator.command("airplay", "pause")
        airplay = result["playback"]["sources"]["airplay"]
        command = result["command"]

        self.assertEqual(commands, ["pause"])
        self.assertEqual(airplay["state"], "paused")
        self.assertTrue(airplay["hold"]["active"])
        self.assertEqual(airplay["hold"]["remaining_seconds"], 600)
        self.assertEqual(command["status"], "accepted-awaiting-observation")

    def test_duplicate_shairport_pause_does_not_restart_hold(self):
        clock = FakeClock()
        with tempfile.TemporaryDirectory() as directory:
            coordinator = self.coordinator(
                clock=clock,
                runtime_path=Path(directory) / "playback-runtime.json",
            )
            coordinator.command("airplay", "pause")
            first_until = coordinator.snapshot()["sources"]["airplay"]["hold"]["until"]
            clock.advance(10)
            coordinator.record_event("airplay", "paused", {"origin": "shairport-end-wrapper"})
            second = coordinator.snapshot()["sources"]["airplay"]["hold"]

        self.assertEqual(second["until"], first_until)
        self.assertEqual(second["remaining_seconds"], 590)

    def test_independent_observation_confirms_command(self):
        remote = {
            "available": True,
            "playback_status": "Playing",
            "can_control": True,
            "can_play": True,
            "can_pause": True,
        }
        coordinator = self.coordinator(remote=remote)
        coordinator.command("airplay", "pause")
        self.assertEqual(coordinator.command_snapshot()["status"], "accepted-awaiting-observation")

        remote["playback_status"] = "Paused"
        snapshot = coordinator.snapshot()

        self.assertEqual(snapshot["commands"]["airplay"]["status"], "confirmed")
        self.assertEqual(snapshot["commands"]["airplay"]["observed_source"], "mpris")

    def test_idempotent_command_is_noop_without_adapter_call(self):
        commands: list[str] = []
        coordinator = self.coordinator(commands=commands)
        result = coordinator.command("airplay", "play")

        self.assertEqual(commands, [])
        self.assertTrue(result["command"]["noop"])
        self.assertEqual(result["command"]["status"], "noop")

    def test_disconnected_sender_and_unsupported_actions_are_rejected(self):
        remote = {
            "available": False,
            "playback_status": "Stopped",
            "can_control": False,
            "can_play": False,
            "can_pause": False,
        }
        coordinator = self.coordinator(remote=remote)

        with self.assertRaisesRegex(ValueError, "sender is connected"):
            coordinator.command("airplay", "play")
        with self.assertRaisesRegex(ValueError, "play or pause"):
            coordinator.command("airplay", "toggle")
        with self.assertRaisesRegex(ValueError, "Only AirPlay"):
            coordinator.command("plexamp", "play")

    def test_adapter_failure_is_reported_without_state_event(self):
        coordinator = self.coordinator(command_ok=False)
        with self.assertRaisesRegex(RuntimeError, "adapter failed"):
            coordinator.command("airplay", "pause")
        self.assertEqual(coordinator.command_snapshot()["status"], "failed")
        self.assertEqual(coordinator.snapshot()["sources"]["airplay"]["state"], "playing")

    def test_command_api_returns_coordinator_snapshot(self):
        coordinator = self.coordinator()
        hub = ApplicationStateHub()
        hub.register_service("playback", coordinator)
        hub.register_provider("playback", coordinator.snapshot)
        app = Flask("playback-command-test")
        register_playback_command_api(app, hub)

        response = app.test_client().post(
            "/api/playback/command",
            json={"source": "airplay", "action": "pause"},
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["playback"]["authority"], "airplay-transport-owner")
        self.assertEqual(payload["playback"]["sources"]["airplay"]["state"], "paused")

    def test_real_runner_promotes_transport_and_registers_command_route(self):
        code = (
            "from app.runner import app, application_state_hub; "
            "from app.playback_transport import TransportPlaybackCoordinator; "
            "routes = {rule.rule for rule in app.url_map.iter_rules()}; "
            "assert '/api/playback/command' in routes, sorted(routes); "
            "assert isinstance(application_state_hub.service('playback'), TransportPlaybackCoordinator)"
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
