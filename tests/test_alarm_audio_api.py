from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app import main
from app.alarm_runtime import ActiveAlarmScheduler


class FakeAudioManager:
    def __init__(self) -> None:
        self.playback_active = False
        self.armed: list[str] = []
        self.last_test: dict | None = None
        self.stop_reasons: list[str] = []

    def status(self):
        return {
            "manager_running": True,
            "playback_active": self.playback_active,
            "current_tone_id": "classic-klaxon" if self.playback_active else None,
            "current_tone_label": "Classic Klaxon" if self.playback_active else None,
            "fallback_used": False,
            "last_error": None,
            "last_action": {"action": "fake-status"},
            "armed_occurrence_count": len(self.armed),
        }

    def diagnostics(self):
        return {
            "settings": main.load_config()["alarm_audio"],
            "runtime": self.status(),
            "helper": {"available": True, "plexamp_active": True, "shairport_active": False, "error": None},
            "player": {"available": True, "command": ["aplay"], "error": None},
            "scheduled_playback_enabled": False,
            "safety_message": "Only explicit tests may make sound. Scheduled alarms remain locked.",
        }

    def test_tone(self, occurrence):
        self.last_test = occurrence
        self.playback_active = True
        return self.status()

    def arm_occurrence(self, key):
        self.armed.append(str(key))

    def disarm_occurrence(self, key=None):
        if key is None:
            self.armed.clear()
        else:
            self.armed = [value for value in self.armed if value != str(key)]

    def stop_playback(self, *, reason="stopped", restore=True):
        self.playback_active = False
        self.stop_reasons.append(reason)
        return self.status()


class AlarmAudioApiTests(unittest.TestCase):
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
        self.original_audio = main.alarm_audio

        main.core.CONFIG_PATH = self.config_path
        main.core.EXAMPLE_CONFIG_PATH = self.example_path
        main.core.STATE_PATH = self.state_path

        config = {
            "dashboard": {"default_mode": "clock", "host": "0.0.0.0", "port": 8088},
            "alarm": {
                "schema_version": 2,
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
                "alarms": [
                    {
                        "id": "bedside-test",
                        "enabled": False,
                        "label": "Bedside test",
                        "time": "11:00",
                        "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                        "snooze_minutes": 8,
                        "ring_minutes": 3,
                        "occurrence_expiry_minutes": 120,
                        "source": {
                            "type": "tone",
                            "tone_id": "classic-klaxon",
                            "fallback_tone_id": "emergency-buzzer",
                        },
                        "volume": {"start_percent": 20, "target_percent": 30, "fade_seconds": 2},
                    }
                ],
            },
            "alarm_audio": {
                "master_enabled": False,
                "scheduled_enabled": True,
                "release_services": True,
                "restore_services": True,
                "backend": "aplay",
                "alsa_device": "default",
                "test_duration_seconds": 5,
            },
        }
        encoded = json.dumps(config)
        self.config_path.write_text(encoded, encoding="utf-8")
        self.example_path.write_text(encoded, encoding="utf-8")

        timezone = ZoneInfo("UTC")
        main.alarm_scheduler = ActiveAlarmScheduler(
            main.load_config,
            self.runtime_path,
            timezone_info=timezone,
            now_provider=lambda: datetime(2026, 7, 20, 10, 0, tzinfo=timezone),
        )
        main.alarm_audio = FakeAudioManager()
        self.client = main.app.test_client()

    def tearDown(self):
        main.alarm_audio = self.original_audio
        main.alarm_scheduler = self.original_scheduler
        main.core.CONFIG_PATH = self.original_config_path
        main.core.EXAMPLE_CONFIG_PATH = self.original_example_path
        main.core.STATE_PATH = self.original_state_path
        self.temp_dir.cleanup()

    def test_status_reports_test_only_lockout(self):
        response = self.client.get("/api/alarms/audio")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload["settings"]["master_enabled"])
        self.assertFalse(payload["settings"]["scheduled_enabled"])
        self.assertFalse(payload["scheduled_playback_enabled"])
        self.assertEqual(payload["alarm_options"][0]["id"], "bedside-test")

    def test_direct_audio_test_requires_saved_master_switch(self):
        blocked = self.client.post("/api/alarms/audio/test", json={"alarm_id": "bedside-test"})
        self.assertEqual(blocked.status_code, 409)

        saved = self.client.post(
            "/api/alarms/audio/settings",
            json={"master_enabled": True, "scheduled_enabled": True, "test_duration_seconds": 5},
        )
        self.assertEqual(saved.status_code, 200)
        self.assertTrue(saved.get_json()["settings"]["master_enabled"])
        self.assertFalse(saved.get_json()["settings"]["scheduled_enabled"])

        started = self.client.post("/api/alarms/audio/test", json={"alarm_id": "bedside-test"})
        self.assertEqual(started.status_code, 200)
        self.assertEqual(main.alarm_audio.last_test["label"], "Bedside test")
        self.assertEqual(main.alarm_audio.last_test["volume"]["target_percent"], 30)

    def test_full_screen_audio_test_requires_explicit_arming(self):
        self.client.post("/api/alarms/audio/settings", json={"master_enabled": True})
        response = self.client.post(
            "/api/alarms/audio/test",
            json={"alarm_id": "bedside-test", "full_screen": True, "delay_seconds": 10},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        key = payload["pending_test"]["occurrence_key"]
        self.assertIn(key, main.alarm_audio.armed)
        self.assertTrue(key.startswith("test|"))

    def test_emergency_stop_is_always_available(self):
        main.alarm_audio.playback_active = True
        response = self.client.post("/api/alarms/audio/stop", json={})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["runtime"]["playback_active"])
        self.assertIn("emergency-stop-button", main.alarm_audio.stop_reasons)


if __name__ == "__main__":
    unittest.main()
