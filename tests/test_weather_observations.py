from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from flask import Flask

from app.weather_observations import (
    WeatherObservationService,
    build_weather_underground_current_url,
    build_weather_underground_recent_history_url,
    normalise_observation_config,
    observation_configuration_error,
    register_weather_observation_api,
    weather_underground_current_to_dashboard,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 10, 2, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.value

    def advance(self, **kwargs) -> None:
        self.value += timedelta(**kwargs)


def weather_config(provider: str = "weather_underground") -> dict:
    return {
        "weather": {
            "provider": provider,
            "ecowitt_push": {
                "path": "/ecowitt",
                "fresh_seconds": 180,
            },
            "weather_underground": {
                "station_id": "IABC123",
                "api_key_env": "ACP_WU_API_KEY",
                "refresh_seconds": 60,
                "stale_seconds": 300,
                "request_timeout_seconds": 8,
                "pressure_history_hours": 6,
            },
        }
    }


def current_payload() -> dict:
    return {
        "observations": [
            {
                "stationID": "IABC123",
                "obsTimeUtc": "2026-08-10T01:59:00Z",
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
        settings = normalise_observation_config(weather_config())

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
        observation = weather_underground_current_to_dashboard(current_payload())

        self.assertEqual(observation["dateutc"], "2026-08-10T01:59:00Z")
        self.assertEqual(observation["tempf"], 64.4)
        self.assertEqual(observation["humidity"], 74)
        self.assertEqual(observation["windspeedmph"], 4.5)
        self.assertEqual(observation["windgustmph"], 9.1)
        self.assertEqual(observation["winddir"], 247)
        self.assertEqual(observation["baromrelin"], 29.98)
        self.assertNotIn("pressurein", observation)
        self.assertEqual(observation["rainratein"], 0.02)
        self.assertEqual(observation["dailyrainin"], 0.18)
        self.assertEqual(observation["solarradiation"], 123.4)
        self.assertEqual(observation["uv"], 2.1)
        self.assertIn("IABC123", observation["model"])

    def test_empty_provider_payload_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "current observation"):
            weather_underground_current_to_dashboard({"observations": []})


class WeatherObservationServiceTests(unittest.TestCase):
    def test_ecowitt_provider_is_passive_and_never_fetches(self):
        calls = []
        writes = []
        service = WeatherObservationService(
            lambda: weather_config("ecowitt_push"),
            writes.append,
            fetcher=lambda url, timeout: calls.append((url, timeout)) or current_payload(),
            environment=lambda name: "secret-key",
        )

        snapshot = service.refresh(force=True)

        self.assertEqual(calls, [])
        self.assertEqual(writes, [])
        self.assertEqual(snapshot["provider"], "ecowitt_push")
        self.assertEqual(snapshot["status"], "push")
        self.assertTrue(snapshot["ok"])

    def test_weather_underground_refresh_writes_mapped_observation(self):
        clock = FakeClock()
        calls = []
        writes = []
        service = WeatherObservationService(
            lambda: weather_config(),
            writes.append,
            fetcher=lambda url, timeout: calls.append((url, timeout)) or current_payload(),
            environment=lambda name: "secret-key" if name == "ACP_WU_API_KEY" else None,
            now_provider=clock.now,
        )

        snapshot = service.refresh(force=True)

        self.assertEqual(len(calls), 1)
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0]["baromrelin"], 29.98)
        self.assertEqual(snapshot["status"], "ready")
        self.assertTrue(snapshot["ok"])
        self.assertEqual(snapshot["last_field_count"], len(writes[0]))
        self.assertEqual(snapshot["last_observation_at"], "2026-08-10T01:59:00+00:00")
        self.assertTrue(snapshot["credential_available"])
        self.assertNotIn("secret-key", str(snapshot))
        self.assertNotIn("apiKey", str(snapshot))

    def test_refresh_interval_prevents_duplicate_remote_poll(self):
        clock = FakeClock()
        calls = []
        service = WeatherObservationService(
            lambda: weather_config(),
            lambda observation: None,
            fetcher=lambda url, timeout: calls.append((url, timeout)) or current_payload(),
            environment=lambda name: "secret-key",
            now_provider=clock.now,
        )

        service.refresh(force=False)
        clock.advance(seconds=30)
        service.refresh(force=False)
        clock.advance(seconds=31)
        service.refresh(force=False)

        self.assertEqual(len(calls), 2)

    def test_missing_runtime_api_key_is_reported_without_fetch_or_secret(self):
        calls = []
        service = WeatherObservationService(
            lambda: weather_config(),
            lambda observation: None,
            fetcher=lambda url, timeout: calls.append((url, timeout)) or current_payload(),
            environment=lambda name: None,
        )

        snapshot = service.refresh(force=True)

        self.assertEqual(calls, [])
        self.assertEqual(snapshot["status"], "credentials_required")
        self.assertFalse(snapshot["credential_available"])
        self.assertEqual(snapshot["settings"]["api_key_env"], "ACP_WU_API_KEY")
        self.assertNotIn("api_key", snapshot["settings"])

    def test_remote_failure_is_degraded_then_stale_after_last_success(self):
        clock = FakeClock()
        failing = {"value": False}

        def fetcher(url: str, timeout: float) -> dict:
            if failing["value"]:
                raise RuntimeError("upstream unavailable for secret-key")
            return current_payload()

        service = WeatherObservationService(
            lambda: weather_config(),
            lambda observation: None,
            fetcher=fetcher,
            environment=lambda name: "secret-key",
            now_provider=clock.now,
        )

        self.assertEqual(service.refresh(force=True)["status"], "ready")
        clock.advance(seconds=61)
        failing["value"] = True
        degraded = service.refresh(force=True)
        clock.advance(seconds=301)
        stale = service.snapshot()

        self.assertEqual(degraded["status"], "degraded")
        self.assertIn("upstream unavailable", degraded["last_error"])
        self.assertNotIn("secret-key", degraded["last_error"])
        self.assertEqual(stale["status"], "stale")

    def test_api_get_reports_status_and_post_forces_remote_refresh(self):
        calls = []
        service = WeatherObservationService(
            lambda: weather_config(),
            lambda observation: None,
            fetcher=lambda url, timeout: calls.append((url, timeout)) or current_payload(),
            environment=lambda name: "secret-key",
        )
        app = Flask(__name__)
        register_weather_observation_api(app, service)
        client = app.test_client()

        before = client.get("/api/weather/observations")
        refreshed = client.post("/api/weather/observations")

        self.assertEqual(before.status_code, 200)
        self.assertEqual(before.get_json()["status"], "pending")
        self.assertEqual(refreshed.status_code, 200)
        self.assertEqual(refreshed.get_json()["status"], "ready")
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
