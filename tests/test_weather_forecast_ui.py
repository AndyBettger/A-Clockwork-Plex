from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from jinja2 import Environment


class WeatherForecastUiTests(unittest.TestCase):
    def test_forecast_assets_are_loaded_only_for_weather_page(self):
        base = Path("app/templates/base.html").read_text(encoding="utf-8")

        self.assertIn("active_page | default(state.mode) == 'weather'", base)
        self.assertIn("css/weather-forecast.css", base)
        self.assertIn("js/weather-forecast.js", base)
        self.assertIn("20260801-provider-console", base)
        Environment().parse(base)

    def test_forecast_client_is_cache_only_and_never_controls_the_appliance(self):
        client = Path("app/static/js/weather-forecast.js").read_text(encoding="utf-8")

        self.assertIn("/api/weather/forecast", client)
        self.assertIn("cache: 'no-store'", client)
        self.assertNotIn("method: 'POST'", client)
        self.assertNotIn("/api/playback", client)
        self.assertNotIn("/api/screen", client)
        self.assertNotIn("systemctl", client)
        self.assertNotIn("location.reload", client)

    def test_disabled_or_empty_forecast_leaves_station_console_untouched(self):
        client = Path("app/static/js/weather-forecast.js").read_text(encoding="utf-8")

        guard = "payload?.enabled !== true || !payload.forecast"
        self.assertIn(guard, client)
        self.assertIn("if (!hourly.length && !daily.length)", client)
        self.assertIn("anchor.parentNode.insertBefore(outer, anchor)", client)
        self.assertNotIn("anchor.replaceWith", client)
        self.assertNotIn("anchor.remove", client)

    def test_source_ownership_and_attribution_are_visible(self):
        client = Path("app/static/js/weather-forecast.js").read_text(encoding="utf-8")

        self.assertIn("Online model guidance from Open-Meteo", client)
        self.assertIn("live Ecowitt observations from your own station", client)
        self.assertIn("Weather data by", client)
        self.assertIn("Open-Meteo.com", client)
        self.assertIn("CC BY 4.0", client)
        self.assertIn("Cached forecast", client)
        self.assertIn("Using the last good forecast", client)

    def test_forecast_console_has_hourly_daily_and_touch_scroll_layouts(self):
        client = Path("app/static/js/weather-forecast.js").read_text(encoding="utf-8")
        styles = Path("app/static/css/weather-forecast.css").read_text(encoding="utf-8")

        self.assertIn("Next hours", client)
        self.assertIn("Daily outlook", client)
        self.assertIn("futureHourly", client)
        self.assertIn("slice(0, 7)", client)
        self.assertIn("overflow-x: auto", styles)
        self.assertIn("scroll-snap-type", styles)
        self.assertIn("body[data-active-page=\"weather\"]", styles)

    def test_forecast_client_has_valid_javascript_syntax(self):
        result = subprocess.run(
            ["node", "--check", "app/static/js/weather-forecast.js"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
