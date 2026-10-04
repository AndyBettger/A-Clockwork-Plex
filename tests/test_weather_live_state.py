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
            {"dateutc": "2026-08-18T12:00:00", "dailyrainin": 0.0, "rainratein": 0.0},
            start,
            station_id="ITEST1",
        )
        self.assertEqual(first["hourlyrainin"], 0.0)
        self.assertEqual(first["eventrainin"], 0.0)

        raining = augment_derived_rain(
            state,
            {"dateutc": "2026-08-18T12:10:00", "dailyrainin": 0.05, "rainratein": 0.1},
            start + timedelta(minutes=10),
            station_id="ITEST1",
        )
        self.assertAlmostEqual(raining["hourlyrainin"], 0.05, places=6)
        self.assertAlmostEqual(raining["eventrainin"], 0.05, places=6)

        later = augment_derived_rain(
            state,
            {"dateutc": "2026-08-18T12:50:00", "dailyrainin": 0.07, "rainratein": 0.0},
            start + timedelta(minutes=50),
            station_id="ITEST1",
        )
        self.assertAlmostEqual(later["hourlyrainin"], 0.07, places=6)
        self.assertAlmostEqual(later["eventrainin"], 0.07, places=6)
        model = state["weather_rain_derived"]
        self.assertTrue(model["event_active"])
        self.assertEqual(model["event_started_at"], "2026-08-18T12:10:00")
        self.assertEqual(model["event_last_rain_at"], "2026-08-18T12:50:00")
        self.assertEqual(model["event_dry_gap_seconds"], 7200)

    def test_event_closes_only_after_two_continuously_dry_hours(self):
        state = {}
        start = datetime(2026, 8, 18, 12, 0, 0)
        augment_derived_rain(state, {"dateutc": "2026-08-18T12:00:00", "dailyrainin": 0.0}, start, station_id="ITEST1")
        raining = augment_derived_rain(
            state,
            {"dateutc": "2026-08-18T12:05:00", "dailyrainin": 0.02},
            start + timedelta(minutes=5),
            station_id="ITEST1",
        )
        self.assertAlmostEqual(raining["eventrainin"], 0.02, places=6)

        not_yet_closed = augment_derived_rain(
            state,
            {"dateutc": "2026-08-18T14:04:00", "dailyrainin": 0.02, "rainratein": 0.0},
            start + timedelta(hours=2, minutes=4),
            station_id="ITEST1",
        )
        self.assertAlmostEqual(not_yet_closed["eventrainin"], 0.02, places=6)

        closed = augment_derived_rain(
            state,
            {"dateutc": "2026-08-18T14:05:00", "dailyrainin": 0.02, "rainratein": 0.0},
            start + timedelta(hours=2, minutes=5),
            station_id="ITEST1",
        )
        self.assertEqual(closed["hourlyrainin"], 0.0)
        self.assertEqual(closed["eventrainin"], 0.0)
        model = state["weather_rain_derived"]
        self.assertFalse(model["event_active"])
        self.assertAlmostEqual(model["last_event_total_in"], 0.02, places=6)
        self.assertEqual(model["last_event_started_at"], "2026-08-18T12:05:00")
        self.assertEqual(model["last_event_ended_at"], "2026-08-18T12:05:00")
        self.assertEqual(model["last_event_closed_at"], "2026-08-18T14:05:00")

    def test_new_rain_after_two_hour_gap_starts_a_new_event(self):
        state = {}
        start = datetime(2026, 8, 18, 12, 0, 0)
        augment_derived_rain(state, {"dateutc": "2026-08-18T12:00:00", "dailyrainin": 0.0}, start, station_id="ITEST1")
        augment_derived_rain(
            state,
            {"dateutc": "2026-08-18T12:05:00", "dailyrainin": 0.04, "rainratein": 0.1},
            start + timedelta(minutes=5),
            station_id="ITEST1",
        )
        closed = augment_derived_rain(
            state,
            {"dateutc": "2026-08-18T14:05:00", "dailyrainin": 0.04, "rainratein": 0.0},
            start + timedelta(hours=2, minutes=5),
            station_id="ITEST1",
        )
        self.assertEqual(closed["eventrainin"], 0.0)

        second_shower = augment_derived_rain(
            state,
            {"dateutc": "2026-08-18T14:20:00", "dailyrainin": 0.06, "rainratein": 0.1},
            start + timedelta(hours=2, minutes=20),
            station_id="ITEST1",
        )

        self.assertAlmostEqual(second_shower["eventrainin"], 0.02, places=6)
        model = state["weather_rain_derived"]
        self.assertAlmostEqual(model["last_event_total_in"], 0.04, places=6)
        self.assertEqual(model["last_event_ended_at"], "2026-08-18T12:05:00")
        self.assertEqual(model["last_event_closed_at"], "2026-08-18T14:05:00")
        self.assertEqual(model["event_started_at"], "2026-08-18T14:20:00")
        self.assertEqual(model["event_last_rain_at"], "2026-08-18T14:20:00")

    def test_event_survives_real_midnight_daily_counter_rollover(self):
        state = {}
        before_midnight = datetime(2026, 8, 18, 23, 50, 0)
        augment_derived_rain(
            state,
            {"dateutc": "2026-08-18T23:50:00", "dailyrainin": 0.0},
            before_midnight,
            station_id="ITEST1",
        )
        augment_derived_rain(
            state,
            {"dateutc": "2026-08-18T23:55:00", "dailyrainin": 0.05},
            before_midnight + timedelta(minutes=5),
            station_id="ITEST1",
        )
        after_midnight = augment_derived_rain(
            state,
            {"dateutc": "2026-08-19T00:05:00", "dailyrainin": 0.01},
            datetime(2026, 8, 19, 0, 5, 0),
            station_id="ITEST1",
        )
        self.assertAlmostEqual(after_midnight["hourlyrainin"], 0.06, places=6)
        self.assertAlmostEqual(after_midnight["eventrainin"], 0.06, places=6)
        self.assertEqual(state["weather_rain_derived"]["last_date"], "2026-08-19")

    def test_stale_pre_midnight_station_observation_is_not_counted_after_midnight(self):
        state = {}
        augment_derived_rain(
            state,
            {"dateutc": "2026-08-18T23:50:00", "dailyrainin": 0.0},
            datetime(2026, 8, 18, 23, 50, 0),
            station_id="ITEST1",
        )
        augment_derived_rain(
            state,
            {"dateutc": "2026-08-18T23:58:00", "dailyrainin": 0.04},
            datetime(2026, 8, 18, 23, 58, 0),
            station_id="ITEST1",
        )

        stale_after_midnight = augment_derived_rain(
            state,
            {"dateutc": "2026-08-18T23:59:50", "dailyrainin": 0.04},
            datetime(2026, 8, 19, 0, 0, 4),
            station_id="ITEST1",
        )
        self.assertAlmostEqual(stale_after_midnight["eventrainin"], 0.04, places=6)
        self.assertEqual(state["weather_rain_derived"]["last_date"], "2026-08-18")
        self.assertEqual(state["weather_rain_derived"]["last_received_at"], "2026-08-19T00:00:04")
        self.assertEqual(state["weather_rain_derived"]["last_observed_at"], "2026-08-18T23:59:50")

        genuine_new_day = augment_derived_rain(
            state,
            {"dateutc": "2026-08-19T00:01:00", "dailyrainin": 0.01},
            datetime(2026, 8, 19, 0, 2, 0),
            station_id="ITEST1",
        )
        self.assertAlmostEqual(genuine_new_day["hourlyrainin"], 0.05, places=6)
        self.assertAlmostEqual(genuine_new_day["eventrainin"], 0.05, places=6)
        self.assertEqual(state["weather_rain_derived"]["last_date"], "2026-08-19")

    def test_out_of_order_station_observation_does_not_regress_counter_state(self):
        state = {}
        augment_derived_rain(
            state,
            {"dateutc": "2026-08-18T12:00:00", "dailyrainin": 0.0},
            datetime(2026, 8, 18, 12, 0, 0),
            station_id="ITEST1",
        )
        augment_derived_rain(
            state,
            {"dateutc": "2026-08-18T12:10:00", "dailyrainin": 0.05},
            datetime(2026, 8, 18, 12, 10, 0),
            station_id="ITEST1",
        )
        stale = augment_derived_rain(
            state,
            {"dateutc": "2026-08-18T12:09:00", "dailyrainin": 0.06},
            datetime(2026, 8, 18, 12, 20, 0),
            station_id="ITEST1",
        )
        self.assertAlmostEqual(stale["eventrainin"], 0.05, places=6)
        model = state["weather_rain_derived"]
        self.assertEqual(model["last_daily_in"], 0.05)
        self.assertEqual(model["last_observed_at"], "2026-08-18T12:10:00")
        self.assertEqual(model["last_payload_observed_at"], "2026-08-18T12:09:00")

    def test_legacy_derived_state_is_rebaselined_without_relabelling_old_event(self):
        state = {
            "weather_rain_derived": {
                "station_id": "ITEST1",
                "last_observed_at": "2026-09-30T23:12:04",
                "last_date": "2026-09-30",
                "last_daily_in": 0.42,
                "increments": [
                    {"time": "2026-09-30T00:00:04", "amount_in": 0.04},
                    {"time": "2026-09-30T23:01:00", "amount_in": 0.38},
                ],
                "event_total_in": 0.50,
            }
        }

        rebased = augment_derived_rain(
            state,
            {
                "dateutc": "2026-10-04T12:00:00",
                "dailyrainin": 0.20,
                "rainratein": 0.0,
            },
            datetime(2026, 10, 4, 12, 0, 5),
            station_id="ITEST1",
        )

        self.assertEqual(rebased["hourlyrainin"], 0.0)
        self.assertEqual(rebased["eventrainin"], 0.0)
        model = state["weather_rain_derived"]
        self.assertEqual(model["schema_version"], 2)
        self.assertEqual(model["last_daily_in"], 0.20)
        self.assertEqual(model["increments"], [])
        self.assertFalse(model["event_active"])
        self.assertIsNone(model["last_event_total_in"])

    def test_existing_daily_total_is_counter_baseline_not_a_new_event(self):
        state = {}
        first = augment_derived_rain(
            state,
            {
                "dateutc": "2026-10-04T12:00:00",
                "dailyrainin": 0.30,
                "rainratein": 0.0,
            },
            datetime(2026, 10, 4, 12, 0, 3),
            station_id="ITEST1",
        )
        self.assertEqual(first["hourlyrainin"], 0.0)
        self.assertEqual(first["eventrainin"], 0.0)

        next_bucket = augment_derived_rain(
            state,
            {
                "dateutc": "2026-10-04T12:10:00",
                "dailyrainin": 0.32,
                "rainratein": 0.1,
            },
            datetime(2026, 10, 4, 12, 10, 2),
            station_id="ITEST1",
        )
        self.assertAlmostEqual(next_bucket["hourlyrainin"], 0.02, places=6)
        self.assertAlmostEqual(next_bucket["eventrainin"], 0.02, places=6)
        self.assertEqual(
            state["weather_rain_derived"]["event_started_at"],
            "2026-10-04T12:10:00",
        )

    def test_two_hour_observation_gap_rebaselines_instead_of_joining_unknown_rain(self):
        state = {}
        start = datetime(2026, 10, 4, 8, 0, 0)
        augment_derived_rain(
            state,
            {"dateutc": "2026-10-04T08:00:00", "dailyrainin": 0.0},
            start,
            station_id="ITEST1",
        )
        augment_derived_rain(
            state,
            {"dateutc": "2026-10-04T08:10:00", "dailyrainin": 0.05, "rainratein": 0.1},
            start + timedelta(minutes=10),
            station_id="ITEST1",
        )

        after_gap = augment_derived_rain(
            state,
            {"dateutc": "2026-10-04T11:00:00", "dailyrainin": 0.20, "rainratein": 0.0},
            start + timedelta(hours=3),
            station_id="ITEST1",
        )

        self.assertEqual(after_gap["hourlyrainin"], 0.0)
        self.assertEqual(after_gap["eventrainin"], 0.0)
        model = state["weather_rain_derived"]
        self.assertAlmostEqual(model["last_event_total_in"], 0.05, places=6)
        self.assertEqual(model["last_event_ended_at"], "2026-10-04T08:10:00")
        self.assertEqual(model["last_event_closed_at"], "2026-10-04T10:10:00")
        self.assertEqual(model["last_daily_in"], 0.20)

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
