from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RainHistoryScrollbarTests(unittest.TestCase):
    def test_rain_history_uses_custom_forecast_style_scrollbar(self) -> None:
        css = (ROOT / "app" / "static" / "css" / "weather-rain-history.css").read_text(encoding="utf-8")
        loader = (ROOT / "app" / "static" / "js" / "weather-forecast-completion.js").read_text(encoding="utf-8")
        script = (ROOT / "app" / "static" / "js" / "weather-rain-history-scroll.js").read_text(encoding="utf-8")

        self.assertIn("scrollbar-width: none", css)
        self.assertIn("weather-forecast-scrollbar.rain-history-scrollbar", css)
        self.assertIn("weather-rain-history-scroll.js", loader)
        self.assertIn("weather-forecast-scrollbar rain-history-scrollbar", script)
        self.assertIn("weather-forecast-scrollbar-thumb", script)
        self.assertIn("role', 'scrollbar", script)


if __name__ == "__main__":
    unittest.main()
