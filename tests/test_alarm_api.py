from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app import main


class AlarmApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.config_path = root / "config.json"
        self.example_path = root / "config.example.json"
        self.original_config_path = main.core.CONFIG_PATH
        self.original_example_path = main.core.EXAMPLE_CONFIG_PATH
        main.core.CONFIG_PATH = self.config_path
        main.core.EXAMPLE_CONFIG_PATH = self.example_path
        self.example_path.write_text(
            json.dumps(
                {
                    "dashboard": {"default_mode": "clock"},
                    "alarm": {
                        "enabled": False,
                        "default_time": "11:00",
                        "snooze_minutes": 8,
                        "defaults": {
                            "snooze_minutes": 8,
                            "ring_minutes": 3,
                            "occurrence_expiry_minutes": 120,
                            "tone_id": "classic-klaxon",
                            "fallback_tone_id": "emergency-buzzer",
                            "source_type": "tone",
                        },
                        "alarms": [],
                    },
                }
            ),
            encoding="utf-8",
        )
        self.client = main.app.test_client()

    def tearDown(self):
        main.core.CONFIG_PATH = self.original_config_path
        main.core.EXAMPLE_CONFIG_PATH = self.original_example_path
        self.temp_dir.cleanup()

    def test_get_migrates_legacy_alarm_values(self):
        self.config_path.write_text(
            json.dumps({"alarm": {"enabled": True, "default_time": "06:45", "snooze_minutes": 8}}),
            encoding="utf-8",
        )
        response = self.client.get("/api/alarms/config")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload["scheduler_active"])
        self.assertEqual(payload["alarm"]["alarms"][0]["time"], "06:45")
        self.assertTrue(payload["alarm"]["alarms"][0]["enabled"])

    def test_post_persists_multiple_alarms(self):
        payload = {
            "schema_version": 2,
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
                    "id": "weekday-alarm",
                    "enabled": True,
                    "label": "Weekday alarm",
                    "time": "07:30",
                    "days": ["mon", "tue", "wed", "thu", "fri"],
                    "snooze_minutes": 8,
                    "ring_minutes": 3,
                    "occurrence_expiry_minutes": 120,
                    "source": {
                        "type": "tone",
                        "tone_id": "classic-klaxon",
                        "fallback_tone_id": "emergency-buzzer",
                    },
                    "volume": {"start_percent": 60, "target_percent": 85, "fade_seconds": 10},
                },
                {
                    "id": "weekend-alarm",
                    "enabled": False,
                    "label": "Weekend alarm",
                    "time": "10:15",
                    "days": ["sat", "sun"],
                    "snooze_minutes": 10,
                    "ring_minutes": 3,
                    "occurrence_expiry_minutes": 120,
                    "source": {
                        "type": "tone",
                        "tone_id": "gentle-chime",
                        "fallback_tone_id": "emergency-buzzer",
                    },
                    "volume": {"start_percent": 50, "target_percent": 75, "fade_seconds": 12},
                },
            ],
        }
        response = self.client.post("/api/alarms/config", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["scheduler_active"])

        stored = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(stored["alarm"]["schema_version"], 2)
        self.assertEqual([alarm["id"] for alarm in stored["alarm"]["alarms"]], ["weekday-alarm", "weekend-alarm"])

    def test_post_rejects_empty_schedule(self):
        response = self.client.post(
            "/api/alarms/config",
            json={
                "defaults": {},
                "alarms": [
                    {
                        "id": "bad-alarm",
                        "enabled": True,
                        "label": "Bad alarm",
                        "time": "07:00",
                        "days": [],
                        "source": {
                            "type": "tone",
                            "tone_id": "classic-klaxon",
                            "fallback_tone_id": "emergency-buzzer",
                        },
                    }
                ],
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("at least one selected day", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
