from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAYOUT_CSS = ROOT / "app" / "static" / "css" / "airplay-layout-v3.css"
NOW_PLAYING_CSS = ROOT / "app" / "static" / "css" / "airplay-nowplaying.css"
GLANCE_CSS = ROOT / "app" / "static" / "css" / "airplay-glance-tuning.css"
AIRPLAY_TEMPLATE = ROOT / "app" / "templates" / "airplay.html"
BASE_TEMPLATE = ROOT / "app" / "templates" / "base.html"
APPLICATION_SURFACES = ROOT / "app" / "static" / "js" / "acp-application-surfaces.js"
AIRPLAY_LIVE = ROOT / "app" / "static" / "js" / "airplay-live.js"
AIRPLAY_HYDRATION = ROOT / "app" / "static" / "js" / "airplay-hydration.js"
SURFACE_HOST = ROOT / "app" / "static" / "js" / "acp-surface-host.js"


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

    def test_unresolved_first_paint_uses_ready_geometry_until_status_resolves(self):
        base = BASE_TEMPLATE.read_text(encoding="utf-8")
        loader = APPLICATION_SURFACES.read_text(encoding="utf-8")
        live = AIRPLAY_LIVE.read_text(encoding="utf-8")
        layout = LAYOUT_CSS.read_text(encoding="utf-8")
        now_playing = NOW_PLAYING_CSS.read_text(encoding="utf-8")
        glance = GLANCE_CSS.read_text(encoding="utf-8")

        self.assertIn("airplay-session-unresolved", base)
        self.assertIn("surface === 'airplay'", loader)
        self.assertIn("classList.add('airplay-session-unresolved')", loader)
        self.assertIn("classList.remove('airplay-session-unresolved')", live)

        self.assertIn("body.airplay-session-unresolved .airplay-copy", layout)
        self.assertIn("body.airplay-session-unresolved .airplay-controls-stack", now_playing)
        self.assertIn("display: none !important", now_playing)
        self.assertIn("body.airplay-session-unresolved .airplay-now-card", now_playing)
        self.assertIn("body.airplay-session-unresolved .airplay-copy .airplay-detail", glance)

    def test_same_document_airplay_waits_for_hydration_before_snapshot(self):
        host = SURFACE_HOST.read_text(encoding="utf-8")
        loader = APPLICATION_SURFACES.read_text(encoding="utf-8")
        hydration = AIRPLAY_HYDRATION.read_text(encoding="utf-8")

        self.assertIn("typeof prepared.beforeSnapshot === 'function'", host)
        self.assertIn("await prepared.beforeSnapshot", host)
        self.assertIn("async beforeSnapshot", loader)
        self.assertIn("await ensureScripts(record.scripts)", loader)
        self.assertIn("ACPAirPlayHydration?.waitForReady?.(1400)", loader)
        self.assertIn("markAirPlayUnresolved()", loader)
        self.assertIn("'airplay-session-active'", loader)
        self.assertIn("'airplay-session-idle'", loader)
        self.assertIn("'airplay-metadata-active'", loader)
        self.assertIn("classList.add('airplay-session-unresolved')", loader)
        self.assertIn("function waitForReady", hydration)
        self.assertIn("!document.body.classList.contains('airplay-session-unresolved')", hydration)
        self.assertIn("detail: { surface: 'airplay' }", hydration)

    def test_template_cache_busts_corrected_layout(self):
        template = AIRPLAY_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("airplay-layout-v3.css", template)
        self.assertIn("20261005-first-paint-v1", template)
        self.assertIn("airplay-live.js", template)
        self.assertIn("20261006-snapshot-hydration-v2", template)


if __name__ == "__main__":
    unittest.main()
