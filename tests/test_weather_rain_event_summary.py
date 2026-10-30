from __future__ import annotations

import ast
from datetime import datetime
import math
from pathlib import Path
from types import ModuleType
import unittest
from unittest.mock import patch


# System Python on the Pi deliberately does not include Flask. These tests
# execute the actual, selected pure rain helpers directly from dashboard_core,
# without importing the Flask application or replacing system dependencies.
_CORE_FILE = Path(__file__).resolve().parents[1] / "app/dashboard_core.py"
_FUNCTIONS = {
    "parse_float", "parse_datetime", "weather_units", "inches_to_mm",
    "mm_to_inches", "format_float", "dynamic_rain_max_mm",
    "format_rain_mm", "rain_event_summary", "rain_overview_data",
}


def load_rain_helpers() -> ModuleType:
    tree = ast.parse(_CORE_FILE.read_text(encoding="utf-8"),
                     filename=str(_CORE_FILE))
    selected = [node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name in _FUNCTIONS]
    found = {node.name for node in selected}
    if found != _FUNCTIONS:
        raise AssertionError(f"Missing real rain helpers: {_FUNCTIONS - found}")
    module = ModuleType("acp_rain_helper_test")
    module.__dict__.update({"datetime": datetime, "math": math})
    # These are mocked in the focused presentation tests; make them explicit
    # dependencies rather than silently loading Flask-heavy dashboard code.
    module.rain_gauges = lambda *_args, **_kwargs: []
    module.rain_gauge = lambda *_args, **_kwargs: None
    module.rain_amount_mm = lambda *_args, **_kwargs: None
    # dashboard_core.py uses postponed type annotations; preserve that
    # compilation feature so symbols such as Any need not be runtime imports.
    future = ast.ImportFrom(module="__future__",
                            names=[ast.alias(name="annotations")], level=0)
    isolated_tree = ast.Module(body=[future, *selected], type_ignores=[])
    exec(compile(ast.fix_missing_locations(isolated_tree),
                 str(_CORE_FILE), "exec"), module.__dict__)
    return module


core = load_rain_helpers()
rain_event_summary = core.rain_event_summary


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

    def test_active_same_value_is_shown_once_in_event_rain_gauge(self):
        # Real-world case: event source and derived event both say 16.8 mm.
        gauge = {"label": "Event Rain", "value": "16.8 mm", "percent": 84.0,
                 "max_label": "20.0 mm"}
        summary = {"kind": "active", "label": "Active rain event",
                   "value": "16.8 mm", "detail": "Since 19:00"}
        state = {"weather_rain_derived": {"event_active": True,
                 "event_total_in": 16.8 / 25.4}}
        with patch.object(core, "rain_gauges", return_value=[gauge]), \
             patch.object(core, "rain_gauge", return_value=gauge), \
             patch.object(core, "rain_event_summary", return_value=summary):
            gauges, note = core.rain_overview_data(self.config(), {}, state)
        self.assertEqual(gauges, [gauge])
        self.assertIsNone(note)

    def test_distinct_active_derived_event_is_a_gauge_not_a_standalone_tile(self):
        gauge = {"label": "Event Rain", "value": "14.0 mm", "percent": 70.0,
                 "max_label": "20.0 mm"}
        summary = {"kind": "active", "label": "Active rain event",
                   "value": "16.8 mm", "detail": "Since 19:00"}
        state = {"weather_rain_derived": {"event_active": True,
                 "event_total_in": 16.8 / 25.4}}
        with patch.object(core, "rain_gauges", return_value=[gauge]), \
             patch.object(core, "rain_gauge", return_value=gauge), \
             patch.object(core, "rain_event_summary", return_value=summary):
            gauges, note = core.rain_overview_data(self.config(), {}, state)
        self.assertIsNone(note)
        self.assertEqual(len(gauges), 2)
        self.assertEqual(gauges[1]["label"], "Active rain event")
        self.assertEqual(gauges[1]["value"], "16.8 mm")
        self.assertEqual(gauges[1]["max_label"], "20.0 mm")
        self.assertEqual(gauges[1]["percent"], 84.0)
        self.assertEqual(gauges[1]["note"], "Since 19:00")

    def test_zero_event_rain_is_replaced_with_last_completed_event_gauge(self):
        source = {"label": "Event rain", "value": "0.0 mm",
                  "percent": 0.0, "max_label": "5.0 mm"}
        summary = {"kind": "last", "label": "Last rain event",
                   "value": "12.7 mm", "detail": "22/10 23:50–23/10 00:10"}
        state = {"weather_rain_derived": {"last_event_total_in": 0.5,
                 "event_active": False}}
        with patch.object(core, "rain_gauges", return_value=[source]), \
             patch.object(core, "rain_amount_mm", return_value=0), \
             patch.object(core, "rain_event_summary", return_value=summary):
            gauges, note = core.rain_overview_data(self.config(), {}, state)
        self.assertIsNone(note)
        self.assertEqual(len(gauges), 1)
        last = gauges[0]
        self.assertEqual(last["label"], "Last rain event")
        self.assertEqual(last["value"], "12.7 mm")
        self.assertEqual(last["max_label"], "15.0 mm")
        self.assertEqual(last["percent"], 84.7)
        self.assertEqual(last["note"], "22/10 23:50–23/10 00:10")

    def test_last_event_appended_when_source_event_field_is_unavailable(self):
        summary = {"kind": "last", "label": "Last rain event",
                   "value": "0.3 mm", "detail": "29/10 22:33"}
        state = {"weather_rain_derived": {"last_event_total_in": 0.3 / 25.4}}
        with patch.object(core, "rain_gauges", return_value=[]), \
             patch.object(core, "rain_amount_mm", return_value=None), \
             patch.object(core, "rain_event_summary", return_value=summary):
            gauges, note = core.rain_overview_data(self.config(), {}, state)
        self.assertIsNone(note)
        self.assertEqual(len(gauges), 1)
        self.assertEqual(gauges[0]["label"], "Last rain event")
        self.assertEqual(gauges[0]["value"], "0.3 mm")
        self.assertEqual(gauges[0]["max_label"], "5.0 mm")
        self.assertEqual(gauges[0]["note"], "29/10 22:33")

    def test_nonzero_event_rain_keeps_current_event_instead_of_stale_last(self):
        source = {"label": "Event rain", "value": "3.0 mm",
                  "percent": 60.0, "max_label": "5.0 mm"}
        summary = {"kind": "last", "label": "Last rain event",
                   "value": "12.7 mm", "detail": "28/10 14:00"}
        state = {"weather_rain_derived": {"last_event_total_in": 0.5}}
        with patch.object(core, "rain_gauges", return_value=[source]), \
             patch.object(core, "rain_amount_mm",
                          side_effect=lambda field, *_: 3 if field == "event_rain" else 0), \
             patch.object(core, "rain_event_summary", return_value=summary):
            gauges, note = core.rain_overview_data(self.config(), {}, state)
        self.assertEqual(gauges, [source])
        self.assertIsNone(note)

    def test_rain_rate_positive_keeps_current_card_even_if_event_source_zero(self):
        source = {"label": "Event rain", "value": "0.0 mm",
                  "percent": 0.0, "max_label": "5.0 mm"}
        summary = {"kind": "last", "label": "Last rain event",
                   "value": "0.3 mm", "detail": "29/10 22:33"}
        with patch.object(core, "rain_gauges", return_value=[source]), \
             patch.object(core, "rain_amount_mm",
                          side_effect=lambda field, *_: 1 if field == "rain_rate" else 0), \
             patch.object(core, "rain_event_summary", return_value=summary):
            gauges, note = core.rain_overview_data(
                self.config(), {},
                {"weather_rain_derived": {"last_event_total_in": 0.3 / 25.4}},
            )
        self.assertEqual(gauges, [source])
        self.assertIsNone(note)

    def test_last_event_without_a_positive_total_does_not_invent_a_gauge(self):
        source = {"label": "Event rain", "value": "0.0 mm",
                  "percent": 0.0, "max_label": "5.0 mm"}
        summary = {"kind": "last", "label": "Last rain event",
                   "value": "0.3 mm", "detail": "29/10 22:33"}
        with patch.object(core, "rain_gauges", return_value=[source]), \
             patch.object(core, "rain_amount_mm", return_value=0), \
             patch.object(core, "rain_event_summary", return_value=summary):
            gauges, note = core.rain_overview_data(self.config(), {}, {})
        self.assertEqual(gauges, [source])
        self.assertIsNone(note)

    def test_same_minute_last_event_collapses_to_one_dated_end_time(self):
        summary = rain_event_summary(self.config(), {
            "weather_rain_derived": {
                "event_active": False,
                "last_event_total_in": 0.3 / 25.4,
                "last_event_started_at": "2026-10-29T22:33:05",
                "last_event_ended_at": "2026-10-29T22:33:59",
            }
        })
        self.assertEqual(summary["detail"], "29/10 22:33")

    def test_same_day_different_minutes_shares_one_date(self):
        summary = rain_event_summary(self.config(), {
            "weather_rain_derived": {
                "event_active": False,
                "last_event_total_in": 0.3 / 25.4,
                "last_event_started_at": "2026-10-29T22:30:00",
                "last_event_ended_at": "2026-10-29T22:33:59",
            }
        })
        self.assertEqual(summary["detail"], "29/10 22:30–22:33")

    def test_last_event_time_is_inside_gauge_not_footer(self):
        html = (Path(__file__).resolve().parents[1]
                / "app/templates/weather.html").read_text(encoding="utf-8")
        css = (Path(__file__).resolve().parents[1]
               / "app/static/css/weather-rain-history.css").read_text(encoding="utf-8")
        self.assertIn('class="rain-event-time"', html)
        self.assertNotIn('class="rain-event-note"', html)
        self.assertNotIn('<section class="rain-event-summary', html)
        self.assertNotIn("or weather_detail.rain_event_summary", html)
        self.assertIn(".rain-overview-scroll .rain-event-time", css)
        self.assertNotIn(".rain-current-subpanel .rain-event-note", css)

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
