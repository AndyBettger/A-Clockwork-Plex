from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from flask import Flask

from app.weather_rainfall_history import (
    WeatherRainfallHistoryService,
    dashboard_period_dates,
    register_weather_rainfall,
)


def rainfall_config() -> dict:
    return {
        "weather": {
            "weather_underground": {
                "station_id": "IABC123",
                "api_key_env": "ACP_WU_API_KEY",
                "request_timeout_seconds": 8,
            },
            "historical_rainfall": {"period": "current_year"},
        }
    }


def history_payload(start: date, end: date, amount: float = 0.1) -> dict:
    observations = []
    cursor = start
    while cursor <= end:
        observations.append(
            {
                "obsTimeLocal": f"{cursor.isoformat()} 23:59:00",
                "imperial": {"precipTotal": amount},
            }
        )
        cursor = date.fromordinal(cursor.toordinal() + 1)
    return {"observations": observations}


class RainfallDashboardHistoryTests(unittest.TestCase):
    def test_dashboard_periods_are_current_and_previous_calendar_windows(self) -> None:
        today = date(2026, 8, 17)  # Monday
        periods = {period: dates for period, _label, dates in dashboard_period_dates(today)}

        self.assertEqual(periods["current_week"], [today])
        self.assertEqual(periods["previous_week"][0], date(2026, 8, 10))
        self.assertEqual(periods["previous_week"][-1], date(2026, 8, 16))
        self.assertEqual(periods["previous_month"][0], date(2026, 7, 1))
        self.assertEqual(periods["previous_month"][-1], date(2026, 7, 31))
        self.assertEqual(periods["previous_year"][0], date(2025, 1, 1))
        self.assertEqual(periods["previous_year"][-1], date(2025, 12, 31))

    def test_dashboard_history_backfills_previous_year_once_and_reuses_cache(self) -> None:
        today = date(2026, 8, 16)
        calls: list[dict] = []

        def fetcher(_url, params, _timeout):
            calls.append(dict(params))
            start = date(int(params["startDate"][:4]), int(params["startDate"][4:6]), int(params["startDate"][6:]))
            end = date(int(params["endDate"][:4]), int(params["endDate"][4:6]), int(params["endDate"][6:]))
            return history_payload(start, end)

        with tempfile.TemporaryDirectory() as temporary:
            service = WeatherRainfallHistoryService(
                rainfall_config,
                Path(temporary) / "rain.json",
                current_weather=lambda: {"dailyrainin": 0.2},
                environment=lambda name: "secret-key" if name == "ACP_WU_API_KEY" else None,
                fetcher=fetcher,
                today_provider=lambda: today,
                dashboard_history=True,
            )
            first = service.refresh()
            first_call_count = len(calls)
            second = service.refresh()
            calculations = {item["period"]: item for item in service.dashboard_calculations()}

        self.assertEqual(first["status"], "ready")
        self.assertEqual(first["gauge_status"], "ready")
        self.assertEqual(first["fetched_ranges"], 8)
        self.assertEqual(first["gauge_fetched_ranges"], 12)
        self.assertEqual(first_call_count, 20)
        self.assertEqual(len(calls), first_call_count)
        self.assertEqual(second["fetched_ranges"], 0)
        self.assertEqual(second["gauge_fetched_ranges"], 0)
        self.assertAlmostEqual(calculations["previous_year"]["total_in"], 36.5)
        self.assertAlmostEqual(calculations["current_week"]["total_in"], 0.8)

    def test_registration_patches_core_context_projection_and_keeps_lifetime_total(self) -> None:
        def base_detail(_config, _weather, _state):
            return {
                "rain_longer_gauges": [
                    {"label": "Rain this week", "value": "old", "percent": 0, "max_label": "old"},
                    {"label": "Total rain", "value": "99.0 mm", "percent": 50, "max_label": "200 mm"},
                ]
            }

        core = SimpleNamespace(
            weather_detail_data=base_detail,
            dynamic_rain_max_mm=lambda amount: max(5.0, amount + 1.0),
            format_rain_mm=lambda amount, _config: f"{amount:.1f} mm",
        )
        dashboard = SimpleNamespace(core=core, weather_detail_data=base_detail)
        service = SimpleNamespace(
            dashboard_calculations=lambda _weather: [
                {
                    "period": "current_week",
                    "label": "Rain this week",
                    "total_in": 1.0,
                    "complete": True,
                    "missing_days": 0,
                },
                {
                    "period": "previous_week",
                    "label": "Rain last week",
                    "total_in": 2.0,
                    "complete": True,
                    "missing_days": 1,
                },
            ],
            refresh=lambda force=False: {},
            snapshot=lambda: {},
        )
        app = Flask(__name__)

        register_weather_rainfall(app, dashboard, service)
        detail = core.weather_detail_data({}, {}, {})

        self.assertIs(core.weather_detail_data, dashboard.weather_detail_data)
        self.assertEqual(
            [gauge["label"] for gauge in detail["rain_longer_gauges"]],
            ["Rain this week", "Rain last week", "Total rain"],
        )
        self.assertEqual(detail["rain_longer_gauges"][1]["note"], "1 day not recorded")


if __name__ == "__main__":
    unittest.main()
