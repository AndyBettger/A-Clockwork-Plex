from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app import main
from app.alarm_scheduler import SilentAlarmScheduler


class AlarmSchedulerApiTests(unittest.TestCase):
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

        saved_config = {
            "dashboard": {
                "default_mode": "clock",
                "host": "0.0.0.0",
                "port": 8088,
            },
            "alarm": {
                "schema_version": 2,
                "enabled": True,
                "default_time": "23:00",
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
                        "time": "23:00",
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
        serialised = json.dumps(saved_config)
        self.example_path.write_text(serialised, encoding="utf-8")
        self.config_path.write_text(serialised, encoding="utf-8")

        timezone = ZoneInfo("UTC")
        main.alarm_scheduler = SilentAlarmScheduler(
            main.load_config,
            self.runtime_path,
            timezone_info=timezone,
            now_provider=lambda: datetime(2026, 7, 20, 12, 0, tzinfo=timezone),
        )
        self.client = main.app.test_client()

    def tearDown(self):
        main.alarm_scheduler = self.original_scheduler
        main.core.CONFIG_PATH = self.original_config_path
        main.core.EXAMPLE_CONFIG_PATH = self.original_example_path
        main.core.STATE_PATH = self.original_state_path
        self.temp_dir.cleanup()

    def test_scheduler_endpoint_recalculates_without_playback(self):
        response = self.client.post("/api/alarms/scheduler")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["playback_enabled"])
        self.assertFalse(payload["scheduler_active"])
        self.assertEqual(payload["scheduler"]["next_occurrence"]["alarm_id"], "daily-alarm")

    def test_api_status_contains_scheduler_diagnostics(self):
        main.alarm_scheduler.recalculate()
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("alarm_scheduler", payload)
        self.assertFalse(payload["alarm_scheduler"]["playback_enabled"])
        self.assertEqual(payload["alarm_scheduler"]["next_occurrence"]["label"], "Daily alarm")


if __name__ == "__main__":
    unittest.main()
