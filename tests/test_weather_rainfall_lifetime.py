from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app.weather_rainfall_lifetime import WeatherRainfallLifetimeService


def config() -> dict:
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


def payload_for(start: date, end: date, first_record: date, *, missing: set[date] | None = None) -> dict:
    missing = missing or set()
    observations = []
    cursor = start
    while cursor <= end:
        if cursor >= first_record and cursor not in missing:
            observations.append(
                {
                    "obsTimeLocal": f"{cursor.isoformat()} 23:59:00",
                    "imperial": {"precipTotal": 0.1},
                }
            )
        cursor += timedelta(days=1)
    return {"observations": observations}


class LifetimeRainfallTests(unittest.TestCase):
    def test_discovers_first_record_backfills_coverage_and_then_reuses_cache(self) -> None:
        today = date(2026, 1, 15)
        first_record = date(2024, 11, 15)
        calls: list[dict] = []

        def fetcher(_url, params, _timeout):
            calls.append(dict(params))
            start = date.fromisoformat(
                f"{params['startDate'][:4]}-{params['startDate'][4:6]}-{params['startDate'][6:]}"
            )
            end = date.fromisoformat(
                f"{params['endDate'][:4]}-{params['endDate'][4:6]}-{params['endDate'][6:]}"
            )
            self.assertLessEqual((end - start).days + 1, 31)
            return payload_for(start, end, first_record)

        with tempfile.TemporaryDirectory() as temporary:
            service = WeatherRainfallLifetimeService(
                config,
                Path(temporary) / "lifetime.json",
                environment=lambda name: "secret" if name == "ACP_WU_API_KEY" else None,
                fetcher=fetcher,
                today_provider=lambda: today,
                probe_ranges_per_refresh=10,
                coverage_ranges_per_refresh=10,
                empty_ranges_to_stop=2,
            )
            first = service.refresh()
            call_count = len(calls)
            second = service.refresh()

        self.assertEqual(first["status"], "ready")
        self.assertTrue(first["discovery_complete"])
        self.assertTrue(first["coverage_complete"])
        self.assertEqual(first["first_record_date"], "2024-11-15")
        self.assertEqual(first["available_days"], 47)
        self.assertAlmostEqual(first["total_in"], 4.7)
        self.assertEqual(second["fetched_ranges"], 0)
        self.assertEqual(second["retried_dates"], 0)
        self.assertEqual(len(calls), call_count)

    def test_omitted_day_inside_lifetime_becomes_confirmed_gap_after_single_day_retry(self) -> None:
        today = date(2026, 1, 15)
        first_record = date(2024, 12, 1)
        missing_day = date(2024, 12, 12)
        calls: list[dict] = []

        def fetcher(_url, params, _timeout):
            calls.append(dict(params))
            start = date.fromisoformat(
                f"{params['startDate'][:4]}-{params['startDate'][4:6]}-{params['startDate'][6:]}"
            )
            end = date.fromisoformat(
                f"{params['endDate'][:4]}-{params['endDate'][4:6]}-{params['endDate'][6:]}"
            )
            return payload_for(start, end, first_record, missing={missing_day})

        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "lifetime.json"
            service = WeatherRainfallLifetimeService(
                config,
                archive,
                environment=lambda name: "secret" if name == "ACP_WU_API_KEY" else None,
                fetcher=fetcher,
                today_provider=lambda: today,
                probe_ranges_per_refresh=10,
                coverage_ranges_per_refresh=10,
                empty_ranges_to_stop=2,
            )
            result = service.refresh()
            cached = json.loads(archive.read_text(encoding="utf-8"))

        station = cached["stations"]["IABC123"]
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["missing_days"], 1)
        self.assertGreaterEqual(result["retried_dates"], 1)
        self.assertEqual(station["gaps"][missing_day.isoformat()], "no_station_data")
        self.assertNotIn(missing_day.isoformat(), station["days"])

    def test_configured_start_date_bypasses_discovery_heuristic(self) -> None:
        today = date(2026, 1, 15)
        configured = config()
        configured["weather"]["historical_rainfall"]["lifetime_start_date"] = "2024-12-20"
        calls: list[dict] = []

        def fetcher(_url, params, _timeout):
            calls.append(dict(params))
            start = date.fromisoformat(
                f"{params['startDate'][:4]}-{params['startDate'][4:6]}-{params['startDate'][6:]}"
            )
            end = date.fromisoformat(
                f"{params['endDate'][:4]}-{params['endDate'][4:6]}-{params['endDate'][6:]}"
            )
            return payload_for(start, end, date(2024, 12, 20))

        with tempfile.TemporaryDirectory() as temporary:
            service = WeatherRainfallLifetimeService(
                lambda: configured,
                Path(temporary) / "lifetime.json",
                environment=lambda name: "secret" if name == "ACP_WU_API_KEY" else None,
                fetcher=fetcher,
                today_provider=lambda: today,
                coverage_ranges_per_refresh=10,
            )
            result = service.refresh()

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["configured_start_date"], "2024-12-20")
        self.assertEqual(result["first_record_date"], "2024-12-20")
        self.assertEqual(result["empty_probe_ranges"], 0)
        self.assertTrue(calls)


if __name__ == "__main__":
    unittest.main()
