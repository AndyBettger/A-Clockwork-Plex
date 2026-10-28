"""B4.3 preview-only shared GTK routing; retained B3 and B4.2 safety."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
GTK = ROOT / "scripts/try-native-navigation-drawer.py"
BROWSER = ROOT / "app/static/js/native-navigation-bridge.js"
BASE = ROOT / "app/templates/base.html"
B1 = ROOT / "scripts/switch-native-plexamp-window.py"

spec = importlib.util.spec_from_file_location("acp_b43_shared_routes", GTK)
assert spec and spec.loader
nav = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nav)


class SharedNativeNavigationRoutesTests(unittest.TestCase):
    def test_cli_shared_routes_require_existing_observer_and_lease(self):
        cases = (
            ["--show", "--navigate-shared"],
            ["--show", "--observe-foreground", "--navigate-shared"],
            ["--show", "--observe-foreground", "--share-chrome",
             "--navigate-shared"],
            ["--show", "--observe-foreground", "--share-chrome",
             "--theme-from-acp", "--navigate-shared"],
        )
        for args in cases:
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, str(GTK), *args],
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("--navigate-shared requires --show", result.stderr)

    def test_configured_navigation_time_and_zero_semantics_are_used(self):
        values = {
            "viewport_width": 1280, "viewport_height": 720,
            "drawer_width": 940, "drawer_height": 76,
            "drawer_bottom": 8, "drawer_padding": 8,
            "workspace_gap": 8, "utility_gap": 6,
            "button_height": 62, "utility_size": 62,
            "font_size": 21.8,
            "navigation_transition_duration_ms": 620,
            "navigation_inactivity_seconds": 12,
            "night_brightness": 1.0, "astronomy_night": False,
        }
        self.assertTrue(nav.valid_presentation(values))
        self.assertEqual(nav.shared_navigation_timing(values), (620, 12))
        self.assertEqual(nav.shared_navigation_timing({
            **values, "navigation_transition_duration_ms": 0,
            "navigation_inactivity_seconds": 0}), (0, 0))
        self.assertEqual(nav.shared_navigation_timing(None),
                         (nav.DRAWER_MOTION_MS, 6))
        self.assertFalse(nav.valid_presentation({
            **values, "navigation_transition_duration_ms": True}))
        self.assertFalse(nav.valid_presentation({
            **values, "navigation_inactivity_seconds": 40}))
        source = GTK.read_text(encoding="utf-8")
        self.assertIn("motion[\"duration_ms\"] = duration", source)
        self.assertIn("drawer_idle[\"seconds\"] = inactivity", source)
        self.assertIn("GLib.timeout_add_seconds(seconds, idle_expired)", source)
        self.assertIn("if seconds <= 0:", source)
        self.assertIn("if not animate_drawer or immediate or duration_ms <= 0:", source)
        self.assertIn("duration_ms / 1000.0 * abs(target - start)", source)
        self.assertIn("revealer.get_preferred_height()[1]", source)
        self.assertIn("gtk_revealed_fraction(natural_height", source)
        self.assertIn("prior = state[\"foreground\"]", source)
        self.assertIn("observed[0] != prior[0]", source)
        self.assertIn("restart_drawer_idle()", source)
        self.assertNotIn(
            'state["handoff_pending"] = False\\n                        set_drawer_open(False)',
            source,
        )

    def test_spatial_row_direction_uses_existing_acp_topology(self):
        script = BROWSER.read_text(encoding="utf-8")
        host = (ROOT / "app/static/js/acp-surface-host.js").read_text()
        pages = (ROOT / "app/static/js/acp-application-surfaces.js").read_text()
        self.assertIn("function sharedSpatialDirection(destination)", script)
        self.assertIn("style !== 'spatial-row'", script)
        self.assertIn("window.ACPWorkspaceTopology", script)
        self.assertIn("window.ACPSurfaceHost?.activeRoute?.()", script)
        self.assertIn("path.every((entry) => entry.renderer === 'acp')", script)
        self.assertIn("topology.direction(from, to)", script)
        self.assertIn("const spatialCommitDirection = sharedSpatialDirection", script)
        self.assertIn("...(spatialCommitDirection ? { spatialCommitDirection } : {})", script)
        self.assertIn("typeof prepared.spatialCommit === 'function'", host)
        self.assertIn("await spatialLiveCommit(direction, from, surface, commit)", pages)
        self.assertIn("const duration = applicationTransitionDurationMs();", pages)
        self.assertIn("const distance = path.length - 1;", pages)

    def test_local_acp_fast_painted_phase_does_not_stall_for_timeout(self):
        # In a focused Chromium window ready -> painted can occur in less
        # than the GTK poll cadence. 'painted' is stronger evidence than
        # 'ready', not a failure. Native Plexamp must still wait to focus
        # until 'ready' and must not skip the post-focus painted guard.
        for phase in ("queued", "taken", "expired", "missing", None):
            with self.subTest(phase=phase):
                self.assertFalse(nav.shared_route_prepared(phase, "acp"))
                self.assertFalse(nav.shared_route_prepared(phase, "plexamp"))
        for phase in ("ready", "painted"):
            with self.subTest(phase=phase):
                self.assertTrue(nav.shared_route_prepared(phase, "acp"))
        self.assertTrue(nav.shared_route_prepared("ready", "plexamp"))
        self.assertFalse(nav.shared_route_prepared("painted", "plexamp"))
        source = GTK.read_text(encoding="utf-8")
        self.assertIn("if shared_route_prepared(phase, foreground[0]):", source)
        self.assertIn("if foreground[0] == \"acp\":", source)
        self.assertIn("start_curtained_focus(name, sequence)", source)
        self.assertIn("confirmed in ACP ({phase})", source)

    def test_shared_button_dispatch_remains_foreground_aware_and_inert_by_default(self):
        source = GTK.read_text(encoding="utf-8")
        self.assertIn("if observe_foreground and not navigate_shared:", source)
        self.assertIn("if navigate_shared:", source)
        self.assertIn('foreground = state["foreground"]', source)
        self.assertIn("unknown foreground; refusing navigation", source)
        self.assertIn('b1.focus(focus_env, "plexamp")', source)
        self.assertIn("except b1.WindowError as exc:", source)
        self.assertIn("sequence = request_page_handoff(name)", source)
        self.assertIn('if foreground[0] == "acp":', source)
        self.assertIn("start_curtained_focus(name, sequence)", source)
        self.assertIn("if curtain_handoff or navigate_shared:", source)
        self.assertIn("complete_handoff(reason)", source)
        self.assertIn('if not navigate_shared:\n        # B4.3', source)
        self.assertIn('if not navigate_shared:\n            stop_once(reason)', source)
        self.assertIn('state["handoff_pending"] = False', source)
        self.assertIn('if name not in {"Home", "Weather", "News", "AirPlay", "Settings", "Audio"}:', source)
        self.assertIn("arm_audio_request(sequence)", source)
        self.assertIn("ThreadPoolExecutor(max_workers=1", source)
        self.assertIn("overlay_allowed(state[\"keyboard\"])", source)
        self.assertNotIn("flatpak kill", source)

    def test_shared_gtk_keeps_existing_one_use_allowlisted_mailbox(self):
        requests = []
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, *_): return b'{"ok":true,"sequence":99}'
        with mock.patch.object(nav.urllib.request, "urlopen",
                               side_effect=lambda req, timeout: (requests.append(req), Response())[1]):
            self.assertEqual(nav.request_page_handoff("Weather"), 99)
            self.assertIsNone(nav.request_page_handoff("Plexamp"))
            self.assertIsNone(nav.request_page_handoff("not a page"))
        self.assertEqual(len(requests), 1)
        self.assertEqual(json.loads(requests[0].data), {"destination": "weather"})
        self.assertEqual(requests[0].get_method(), "POST")
        self.assertEqual(requests[0].get_header("X-acp-b3-source"),
                         "native-gtk-b3-dev")

    def test_browser_preserves_configured_local_acp_transition_and_native_background(self):
        script = BROWSER.read_text(encoding="utf-8")
        self.assertIn("document.body.classList.contains('acp-b4-gtk-owned')", script)
        self.assertIn("&& document.hasFocus()", script)
        self.assertIn("source: 'native-gtk-b4-shared', animate: true", script)
        self.assertIn("source: 'native-plexamp-b3', animate: false", script)
        self.assertIn("const sharedACP", script)
        self.assertIn("if (!sharedACP) {", script)
        self.assertIn("window.ACPNavDrawer?.show?.()", script)
        self.assertIn("/api/native-navigation/ready", script)
        self.assertIn("/api/native-navigation/painted", script)
        self.assertIn("function readyForHandoff(command)", script)
        self.assertIn("projection?.lease?.manual_surface !== destination", script)
        self.assertIn("function weatherContentReady()", script)
        self.assertIn("20261028-b43-shared-audio-v1",
                      BASE.read_text(encoding="utf-8"))

    def test_focus_destination_remains_exact_b1_identity_and_b3_preview_independent(self):
        source = GTK.read_text(encoding="utf-8")
        b1 = B1.read_text(encoding="utf-8")
        self.assertIn('APP_ID = "Plexamp"', b1)
        self.assertIn('BROWSER_ID = "chromium"', b1)
        self.assertIn("def focus(env: dict[str, str], destination: str)", b1)
        self.assertIn("b1 = load_window_helper()", source)
        self.assertIn("if observe_foreground:", source)
        self.assertIn("if args.share_chrome and not args.observe_foreground:", source)
        self.assertIn("elif route_pages:", source)
        self.assertIn("stop_once(\"ACP focused, ending preview\")", source)
        self.assertIn("GLib.timeout_add_seconds(seconds,", source)


if __name__ == "__main__":
    unittest.main()
