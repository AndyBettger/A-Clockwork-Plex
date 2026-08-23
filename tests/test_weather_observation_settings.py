from __future__ import annotations

import unittest
from pathlib import Path

from app.weather_observation_settings import (
    public_observation_config,
    submitted_observation_config,
)


def config(provider: str = "ecowitt_push") -> dict:
    return {
        "weather": {
            "provider": provider,
            "ecowitt_push": {
                "path": "/ecowitt",
                "fresh_seconds": 180,
            },
            "weather_underground": {
                "station_id": "IOLD123",
                "api_key_env": "WEATHER_UNDERGROUND_API_KEY",
                "refresh_seconds": 60,
                "stale_seconds": 300,
                "request_timeout_seconds": 8,
                "pressure_history_hours": 6,
            },
        }
    }


class WeatherObservationSettingsTests(unittest.TestCase):
    def test_public_config_contains_reference_but_never_api_key_value(self):
        current = config("weather_underground")
        current["weather"]["weather_underground"]["api_key"] = "must-not-escape"

        public = public_observation_config(current)

        self.assertEqual(public["provider"], "weather_underground")
        self.assertEqual(
            public["weather_underground"]["api_key_env"],
            "WEATHER_UNDERGROUND_API_KEY",
        )
        self.assertNotIn("api_key", public["weather_underground"])
        self.assertNotIn("must-not-escape", str(public))

    def test_submission_can_select_weather_underground_without_secret_material(self):
        updated, public = submitted_observation_config(
            config(),
            {
                "provider": "weather_underground",
                "weather_underground": {
                    "station_id": "iengland987",
                    "api_key_env": "ACP_WU_KEY",
                    "refresh_seconds": 45,
                    "stale_seconds": 240,
                    "request_timeout_seconds": 10,
                    "pressure_history_hours": 8,
                },
            },
        )

        self.assertEqual(updated["weather"]["provider"], "weather_underground")
        self.assertEqual(
            updated["weather"]["weather_underground"]["station_id"],
            "IENGLAND987",
        )
        self.assertEqual(public["weather_underground"]["api_key_env"], "ACP_WU_KEY")
        self.assertEqual(public["weather_underground"]["refresh_seconds"], 45)
        self.assertEqual(public["weather_underground"]["pressure_history_hours"], 8)
        self.assertNotIn("api_key", public["weather_underground"])

    def test_submission_rejects_api_key_in_settings_payload(self):
        with self.assertRaisesRegex(ValueError, "environment variable"):
            submitted_observation_config(
                config(),
                {
                    "provider": "weather_underground",
                    "weather_underground": {
                        "station_id": "IABC123",
                        "api_key": "do-not-store-this",
                    },
                },
            )

    def test_weather_underground_selection_requires_station_id(self):
        current = config()
        current["weather"]["weather_underground"]["station_id"] = ""

        with self.assertRaisesRegex(ValueError, "station ID"):
            submitted_observation_config(
                current,
                {"provider": "weather_underground"},
            )

    def test_ecowitt_submission_validates_and_normalises_path_and_freshness(self):
        updated, public = submitted_observation_config(
            config(),
            {
                "provider": "ecowitt_push",
                "ecowitt_push": {
                    "path": "/weather-station",
                    "fresh_seconds": 90,
                },
            },
        )

        self.assertEqual(updated["weather"]["provider"], "ecowitt_push")
        self.assertEqual(public["ecowitt_push"]["path"], "/weather-station")
        self.assertEqual(public["ecowitt_push"]["fresh_seconds"], 90)

    def test_runner_passes_observation_service_to_unified_settings(self):
        source = Path("app/runner.py").read_text(encoding="utf-8")

        self.assertIn("observations=weather_observations", source)


if __name__ == "__main__":
    unittest.main()
