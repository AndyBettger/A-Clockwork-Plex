from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "app" / "templates" / "base.html"
TOKENS = ROOT / "app" / "static" / "css" / "acp-design-tokens.css"
STYLE = ROOT / "app" / "static" / "css" / "style.css"
AIRPLAY = ROOT / "app" / "static" / "css" / "airplay.css"
WEATHER = ROOT / "app" / "static" / "css" / "weather.css"
NEWS = ROOT / "app" / "static" / "css" / "news.css"
SETTINGS = ROOT / "app" / "static" / "css" / "settings.css"
SETTINGS_SELECTS = ROOT / "app" / "static" / "css" / "settings-selects.css"
SETTINGS_IPAD = ROOT / "app" / "static" / "css" / "settings-ipad.css"
WEATHER_FORECAST = ROOT / "app" / "static" / "css" / "weather-forecast.css"
WEATHER_RAIN_HISTORY = ROOT / "app" / "static" / "css" / "weather-rain-history.css"
KIOSK_LINKS = ROOT / "app" / "static" / "css" / "kiosk-safe-links.css"


class AcpDesignTokenBoundaryTests(unittest.TestCase):
    def test_token_layer_loads_before_shared_and_surface_styles(self):
        base = BASE.read_text(encoding="utf-8")
        self.assertIn("acp-design-tokens.css", base)
        self.assertLess(base.index("acp-design-tokens.css"), base.index("css/style.css"))

    def test_semantic_tokens_derive_from_existing_palette_authority(self):
        source = TOKENS.read_text(encoding="utf-8")
        for token, palette in (
            ("--acp-color-surface", "--panel"),
            ("--acp-color-border", "--panel-border"),
            ("--acp-color-text", "--text"),
            ("--acp-color-muted", "--muted"),
            ("--acp-color-accent", "--accent"),
            ("--acp-color-accent-strong", "--accent-strong"),
        ):
            self.assertIn(f"{token}: var({palette})", source)

    def test_shared_primitives_use_semantic_component_tokens(self):
        source = STYLE.read_text(encoding="utf-8")
        panel = source.split(".panel {", 1)[1].split("}", 1)[0]
        card = source.split(".weather-card {", 1)[1].split("}", 1)[0]
        button = source.split(".button {", 1)[1].split("}", 1)[0]

        self.assertIn("var(--acp-radius-panel)", panel)
        self.assertIn("var(--acp-color-surface)", panel)
        self.assertIn("var(--acp-color-border)", panel)
        self.assertIn("var(--acp-shadow-panel)", panel)

        self.assertIn("var(--acp-radius-card)", card)
        self.assertIn("var(--acp-fill-card-neutral)", card)

        self.assertIn("var(--acp-radius-pill)", button)
        self.assertIn("var(--acp-fill-control-neutral)", button)
        self.assertIn("var(--acp-border-control-neutral)", button)
        self.assertIn("var(--acp-color-text)", button)

    def test_second_slice_exposes_form_and_scrollbar_contracts(self):
        tokens = TOKENS.read_text(encoding="utf-8")
        settings = SETTINGS.read_text(encoding="utf-8")
        selects = SETTINGS_SELECTS.read_text(encoding="utf-8")
        settings_ipad = SETTINGS_IPAD.read_text(encoding="utf-8")
        news = NEWS.read_text(encoding="utf-8")
        forecast = WEATHER_FORECAST.read_text(encoding="utf-8")
        rain = WEATHER_RAIN_HISTORY.read_text(encoding="utf-8")
        kiosk = KIOSK_LINKS.read_text(encoding="utf-8")

        for token, value in (
            ("--acp-fill-field-container-neutral", "rgba(255, 255, 255, 0.07)"),
            ("--acp-field-border-neutral", "rgba(255, 255, 255, 0.18)"),
            ("--acp-field-fill-neutral", "rgba(0, 0, 0, 0.26)"),
            ("--acp-field-focus-neutral", "rgba(143, 211, 255, 0.65)"),
            ("--acp-scrollbar-track-size", "8px"),
            ("--acp-scrollbar-thumb-size", "4px"),
            ("--acp-scrollbar-thumb-min", "42px"),
        ):
            self.assertIn(f"{token}: {value}", tokens)

        self.assertIn("background: var(--acp-fill-field-container-neutral)", settings)
        self.assertIn("border: 1px solid var(--acp-field-border-neutral)", settings)
        self.assertIn("background: var(--acp-field-fill-neutral)", settings)
        self.assertIn("outline: 2px solid var(--acp-field-focus-neutral)", settings)

        self.assertIn("border: 1px solid var(--acp-field-border-neutral)", selects)
        self.assertIn("background: var(--acp-field-fill-neutral)", selects)
        self.assertIn("outline: 2px solid var(--acp-field-focus-neutral)", selects)

        self.assertIn("background: var(--acp-fill-soft-neutral)", settings_ipad)
        self.assertIn("var(--acp-scrollbar-track-size)", news)
        self.assertIn("var(--acp-scrollbar-thumb-size)", news)
        self.assertIn("var(--acp-scrollbar-thumb-min)", news)
        self.assertIn("var(--acp-scrollbar-track-size)", forecast)
        self.assertIn("var(--acp-scrollbar-thumb-size)", forecast)
        self.assertIn("var(--acp-scrollbar-thumb-min)", forecast)
        self.assertIn("flex: 0 0 var(--acp-scrollbar-track-size)", rain)

        self.assertIn("var(--acp-color-accent)", kiosk)
        self.assertIn("var(--acp-color-text)", kiosk)
        self.assertIn("var(--acp-color-muted)", kiosk)

    def test_application_surfaces_can_share_palette_tokens_without_geometry_rewrite(self):
        airplay = AIRPLAY.read_text(encoding="utf-8")
        weather = WEATHER.read_text(encoding="utf-8")
        news = NEWS.read_text(encoding="utf-8")

        self.assertIn("background: var(--acp-color-surface)", airplay)
        self.assertIn("border: 1px solid var(--acp-color-border)", airplay)
        self.assertIn("background: var(--acp-color-surface)", weather)
        self.assertIn("border: 1px solid var(--acp-color-border)", weather)
        self.assertIn("background: var(--acp-color-surface)", news)
        self.assertIn("border: 1px solid var(--acp-color-border)", news)
        self.assertIn("box-shadow: var(--acp-shadow-content)", news)


if __name__ == "__main__":
    unittest.main()
