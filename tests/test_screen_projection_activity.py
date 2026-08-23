from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.plexamp_observer import PlexampTimelineObserver
from app.screen_projection_activity import ActivityAwareScreenProjectionController


class FakePlayback:
    def __init__(self) -> None:
        self.calls = 0
        self.state = {
            "current_screen": "weather",
            "active_source": "plexamp",
            "activity_token": "queue:playQueueID=100",
            "alarm_active": False,
        }

    def snapshot(self) -> dict:
        self.calls += 1
        source = self.state["active_source"]
        return {
            "current_screen": self.state["current_screen"],
            "active_source": source,
            "playback_activity": {
                "source": source,
                "token": self.state.get("activity_token"),
            },
            "sources": {
                "plexamp": {"activity_token": self.state.get("activity_token")},
                "airplay": {"activity_token": self.state.get("activity_token")},
                "alarm": {"active": self.state.get("alarm_active", False)},
            },
        }


class PlexampTimelineObserverTests(unittest.TestCase):
    def test_queue_token_survives_track_progression_but_changes_for_new_queue(self):
        first = PlexampTimelineObserver.parse_timeline(
            b'<MediaContainer><Timeline type="music" state="playing" volume="72" '
            b'playQueueID="100" containerKey="/playQueues/100" ratingKey="1" /></MediaContainer>'
        )
        next_track = PlexampTimelineObserver.parse_timeline(
            b'<MediaContainer><Timeline type="music" state="playing" volume="72" '
            b'playQueueID="100" containerKey="/playQueues/100" ratingKey="2" /></MediaContainer>'
        )
        new_nfc_queue = PlexampTimelineObserver.parse_timeline(
            b'<MediaContainer><Timeline type="music" state="playing" volume="72" '
            b'playQueueID="101" containerKey="/playQueues/101" ratingKey="3" /></MediaContainer>'
        )

        self.assertEqual(first["activity_token"], next_track["activity_token"])
        self.assertNotEqual(first["media_token"], next_track["media_token"])
        self.assertNotEqual(first["activity_token"], new_nfc_queue["activity_token"])


class ActivityAwareScreenProjectionTests(unittest.TestCase):
    def controller(self):
        playback = FakePlayback()
        mode = {"value": "weather"}
        controller = ActivityAwareScreenProjectionController(
            load_config=lambda: {
                "dashboard": {
                    "idle_timeout_seconds": 30,
                    "default_mode": "clock",
                }
            },
            load_state=lambda _config: {"mode": mode["value"]},
            playback=playback,
            set_mode=lambda value: mode.update(value=value),
            input_activity=lambda: {
                "authority": "linux-input-activity-monitor",
                "running": True,
                "available": True,
                "sequence": 0,
                "last_activity_at": None,
                "last_event": None,
                "last_error": None,
            },
            now_provider=lambda: datetime(2026, 7, 30, 1, 0, tzinfo=timezone.utc),
        )
        return controller, playback

    def test_same_plexamp_owner_new_queue_interrupts_manual_page(self):
        controller, playback = self.controller()
        opened = controller.interaction("weather", manual=True, visible_surface="weather")
        self.assertTrue(opened["lease"]["active"])
        self.assertEqual(opened["lease"]["activity_token_at_start"], "queue:playQueueID=100")

        playback.state["activity_token"] = "queue:playQueueID=101"
        takeover = controller.snapshot("weather")

        self.assertFalse(takeover["lease"]["active"])
        self.assertEqual(takeover["recommended_screen"], "plexamp")
        self.assertEqual(takeover["lease"]["last_end_reason"], "playback-activity-changed:plexamp")

    def test_airplay_resume_generation_interrupts_manual_page(self):
        controller, playback = self.controller()
        playback.state.update(
            {
                "active_source": "airplay",
                "activity_token": "airplay-playing:10",
            }
        )
        opened = controller.interaction("weather", manual=True, visible_surface="weather")
        self.assertTrue(opened["lease"]["active"])

        playback.state["activity_token"] = "airplay-playing:14"
        resumed = controller.snapshot("weather")

        self.assertFalse(resumed["lease"]["active"])
        self.assertEqual(resumed["recommended_screen"], "airplay")
        self.assertEqual(resumed["lease"]["last_end_reason"], "playback-activity-changed:airplay")

    def test_ordinary_same_queue_track_change_does_not_interrupt_lease(self):
        controller, playback = self.controller()
        controller.interaction("weather", manual=True, visible_surface="weather")

        unchanged = controller.snapshot("weather")

        self.assertTrue(unchanged["lease"]["active"])
        self.assertEqual(unchanged["recommended_screen"], "weather")
        self.assertEqual(playback.state["activity_token"], "queue:playQueueID=100")

    def test_manual_lease_claim_reads_playback_once(self):
        controller, playback = self.controller()
        controller.set_idle_return_mode("clock")
        playback.calls = 0

        controller.interaction("weather", manual=True, visible_surface="plexamp")

        self.assertEqual(playback.calls, 1)


if __name__ == "__main__":
    unittest.main()
