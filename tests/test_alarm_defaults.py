from __future__ import annotations

import unittest

from app.alarm_config import normalise_alarm_config, validate_submitted_alarm_config


MANIFEST = {
    "default_tone_id": "classic-klaxon",
    "fallback_tone_id": "emergency-buzzer",
    "preview_seconds": 10,
    "tones": [
        {"id": "classic-klaxon", "label": "Classic Klaxon", "pattern": []},
        {"id": "emergency-buzzer", "label": "Emergency Buzzer", "pattern": []},
    ],
}


class AlarmDefaultsTests(unittest.TestCase):
    def test_global_snooze_default_stays_independent_from_first_alarm(self):
        submitted = validate_submitted_alarm_config(
            {
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
                        "id": "early-alarm",
                        "enabled": True,
                        "label": "Early alarm",
                        "time": "06:30",
                        "days": ["mon"],
                        "snooze_minutes": 5,
                        "ring_minutes": 3,
                        "occurrence_expiry_minutes": 120,
                        "source": {
                            "type": "tone",
                            "tone_id": "classic-klaxon",
                            "fallback_tone_id": "emergency-buzzer",
                        },
                        "volume": {"start_percent": 60, "target_percent": 85, "fade_seconds": 10},
                    }
                ],
            },
            MANIFEST,
        )
        reloaded = normalise_alarm_config(submitted, MANIFEST)
        self.assertEqual(reloaded["defaults"]["snooze_minutes"], 8)
        self.assertEqual(reloaded["alarms"][0]["snooze_minutes"], 5)


if __name__ == "__main__":
    unittest.main()
