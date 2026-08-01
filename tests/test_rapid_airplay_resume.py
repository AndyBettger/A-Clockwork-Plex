from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from app.playback_handoff_retention import RetainedBidirectionalHandoffCoordinator


class FakeClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 1, 18, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)


class RapidAirPlayResumeTests(unittest.TestCase):
    def coordinator(
        self,
        *,
        clock: FakeClock,
        mutate_remote_on_pause: bool,
    ) -> tuple[
        RetainedBidirectionalHandoffCoordinator,
        dict,
        dict,
        list[str],
        list[str],
    ]:
        remote = {
            "available": True,
            "playback_status": "Playing",
            "position_us": 1_000_000,
            "can_control": True,
            "can_play": True,
            "can_pause": True,
        }
        plexamp = {
            "available": True,
            "playback_state": "paused",
            "percent": 75,
        }
        airplay_commands: list[str] = []
        plexamp_commands: list[str] = []

        def airplay_command(action: str):
            airplay_commands.append(action)
            if action == "pause" and mutate_remote_on_pause:
                remote["playback_status"] = "Paused"
            return True, None

        def pause_plexamp():
            plexamp_commands.append("pause")
            plexamp["playback_state"] = "paused"
            return True, None

        coordinator = RetainedBidirectionalHandoffCoordinator(
            load_config=lambda: {"dashboard": {"default_mode": "clock"}},
            load_state=lambda _config: {
                "mode": "plexamp",
                "airplay": {
                    "active": remote.get("available") is True,
                    "started_at": "2026-08-01T18:00:00+00:00",
                    "ended_at": None,
                    "metadata": {},
                },
            },
            plexamp_status=lambda: dict(plexamp),
            airplay_status=lambda: dict(remote),
            alarm_status=lambda: {"screen_required": False},
            alarm_audio_status=lambda: {"playback_active": False},
            airplay_command=airplay_command,
            plexamp_pause=pause_plexamp,
            airplay_hold_seconds=600,
            reconcile_seconds=0.05,
            command_verify_seconds=20,
            now_provider=clock.now,
        )
        return coordinator, remote, plexamp, airplay_commands, plexamp_commands

    def start_plexamp_takeover(
        self,
        coordinator: RetainedBidirectionalHandoffCoordinator,
        plexamp: dict,
    ) -> dict:
        coordinator.snapshot()
        plexamp["playback_state"] = "playing"
        return coordinator.snapshot()

    def test_paused_to_playing_transition_immediately_reclaims_airplay(self):
        clock = FakeClock()
        coordinator, remote, plexamp, airplay_commands, plexamp_commands = self.coordinator(
            clock=clock,
            mutate_remote_on_pause=True,
        )

        takeover = self.start_plexamp_takeover(coordinator, plexamp)
        self.assertEqual(takeover["active_source"], "plexamp")
        self.assertEqual(airplay_commands, ["pause"])

        clock.advance(0.2)
        remote["playback_status"] = "Playing"
        remote["position_us"] = 1_100_000
        resumed = coordinator.snapshot()

        self.assertEqual(plexamp_commands, ["pause"])
        self.assertEqual(resumed["active_source"], "airplay")
        self.assertEqual(resumed["recommended_screen"], "airplay")
        self.assertEqual(
            resumed["handoffs"]["ceded_airplay_resume"]["last_evidence"],
            "paused-to-playing",
        )

    def test_frozen_stale_playing_state_does_not_bounce_back_to_airplay(self):
        clock = FakeClock()
        coordinator, remote, plexamp, airplay_commands, plexamp_commands = self.coordinator(
            clock=clock,
            mutate_remote_on_pause=False,
        )

        self.start_plexamp_takeover(coordinator, plexamp)
        for _ in range(5):
            clock.advance(1)
            snapshot = coordinator.snapshot()

        self.assertEqual(airplay_commands, ["pause"])
        self.assertEqual(plexamp_commands, [])
        self.assertEqual(snapshot["active_source"], "plexamp")
        self.assertEqual(
            snapshot["handoffs"]["ceded_airplay_resume"]["progress_samples"],
            0,
        )

    def test_advancing_position_detects_resume_without_a_visible_pause_sample(self):
        clock = FakeClock()
        coordinator, remote, plexamp, airplay_commands, plexamp_commands = self.coordinator(
            clock=clock,
            mutate_remote_on_pause=False,
        )

        self.start_plexamp_takeover(coordinator, plexamp)
        clock.advance(1)
        remote["position_us"] = 1_500_000
        first_progress = coordinator.snapshot()
        self.assertEqual(first_progress["active_source"], "plexamp")

        clock.advance(1)
        remote["position_us"] = 2_000_000
        resumed = coordinator.snapshot()

        self.assertEqual(airplay_commands, ["pause"])
        self.assertEqual(plexamp_commands, ["pause"])
        self.assertEqual(resumed["active_source"], "airplay")
        self.assertEqual(resumed["recommended_screen"], "airplay")
        self.assertEqual(
            resumed["handoffs"]["ceded_airplay_resume"]["last_evidence"],
            "advancing-position",
        )


if __name__ == "__main__":
    unittest.main()
