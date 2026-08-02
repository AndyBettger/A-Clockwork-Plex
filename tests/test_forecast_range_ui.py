from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPLETION = ROOT / "app" / "static" / "js" / "weather-forecast-completion.js"
BASE = ROOT / "app" / "templates" / "base.html"
SETTINGS = ROOT / "app" / "templates" / "settings.html"
BACKEND = ROOT / "app" / "weather_forecast.py"


class ForecastRangeUiTests(unittest.TestCase):
    def test_completion_client_has_valid_javascript_syntax(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is not installed.")
        result = subprocess.run(
            [node, "--check", str(COMPLETION)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_backend_and_settings_offer_sixteen_days(self):
        backend = BACKEND.read_text(encoding="utf-8")
        settings = SETTINGS.read_text(encoding="utf-8")
        self.assertIn("1,\n            16", backend)
        self.assertIn('<option value="16">16 days</option>', settings)

    def test_completion_appends_every_returned_daily_item(self):
        text = COMPLETION.read_text(encoding="utf-8")
        self.assertIn("for (let index = existing; index < daily.length; index += 1)", text)
        self.assertIn("dailyStrip.appendChild", text)
        self.assertNotIn("slice(0, 7)", text)

    def test_weather_page_loads_completion_after_foundation_renderer(self):
        text = BASE.read_text(encoding="utf-8")
        self.assertIn("weather-forecast-completion.js", text)
        self.assertLess(text.index("weather-forecast.js"), text.index("weather-forecast-completion.js"))

    def test_hourly_and_fetched_times_use_global_clock_format(self):
        text = COMPLETION.read_text(encoding="utf-8")
        self.assertIn("window.ACPTime?.formatTime", text)
        self.assertIn("window.ACPTime?.formatDateTime", text)


if __name__ == "__main__":
    unittest.main()
