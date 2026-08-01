from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from flask import Flask

from app.weather_forecast import (
    WeatherForecastService,
    build_open_meteo_url,
    normalise_forecast_config,
    register_weather_forecast_api,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 1, 22, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.value

    def advance(self, **kwargs) -> None:
        self.value += timedelta(**kwargs)


def forecast_config(*, enabled: bool = True) -> dict:
    return {
        "weather": {
            "units": {
                "temperature": "c",
                "pressure": "hpa",
                "rain": "mm",
                "wind": "mph",
            },
            "forecast": {
                "enabled": enabled,
                "provider": "open_meteo",
                "latitude": 51.5,
                "longitude": -0.12,
                "timezone": "Europe/London",
                "forecast_days": 7,
                "refresh_minutes": 30,
                "request_timeout_seconds": 8,
                "stale_after_hours": 6,
            },
        }
    }


def sample_payload() -> dict:
    return {
        "latitude": 51.5,
        "longitude": -0.125,
        "elevation": 25,
        "timezone": "Europe/London",
        "timezone_abbreviation": "BST",
        "current": {
            "time": "2026-08-01T23:00",
            "temperature_2m": 18.2,
            "apparent_temperature": 17.7,
            "precipitation": 0.0,
            "weather_code": 2,
            "wind_speed_10m": 7.4,
            "wind_gusts_10m": 13.1,
        },
        "current_units": {
            "temperature_2m": "°C",
            "apparent_temperature": "°C",
            "precipitation": "mm",
            "wind_speed_10m": "mp/h",
            "wind_gusts_10m": "mp/h",
        },
        "hourly": {
            "time": ["2026-08-01T23:00", "2026-08-02T00:00"],
            "temperature_2m": [18.2, 17.6],
            "apparent_temperature": [17.7, 17.0],
            "precipitation_probability": [15, 30],
            "precipitation": [0.0, 0.2],
            "weather_code": [2, 61],
            "wind_speed_10m": [7.4, 6.8],
            "wind_gusts_10m": [13.1, 12.0],
        },
        "hourly_units": {
            "temperature_2m": "°C",
            "apparent_temperature": "°C",
            "precipitation_probability": "%",
            "precipitation": "mm",
            "wind_speed_10m": "mp/h",
            "wind_gusts_10m": "mp/h",
        },
        "daily": {
            "time": ["2026-08-01", "2026-08-02"],
            "weather_code": [2, 63],
            "temperature_2m_max": [22.4, 19.8],
            "temperature_2m_min": [13.0, 12.6],
            "precipitation_sum": [0.0, 4.2],
            "precipitation_probability_max": [20, 75],
            "wind_speed_10m_max": [12.0, 17.0],
            "wind_gusts_10m_max": [20.0, 29.0],
            "sunrise": ["2026-08-01T05:24", "2026-08-02T05:26"],
            "sunset": ["2026-08-01T20:47", "2026-08-02T20:45"],
        },
        "daily_units": {
            "temperature_2m_max": "°C",
            "temperature_2m_min": "°C",
            "precipitation_sum": "mm",
            "precipitation_probability_max": "%",
            "wind_speed_10m_max": "mp/h",
            "wind_gusts_10m_max": "mp/h",
        },
    }


class WeatherForecastTests(unittest.TestCase):
    def test_url_uses_location_units_and_supported_forecast_variables(self):
        settings = normalise_forecast_config(forecast_config())
        query = parse_qs(urlparse(build_open_meteo_url(settings)).query)

        self.assertEqual(query["latitude"], ["51.5"])
        self.assertEqual(query["longitude"], ["-0.12"])
        self.assertEqual(query["timezone"], ["Europe/London"])
        self.assertEqual(query["temperature_unit"], ["celsius"])
        self.assertEqual(query["wind_speed_unit"], ["mph"])
        self.assertEqual(query["precipitation_unit"], ["mm"])
        self.assertIn("precipitation_probability", query["hourly"][0])
        self.assertIn("sunrise", query["daily"][0])

    def test_disabled_service_never_calls_remote_provider(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            service = WeatherForecastService(
                lambda: forecast_config(enabled=False),
                Path(directory) / "forecast.json",
                fetcher=lambda url, timeout: calls.append((url, timeout)) or sample_payload(),
            )
            snapshot = service.refresh(force=True)

        self.assertEqual(calls, [])
        self.assertEqual(snapshot["status"], "disabled")
        self.assertFalse(snapshot["enabled"])
        self.assertIn("disabled", snapshot["last_error"].lower())

    def test_successful_refresh_normalises_and_persists_forecast(self):
        clock = FakeClock()
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "forecast.json"
            service = WeatherForecastService(
                lambda: forecast_config(),
                cache_path,
                fetcher=lambda url, timeout: calls.append((url, timeout)) or sample_payload(),
                now_provider=clock.now,
            )
            snapshot = service.refresh(force=True)
            persisted = json.loads(cache_path.read_text(encoding="utf-8"))

        self.assertEqual(len(calls), 1)
        self.assertEqual(snapshot["status"], "ready")
        self.assertFalse(snapshot["stale"])
        self.assertEqual(snapshot["forecast"]["current"]["condition"]["tone"], "partly-cloudy")
        self.assertEqual(snapshot["forecast"]["hourly"][1]["condition"]["label"], "Light rain")
        self.assertEqual(snapshot["forecast"]["daily"][1]["precipitation_probability_max"], 75)
        self.assertEqual(snapshot["forecast"]["attribution"]["label"], "Weather data by Open-Meteo.com")
        self.assertEqual(persisted["forecast"]["provider"], "open_meteo")

    def test_remote_failure_preserves_last_good_forecast(self):
        clock = FakeClock()
        fail = {"enabled": False}

        def fetcher(_url: str, _timeout: float) -> dict:
            if fail["enabled"]:
                raise RuntimeError("forecast network unavailable")
            return sample_payload()

        with tempfile.TemporaryDirectory() as directory:
            service = WeatherForecastService(
                lambda: forecast_config(),
                Path(directory) / "forecast.json",
                fetcher=fetcher,
                now_provider=clock.now,
            )
            first = service.refresh(force=True)
            clock.advance(minutes=31)
            fail["enabled"] = True
            second = service.refresh(force=True)

        self.assertEqual(first["status"], "ready")
        self.assertEqual(second["status"], "stale")
        self.assertIsNotNone(second["forecast"])
        self.assertIn("network unavailable", second["last_error"])

    def test_api_get_reads_cache_and_post_forces_refresh(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            service = WeatherForecastService(
                lambda: forecast_config(),
                Path(directory) / "forecast.json",
                fetcher=lambda url, timeout: calls.append((url, timeout)) or sample_payload(),
            )
            app = Flask(__name__)
            register_weather_forecast_api(app, service)
            client = app.test_client()

            before = client.get("/api/weather/forecast")
            refreshed = client.post("/api/weather/forecast")

        self.assertEqual(before.status_code, 200)
        self.assertEqual(before.get_json()["status"], "disabled")
        self.assertEqual(refreshed.status_code, 200)
        self.assertEqual(refreshed.get_json()["status"], "ready")
        self.assertEqual(len(calls), 1)

    def test_runner_owns_forecast_service_lifecycle(self):
        source = Path("app/runner.py").read_text(encoding="utf-8")
        self.assertIn("WeatherForecastService", source)
        self.assertIn("weather_forecast.start()", source)
        self.assertIn("weather_forecast.shutdown()", source)
        self.assertIn("register_weather_forecast_api", source)


if __name__ == "__main__":
    unittest.main()
