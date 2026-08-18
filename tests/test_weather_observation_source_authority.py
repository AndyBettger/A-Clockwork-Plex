from __future__ import annotations

import unittest

from flask import Flask

from app.weather_observation_store import (
    configured_observation_provider,
    promote_ecowitt_observation_store,
)


class _FakeDashboard:
    STATE_PATH = "/tmp/state.json"

    def __init__(self, provider: str) -> None:
        self.config = {"weather": {"provider": provider}}
        self.state = {
            "weather": {"tempf": 61.0, "humidity": 70},
            "last_weather_update": "2026-08-18T00:00:00",
        }
        self.normalise_calls = 0
        self.save_calls = 0

    def load_config(self):
        return self.config

    def load_state(self, _config):
        return self.state

    def normalise_weather_payload(self):
        self.normalise_calls += 1
        return {"tempf": "68.0", "humidity": "55", "tempinf": "71.0"}

    def update_weather_extremes(self, _state, _weather):
        return None

    def update_pressure_history(self, _state, _weather):
        return None

    def save_json(self, _path, state):
        self.save_calls += 1
        self.state = state

    def pick_weather_fields(self, *_args):
        return []

    def weather_detail_data(self, *_args):
        return {}


class WeatherObservationSourceAuthorityTests(unittest.TestCase):
    def test_provider_defaults_to_ecowitt_for_legacy_config(self) -> None:
        self.assertEqual(configured_observation_provider({}), "ecowitt_push")
        self.assertEqual(configured_observation_provider({"weather": {}}), "ecowitt_push")
        self.assertEqual(
            configured_observation_provider({"weather": {"provider": " WEATHER_UNDERGROUND "}}),
            "weather_underground",
        )

    def _app_with_promoted_endpoint(self, dashboard: _FakeDashboard) -> Flask:
        app = Flask(__name__)

        def original():
            return "original"

        app.add_url_rule("/ecowitt", endpoint="api_weather_ecowitt", view_func=original, methods=["POST"])
        promote_ecowitt_observation_store(app, dashboard)
        return app

    def test_wu_selected_acknowledges_ecowitt_without_overwriting_live_state(self) -> None:
        dashboard = _FakeDashboard("weather_underground")
        app = self._app_with_promoted_endpoint(dashboard)

        response = app.test_client().post("/ecowitt", data={"tempinf": "71.0"})

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertFalse(body["stored"])
        self.assertTrue(body["supplemental_indoor_stored"])
        self.assertIn("weather_underground", body["message"])
        self.assertEqual(dashboard.normalise_calls, 1)
        self.assertEqual(dashboard.save_calls, 1)
        self.assertEqual(
            dashboard.state["weather"],
            {"tempf": 61.0, "humidity": 70, "tempinf": "71.0"},
        )
        self.assertIn("last_weather_indoor_update", dashboard.state)

    def test_ecowitt_selected_still_promotes_station_push(self) -> None:
        dashboard = _FakeDashboard("ecowitt_push")
        app = self._app_with_promoted_endpoint(dashboard)

        response = app.test_client().post("/ecowitt", data={"tempf": "68.0"})

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["stored"])
        self.assertEqual(dashboard.normalise_calls, 1)
        self.assertEqual(dashboard.save_calls, 1)
        self.assertEqual(dashboard.state["weather"]["tempinf"], "71.0")


if __name__ == "__main__":
    unittest.main()
