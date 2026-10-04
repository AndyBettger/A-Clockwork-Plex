from __future__ import annotations

import unittest

from app.dashboard_core import rain_event_summary


class WeatherRainEventSummaryTests(unittest.TestCase):
    def config(self, provider: str = "weather_underground") -> dict:
        return {
            "weather": {
                "provider": provider,
                "display_units": "metric",
                "units": {"rain": "mm"},
            }
        }

    def test_active_wu_event_shows_total_and_start_time(self):
        summary = rain_event_summary(
            self.config(),
            {
                "weather_rain_derived": {
                    "event_active": True,
                    "event_total_in": 0.3189,
                    "event_started_at": "2026-10-04T22:39:00",
                }
            },
        )

        self.assertEqual(summary["kind"], "active")
        self.assertEqual(summary["label"], "Active rain event")
        self.assertEqual(summary["value"], "8.1 mm")
        self.assertEqual(summary["detail"], "Since 22:39")

    def test_completed_wu_event_retains_cross_midnight_span(self):
        summary = rain_event_summary(
            self.config(),
            {
                "weather_rain_derived": {
                    "event_active": False,
                    "last_event_total_in": 0.5,
                    "last_event_started_at": "2026-10-04T23:50:00",
                    "last_event_ended_at": "2026-10-05T00:10:00",
                    "last_event_closed_at": "2026-10-05T02:10:00",
                }
            },
        )

        self.assertEqual(summary["kind"], "last")
        self.assertEqual(summary["label"], "Last rain event")
        self.assertEqual(summary["value"], "12.7 mm")
        self.assertEqual(summary["detail"], "04/10 23:50–05/10 00:10")

    def test_native_provider_does_not_show_wu_derived_provenance(self):
        summary = rain_event_summary(
            self.config("ecowitt_push"),
            {
                "weather_rain_derived": {
                    "event_active": False,
                    "last_event_total_in": 0.5,
                }
            },
        )

        self.assertIsNone(summary)


if __name__ == "__main__":
    unittest.main()
