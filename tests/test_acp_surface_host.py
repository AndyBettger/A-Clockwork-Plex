from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "app" / "templates" / "base.html"
HOST = ROOT / "app" / "static" / "js" / "acp-surface-host.js"
TRANSITIONS = ROOT / "app" / "static" / "js" / "page-transitions.js"


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


if __name__ == "__main__":
    unittest.main()
