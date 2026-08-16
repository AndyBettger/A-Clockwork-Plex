from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.alarm_runtime import ActiveAlarmScheduler


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


class AlarmDeadlineTimingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runtime_path = Path(self.temp_dir.name) / "alarm-runtime.json"
        self.timezone = ZoneInfo("UTC")
        self.clock = MutableClock(datetime(2026, 8, 16, 11, 59, 50, tzinfo=self.timezone))
        self.config = {
            "alarm": {
                "defaults": {
                    "snooze_minutes": 8,
                    "ring_minutes": 3,
                    "occurrence_expiry_minutes": 120,
                    "tone_id": "classic-klaxon",
                    "fallback_tone_id": "emergency-buzzer",
                },
                "alarms": [
                    {
                        "id": "deadline-alarm",
                        "enabled": True,
                        "label": "Deadline alarm",
                        "time": "12:00",
                        "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                        "snooze_minutes": 8,
                        "ring_minutes": 1,
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

    def scheduler(self, *, poll_seconds: int = 15) -> ActiveAlarmScheduler:
        return ActiveAlarmScheduler(
            lambda: self.config,
            self.runtime_path,
            timezone_info=self.timezone,
            now_provider=self.clock.now,
            poll_seconds=poll_seconds,
        )

    def test_saved_alarm_deadline_shortens_safety_poll(self):
        scheduler = self.scheduler(poll_seconds=15)
        scheduler.tick(now=self.clock.now(), startup=True, force_persist=True)
        self.assertAlmostEqual(scheduler._next_wait_seconds(), 10.0, delta=0.01)

    def test_pending_test_deadline_shortens_safety_poll(self):
        self.config["alarm"]["alarms"] = []
        scheduler = self.scheduler(poll_seconds=15)
        scheduler.tick(now=self.clock.now(), startup=True, force_persist=True)
        scheduler.schedule_test(delay_seconds=2)
        self.assertAlmostEqual(scheduler._next_wait_seconds(), 2.0, delta=0.01)

    def test_snooze_deadline_wakes_before_long_safety_poll(self):
        self.clock.value = datetime(2026, 8, 16, 12, 0, tzinfo=self.timezone)
        scheduler = self.scheduler(poll_seconds=900)
        scheduler.tick(now=self.clock.now(), startup=False, force_persist=True)
        scheduler.snooze()
        self.assertAlmostEqual(scheduler._next_wait_seconds(), 8 * 60, delta=0.01)

    def test_ring_cycle_deadline_wakes_before_long_safety_poll(self):
        self.clock.value = datetime(2026, 8, 16, 12, 0, tzinfo=self.timezone)
        scheduler = self.scheduler(poll_seconds=900)
        scheduler.tick(now=self.clock.now(), startup=False, force_persist=True)
        self.assertEqual(scheduler.status()["active_phase"], "ringing")
        self.assertAlmostEqual(scheduler._next_wait_seconds(), 60.0, delta=0.01)


if __name__ == "__main__":
    unittest.main()
