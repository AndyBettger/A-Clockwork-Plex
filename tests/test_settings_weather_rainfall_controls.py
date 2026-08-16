from __future__ import annotations

import unittest
from pathlib import Path


PRESENTER = Path("app/static/js/settings-weather-observations.js")
RUNNER = Path("app/runner.py")
SETTINGS = Path("app/settings_weather_rainfall.py")


class SettingsWeatherRainfallControlsTests(unittest.TestCase):
    def test_weather_source_is_promoted_to_its_own_runtime_subpage(self) -> None:
        presenter = PRESENTER.read_text(encoding="utf-8")

        self.assertIn("weather:source", presenter)
        self.assertIn("Observation source", presenter)
        self.assertIn("Live provider, WU history and source health", presenter)
        self.assertIn("Dashboard labels and refresh", presenter)
        self.assertIn("weather-settings-source", presenter)

    def test_history_period_exposes_exact_four_choices(self) -> None:
        presenter = PRESENTER.read_text(encoding="utf-8")

        self.assertIn('data-setting-path="weather.historical_rainfall.period"', presenter)
        for value, label in (
            ("today", "Today"),
            ("last_7_days", "Last 7 days"),
            ("current_month", "Current month"),
            ("current_year", "Current year"),
        ):
            self.assertIn(f'<option value="{value}">{label}</option>', presenter)

    def test_observation_status_uses_requested_source_labels(self) -> None:
        presenter = PRESENTER.read_text(encoding="utf-8")

        self.assertIn("push: 'Ecowitt Push'", presenter)
        self.assertIn("ready: 'WU Ready'", presenter)
        self.assertIn("data-observation-status", presenter)

    def test_wu_history_configuration_remains_available_with_ecowitt_live_source(self) -> None:
        presenter = PRESENTER.read_text(encoding="utf-8")

        self.assertIn("historyNeedsWu", presenter)
        self.assertIn("independent of the live observation provider", presenter.lower())
        self.assertIn("write-only API key", presenter)

    def test_production_runner_registers_and_lifecycles_rainfall_service(self) -> None:
        runner = RUNNER.read_text(encoding="utf-8")
        settings = SETTINGS.read_text(encoding="utf-8")

        self.assertIn("WeatherRainfallHistoryService", runner)
        self.assertIn("register_weather_rainfall(app, dashboard, weather_rainfall)", runner)
        self.assertIn("weather_rainfall.start()", runner)
        self.assertIn("weather_rainfall.shutdown()", runner)
        self.assertIn("rainfall=weather_rainfall", runner)
        self.assertIn('"historical_rainfall"', settings)
        self.assertIn('"weather_rainfall"', settings)


if __name__ == "__main__":
    unittest.main()
