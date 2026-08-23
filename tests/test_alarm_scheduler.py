from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.alarm_scheduler import (
    SilentAlarmScheduler,
    next_alarm_occurrence,
    occurrences_between,
)


def alarm_config(*alarms):
    return {"alarm": {"alarms": list(alarms)}}


def alarm(
    alarm_id="weekday",
    *,
    enabled=True,
    label="Weekday alarm",
    alarm_time="07:30",
    days=None,
):
    return {
        "id": alarm_id,
        "enabled": enabled,
        "label": label,
        "time": alarm_time,
        "days": days or ["mon", "tue", "wed", "thu", "fri"],
        "snooze_minutes": 8,
        "ring_minutes": 3,
        "occurrence_expiry_minutes": 120,
        "source": {
            "type": "tone",
            "tone_id": "classic-klaxon",
            "fallback_tone_id": "emergency-buzzer",
        },
        "volume": {"start_percent": 60, "target_percent": 85, "fade_seconds": 10},
    }


class AlarmSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.timezone = ZoneInfo("Europe/London")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runtime_path = Path(self.temp_dir.name) / "alarm-runtime.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_next_weekday_alarm(self):
        now = datetime(2026, 7, 20, 7, 0, tzinfo=self.timezone)
        occurrence = next_alarm_occurrence(
            alarm_config(alarm())["alarm"],
            now,
            self.timezone,
        )
        self.assertIsNotNone(occurrence)
        self.assertEqual(occurrence["scheduled_for"], "2026-07-20T07:30:00+01:00")

    def test_disabled_alarm_has_no_next_occurrence(self):
        now = datetime(2026, 7, 20, 7, 0, tzinfo=self.timezone)
        occurrence = next_alarm_occurrence(
            alarm_config(alarm(enabled=False))["alarm"],
            now,
            self.timezone,
        )
        self.assertIsNone(occurrence)

    def test_due_occurrence_is_observed_only_once(self):
        current_config = alarm_config(alarm())
        scheduler = SilentAlarmScheduler(
            lambda: current_config,
            self.runtime_path,
            timezone_info=self.timezone,
            poll_seconds=15,
        )
        scheduler.tick(now=datetime(2026, 7, 20, 7, 29, tzinfo=self.timezone), startup=True)
        scheduler.tick(now=datetime(2026, 7, 20, 7, 31, tzinfo=self.timezone), startup=False)
        scheduler.tick(now=datetime(2026, 7, 20, 7, 32, tzinfo=self.timezone), startup=False)

        status = scheduler.status()
        self.assertEqual(status["observed_occurrence_count"], 1)
        self.assertEqual(
            status["last_observed_occurrence"]["occurrence_key"],
            "weekday|2026-07-20|07:30",
        )
        self.assertFalse(status["last_observed_occurrence"]["playback_attempted"])

    def test_restart_recovery_marks_recent_occurrence(self):
        current_config = alarm_config(alarm())
        self.runtime_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "last_check_at": "2026-07-20T07:20:00+01:00",
                    "observed_occurrences": [],
                }
            ),
            encoding="utf-8",
        )
        scheduler = SilentAlarmScheduler(
            lambda: current_config,
            self.runtime_path,
            timezone_info=self.timezone,
            missed_grace_minutes=10,
        )
        scheduler.tick(now=datetime(2026, 7, 20, 7, 35, tzinfo=self.timezone), startup=True)
        observed = scheduler.status()["last_observed_occurrence"]
        self.assertIsNotNone(observed)
        self.assertTrue(observed["recovered_after_restart"])

    def test_occurrence_outside_recovery_grace_is_not_observed(self):
        current_config = alarm_config(alarm())
        scheduler = SilentAlarmScheduler(
            lambda: current_config,
            self.runtime_path,
            timezone_info=self.timezone,
            missed_grace_minutes=10,
        )
        scheduler.tick(now=datetime(2026, 7, 20, 8, 0, tzinfo=self.timezone), startup=True)
        self.assertEqual(scheduler.status()["observed_occurrence_count"], 0)

    def test_duplicate_protection_survives_scheduler_restart(self):
        current_config = alarm_config(alarm())
        first = SilentAlarmScheduler(
            lambda: current_config,
            self.runtime_path,
            timezone_info=self.timezone,
        )
        first.tick(now=datetime(2026, 7, 20, 7, 29, tzinfo=self.timezone), startup=True)
        first.tick(now=datetime(2026, 7, 20, 7, 31, tzinfo=self.timezone), startup=False)

        second = SilentAlarmScheduler(
            lambda: current_config,
            self.runtime_path,
            timezone_info=self.timezone,
        )
        second.tick(now=datetime(2026, 7, 20, 7, 35, tzinfo=self.timezone), startup=True)
        self.assertEqual(second.status()["observed_occurrence_count"], 1)

    def test_spring_forward_alarm_moves_to_next_valid_local_time(self):
        sunday_alarm = alarm(
            alarm_id="dst-alarm",
            alarm_time="01:30",
            days=["sun"],
        )
        now = datetime(2026, 3, 29, 0, 30, tzinfo=self.timezone)
        occurrence = next_alarm_occurrence(
            alarm_config(sunday_alarm)["alarm"],
            now,
            self.timezone,
        )
        self.assertEqual(occurrence["scheduled_for"], "2026-03-29T02:30:00+01:00")
        self.assertEqual(occurrence["occurrence_key"], "dst-alarm|2026-03-29|01:30")

    def test_fall_back_alarm_occurs_only_once(self):
        sunday_alarm = alarm(
            alarm_id="dst-alarm",
            alarm_time="01:30",
            days=["sun"],
        )
        start = datetime(2026, 10, 25, 0, 0, tzinfo=self.timezone)
        end = datetime(2026, 10, 25, 3, 0, tzinfo=self.timezone)
        occurrences = occurrences_between(
            alarm_config(sunday_alarm)["alarm"],
            start,
            end,
            self.timezone,
        )
        self.assertEqual(len(occurrences), 1)
        self.assertEqual(occurrences[0]["occurrence_key"], "dst-alarm|2026-10-25|01:30")


if __name__ == "__main__":
    unittest.main()
