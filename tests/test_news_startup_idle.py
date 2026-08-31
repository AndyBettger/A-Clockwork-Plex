from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace

from flask import Flask

from app import news_ui, screen_projection, settings_unified


class NewsStartupIdleTests(unittest.TestCase):
    def test_news_registration_extends_existing_destination_authorities(self):
        dashboard = SimpleNamespace(
            VALID_MODES={"clock", "weather", "plexamp", "airplay", "settings"},
            settings_page_context=lambda *_args, **_kwargs: {
                "mode_options": [
                    {"id": "clock", "label": "Clock"},
                    {"id": "weather", "label": "Weather"},
                    {"id": "plexamp", "label": "Plexamp"},
                    {"id": "airplay", "label": "AirPlay"},
                ]
            },
            set_mode=lambda _mode: None,
        )
        app = Flask(__name__)

        settings_had_news = "news" in settings_unified.VALID_MODES
        valid_screen_had_news = "news" in screen_projection.VALID_SCREENS
        manual_had_news = "news" in screen_projection.MANUAL_LEASE_SCREENS
        idle_had_news = "news" in screen_projection.IDLE_RETURN_SCREENS
        try:
            news_ui.register_news_ui(app, dashboard)

            self.assertIn("news", dashboard.VALID_MODES)
            self.assertIn("news", settings_unified.VALID_MODES)
            self.assertIn("news", screen_projection.VALID_SCREENS)
            self.assertIn("news", screen_projection.MANUAL_LEASE_SCREENS)
            self.assertIn("news", screen_projection.IDLE_RETURN_SCREENS)

            options = dashboard.settings_page_context()["mode_options"]
            self.assertEqual(
                [item["id"] for item in options],
                ["clock", "weather", "news", "plexamp", "airplay"],
            )

            # Registration can be called again without duplicating the Settings option.
            news_ui.register_news_ui(app, dashboard)
            options = dashboard.settings_page_context()["mode_options"]
            self.assertEqual(sum(item["id"] == "news" for item in options), 1)
        finally:
            if not settings_had_news:
                settings_unified.VALID_MODES.discard("news")
            if not valid_screen_had_news:
                screen_projection.VALID_SCREENS.discard("news")
            if not manual_had_news:
                screen_projection.MANUAL_LEASE_SCREENS.discard("news")
            if not idle_had_news:
                screen_projection.IDLE_RETURN_SCREENS.discard("news")

    def test_startup_bootstrap_accepts_news_and_has_valid_javascript(self):
        path = Path("app/static/js/dashboard-preferences-bootstrap.js")
        source = path.read_text(encoding="utf-8")
        self.assertIn("new Set(['clock', 'weather', 'news', 'airplay', 'plexamp'])", source)
        self.assertIn("window.location.replace(`/${preferences.startupMode}`)", source)

        result = subprocess.run(
            ["node", "--check", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
