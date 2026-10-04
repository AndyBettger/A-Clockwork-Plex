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
