from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.settings_weather_rainfall import _bounded_airplay_pause_hold_seconds
from app.weather_observation_settings import submitted_observation_config


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/settings.html"
BASE = ROOT / "app/templates/base.html"
NUMERIC_JS = ROOT / "app/static/js/settings-numeric-controls.js"
DISPLAY_JS = ROOT / "app/static/js/settings-display-sections.js"
THEME_CSS = ROOT / "app/static/css/settings-theme-closure.css"


class SettingsNumericControlTests(unittest.TestCase):
    def test_every_number_keyboard_field_has_a_non_text_runtime_owner(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8")
        numeric = NUMERIC_JS.read_text(encoding="utf-8")
        display = DISPLAY_JS.read_text(encoding="utf-8")
        number_paths = set(
            re.findall(r'data-keyboard="number" data-setting-path="([^"]+)"', template)
        )
        expected = {
            "dashboard.idle_timeout_seconds",
            "display.transition_duration_ms",
            "weather.observations.ecowitt_push.fresh_seconds",
            "weather.observations.weather_underground.refresh_seconds",
            "weather.observations.weather_underground.stale_seconds",
            "weather.observations.weather_underground.request_timeout_seconds",
            "weather.auto_refresh_seconds",
            "airplay.pause_hold_seconds",
        }
        self.assertEqual(number_paths, expected)
        for path in expected - {"display.transition_duration_ms"}:
            self.assertIn(f"['{path}', [", numeric)
        self.assertIn("duration.type = 'range'", display)
        self.assertNotIn("input.type = 'number'", numeric)

    def test_human_facing_timings_use_touch_dropdowns_and_keep_420_second_hold(self) -> None:
        source = NUMERIC_JS.read_text(encoding="utf-8")
        dropdown_paths = (
            "dashboard.idle_timeout_seconds",
            "weather.observations.ecowitt_push.fresh_seconds",
            "weather.observations.weather_underground.refresh_seconds",
            "weather.observations.weather_underground.stale_seconds",
            "weather.observations.weather_underground.request_timeout_seconds",
            "weather.auto_refresh_seconds",
            "airplay.pause_hold_seconds",
        )
        for path in dropdown_paths:
            self.assertIn(f"['{path}', [", source)
        self.assertIn("document.createElement('select')", source)
        self.assertIn("input.replaceWith(select)", source)
        self.assertIn("['420', '7 minutes']", source)
        self.assertIn("Math.min(420, parsed)", source)
        self.assertIn("Current custom value", source)
        self.assertIn("addCustomOption(select, value)", source)

        airplay_block = source.split("['airplay.pause_hold_seconds', [", 1)[1].split("    ]],", 1)[0]
        for forbidden in ("600", "900", "1800", "3600"):
            self.assertNotIn(f"['{forbidden}'", airplay_block)

    def test_weather_provider_dropdowns_cover_runtime_boundaries_and_current_defaults(self) -> None:
        source = NUMERIC_JS.read_text(encoding="utf-8")

        ecowitt = source.split("['weather.observations.ecowitt_push.fresh_seconds', [", 1)[1].split("    ]],", 1)[0]
        self.assertIn("['30', '30 seconds']", ecowitt)
        self.assertIn("['300', '5 minutes']", ecowitt)
        self.assertIn("['3600', '1 hour']", ecowitt)

        refresh = source.split("['weather.observations.weather_underground.refresh_seconds', [", 1)[1].split("    ]],", 1)[0]
        self.assertIn("['30', '30 seconds']", refresh)
        self.assertIn("['60', '1 minute']", refresh)
        self.assertIn("['3600', '1 hour']", refresh)

        stale = source.split("['weather.observations.weather_underground.stale_seconds', [", 1)[1].split("    ]],", 1)[0]
        self.assertIn("['60', '1 minute']", stale)
        self.assertIn("['300', '5 minutes']", stale)
        self.assertIn("['21600', '6 hours']", stale)

        timeout = source.split("['weather.observations.weather_underground.request_timeout_seconds', [", 1)[1].split("    ]],", 1)[0]
        self.assertIn("['2', '2 seconds']", timeout)
        self.assertIn("['8', '8 seconds']", timeout)
        self.assertIn("['60', '60 seconds']", timeout)

    def test_airplay_hold_backend_boundary_matches_touch_choices(self) -> None:
        self.assertEqual(_bounded_airplay_pause_hold_seconds(30), 30)
        self.assertEqual(_bounded_airplay_pause_hold_seconds(120), 120)
        self.assertEqual(_bounded_airplay_pause_hold_seconds(420), 420)
        self.assertEqual(_bounded_airplay_pause_hold_seconds(421), 420)
        self.assertEqual(_bounded_airplay_pause_hold_seconds(3600), 420)
        self.assertEqual(_bounded_airplay_pause_hold_seconds(1), 30)
        self.assertEqual(_bounded_airplay_pause_hold_seconds("not-a-number"), 420)

    def test_precise_forecast_coordinates_remain_exact_entry_without_native_spinners(self) -> None:
        source = NUMERIC_JS.read_text(encoding="utf-8")
        self.assertIn(
            "['weather.forecast.latitude', { min: -90, max: 90, step: 0.000001, decimal: true }]",
            source,
        )
        self.assertIn(
            "['weather.forecast.longitude', { min: -180, max: 180, step: 0.000001, decimal: true }]",
            source,
        )
        self.assertIn("input.type = 'text'", source)
        self.assertIn("input.dataset.numericMin", source)
        self.assertIn("input.dataset.numericMax", source)
        self.assertNotIn("input.type = 'number'", source)

    def test_assets_load_in_the_intended_final_order(self) -> None:
        base = BASE.read_text(encoding="utf-8")
        self.assertIn("20260820-settings-theme-closure-v1", base)
        self.assertIn("20260820-numeric-controls-v3", base)
        self.assertLess(
            base.index("daytime-theme-followup.css"),
            base.index("settings-theme-closure.css"),
        )
        self.assertLess(
            base.index("settings-numeric-controls.js"),
            base.index("settings-selects.js"),
        )


class SettingsThemeClosureTests(unittest.TestCase):
    def test_non_classic_text_field_focus_uses_theme_not_literal_cyan(self) -> None:
        source = THEME_CSS.read_text(encoding="utf-8")
        self.assertIn(':not([data-daytime-theme="classic_dark"])', source)
        self.assertIn('body[data-active-page="settings"] .setting-field', source)
        self.assertIn(":focus {", source)
        self.assertIn("outline: 2px solid var(--accent) !important", source)
        self.assertIn("border-color: var(--accent-strong) !important", source)
        self.assertNotIn("143, 211, 255", source)
        self.assertNotIn("#8fd3ff", source.lower())
        self.assertNotIn("#83d8ff", source.lower())

    def test_residual_classic_dark_diagnostic_and_modal_paint_is_palette_owned(self) -> None:
        source = THEME_CSS.read_text(encoding="utf-8")
        for selector in (
            ".settings-json-status",
            ".settings-confirmation-card",
            ".settings-live-trim",
            ".alarm-time-select",
            ".alarm-tone-description",
        ):
            self.assertIn(selector, source)
        self.assertIn("var(--acp-theme-surface-raised)", source)
        self.assertIn("var(--acp-theme-control-border)", source)


class WeatherObservationNumericValidationTests(unittest.TestCase):
    @staticmethod
    def base_config() -> dict:
        return {
            "weather": {
                "provider": "weather_underground",
                "ecowitt_push": {"path": "/ecowitt", "fresh_seconds": 180},
                "weather_underground": {
                    "station_id": "ITEST1",
                    "api_key_env": "WEATHER_UNDERGROUND_API_KEY",
                    "refresh_seconds": 60,
                    "stale_seconds": 300,
                    "request_timeout_seconds": 8,
                    "pressure_history_hours": 6,
                },
            }
        }

    def test_provider_timing_text_is_rejected_instead_of_being_silently_coerced(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be a whole number"):
            submitted_observation_config(
                self.base_config(),
                {"weather_underground": {"request_timeout_seconds": "Little Bobby Tables"}},
            )

    def test_provider_timing_values_outside_runtime_bounds_are_rejected(self) -> None:
        cases = (
            ({"ecowitt_push": {"fresh_seconds": 29}}, "Ecowitt freshness"),
            ({"weather_underground": {"refresh_seconds": 3601}}, "refresh interval"),
            ({"weather_underground": {"stale_seconds": 59}}, "stale interval"),
            ({"weather_underground": {"request_timeout_seconds": 61}}, "request timeout"),
            ({"weather_underground": {"pressure_history_hours": 25}}, "pressure-history hours"),
        )
        for payload, message in cases:
            with self.subTest(payload=payload), self.assertRaisesRegex(ValueError, message):
                submitted_observation_config(self.base_config(), payload)

    def test_runtime_boundary_values_remain_valid(self) -> None:
        updated, public = submitted_observation_config(
            self.base_config(),
            {
                "ecowitt_push": {"fresh_seconds": 30},
                "weather_underground": {
                    "refresh_seconds": 3600,
                    "stale_seconds": 21600,
                    "request_timeout_seconds": 2,
                    "pressure_history_hours": 24,
                },
            },
        )
        self.assertEqual(updated["weather"]["ecowitt_push"]["fresh_seconds"], 30)
        self.assertEqual(public["weather_underground"]["refresh_seconds"], 3600)
        self.assertEqual(public["weather_underground"]["stale_seconds"], 21600)
        self.assertEqual(public["weather_underground"]["request_timeout_seconds"], 2)
        self.assertEqual(public["weather_underground"]["pressure_history_hours"], 24)


if __name__ == "__main__":
    unittest.main()
