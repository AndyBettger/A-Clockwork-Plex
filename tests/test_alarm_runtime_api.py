from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app import main
from app.alarm_runtime import ActiveAlarmScheduler


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value

    def advance(self, **kwargs) -> None:
        self.value += timedelta(**kwargs)


class AlarmRuntimeApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.config_path = root / "config.json"
        self.example_path = root / "config.example.json"
        self.state_path = root / "state.json"
        self.runtime_path = root / "alarm-runtime.json"

        self.original_config_path = main.core.CONFIG_PATH
        self.original_example_path = main.core.EXAMPLE_CONFIG_PATH
        self.original_state_path = main.core.STATE_PATH
        self.original_scheduler = main.alarm_scheduler

        main.core.CONFIG_PATH = self.config_path
        main.core.EXAMPLE_CONFIG_PATH = self.example_path
        main.core.STATE_PATH = self.state_path

        config = {
            "dashboard": {
                "default_mode": "clock",
                "host": "0.0.0.0",
                "port": 8088,
            },
            "alarm": {
                "schema_version": 2,
                "enabled": True,
                "default_time": "12:00",
                "snooze_minutes": 8,
                "defaults": {
                    "snooze_minutes": 8,
                    "ring_minutes": 3,
                    "occurrence_expiry_minutes": 120,
                    "tone_id": "classic-klaxon",
                    "fallback_tone_id": "emergency-buzzer",
                    "source_type": "tone",
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
            },
        }
        encoded = json.dumps(config)
        self.config_path.write_text(encoded, encoding="utf-8")
        self.example_path.write_text(encoded, encoding="utf-8")

        self.timezone = ZoneInfo("UTC")
        self.clock = MutableClock(datetime(2026, 7, 20, 11, 0, tzinfo=self.timezone))
        main.alarm_scheduler = ActiveAlarmScheduler(
            main.load_config,
            self.runtime_path,
            timezone_info=self.timezone,
            now_provider=self.clock.now,
            poll_seconds=5,
            persist_seconds=15,
        )
        self.client = main.app.test_client()

    def tearDown(self):
        main.alarm_scheduler = self.original_scheduler
        main.core.CONFIG_PATH = self.original_config_path
        main.core.EXAMPLE_CONFIG_PATH = self.original_example_path
        main.core.STATE_PATH = self.original_state_path
        self.temp_dir.cleanup()

    def test_visual_test_screen_snooze_and_dismiss_round_trip(self):
        armed_response = self.client.post(
            "/api/alarms/test",
            json={"delay_seconds": 2, "alarm_id": "daily-alarm"},
        )
        self.assertEqual(armed_response.status_code, 200)
        self.assertFalse(armed_response.get_json()["playback_enabled"])

        self.clock.advance(seconds=3)
        main.alarm_scheduler.tick(now=self.clock.now(), startup=False, force_persist=True)

        alarm_page = self.client.get("/alarm")
        self.assertEqual(alarm_page.status_code, 200)
        self.assertIn(b"Slide to dismiss", alarm_page.data)

        active_response = self.client.get("/api/alarms/active")
        active_payload = active_response.get_json()
        self.assertTrue(active_payload["screen_required"])
        self.assertEqual(active_payload["tone_label"], "Classic Klaxon")
        self.assertFalse(active_payload["playback_enabled"])

        snooze_response = self.client.post("/api/alarms/snooze", json={})
        self.assertEqual(snooze_response.status_code, 200)
        self.assertIsNotNone(snooze_response.get_json()["snoozed_until"])
        self.assertEqual(self.client.get("/alarm").status_code, 302)

        self.clock.advance(minutes=8, seconds=1)
        main.alarm_scheduler.tick(now=self.clock.now(), startup=False, force_persist=True)
        self.assertEqual(self.client.get("/alarm").status_code, 200)

        dismiss_response = self.client.post("/api/alarms/dismiss", json={})
        self.assertEqual(dismiss_response.status_code, 200)
        self.assertIsNone(dismiss_response.get_json()["scheduler"]["active_occurrence"])
        self.assertEqual(self.client.get("/alarm").status_code, 302)

    def test_control_endpoints_reject_actions_without_active_alarm(self):
        snooze = self.client.post("/api/alarms/snooze", json={})
        dismiss = self.client.post("/api/alarms/dismiss", json={})
        self.assertEqual(snooze.status_code, 409)
        self.assertEqual(dismiss.status_code, 409)


if __name__ == "__main__":
    unittest.main()
