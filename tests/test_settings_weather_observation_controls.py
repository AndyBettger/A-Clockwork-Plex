from __future__ import annotations

import unittest
from pathlib import Path


TEMPLATE = Path("app/templates/settings.html")
PRESENTER = Path("app/static/js/settings-weather-observations.js")


class SettingsWeatherObservationControlsTests(unittest.TestCase):
    def test_weather_station_page_exposes_supported_observation_settings(self) -> None:
        source = TEMPLATE.read_text(encoding="utf-8")

        expected_paths = (
            "weather.observations.provider",
            "weather.observations.ecowitt_push.path",
            "weather.observations.ecowitt_push.fresh_seconds",
            "weather.observations.weather_underground.station_id",
            "weather.observations.weather_underground.refresh_seconds",
            "weather.observations.weather_underground.stale_seconds",
            "weather.observations.weather_underground.request_timeout_seconds",
        )
        for path in expected_paths:
            self.assertIn(f'data-setting-path="{path}"', source)

        self.assertIn('value="ecowitt_push"', source)
        self.assertIn('value="weather_underground"', source)
        self.assertIn('data-observation-provider-panel="ecowitt_push"', source)
        self.assertIn('data-observation-provider-panel="weather_underground"', source)

    def test_secret_remains_outside_revisioned_settings_model(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8")
        presenter = PRESENTER.read_text(encoding="utf-8")

        self.assertNotIn('data-setting-path="weather.observations.weather_underground.api_key"', template)
        self.assertNotIn('data-setting-path="weather.observations.weather_underground.apikey"', template)
        self.assertNotIn('data-setting-path="weather.observations.weather_underground.secret"', template)
        self.assertNotIn('data-setting-path="weather.observations.weather_underground.token"', template)
        self.assertNotIn('data-setting-path="weather.observations.weather_underground.api_key"', presenter)
        self.assertIn('type="password"', presenter)
        self.assertIn('data-wu-api-key', presenter)
        self.assertIn('write-only', presenter)
        self.assertIn("elements.input.value = ''", presenter)

    def test_commissioning_uses_dedicated_credential_and_test_endpoints(self) -> None:
        presenter = PRESENTER.read_text(encoding="utf-8")

        self.assertIn("/api/weather/underground/credentials", presenter)
        self.assertIn("/api/weather/underground/test", presenter)
        self.assertIn("method: 'POST'", presenter)
        self.assertIn("method: 'DELETE'", presenter)
        self.assertIn("JSON.stringify({ api_key: key })", presenter)
        self.assertIn("Test connection", presenter)
        self.assertNotIn("localStorage", presenter)
        self.assertNotIn("sessionStorage", presenter)

    def test_forecast_copy_keeps_open_meteo_independent_of_observation_provider(self) -> None:
        source = TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("current observations use the provider selected under Station", source)
        self.assertIn("<strong>Open-Meteo</strong>", source)
        self.assertNotIn("Ecowitt remains the observation source", source)

    def test_observation_presenter_still_presents_unified_runtime_state(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8")
        presenter = PRESENTER.read_text(encoding="utf-8")

        self.assertIn("settings-weather-observations.js", template)
        self.assertIn("ACPUnifiedSettings?.getSnapshot", presenter)
        self.assertIn("data-observation-provider-panel", presenter)
        self.assertIn("credentials_required", presenter)
        self.assertIn("configuration_required", presenter)
        self.assertNotIn("/api/weather/observations", presenter)

    def test_pressure_history_control_is_not_presented_as_a_working_bootstrap(self) -> None:
        source = TEMPLATE.read_text(encoding="utf-8")

        self.assertNotIn(
            'data-setting-path="weather.observations.weather_underground.pressure_history_hours"',
            source,
        )


if __name__ == "__main__":
    unittest.main()
