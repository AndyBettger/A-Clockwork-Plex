from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path

from app.weather_observation_store import (
    sanitise_weather_observation,
    store_dashboard_observation,
)


class FakeDashboard:
    STATE_PATH = Path("/tmp/not-written-state.json")

    def __init__(self) -> None:
        self.state = {
            "weather": {"old": "reading"},
            "weather_extremes": {"date": "2026-08-10", "fields": {}},
            "pressure_history": [],
            "last_weather_update": None,
        }
        self.extremes_payload = None
        self.pressure_payload = None
        self.saved = None

    def load_config(self):
        return {"weather": {"provider": "weather_underground"}}

    def load_state(self, config):
        return dict(self.state)

    def update_weather_extremes(self, state, payload):
        self.extremes_payload = dict(payload)
        state["weather_extremes"]["touched"] = True

    def update_pressure_history(self, state, payload):
        self.pressure_payload = dict(payload)
        state["pressure_history"].append({"time": "test", "hpa": 1015.2})

    def save_json(self, path, state):
        self.saved = (path, state)


class WeatherObservationStoreTests(unittest.TestCase):
    def test_sanitiser_drops_empty_and_sensitive_fields(self):
        clean = sanitise_weather_observation(
            {
                "tempf": 64.4,
                "humidity": "",
                "api_key": "must-not-persist",
                "PASSKEY": "must-not-persist-either",
                "dateutc": "2026-08-10T02:00:00Z",
            }
        )

        self.assertEqual(
            clean,
            {"tempf": 64.4, "dateutc": "2026-08-10T02:00:00Z"},
        )

    def test_empty_observation_is_rejected_without_replacing_state(self):
        with self.assertRaisesRegex(ValueError, "no usable fields"):
            sanitise_weather_observation({"api_key": "secret", "humidity": ""})

    def test_store_owns_current_extremes_pressure_history_and_issue_time(self):
        dashboard = FakeDashboard()
        now = datetime(2026, 8, 10, 3, 15, 20)

        state = store_dashboard_observation(
            dashboard,
            {
                "tempf": 64.4,
                "baromrelin": 29.98,
                "api_key": "must-not-persist",
            },
            now_provider=lambda: now,
        )

        self.assertEqual(state["weather"], {"tempf": 64.4, "baromrelin": 29.98})
        self.assertEqual(state["last_weather_update"], "2026-08-10T03:15:20")
        self.assertEqual(dashboard.extremes_payload, state["weather"])
        self.assertEqual(dashboard.pressure_payload, state["weather"])
        self.assertEqual(state["pressure_history"], [{"time": "test", "hpa": 1015.2}])
        self.assertEqual(dashboard.saved[0], dashboard.STATE_PATH)
        self.assertIs(dashboard.saved[1], state)
        self.assertNotIn("api_key", str(dashboard.saved))

    def test_runner_owns_remote_observation_service_lifecycle(self):
        source = Path("app/runner.py").read_text(encoding="utf-8")

        self.assertIn("WeatherObservationService", source)
        self.assertIn("register_weather_observation_api", source)
        self.assertIn("store_dashboard_observation", source)
        self.assertIn("weather_observations.start()", source)
        self.assertIn("weather_observations.shutdown()", source)


if __name__ == "__main__":
    unittest.main()
