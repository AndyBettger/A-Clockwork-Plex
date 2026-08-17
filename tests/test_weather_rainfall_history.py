from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app.weather_rainfall_history import (
    CONFIRMED_GAP,
    MAX_RANGE_DAYS,
    WeatherRainfallHistoryService,
    contiguous_ranges,
    daily_precip_totals,
    period_dates,
    submitted_rainfall_config,
)


def rainfall_config(period: str = "last_7_days") -> dict:
    return {
        "weather": {
            "weather_underground": {
                "station_id": "IABC123",
                "api_key_env": "ACP_WU_API_KEY",
                "request_timeout_seconds": 8,
            },
            "historical_rainfall": {"period": period},
        }
    }


def history_payload(start: date, end: date, *, amount: float = 0.1, omit: date | None = None) -> dict:
    observations = []
    cursor = start
    while cursor <= end:
        if cursor != omit:
            observations.append(
                {
                    "stationID": "IABC123",
                    "obsTimeLocal": f"{cursor.isoformat()} 23:59:00",
                    "imperial": {"precipTotal": amount},
                }
            )
        cursor += timedelta(days=1)
    return {"observations": observations}


class RainfallHistoryHelperTests(unittest.TestCase):
    def test_supported_periods_resolve_to_expected_dates(self):
        today = date(2026, 8, 16)

        self.assertEqual(period_dates("today", today), [today])
        self.assertEqual(period_dates("last_7_days", today)[0], date(2026, 8, 10))
        self.assertEqual(len(period_dates("last_7_days", today)), 7)
        self.assertEqual(period_dates("current_month", today)[0], date(2026, 8, 1))
        self.assertEqual(period_dates("current_year", today)[0], date(2026, 1, 1))

    def test_missing_days_are_collapsed_into_ranges_no_longer_than_31_days(self):
        days = [date(2026, 1, 1) + timedelta(days=offset) for offset in range(80)]

        ranges = contiguous_ranges(days)

        self.assertEqual(len(ranges), 3)
        for start, end in ranges:
            self.assertLessEqual((end - start).days + 1, MAX_RANGE_DAYS)

    def test_daily_precip_parser_accepts_single_and_wrapped_records(self):
        single = {
            "obsTimeLocal": "2026-08-10 23:59:00",
            "imperial": {"precipTotal": 0.25},
        }
        wrapped = {"observations": [single]}

        self.assertEqual(daily_precip_totals(single), {date(2026, 8, 10): 0.25})
        self.assertEqual(daily_precip_totals(wrapped), {date(2026, 8, 10): 0.25})

    def test_invalid_period_is_rejected_by_settings_normaliser(self):
        with self.assertRaisesRegex(ValueError, "Historical rainfall period"):
            submitted_rainfall_config(rainfall_config(), {"period": "fortnight"})


class RainfallHistoryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.cache_path = Path(self.temporary.name) / "weather-rainfall-history.json"
        self.today = date(2026, 8, 16)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def service(self, config: dict, fetcher, *, current_weather=None, environment=None) -> WeatherRainfallHistoryService:
        return WeatherRainfallHistoryService(
            lambda: config,
            self.cache_path,
            current_weather=current_weather or (lambda: {"dailyrainin": 0.2}),
            environment=environment or (lambda name: "secret-key" if name == "ACP_WU_API_KEY" else None),
            fetcher=fetcher,
            today_provider=lambda: self.today,
        )

    def test_current_year_backfill_uses_range_requests_then_cache_only(self):
        config = rainfall_config("current_year")
        calls = []

        def fetcher(url, params, timeout):
            calls.append((url, dict(params), timeout))
            start = date.fromisoformat(f"{params['startDate'][:4]}-{params['startDate'][4:6]}-{params['startDate'][6:]}")
            end = date.fromisoformat(f"{params['endDate'][:4]}-{params['endDate'][4:6]}-{params['endDate'][6:]}")
            return history_payload(start, end)

        service = self.service(config, fetcher)
        first = service.refresh()
        first_call_count = len(calls)
        second = service.refresh()

        self.assertEqual(first["status"], "ready")
        self.assertGreater(first_call_count, 1)
        self.assertEqual(first_call_count, 8)
        self.assertEqual(len(calls), first_call_count)
        self.assertTrue(second["complete"])
        self.assertTrue(second["coverage_complete"])
        self.assertEqual(second["fetched_ranges"], 0)
        self.assertEqual(second["retried_dates"], 0)
        for _url, params, _timeout in calls:
            start = date.fromisoformat(f"{params['startDate'][:4]}-{params['startDate'][4:6]}-{params['startDate'][6:]}")
            end = date.fromisoformat(f"{params['endDate'][:4]}-{params['endDate'][4:6]}-{params['endDate'][6:]}")
            self.assertLessEqual((end - start).days + 1, 31)
            self.assertNotIn("20260816", (params["startDate"], params["endDate"]))

    def test_last_7_days_total_combines_six_cached_days_with_live_today(self):
        config = rainfall_config("last_7_days")

        def fetcher(url, params, timeout):
            start_text = params["startDate"]
            end_text = params["endDate"]
            start = date(int(start_text[:4]), int(start_text[4:6]), int(start_text[6:]))
            end = date(int(end_text[:4]), int(end_text[4:6]), int(end_text[6:]))
            return history_payload(start, end, amount=0.1)

        service = self.service(config, fetcher, current_weather=lambda: {"dailyrainin": 0.2})
        snapshot = service.refresh()

        self.assertTrue(snapshot["complete"])
        self.assertTrue(snapshot["coverage_complete"])
        self.assertEqual(snapshot["available_days"], 7)
        self.assertAlmostEqual(snapshot["total_in"], 0.8)
        cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        self.assertEqual(len(cache["stations"]["IABC123"]["days"]), 6)
        self.assertNotIn(self.today.isoformat(), cache["stations"]["IABC123"]["days"])
        self.assertNotIn("secret-key", self.cache_path.read_text(encoding="utf-8"))

    def test_range_omission_is_retried_once_as_a_single_day_before_becoming_a_gap(self):
        config = rainfall_config("last_7_days")
        calls = []
        missing_day = date(2026, 8, 12)

        def fetcher(url, params, timeout):
            calls.append(dict(params))
            start_text = params["startDate"]
            end_text = params["endDate"]
            start = date(int(start_text[:4]), int(start_text[4:6]), int(start_text[6:]))
            end = date(int(end_text[:4]), int(end_text[4:6]), int(end_text[6:]))
            omit = missing_day if len(calls) == 1 else None
            return history_payload(start, end, omit=omit)

        service = self.service(config, fetcher)
        snapshot = service.refresh()

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1]["startDate"], "20260812")
        self.assertEqual(calls[1]["endDate"], "20260812")
        self.assertEqual(snapshot["retried_dates"], 1)
        self.assertTrue(snapshot["complete"])
        self.assertTrue(snapshot["coverage_complete"])
        self.assertEqual(snapshot["missing_days"], 0)
        self.assertAlmostEqual(snapshot["total_in"], 0.8)
        cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        self.assertEqual(len(cache["stations"]["IABC123"]["days"]), 6)
        self.assertEqual(cache["stations"]["IABC123"].get("gaps", {}), {})

    def test_confirmed_no_data_day_keeps_ready_minimum_total_and_is_not_refetched(self):
        config = rainfall_config("last_7_days")
        calls = []
        missing_day = date(2026, 8, 12)

        def fetcher(url, params, timeout):
            calls.append(dict(params))
            start_text = params["startDate"]
            end_text = params["endDate"]
            start = date(int(start_text[:4]), int(start_text[4:6]), int(start_text[6:]))
            end = date(int(end_text[:4]), int(end_text[4:6]), int(end_text[6:]))
            return history_payload(start, end, amount=0.1, omit=missing_day)

        service = self.service(config, fetcher)
        first = service.refresh()
        first_call_count = len(calls)
        second = service.refresh()

        self.assertEqual(first_call_count, 2)
        self.assertEqual(first["status"], "ready")
        self.assertTrue(first["complete"])
        self.assertFalse(first["coverage_complete"])
        self.assertEqual(first["missing_days"], 1)
        self.assertEqual(first["missing_dates"], [missing_day.isoformat()])
        self.assertEqual(first["pending_days"], 0)
        self.assertAlmostEqual(first["total_in"], 0.7)
        self.assertEqual(len(calls), first_call_count)
        self.assertTrue(second["complete"])
        self.assertFalse(second["coverage_complete"])
        self.assertEqual(second["fetched_ranges"], 0)
        self.assertEqual(second["retried_dates"], 0)
        self.assertAlmostEqual(second["total_in"], 0.7)

        cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        station = cache["stations"]["IABC123"]
        self.assertNotIn(missing_day.isoformat(), station["days"])
        self.assertEqual(station["gaps"][missing_day.isoformat()], CONFIRMED_GAP)
        self.assertNotIn(None, station["days"].values())

    def test_legacy_null_cache_marker_is_retried_and_replaced(self):
        config = rainfall_config("last_7_days")
        missing_day = date(2026, 8, 12)
        cached_days = {
            (self.today - timedelta(days=offset)).isoformat(): 0.1
            for offset in range(1, 7)
        }
        cached_days[missing_day.isoformat()] = None
        self.cache_path.write_text(
            json.dumps({"version": 1, "stations": {"IABC123": {"days": cached_days}}}),
            encoding="utf-8",
        )
        calls = []

        def fetcher(url, params, timeout):
            calls.append(dict(params))
            return history_payload(missing_day, missing_day, amount=0.3)

        service = self.service(config, fetcher)
        snapshot = service.refresh()

        self.assertTrue(snapshot["complete"])
        self.assertTrue(snapshot["coverage_complete"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["startDate"], "20260812")
        self.assertEqual(calls[0]["endDate"], "20260812")
        cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        self.assertEqual(cache["stations"]["IABC123"]["days"][missing_day.isoformat()], 0.3)
        self.assertEqual(snapshot["cached_days"], 6)

    def test_today_uses_live_reading_without_wu_configuration_or_fetch(self):
        config = {"weather": {"historical_rainfall": {"period": "today"}}}
        calls = []
        service = self.service(
            config,
            lambda *args: calls.append(args),
            current_weather=lambda: {"dailyrainin": 0.37},
            environment=lambda name: None,
        )

        snapshot = service.refresh()

        self.assertEqual(calls, [])
        self.assertEqual(snapshot["status"], "ready")
        self.assertTrue(snapshot["complete"])
        self.assertTrue(snapshot["coverage_complete"])
        self.assertEqual(snapshot["total_in"], 0.37)

    def test_provider_failure_is_supplemental_and_redacts_api_key(self):
        config = rainfall_config("last_7_days")

        def failing_fetcher(url, params, timeout):
            raise RuntimeError(f"history failed with {params['apiKey']}")

        service = self.service(config, failing_fetcher)
        snapshot = service.refresh()

        self.assertEqual(snapshot["status"], "error")
        self.assertIn("history failed", snapshot["last_error"])
        self.assertNotIn("secret-key", snapshot["last_error"])
        self.assertFalse(snapshot["complete"])
        self.assertIsNone(snapshot["total_in"])


if __name__ == "__main__":
    unittest.main()
