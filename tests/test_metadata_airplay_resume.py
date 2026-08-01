from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from app.playback_resume_metadata import MetadataResumeRetainedCoordinator


class FakeClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 1, 20, 13, 24, 500000, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)


class MetadataAirPlayResumeTests(unittest.TestCase):
    def coordinator(self, clock: FakeClock):
        metadata = {
            "last_event": "play_start",
            "updated_at": "2026-08-01T20:12:00+00:00",
        }
        remote = {
            "available": True,
            "playback_status": "Playing",
            "position_us": 0,
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
            # Match the bedroom Pi: MPRIS continues reporting Playing after Pause.
            return True, None

        def pause_plexamp():
            plexamp_commands.append("pause")
            plexamp["playback_state"] = "paused"
            return True, None

        coordinator = MetadataResumeRetainedCoordinator(
            load_config=lambda: {"dashboard": {"default_mode": "clock"}},
            load_state=lambda _config: {
                "mode": "plexamp",
                "airplay": {
                    "active": True,
                    "started_at": "2026-08-01T20:00:00+00:00",
                    "ended_at": None,
                    "metadata": dict(metadata),
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
        return coordinator, metadata, plexamp, airplay_commands, plexamp_commands

    def start_takeover(self, coordinator, plexamp):
        coordinator.snapshot()
        plexamp["playback_state"] = "playing"
        snapshot = coordinator.snapshot()
        self.assertEqual(snapshot["active_source"], "plexamp")

    def test_fifo_play_resume_pauses_plexamp_when_mpris_never_changes(self):
        clock = FakeClock()
        coordinator, metadata, plexamp, airplay_commands, plexamp_commands = self.coordinator(clock)
        self.start_takeover(coordinator, plexamp)
        self.assertEqual(airplay_commands, ["pause"])

        clock.advance(0.2)
        metadata["last_event"] = "play_resume"
        metadata["updated_at"] = "2026-08-01T20:13:24+00:00"
        resumed = coordinator.snapshot()

        self.assertEqual(plexamp_commands, ["pause"])
        self.assertEqual(resumed["active_source"], "airplay")
        self.assertEqual(resumed["recommended_screen"], "airplay")
        self.assertEqual(
            resumed["handoffs"]["metadata_airplay_resume"]["last_evidence"],
            "metadata-play_resume",
        )

    def test_old_play_start_before_takeover_does_not_reclaim_airplay(self):
        clock = FakeClock()
        coordinator, _metadata, plexamp, airplay_commands, plexamp_commands = self.coordinator(clock)
        self.start_takeover(coordinator, plexamp)

        for _ in range(4):
            clock.advance(1)
            snapshot = coordinator.snapshot()

        self.assertEqual(airplay_commands, ["pause"])
        self.assertEqual(plexamp_commands, [])
        self.assertEqual(snapshot["active_source"], "plexamp")

    def test_same_second_resume_is_new_intent_even_before_first_probe(self):
        clock = FakeClock()
        coordinator, metadata, plexamp, airplay_commands, plexamp_commands = self.coordinator(clock)
        coordinator.snapshot()
        plexamp["playback_state"] = "playing"
        metadata["last_event"] = "resume"
        metadata["updated_at"] = "2026-08-01T20:13:24+00:00"

        resumed = coordinator.snapshot()

        self.assertEqual(airplay_commands, ["pause"])
        self.assertEqual(plexamp_commands, ["pause"])
        self.assertEqual(resumed["active_source"], "airplay")
        self.assertEqual(
            resumed["handoffs"]["metadata_airplay_resume"]["last_evidence"],
            "metadata-resume",
        )


if __name__ == "__main__":
    unittest.main()
