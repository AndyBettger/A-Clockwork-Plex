from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "app" / "templates" / "base.html"
HOST = ROOT / "app" / "static" / "js" / "acp-surface-host.js"
TRANSITIONS = ROOT / "app" / "static" / "js" / "page-transitions.js"
PAIR = ROOT / "app" / "static" / "js" / "acp-clock-weather-surfaces.js"
DASHBOARD = ROOT / "app" / "dashboard_core.py"
TRANSITION_CSS = ROOT / "app" / "static" / "css" / "page-transitions.css"


class AcpSurfaceHostTests(unittest.TestCase):
    def test_surface_host_loads_before_legacy_page_transition_owner(self):
        base = BASE.read_text(encoding="utf-8")
        host_index = base.index("js/acp-surface-host.js")
        transitions_index = base.index("js/page-transitions.js")

        self.assertLess(host_index, transitions_index)

    def test_surface_host_has_prepare_commit_and_view_transition_contract(self):
        source = HOST.read_text(encoding="utf-8")

        self.assertIn("function register(surface, lifecycle)", source)
        self.assertIn("typeof lifecycle.prepare !== 'function'", source)
        self.assertIn("prepared = await lifecycle.prepare", source)
        self.assertIn("typeof prepared.commit !== 'function'", source)
        self.assertIn("document.startViewTransition(commit)", source)
        self.assertIn("acp:surface-changed", source)
        self.assertIn("surface-not-registered", source)

    def test_page_navigation_delegates_only_registered_routes_and_keeps_route_fallback(self):
        source = TRANSITIONS.read_text(encoding="utf-8")

        self.assertIn("window.ACPSurfaceHost?.canNavigate?.(target.pathname)", source)
        self.assertIn("await window.ACPSurfaceHost.navigate(target.pathname", source)
        self.assertIn("if (result?.handled) return;", source)

        # Until a destination surface has explicitly registered with the host,
        # the accepted multi-document route remains the fail-safe.
        self.assertGreaterEqual(source.count("window.location.assign(target.href)"), 3)

    def test_surface_host_does_not_register_product_surfaces_itself(self):
        source = HOST.read_text(encoding="utf-8")

        self.assertNotIn("register('clock'", source)
        self.assertNotIn('register("clock"', source)
        self.assertNotIn("register('weather'", source)
        self.assertNotIn('register("weather"', source)
        self.assertNotIn("register('news'", source)
        self.assertNotIn('register("news"', source)

    def test_clock_weather_pair_is_the_only_registered_product_pair(self):
        source = PAIR.read_text(encoding="utf-8")

        self.assertIn("const pair = new Set(['clock', 'weather'])", source)
        self.assertIn("surfaceHost.register(surface", source)
        self.assertIn("/api/surfaces/", source)
        self.assertIn("record.wrapper.hidden = name !== surface", source)
        self.assertIn("/api/mode/", source)
        self.assertNotIn("'news'", source)
        self.assertNotIn("'settings'", source)
        self.assertNotIn("'airplay'", source)

    def test_surface_document_endpoint_is_read_only_for_mode(self):
        source = DASHBOARD.read_text(encoding="utf-8")
        start = source.index('@app.route("/api/surfaces/<surface>")')
        end = source.index('@app.route("/airplay")', start)
        endpoint = source[start:end]

        self.assertIn('"clock": "clock.html"', endpoint)
        self.assertIn('"weather": "weather.html"', endpoint)
        self.assertIn("render_template(template)", endpoint)
        self.assertNotIn("set_mode(", endpoint)

    def test_surface_host_activation_is_part_of_navigation_busy_state(self):
        transitions = TRANSITIONS.read_text(encoding="utf-8")

        self.assertIn("window.ACPSurfaceHost?.isTransitioning?.() === true", transitions)

    def test_same_document_view_transition_uses_configured_acp_motion(self):
        styles = TRANSITION_CSS.read_text(encoding="utf-8")

        self.assertIn("::view-transition-old(root)", styles)
        self.assertIn("::view-transition-new(root)", styles)
        self.assertIn("--acp-transition-duration", styles)
        for style, outgoing, incoming in (
            ("grow-fade", "acp-out-grow-fade", "acp-in-grow-fade"),
            ("crossfade", "acp-out-crossfade", "acp-in-crossfade"),
            ("horizontal-slide", "acp-out-horizontal-slide", "acp-in-horizontal-slide"),
            ("vertical-lift", "acp-out-vertical-lift", "acp-in-vertical-lift"),
            ("cover-reveal", "acp-out-cover-reveal", "acp-in-cover-reveal"),
            ("zoom", "acp-out-zoom", "acp-in-zoom"),
            ("blur-dissolve", "acp-out-blur-dissolve", "acp-in-blur-dissolve"),
        ):
            self.assertIn(f':root[data-transition-style="{style}"]', styles)
            self.assertIn(f"--acp-view-transition-old: {outgoing};", styles)
            self.assertIn(f"--acp-view-transition-new: {incoming};", styles)


if __name__ == "__main__":
    unittest.main()
