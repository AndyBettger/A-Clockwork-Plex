from __future__ import annotations

import json
import subprocess
import unittest
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from flask import Flask

from app.weather_forecast_settings import (
    register_weather_forecast_settings_api,
    search_forecast_locations,
    submitted_forecast_config,
)


class FakeForecastService:
    def __init__(self) -> None:
        self.wake_count = 0
        self.refresh_calls: list[bool] = []

    def snapshot(self) -> dict:
        return {
            "status": "disabled",
            "enabled": False,
            "configured": False,
            "forecast": None,
        }

    def wake(self) -> None:
        self.wake_count += 1

    def refresh(self, *, force: bool = False) -> dict:
        self.refresh_calls.append(force)
        return {
            "status": "ready" if force else "disabled",
            "enabled": force,
            "configured": force,
            "forecast": {"provider": "open_meteo"} if force else None,
        }


class FakeHttpResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def base_config() -> dict:
    return {
        "dashboard": {"default_mode": "clock"},
        "weather": {
            "units": {
                "temperature": "c",
                "pressure": "hpa",
                "rain": "mm",
                "wind": "mph",
            },
            "forecast": {
                "enabled": False,
                "provider": "open_meteo",
                "latitude": None,
                "longitude": None,
                "timezone": "Europe/London",
                "forecast_days": 7,
                "refresh_minutes": 30,
                "request_timeout_seconds": 8,
                "stale_after_hours": 6,
            },
        },
        "alarm": {"alarms": [{"id": "wake"}]},
    }


class WeatherForecastSettingsTests(unittest.TestCase):
    def test_disabled_forecast_can_save_without_coordinates(self):
        config, forecast = submitted_forecast_config(
            base_config(),
            {
                "enabled": False,
                "latitude": None,
                "longitude": None,
                "forecast_days": 7,
                "refresh_minutes": 30,
            },
        )

        self.assertFalse(forecast["enabled"])
        self.assertIsNone(forecast["latitude"])
        self.assertIsNone(forecast["longitude"])
        self.assertEqual(config["alarm"]["alarms"][0]["id"], "wake")

    def test_enabled_forecast_requires_valid_coordinates(self):
        with self.assertRaisesRegex(ValueError, "latitude and longitude"):
            submitted_forecast_config(
                base_config(),
                {"enabled": True, "latitude": None, "longitude": None},
            )

        with self.assertRaisesRegex(ValueError, "latitude must be between"):
            submitted_forecast_config(
                base_config(),
                {"enabled": True, "latitude": 91, "longitude": 0},
            )

        with self.assertRaisesRegex(ValueError, "longitude must be between"):
            submitted_forecast_config(
                base_config(),
                {"enabled": True, "latitude": 51.5, "longitude": -181},
            )

    def test_settings_are_normalised_and_bounded_before_persistence(self):
        config, forecast = submitted_forecast_config(
            base_config(),
            {
                "enabled": True,
                "latitude": "51.5014",
                "longitude": "-0.1419",
                "timezone": " Europe/London ",
                "forecast_days": 99,
                "refresh_minutes": 1,
                "request_timeout_seconds": 99,
                "stale_after_hours": 0,
            },
        )

        self.assertEqual(forecast["latitude"], 51.5014)
        self.assertEqual(forecast["longitude"], -0.1419)
        self.assertEqual(forecast["timezone"], "Europe/London")
        self.assertEqual(forecast["forecast_days"], 16)
        self.assertEqual(forecast["refresh_minutes"], 10)
        self.assertEqual(forecast["request_timeout_seconds"], 30)
        self.assertEqual(forecast["stale_after_hours"], 1)
        self.assertEqual(config["weather"]["forecast"], forecast)

    def test_structured_values_are_rejected_instead_of_crashing(self):
        with self.assertRaisesRegex(ValueError, "latitude must be a number"):
            submitted_forecast_config(
                base_config(),
                {"enabled": True, "latitude": [51.5], "longitude": -0.12},
            )

        with self.assertRaisesRegex(ValueError, "forecast days must be a whole number"):
            submitted_forecast_config(
                base_config(),
                {
                    "enabled": False,
                    "forecast_days": {"days": 7},
                },
            )

    def test_location_search_uses_open_meteo_and_returns_only_safe_fields(self):
        captured: dict = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = {key.lower(): value for key, value in request.header_items()}
            captured["timeout"] = timeout
            return FakeHttpResponse(
                {
                    "results": [
                        {
                            "id": 2643743,
                            "name": "London",
                            "latitude": 51.50853,
                            "longitude": -0.12574,
                            "timezone": "Europe/London",
                            "country": "United Kingdom",
                            "country_code": "GB",
                            "admin1": "England",
                            "admin2": "Greater London",
                            "postcodes": ["EC1A", "SW1A"],
                            "population": 8961989,
                            "secret_provider_field": "do not forward",
                        },
                        {"name": "Broken", "latitude": "north", "longitude": 0},
                    ]
                }
            )

        results = search_forecast_locations("  SW1A   1AA  ", opener=opener)
        query = parse_qs(urlsplit(captured["url"]).query)

        self.assertEqual(urlsplit(captured["url"]).netloc, "geocoding-api.open-meteo.com")
        self.assertEqual(query["name"], ["SW1A 1AA"])
        self.assertEqual(query["count"], ["8"])
        self.assertEqual(query["language"], ["en"])
        self.assertEqual(captured["timeout"], 5)
        self.assertIn("A-Clockwork-Plex", captured["headers"]["user-agent"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "London")
        self.assertEqual(results[0]["latitude"], 51.50853)
        self.assertEqual(results[0]["longitude"], -0.12574)
        self.assertEqual(results[0]["timezone"], "Europe/London")
        self.assertEqual(results[0]["postcodes"], ["EC1A", "SW1A"])
        self.assertNotIn("population", results[0])
        self.assertNotIn("secret_provider_field", results[0])

    def test_full_uk_postcode_falls_back_to_postcodes_io_when_open_meteo_has_no_match(self):
        calls: list[str] = []

        def opener(request, timeout):
            host = urlsplit(request.full_url).netloc
            calls.append(host)
            self.assertEqual(timeout, 5)
            if host == "geocoding-api.open-meteo.com":
                return FakeHttpResponse({"results": []})
            if host == "api.postcodes.io":
                self.assertTrue(request.full_url.endswith("/GU307JS"))
                return FakeHttpResponse(
                    {
                        "status": 200,
                        "result": {
                            "postcode": "GU30 7JS",
                            "latitude": 51.03117,
                            "longitude": -0.80376,
                            "country": "England",
                            "region": "South East",
                            "admin_district": "Chichester",
                            "parliamentary_constituency": "Chichester",
                            "quality": 1,
                        },
                    }
                )
            raise AssertionError(f"Unexpected host: {host}")

        results = search_forecast_locations("GU30 7JS", opener=opener)

        self.assertEqual(calls, ["geocoding-api.open-meteo.com", "api.postcodes.io"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "GU30 7JS")
        self.assertEqual(results[0]["latitude"], 51.03117)
        self.assertEqual(results[0]["longitude"], -0.80376)
        self.assertEqual(results[0]["timezone"], "Europe/London")
        self.assertEqual(results[0]["country"], "United Kingdom")
        self.assertEqual(results[0]["country_code"], "GB")
        self.assertEqual(results[0]["admin1"], "England")
        self.assertEqual(results[0]["admin2"], "Chichester")
        self.assertEqual(results[0]["postcodes"], ["GU30 7JS"])
        self.assertNotIn("parliamentary_constituency", results[0])
        self.assertNotIn("quality", results[0])

    def test_non_postcode_empty_open_meteo_search_does_not_call_postcode_fallback(self):
        calls: list[str] = []

        def opener(request, timeout):
            calls.append(urlsplit(request.full_url).netloc)
            return FakeHttpResponse({"results": []})

        results = search_forecast_locations("Nowhere Village", opener=opener)

        self.assertEqual(results, [])
        self.assertEqual(calls, ["geocoding-api.open-meteo.com"])

    def test_location_search_requires_a_useful_query(self):
        with self.assertRaisesRegex(ValueError, "at least 2 characters"):
            search_forecast_locations(" x ", opener=lambda *_args, **_kwargs: None)

    def test_location_lookup_api_is_read_only_and_normalises_query(self):
        searches: list[str] = []
        saves: list[dict] = []
        service = FakeForecastService()
        app = Flask(__name__)

        def fake_location_search(query: str) -> list[dict]:
            searches.append(query)
            return [
                {
                    "name": "Bristol",
                    "latitude": 51.4552,
                    "longitude": -2.5967,
                    "timezone": "Europe/London",
                    "country": "United Kingdom",
                    "country_code": "GB",
                    "admin1": "England",
                    "admin2": "City of Bristol",
                    "postcodes": ["BS1"],
                }
            ]

        register_weather_forecast_settings_api(
            app,
            service,
            base_config,
            lambda config: saves.append(config),
            location_search=fake_location_search,
        )
        response = app.test_client().get("/api/weather/forecast/locations?q=%20Bristol%20%20City%20")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["query"], "Bristol City")
        self.assertEqual(payload["results"][0]["name"], "Bristol")
        self.assertEqual(searches, ["Bristol City"])
        self.assertEqual(saves, [])
        self.assertEqual(service.wake_count, 0)
        self.assertEqual(service.refresh_calls, [])

    def test_location_lookup_api_reports_validation_and_provider_errors(self):
        service = FakeForecastService()
        app = Flask(__name__)

        def unavailable(_query: str) -> list[dict]:
            raise OSError("Forecast location service is unavailable.")

        register_weather_forecast_settings_api(
            app,
            service,
            base_config,
            lambda _config: None,
            location_search=unavailable,
        )
        client = app.test_client()

        invalid = client.get("/api/weather/forecast/locations?q=x")
        unavailable_response = client.get("/api/weather/forecast/locations?q=Bristol")

        self.assertEqual(invalid.status_code, 400)
        self.assertIn("at least 2 characters", invalid.get_json()["error"])
        self.assertEqual(unavailable_response.status_code, 502)
        self.assertIn("unavailable", unavailable_response.get_json()["error"])

    def test_config_api_saves_and_refreshes_without_parent_form_submission(self):
        stored = base_config()
        saves: list[dict] = []
        service = FakeForecastService()
        app = Flask(__name__)

        def load_config() -> dict:
            return deepcopy(stored)

        def save_config(config: dict) -> None:
            stored.clear()
            stored.update(deepcopy(config))
            saves.append(deepcopy(config))

        register_weather_forecast_settings_api(
            app,
            service,
            load_config,
            save_config,
        )
        client = app.test_client()

        initial = client.get("/api/weather/forecast/config")
        saved = client.post(
            "/api/weather/forecast/config",
            json={
                "enabled": True,
                "latitude": 51.5014,
                "longitude": -0.1419,
                "timezone": "Europe/London",
                "forecast_days": 7,
                "refresh_minutes": 30,
            },
        )

        self.assertEqual(initial.status_code, 200)
        self.assertFalse(initial.get_json()["forecast"]["enabled"])
        self.assertEqual(saved.status_code, 200)
        self.assertTrue(saved.get_json()["forecast"]["enabled"])
        self.assertEqual(len(saves), 1)
        self.assertEqual(service.wake_count, 1)
        self.assertEqual(service.refresh_calls, [True])
        self.assertEqual(stored["alarm"]["alarms"][0]["id"], "wake")

    def test_invalid_api_payload_does_not_save_or_refresh(self):
        service = FakeForecastService()
        saves: list[dict] = []
        app = Flask(__name__)
        register_weather_forecast_settings_api(
            app,
            service,
            base_config,
            lambda config: saves.append(config),
        )
        client = app.test_client()

        response = client.post(
            "/api/weather/forecast/config",
            json={"enabled": True, "latitude": "north", "longitude": -0.12},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])
        self.assertEqual(saves, [])
        self.assertEqual(service.wake_count, 0)
        self.assertEqual(service.refresh_calls, [])

    def test_forecast_client_uses_dedicated_api_and_coordinate_keyboard(self):
        client = Path("app/static/js/settings-weather-forecast.js").read_text(encoding="utf-8")
        tabs = Path("app/static/js/settings-tabs.js").read_text(encoding="utf-8")
        keyboard = Path("app/static/js/settings-keyboard.js").read_text(encoding="utf-8")

        self.assertIn("/api/weather/forecast/config", client)
        self.assertIn("type=\"button\" data-forecast-save", client)
        self.assertNotIn("form.submit", client)
        self.assertNotIn("requestSubmit", client)
        self.assertGreaterEqual(client.count('data-keyboard=\"decimal\"'), 2)
        self.assertIn("Open-Meteo.com", client)
        self.assertIn("CC BY 4.0", client)
        self.assertIn("settings-weather-forecast.js", tabs)
        self.assertIn("decimal:", keyboard)
        self.assertIn("['-', '0', '.']", keyboard)

    def test_forecast_client_has_valid_javascript_syntax(self):
        result = subprocess.run(
            ["node", "--check", "app/static/js/settings-weather-forecast.js"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
