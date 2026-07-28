from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from flask import Flask

from app.application_state import ApplicationStateHub
from app.playback_authority import promote_playback_authority
from app.playback_coordinator import PlaybackCoordinator
from app.playback_handoff_retention import RetainedBidirectionalHandoffCoordinator


class FakeDashboard:
    def __init__(self) -> None:
        self.app = Flask(__name__)
        self.mpris_calls: list[tuple[str, tuple[str, ...]]] = []

    @staticmethod
    def load_config() -> dict:
        return {
            "dashboard": {"default_mode": "clock"},
            "plexamp": {"url": "http://localhost:32500"},
        }

    def mpris_call(self, method: str, *arguments: str) -> tuple[bool, str | None]:
        self.mpris_calls.append((method, tuple(arguments)))
        return True, None


class PlaybackAuthorityTests(unittest.TestCase):
    def build_base(self, runtime_path: Path) -> tuple[ApplicationStateHub, PlaybackCoordinator]:
        coordinator = PlaybackCoordinator(
            load_config=lambda: {"dashboard": {"default_mode": "clock"}},
            load_state=lambda _config: {"mode": "clock", "airplay": {"active": False}},
            plexamp_status=lambda: {
                "available": True,
                "playback_state": "paused",
                "percent": 50,
            },
            airplay_status=lambda: {
                "available": False,
                "playback_status": "stopped",
                "sender_available": False,
            },
            alarm_status=lambda: {"active": False},
            alarm_audio_status=lambda: {"active": False},
            runtime_path=runtime_path,
            airplay_hold_seconds=600,
        )
        hub = ApplicationStateHub()
        hub.register_service("playback", coordinator)
        hub.register_provider("playback", coordinator.snapshot)
        return hub, coordinator

    def test_final_authority_is_registered_in_one_promotion(self):
        with tempfile.TemporaryDirectory() as directory:
            hub, base = self.build_base(Path(directory) / "playback-runtime.json")
            dashboard = FakeDashboard()

            authority = promote_playback_authority(hub, dashboard)

        self.assertIsInstance(authority, RetainedBidirectionalHandoffCoordinator)
        self.assertIs(hub.service("playback"), authority)
        self.assertIs(authority._events, base._events)
        snapshot = authority.snapshot()
        capabilities = snapshot["command_capabilities"]
        self.assertEqual(snapshot["authority"], "playback-handoff-owner")
        self.assertEqual(
            capabilities["airplay_actions"],
            ["play", "pause", "previous", "next"],
        )
        self.assertTrue(capabilities["airplay_to_plexamp_handoff"])
        self.assertTrue(capabilities["plexamp_to_airplay_handoff"])
        self.assertTrue(capabilities["airplay_ceded_to_plexamp"] is False)

    def test_final_authority_uses_one_complete_mpris_adapter(self):
        with tempfile.TemporaryDirectory() as directory:
            hub, _base = self.build_base(Path(directory) / "playback-runtime.json")
            dashboard = FakeDashboard()
            authority = promote_playback_authority(hub, dashboard)

            self.assertEqual(authority._airplay_command("next"), (True, None))
            self.assertEqual(authority._airplay_command("previous"), (True, None))
            self.assertEqual(authority._airplay_command("play"), (True, None))
            self.assertEqual(authority._airplay_command("pause"), (True, None))
            unsupported = authority._airplay_command("shuffle")

        self.assertEqual(
            dashboard.mpris_calls,
            [
                ("Next", ()),
                ("Previous", ()),
                ("Play", ()),
                ("Pause", ()),
            ],
        )
        self.assertFalse(unsupported[0])
        self.assertIn("Unsupported AirPlay transport action", unsupported[1] or "")

    def test_promotion_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            hub, _base = self.build_base(Path(directory) / "playback-runtime.json")
            dashboard = FakeDashboard()

            first = promote_playback_authority(hub, dashboard)
            second = promote_playback_authority(hub, dashboard)

        self.assertIs(first, second)


if __name__ == "__main__":
    unittest.main()
