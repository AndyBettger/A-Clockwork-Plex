from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.alarm_runtime import ActiveAlarmScheduler


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value

    def advance(self, **kwargs) -> None:
        self.value += timedelta(**kwargs)


class ActiveAlarmRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runtime_path = Path(self.temp_dir.name) / "alarm-runtime.json"
        self.timezone = ZoneInfo("UTC")
        self.clock = MutableClock(datetime(2026, 7, 20, 12, 0, tzinfo=self.timezone))
        self.config = {
            "alarm": {
                "schema_version": 2,
                "defaults": {
                    "snooze_minutes": 8,
                    "ring_minutes": 3,
                    "occurrence_expiry_minutes": 120,
                    "tone_id": "classic-klaxon",
                    "fallback_tone_id": "emergency-buzzer",
                },
                "alarms": [
                    {
                        "id": "daily-alarm",
                        "enabled": True,
                        "label": "Daily alarm",
                        "time": "12:00",
                        "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                        "snooze_minutes": 8,
                        "ring_minutes": 3,
                        "occurrence_expiry_minutes": 120,
                        "source": {
                            "type": "tone",
                            "tone_id": "classic-klaxon",
                            "fallback_tone_id": "emergency-buzzer",
                        },
                        "volume": {
                            "start_percent": 60,
                            "target_percent": 85,
                            "fade_seconds": 10,
                        },
                    }
                ],
            }
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def scheduler(self) -> ActiveAlarmScheduler:
        return ActiveAlarmScheduler(
            lambda: self.config,
            self.runtime_path,
            timezone_info=self.timezone,
            now_provider=self.clock.now,
            poll_seconds=5,
            persist_seconds=15,
        )

    def activate_due_alarm(self, scheduler: ActiveAlarmScheduler) -> dict:
        return scheduler.tick(now=self.clock.now(), startup=False, force_persist=True)

    def test_due_alarm_activates_screen_without_playback(self):
        scheduler = self.scheduler()
        status = self.activate_due_alarm(scheduler)

        self.assertTrue(status["screen_required"])
        self.assertFalse(status["playback_enabled"])
        self.assertEqual(status["active_phase"], "ringing")
        self.assertEqual(status["active_occurrence"]["alarm_id"], "daily-alarm")
        self.assertEqual(status["active_occurrence"]["snooze_minutes"], 8)

    def test_manual_snooze_returns_to_ringing_after_interval(self):
        scheduler = self.scheduler()
        self.activate_due_alarm(scheduler)

        snoozed = scheduler.snooze()
        self.assertFalse(snoozed["screen_required"])
        self.assertEqual(snoozed["active_phase"], "snoozed")
        self.assertIsNotNone(snoozed["snoozed_until"])

        self.clock.advance(minutes=8, seconds=1)
        resumed = scheduler.tick(now=self.clock.now(), startup=False, force_persist=True)
        self.assertTrue(resumed["screen_required"])
        self.assertEqual(resumed["active_phase"], "ringing")
        self.assertEqual(resumed["active_occurrence"]["snooze_count"], 1)

    def test_ring_cycle_automatically_snoozes(self):
        self.config["alarm"]["alarms"][0]["ring_minutes"] = 1
        scheduler = self.scheduler()
        self.activate_due_alarm(scheduler)

        self.clock.advance(minutes=1, seconds=1)
        status = scheduler.tick(now=self.clock.now(), startup=False, force_persist=True)
        self.assertFalse(status["screen_required"])
        self.assertEqual(status["active_phase"], "snoozed")
        self.assertTrue(status["active_occurrence"]["last_snooze_was_automatic"])

    def test_dismiss_completes_occurrence_and_prevents_reactivation(self):
        scheduler = self.scheduler()
        active = self.activate_due_alarm(scheduler)
        occurrence_key = active["active_occurrence"]["occurrence_key"]

        dismissed = scheduler.dismiss()
        self.assertIsNone(dismissed["active_occurrence"])
        self.assertFalse(dismissed["screen_required"])
        self.assertIn(occurrence_key, dismissed["completed_occurrence_keys"])

        self.clock.advance(seconds=30)
        later = scheduler.tick(now=self.clock.now(), startup=False, force_persist=True)
        self.assertIsNone(later["active_occurrence"])

    def test_snoozed_alarm_survives_process_restart(self):
        scheduler = self.scheduler()
        self.activate_due_alarm(scheduler)
        scheduler.snooze()

        restarted = self.scheduler()
        restored = restarted.status()
        self.assertEqual(restored["active_phase"], "snoozed")
        self.assertFalse(restored["screen_required"])

        self.clock.advance(minutes=8, seconds=1)
        resumed = restarted.tick(now=self.clock.now(), startup=True, force_persist=True)
        self.assertTrue(resumed["screen_required"])
        self.assertEqual(resumed["active_occurrence"]["alarm_id"], "daily-alarm")

    def test_visual_test_activates_without_saved_alarms(self):
        self.config["alarm"]["alarms"] = []
        scheduler = self.scheduler()
        armed = scheduler.schedule_test(delay_seconds=2)
        self.assertIsNotNone(armed["pending_test_occurrence"])
        self.assertFalse(armed["screen_required"])

        self.clock.advance(seconds=3)
        active = scheduler.tick(now=self.clock.now(), startup=False, force_persist=True)
        self.assertTrue(active["screen_required"])
        self.assertTrue(active["active_occurrence"]["test_mode"])
        self.assertFalse(active["playback_enabled"])

        cleared = scheduler.clear_test()
        self.assertIsNone(cleared["active_occurrence"])
        self.assertFalse(cleared["screen_required"])


if __name__ == "__main__":
    unittest.main()
