from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlparse

from app.weather_observations import (
    build_weather_underground_current_url,
    build_weather_underground_recent_history_url,
    normalise_observation_config,
    observation_configuration_error,
    weather_underground_current_to_dashboard,
)


class WeatherObservationProviderTests(unittest.TestCase):
    def test_existing_ecowitt_push_remains_default(self):
        settings = normalise_observation_config({"weather": {}})

        self.assertEqual(settings["provider"], "ecowitt_push")
        self.assertEqual(settings["ecowitt_push"]["path"], "/ecowitt")
        self.assertIsNone(observation_configuration_error(settings))

    def test_weather_underground_config_uses_environment_key_reference(self):
        settings = normalise_observation_config(
            {
                "weather": {
                    "provider": "weather_underground",
                    "weather_underground": {
                        "station_id": "iengland123",
                        "api_key_env": "ACP_WU_API_KEY",
                        "refresh_seconds": 45,
                        "pressure_history_hours": 8,
                    },
                }
            }
        )

        self.assertEqual(settings["provider"], "weather_underground")
        self.assertEqual(settings["weather_underground"]["station_id"], "IENGLAND123")
        self.assertEqual(settings["weather_underground"]["api_key_env"], "ACP_WU_API_KEY")
        self.assertEqual(settings["weather_underground"]["refresh_seconds"], 45)
        self.assertEqual(settings["weather_underground"]["pressure_history_hours"], 8)
        self.assertNotIn("api_key", settings["weather_underground"])
        self.assertIsNone(observation_configuration_error(settings))

    def test_weather_underground_requires_station_id(self):
        settings = normalise_observation_config(
            {"weather": {"provider": "weather_underground"}}
        )

        self.assertIn("station ID", observation_configuration_error(settings) or "")

    def test_current_and_history_urls_use_station_and_runtime_api_key(self):
        settings = normalise_observation_config(
            {
                "weather": {
                    "provider": "weather_underground",
                    "weather_underground": {"station_id": "IABC123"},
                }
            }
        )

        current = urlparse(build_weather_underground_current_url(settings, "secret-key"))
        history = urlparse(build_weather_underground_recent_history_url(settings, "secret-key"))
        current_query = parse_qs(current.query)
        history_query = parse_qs(history.query)

        self.assertEqual(current.path, "/v2/pws/observations/current")
        self.assertEqual(history.path, "/v2/pws/observations/all/1day")
        for query in (current_query, history_query):
            self.assertEqual(query["stationId"], ["IABC123"])
            self.assertEqual(query["format"], ["json"])
            self.assertEqual(query["units"], ["e"])
            self.assertEqual(query["numericPrecision"], ["decimal"])
            self.assertEqual(query["apiKey"], ["secret-key"])

    def test_current_payload_maps_to_existing_dashboard_weather_keys(self):
        payload = {
            "observations": [
                {
                    "stationID": "IABC123",
                    "obsTimeUtc": "2026-08-10T01:35:00Z",
                    "softwareType": "GW2000A",
                    "solarRadiation": 123.4,
                    "uv": 2.1,
                    "winddir": 247,
                    "humidity": 74,
                    "imperial": {
                        "temp": 64.4,
                        "windSpeed": 4.5,
                        "windGust": 9.1,
                        "pressure": 29.98,
                        "precipRate": 0.02,
                        "precipTotal": 0.18,
                    },
                }
            ]
        }

        observation = weather_underground_current_to_dashboard(payload)

        self.assertEqual(observation["dateutc"], "2026-08-10T01:35:00Z")
        self.assertEqual(observation["tempf"], 64.4)
        self.assertEqual(observation["humidity"], 74)
        self.assertEqual(observation["windspeedmph"], 4.5)
        self.assertEqual(observation["windgustmph"], 9.1)
        self.assertEqual(observation["winddir"], 247)
        self.assertEqual(observation["pressurein"], 29.98)
        self.assertEqual(observation["rainratein"], 0.02)
        self.assertEqual(observation["dailyrainin"], 0.18)
        self.assertEqual(observation["solarradiation"], 123.4)
        self.assertEqual(observation["uv"], 2.1)
        self.assertIn("IABC123", observation["model"])

    def test_empty_provider_payload_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "current observation"):
            weather_underground_current_to_dashboard({"observations": []})


if __name__ == "__main__":
    unittest.main()
