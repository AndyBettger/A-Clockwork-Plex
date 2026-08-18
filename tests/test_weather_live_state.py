from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from app.weather_live_state import (
    augment_daily_max_gust,
    augment_derived_rain,
    fresh_supplemental_indoor,
    update_supplemental_indoor_state,
)


class WeatherLiveStateTests(unittest.TestCase):
    def test_supplemental_indoor_is_fresh_then_expires(self):
        state = {}
        now = datetime(2026, 8, 18, 12, 0, 0)
        stored = update_supplemental_indoor_state(
            state,
            {"tempinf": 72.5, "humidityin": 54, "tempf": 91.0},
            now,
        )
        self.assertEqual(stored, {"tempinf": 72.5, "humidityin": 54})
        self.assertEqual(
            fresh_supplemental_indoor(state, now + timedelta(seconds=120), fresh_seconds=180),
            {"tempinf": 72.5, "humidityin": 54},
        )
        self.assertEqual(
            fresh_supplemental_indoor(state, now + timedelta(seconds=181), fresh_seconds=180),
            {},
        )

    def test_wu_daily_max_gust_tracks_highest_current_gust(self):
        state = {}
        start = datetime(2026, 8, 18, 12, 0, 0)

        first = augment_daily_max_gust(
            state,
            {"windgustmph": 7.2},
            start,
            station_id="ITEST1",
        )
        self.assertEqual(first["maxdailygust"], 7.2)

        peak = augment_daily_max_gust(
            state,
            {"windgustmph": 14.8},
            start + timedelta(minutes=10),
            station_id="ITEST1",
        )
        self.assertEqual(peak["maxdailygust"], 14.8)

        later = augment_daily_max_gust(
            state,
            {"windgustmph": 9.0},
            start + timedelta(minutes=20),
            station_id="ITEST1",
        )
        self.assertEqual(later["maxdailygust"], 14.8)
        self.assertEqual(state["weather_daily_max_gust"]["max_gust_mph"], 14.8)

    def test_wu_daily_max_gust_resets_for_new_day_or_station(self):
        state = {}
        start = datetime(2026, 8, 18, 23, 55, 0)
        augment_daily_max_gust(state, {"windgustmph": 18.0}, start, station_id="OLD")

        next_day = augment_daily_max_gust(
            state,
            {"windgustmph": 4.0},
            datetime(2026, 8, 19, 0, 5, 0),
            station_id="OLD",
        )
        self.assertEqual(next_day["maxdailygust"], 4.0)

        changed_station = augment_daily_max_gust(
            state,
            {"windgustmph": 3.0},
            datetime(2026, 8, 19, 0, 10, 0),
            station_id="NEW",
        )
        self.assertEqual(changed_station["maxdailygust"], 3.0)
        self.assertEqual(state["weather_daily_max_gust"]["station_id"], "NEW")

    def test_native_daily_max_gust_is_not_replaced(self):
        state = {}
        weather = augment_daily_max_gust(
            state,
            {"windgustmph": 9.0, "maxdailygust": 21.5},
            datetime(2026, 8, 18, 12, 0, 0),
            station_id="ITEST1",
        )
        self.assertEqual(weather["maxdailygust"], 21.5)
        self.assertNotIn("weather_daily_max_gust", state)

    def test_hourly_and_event_rain_are_derived_from_successive_daily_totals(self):
        state = {}
        start = datetime(2026, 8, 18, 12, 0, 0)
        first = augment_derived_rain(
            state,
            {"dailyrainin": 0.0, "rainratein": 0.0},
            start,
            station_id="ITEST1",
        )
        self.assertEqual(first["hourlyrainin"], 0.0)
        self.assertEqual(first["eventrainin"], 0.0)

        raining = augment_derived_rain(
            state,
            {"dailyrainin": 0.05, "rainratein": 0.1},
            start + timedelta(minutes=10),
            station_id="ITEST1",
        )
        self.assertAlmostEqual(raining["hourlyrainin"], 0.05, places=6)
        self.assertAlmostEqual(raining["eventrainin"], 0.05, places=6)

        later = augment_derived_rain(
            state,
            {"dailyrainin": 0.07, "rainratein": 0.0},
            start + timedelta(minutes=50),
            station_id="ITEST1",
        )
        self.assertAlmostEqual(later["hourlyrainin"], 0.07, places=6)
        self.assertAlmostEqual(later["eventrainin"], 0.07, places=6)

    def test_small_event_resets_after_dry_hour_when_24h_total_is_below_one_mm(self):
        state = {}
        start = datetime(2026, 8, 18, 12, 0, 0)
        augment_derived_rain(state, {"dailyrainin": 0.0}, start, station_id="ITEST1")
        raining = augment_derived_rain(
            state,
            {"dailyrainin": 0.02},
            start + timedelta(minutes=5),
            station_id="ITEST1",
        )
        self.assertAlmostEqual(raining["eventrainin"], 0.02, places=6)

        dry = augment_derived_rain(
            state,
            {"dailyrainin": 0.02},
            start + timedelta(minutes=66),
            station_id="ITEST1",
        )
        self.assertEqual(dry["hourlyrainin"], 0.0)
        self.assertEqual(dry["eventrainin"], 0.0)

    def test_event_survives_midnight_daily_counter_rollover(self):
        state = {}
        before_midnight = datetime(2026, 8, 18, 23, 50, 0)
        augment_derived_rain(state, {"dailyrainin": 0.0}, before_midnight, station_id="ITEST1")
        augment_derived_rain(
            state,
            {"dailyrainin": 0.05},
            before_midnight + timedelta(minutes=5),
            station_id="ITEST1",
        )
        after_midnight = augment_derived_rain(
            state,
            {"dailyrainin": 0.01},
            datetime(2026, 8, 19, 0, 5, 0),
            station_id="ITEST1",
        )
        self.assertAlmostEqual(after_midnight["hourlyrainin"], 0.06, places=6)
        self.assertAlmostEqual(after_midnight["eventrainin"], 0.06, places=6)

    def test_native_hourly_and_event_values_are_not_replaced(self):
        state = {}
        weather = augment_derived_rain(
            state,
            {"dailyrainin": 1.0, "hourlyrainin": 0.4, "eventrainin": 0.8},
            datetime(2026, 8, 18, 12, 0, 0),
            station_id="ITEST1",
        )
        self.assertEqual(weather["hourlyrainin"], 0.4)
        self.assertEqual(weather["eventrainin"], 0.8)

    def test_station_change_resets_derived_event_state(self):
        state = {}
        now = datetime(2026, 8, 18, 12, 0, 0)
        augment_derived_rain(state, {"dailyrainin": 0.0}, now, station_id="OLD")
        augment_derived_rain(
            state,
            {"dailyrainin": 0.1},
            now + timedelta(minutes=10),
            station_id="OLD",
        )
        changed = augment_derived_rain(
            state,
            {"dailyrainin": 0.0},
            now + timedelta(minutes=20),
            station_id="NEW",
        )
        self.assertEqual(changed["eventrainin"], 0.0)
        self.assertEqual(state["weather_rain_derived"]["station_id"], "NEW")


if __name__ == "__main__":
    unittest.main()
