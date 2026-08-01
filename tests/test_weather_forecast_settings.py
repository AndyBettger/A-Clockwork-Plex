from __future__ import annotations

import subprocess
import unittest
from copy import deepcopy
from pathlib import Path

from flask import Flask

from app.weather_forecast_settings import (
    register_weather_forecast_settings_api,
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
