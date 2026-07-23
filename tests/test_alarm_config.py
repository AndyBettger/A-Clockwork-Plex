from __future__ import annotations

import unittest

from app.alarm_config import normalise_alarm_config, validate_submitted_alarm_config


MANIFEST = {
    "schema_version": 1,
    "default_tone_id": "classic-klaxon",
    "fallback_tone_id": "emergency-buzzer",
    "preview_seconds": 10,
    "tones": [
        {"id": "classic-klaxon", "label": "Classic Klaxon", "pattern": []},
        {"id": "gentle-chime", "label": "Gentle Chime", "pattern": []},
        {"id": "emergency-buzzer", "label": "Emergency Buzzer", "pattern": []},
    ],
}


def alarm_payload(**overrides):
    alarm = {
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
    }
    alarm.update(overrides)
    return {
        "schema_version": 2,
        "defaults": {
            "snooze_minutes": 8,
            "ring_minutes": 3,
            "occurrence_expiry_minutes": 120,
            "tone_id": "classic-klaxon",
            "fallback_tone_id": "emergency-buzzer",
            "source_type": "tone",
        },
        "alarms": [alarm],
    }


class AlarmConfigTests(unittest.TestCase):
    def test_legacy_alarm_migrates_without_losing_values(self):
        model = normalise_alarm_config(
            {"enabled": True, "default_time": "07:45", "snooze_minutes": 8},
            MANIFEST,
            prefer_legacy=True,
        )
        self.assertEqual(model["schema_version"], 2)
        self.assertEqual(len(model["alarms"]), 1)
        self.assertTrue(model["alarms"][0]["enabled"])
        self.assertEqual(model["alarms"][0]["time"], "07:45")
        self.assertEqual(model["alarms"][0]["snooze_minutes"], 8)

    def test_explicit_empty_alarm_list_stays_empty(self):
        model = normalise_alarm_config({"defaults": {}, "alarms": []}, MANIFEST)
        self.assertEqual(model["alarms"], [])
        self.assertFalse(model["enabled"])

    def test_valid_multiple_alarm_payload_is_preserved(self):
        payload = alarm_payload()
        second = alarm_payload(
            id="weekend-alarm",
            label="Weekend alarm",
            time="10:15",
            days=["sat", "sun"],
            enabled=False,
            source={
                "type": "tone",
                "tone_id": "gentle-chime",
                "fallback_tone_id": "emergency-buzzer",
            },
        )["alarms"][0]
        payload["alarms"].append(second)
        model = validate_submitted_alarm_config(payload, MANIFEST)
        self.assertEqual([alarm["id"] for alarm in model["alarms"]], ["weekday-alarm", "weekend-alarm"])
        self.assertEqual(model["alarms"][1]["source"]["tone_id"], "gentle-chime")

    def test_duplicate_ids_are_rejected(self):
        payload = alarm_payload()
        payload["alarms"].append(dict(payload["alarms"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate alarm ID"):
            validate_submitted_alarm_config(payload, MANIFEST)

    def test_invalid_time_is_rejected(self):
        payload = alarm_payload(time="25:99")
        with self.assertRaisesRegex(ValueError, "Invalid alarm time"):
            validate_submitted_alarm_config(payload, MANIFEST)

    def test_empty_schedule_is_rejected(self):
        payload = alarm_payload(days=[])
        with self.assertRaisesRegex(ValueError, "at least one selected day"):
            validate_submitted_alarm_config(payload, MANIFEST)

    def test_unknown_tone_is_rejected(self):
        payload = alarm_payload(
            source={
                "type": "tone",
                "tone_id": "pan-galactic-gargle-blaster",
                "fallback_tone_id": "emergency-buzzer",
            }
        )
        with self.assertRaisesRegex(ValueError, "unknown tone"):
            validate_submitted_alarm_config(payload, MANIFEST)

    def test_limits_are_clamped_to_supported_ranges(self):
        payload = alarm_payload(
            snooze_minutes=999,
            ring_minutes=0,
            occurrence_expiry_minutes=99999,
            volume={"start_percent": -5, "target_percent": 200, "fade_seconds": 9999},
        )
        alarm = validate_submitted_alarm_config(payload, MANIFEST)["alarms"][0]
        self.assertEqual(alarm["snooze_minutes"], 60)
        self.assertEqual(alarm["ring_minutes"], 1)
        self.assertEqual(alarm["occurrence_expiry_minutes"], 1440)
        self.assertEqual(alarm["volume"], {"start_percent": 0, "target_percent": 100, "fade_seconds": 300})


if __name__ == "__main__":
    unittest.main()
