from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAYOUT_CSS = ROOT / "app" / "static" / "css" / "airplay-layout-v3.css"
AIRPLAY_TEMPLATE = ROOT / "app" / "templates" / "airplay.html"


class AirPlayMetadataPendingUiTests(unittest.TestCase):
    def test_corrected_glyph_geometry_is_not_idle_only(self):
        css = LAYOUT_CSS.read_text(encoding="utf-8")

        self.assertIn(".airplay-glyph .airplay-route-logo", css)
        self.assertIn(".airplay-glyph .airplay-pulse", css)
        self.assertIn(".airplay-glyph .airplay-pulse.two", css)
        self.assertNotIn("body.airplay-session-idle .airplay-pulse {", css)
        self.assertNotIn("body.airplay-session-idle .airplay-route-logo", css)

    def test_metadata_pending_geometry_keeps_measured_arc_origin(self):
        css = LAYOUT_CSS.read_text(encoding="utf-8")

        self.assertIn("left: var(--airplay-pulse-origin-x) !important", css)
        self.assertIn("top: var(--airplay-pulse-origin-y) !important", css)
        self.assertIn("animation: airplay-route-wave 4.2s linear infinite !important", css)

    def test_template_cache_busts_corrected_layout(self):
        template = AIRPLAY_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("airplay-layout-v3.css", template)
        self.assertIn("20260731-metadata-pending-glyph", template)


if __name__ == "__main__":
    unittest.main()
