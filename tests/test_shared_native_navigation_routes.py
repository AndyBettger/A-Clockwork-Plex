"""B4.3 preview-only shared GTK routing; retained B3 and B4.2 safety."""
from __future__ import annotations

import importlib.util
import io
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
        self.assertIn("complete_handoff(reason)", source)
        self.assertIn('if not navigate_shared:\n            stop_once(reason)', source)
        self.assertIn('state["handoff_pending"] = False', source)
        self.assertIn("audio mixer lives in Chromium", source.lower())
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
        self.assertIn("20261026-b43-shared-local-transition-v1",
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
