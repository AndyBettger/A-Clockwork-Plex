from __future__ import annotations

import unittest
from pathlib import Path


PRESENTER = Path("app/static/js/settings-weather-observations.js")
RUNNER = Path("app/runner.py")
SETTINGS = Path("app/settings_weather_rainfall.py")
WEATHER_TEMPLATE = Path("app/templates/weather.html")


class SettingsWeatherRainfallControlsTests(unittest.TestCase):
    def test_weather_source_is_promoted_to_its_own_runtime_subpage(self) -> None:
        presenter = PRESENTER.read_text(encoding="utf-8")

        self.assertIn("weather:source", presenter)
        self.assertIn("Observation source", presenter)
        self.assertIn("Live provider, WU history and source health", presenter)
        self.assertIn("Dashboard labels and refresh", presenter)
        self.assertIn("weather-settings-source", presenter)

    def test_observation_status_uses_requested_source_labels(self) -> None:
        presenter = PRESENTER.read_text(encoding="utf-8")

        self.assertIn("push: 'Ecowitt Push'", presenter)
        self.assertIn("ready: 'WU Ready'", presenter)
        self.assertIn("data-observation-status", presenter)

    def test_observation_and_rainfall_status_badges_stay_inside_their_card_headings(self) -> None:
        presenter = PRESENTER.read_text(encoding="utf-8")

        self.assertIn("weather-observation-source-card", presenter)
        self.assertIn("weather-rainfall-card", presenter)
        self.assertNotIn("weatherHeader.appendChild(statusChip)", presenter)
        self.assertIn('.weather-settings-source .settings-card-heading {', presenter)
        self.assertIn('grid-template-columns: minmax(0, 1fr) auto;', presenter)
        self.assertIn('.weather-settings-source .settings-chip {', presenter)
        self.assertIn('border-radius: 11px;', presenter)

    def test_weather_source_workspace_spacing_supports_1280x720_and_1024x600(self) -> None:
        presenter = PRESENTER.read_text(encoding="utf-8")

        self.assertIn(
            '.weather-settings-source { gap: clamp(20px, 3.2vmin, 24px); }',
            presenter,
        )
        self.assertIn('column-gap: clamp(14px, 2.4vmin, 18px);', presenter)
        self.assertIn('row-gap: clamp(18px, 2.8vmin, 22px);', presenter)
        self.assertIn('margin: clamp(16px, 2.5vmin, 20px) 0 0;', presenter)
        self.assertIn('[data-wu-commissioning] {', presenter)
        self.assertIn('margin-top: clamp(18px, 2.8vmin, 22px);', presenter)

    def test_history_badge_refreshes_directly_after_credential_actions(self) -> None:
        presenter = PRESENTER.read_text(encoding="utf-8")

        self.assertIn("async function refreshRainfallStatus(force = false)", presenter)
        self.assertIn("'/api/weather/rainfall'", presenter)
        self.assertIn("force ? { method: 'POST', body: '{}' } : {}", presenter)
        self.assertGreaterEqual(presenter.count("await refreshRainfallStatus(true);"), 3)
        self.assertIn("renderStatus(payload);", presenter)
        self.assertNotIn("renderRainfallStatus(snapshot.status?.weather_rainfall", presenter)

    def test_successful_station_gaps_stay_ready_and_explain_minimum_recorded_total(self) -> None:
        presenter = PRESENTER.read_text(encoding="utf-8")

        self.assertIn("ready: 'History ready'", presenter)
        self.assertNotIn("History incomplete", presenter)
        self.assertIn("had no station data. Total shown is the minimum recorded.", presenter)
        self.assertIn("A date omitted from a range is retried once on its own", presenter)
        self.assertIn("confirmed station gaps are counted", presenter)

    def test_rainy_day_fund_can_show_missing-day_coverage_note(self) -> None:
        template = WEATHER_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("{% if gauge.note %}", template)
        self.assertIn('class="rain-coverage-note"', template)
        self.assertIn("{{ gauge.note }}", template)

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
        self.assertIn("rainfall_wake=weather_rainfall.wake", runner)
        self.assertIn("weather_rainfall.start()", runner)
        self.assertIn("weather_rainfall.shutdown()", runner)
        self.assertIn("rainfall=weather_rainfall", runner)
        self.assertIn('"historical_rainfall"', settings)
        self.assertIn('"weather_rainfall"', settings)


if __name__ == "__main__":
    unittest.main()
