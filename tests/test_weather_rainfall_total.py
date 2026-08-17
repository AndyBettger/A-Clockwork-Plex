from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.weather_rainfall_total import register_calculated_rain_total


class CalculatedRainTotalTests(unittest.TestCase):
    def test_replaces_station_lifetime_with_previous_plus_current_year(self) -> None:
        def base_detail(_config, _weather, _state):
            return {
                "rain_longer_gauges": [
                    {"label": "Rain this year", "value": "127.0 mm", "percent": 50, "max_label": "250 mm"},
                    {"label": "Rain last year", "value": "254.0 mm", "percent": 50, "max_label": "500 mm"},
                    {"label": "Total rain", "value": "0.0 mm", "percent": 0, "max_label": "5 mm"},
                ]
            }

        core = SimpleNamespace(
            weather_detail_data=base_detail,
            dynamic_rain_max_mm=lambda amount: amount + 19.0,
            format_rain_mm=lambda amount, _config: f"{amount:.1f} mm",
        )
        dashboard = SimpleNamespace(core=core, weather_detail_data=base_detail)
        service = SimpleNamespace(
            dashboard_calculations=lambda _weather: [
                {
                    "period": "previous_year",
                    "total_in": 10.0,
                    "complete": True,
                    "missing_days": 8,
                },
                {
                    "period": "current_year",
                    "total_in": 5.0,
                    "complete": True,
                    "missing_days": 3,
                },
            ]
        )

        register_calculated_rain_total(dashboard, service)
        detail = core.weather_detail_data({}, {}, {})

        self.assertIs(core.weather_detail_data, dashboard.weather_detail_data)
        self.assertEqual(
            [gauge["label"] for gauge in detail["rain_longer_gauges"]],
            ["Rain this year", "Rain last year", "Rain total"],
        )
        total = detail["rain_longer_gauges"][-1]
        self.assertEqual(total["value"], "381.0 mm")
        self.assertEqual(total["note"], "Last year + this year · 11 days not recorded")
        self.assertAlmostEqual(total["percent"], 95.2, places=1)

    def test_suppresses_calculated_total_until_both_year_windows_are_complete(self) -> None:
        def base_detail(_config, _weather, _state):
            return {
                "rain_longer_gauges": [
                    {"label": "Rain last year", "value": "254.0 mm", "percent": 50, "max_label": "500 mm"},
                    {"label": "Total rain", "value": "999.0 mm", "percent": 50, "max_label": "1000 mm"},
                ]
            }

        core = SimpleNamespace(
            weather_detail_data=base_detail,
            dynamic_rain_max_mm=lambda amount: amount + 1.0,
            format_rain_mm=lambda amount, _config: f"{amount:.1f} mm",
        )
        dashboard = SimpleNamespace(core=core, weather_detail_data=base_detail)
        service = SimpleNamespace(
            dashboard_calculations=lambda _weather: [
                {
                    "period": "previous_year",
                    "total_in": 10.0,
                    "complete": True,
                    "missing_days": 0,
                },
                {
                    "period": "current_year",
                    "total_in": 5.0,
                    "complete": False,
                    "missing_days": 0,
                },
            ]
        )

        register_calculated_rain_total(dashboard, service)
        detail = core.weather_detail_data({}, {}, {})

        self.assertEqual([gauge["label"] for gauge in detail["rain_longer_gauges"]], ["Rain last year"])


if __name__ == "__main__":
    unittest.main()
