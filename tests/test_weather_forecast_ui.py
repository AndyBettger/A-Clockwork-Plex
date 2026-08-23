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
        self.assertIn("20260802-custom-forecast-scrollbar", base)
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
        self.assertNotIn("anchor.replaceWith", client)
        self.assertNotIn("anchor.remove", client)

    def test_forecast_joins_existing_vertical_weather_scroll_surface(self):
        client = Path("app/static/js/weather-forecast.js").read_text(encoding="utf-8")
        styles = Path("app/static/css/weather-forecast.css").read_text(encoding="utf-8")
        weather_styles = Path("app/static/css/weather.css").read_text(encoding="utf-8")

        self.assertIn("anchor.insertBefore(outer, anchor.firstChild)", client)
        self.assertNotIn("anchor.parentNode.insertBefore(outer, anchor)", client)
        self.assertIn(".weather-detail-page", weather_styles)
        self.assertIn("overflow-y: auto", weather_styles)
        self.assertIn("width: min(100%, 1120px)", styles)
        self.assertNotIn("width: min(100%, 1500px)", styles)

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
        self.assertIn("overflow-y: hidden", styles)
        self.assertIn("overscroll-behavior-block: auto", styles)
        self.assertIn("touch-action: pan-x pan-y", styles)
        self.assertIn("scroll-snap-type", styles)
        self.assertIn("body[data-active-page=\"weather\"]", styles)

    def test_native_scrollbar_is_hidden_in_favour_of_custom_control(self):
        styles = Path("app/static/css/weather-forecast.css").read_text(encoding="utf-8")

        self.assertIn("scrollbar-width: none", styles)
        self.assertIn("-ms-overflow-style: none", styles)
        self.assertIn(".weather-forecast-strip::-webkit-scrollbar", styles)
        self.assertIn("display: none", styles)
        self.assertIn("width: 0", styles)
        self.assertIn("height: 0", styles)
        self.assertNotIn("::-webkit-scrollbar-button", styles)

    def test_custom_scrollbar_is_a_real_rounded_capsule(self):
        client = Path("app/static/js/weather-forecast.js").read_text(encoding="utf-8")
        styles = Path("app/static/css/weather-forecast.css").read_text(encoding="utf-8")

        self.assertIn("weather-forecast-scrollbar", client)
        self.assertIn("weather-forecast-scrollbar-thumb", client)
        self.assertIn("role', 'scrollbar", client)
        self.assertIn("bindCustomScrollbar", client)
        self.assertIn("setPointerCapture", client)
        self.assertIn("aria-valuenow", client)
        self.assertIn(".weather-forecast-scrollbar {", styles)
        self.assertIn(".weather-forecast-scrollbar-thumb {", styles)
        self.assertIn("border-radius: 999px", styles)
        self.assertIn("background: rgba(5, 13, 24, 0.46)", styles)
        self.assertIn("cursor: grab", styles)

    def test_custom_scrollbar_preserves_mouse_keyboard_and_touch_paths(self):
        client = Path("app/static/js/weather-forecast.js").read_text(encoding="utf-8")
        styles = Path("app/static/css/weather-forecast.css").read_text(encoding="utf-8")

        self.assertIn("pointerdown", client)
        self.assertIn("pointermove", client)
        self.assertIn("ArrowLeft", client)
        self.assertIn("ArrowRight", client)
        self.assertIn("Home", client)
        self.assertIn("End", client)
        self.assertIn("touch-action: none", styles)
        self.assertIn("touch-action: pan-x pan-y", styles)

    def test_settings_location_lookup_stages_existing_forecast_fields(self):
        presenter = Path("app/static/js/settings-weather-location.js").read_text(
            encoding="utf-8"
        )
        keyboard = Path("app/static/js/settings-keyboard.js").read_text(encoding="utf-8")
        base = Path("app/templates/base.html").read_text(encoding="utf-8")

        self.assertIn("Find forecast location", presenter)
        self.assertIn("Town, city or postcode", presenter)
        self.assertIn("/api/weather/forecast/locations?q=", presenter)
        self.assertIn('data-setting-path="weather.forecast.latitude"', presenter)
        self.assertIn('data-setting-path="weather.forecast.longitude"', presenter)
        self.assertIn('data-setting-path="weather.forecast.timezone"', presenter)
        self.assertIn("Latitude (advanced)", presenter)
        self.assertIn("Longitude (advanced)", presenter)
        self.assertIn("Save Changes still controls persistence", presenter)
        self.assertIn("dispatchEvent(new Event('input', { bubbles: true }))", presenter)
        self.assertNotIn("method: 'POST'", presenter)
        self.assertIn("document.addEventListener('focusin'", keyboard)
        self.assertIn("input[data-keyboard]", keyboard)
        self.assertIn("js/settings-weather-location.js", base)
        self.assertGreater(
            base.index("{% block scripts %}{% endblock %}"),
            base.index("js/settings-transaction-guard.js"),
        )
        self.assertGreater(
            base.index("js/settings-weather-location.js"),
            base.index("{% block scripts %}{% endblock %}"),
        )
        Environment().parse(base)

    def test_settings_location_lookup_has_valid_javascript_syntax(self):
        result = subprocess.run(
            ["node", "--check", "app/static/js/settings-weather-location.js"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

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
