"""B4.2: expiring native GTK ownership and automatic Chromium fallback."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "app/native_navigation_bridge.py"
GTK = ROOT / "scripts/try-native-navigation-drawer.py"
SCRIPT = ROOT / "app/static/js/shared-native-nav-owner.js"
CSS = ROOT / "app/static/css/shared-native-nav-owner.css"
MAIN = ROOT / "app/main.py"
TEMPLATE = ROOT / "app/templates/base.html"
TOKEN = "a" * 32
OTHER = "b" * 32

spec = importlib.util.spec_from_file_location("acp_b4_chrome_owner", BRIDGE)
assert spec and spec.loader
nav = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nav)


class SharedNativeNavigationOwnerTests(unittest.TestCase):
    def test_four_second_lease_expires_and_restart_starts_unowned(self):
        now = [90.0]
        lease = nav.ChromeOwnerLease(lambda: now[0])
        self.assertFalse(lease.active())
        lease.publish({"owner": TOKEN, "foreground": "acp", "visible": True})
        self.assertTrue(lease.active())
        now[0] += 3.9
        self.assertTrue(lease.active())
        now[0] += 0.1
        self.assertFalse(lease.active())
        # A dashboard process restart gets a fresh in-memory unowned state.
        self.assertFalse(nav.ChromeOwnerLease(lambda: now[0]).active())
        lease.publish({"owner": OTHER, "foreground": "acp", "visible": True})
        self.assertTrue(lease.active())
        now[0] -= 1.0
        self.assertFalse(lease.active())  # monotonic clock reversal: fail closed

    def test_reject_unknown_second_owner_and_invalid_heartbeat(self):
        now = [5.0]
        lease = nav.ChromeOwnerLease(lambda: now[0])
        payload = {"owner": TOKEN, "foreground": "acp", "visible": True}
        for bad in (
            {}, {"owner": TOKEN, "foreground": "plexamp", "visible": True},
            {"owner": TOKEN, "foreground": "acp", "visible": False},
            {"owner": TOKEN, "foreground": "acp", "visible": 1},
            {"owner": "not-token", "foreground": "acp", "visible": True},
            {**payload, "extra": 1},
            ["acp"], "acp",
        ):
            with self.subTest(bad=bad), self.assertRaises(nav.NavigationError):
                lease.publish(bad)
        lease.publish(payload)
        now[0] += 2
        lease.publish(payload)  # same process may renew
        self.assertTrue(lease.active())
        with self.assertRaisesRegex(nav.NavigationError, "Another GTK"):
            lease.publish({**payload, "owner": OTHER})
        now[0] += 4.0
        lease.publish({**payload, "owner": OTHER})
        self.assertTrue(lease.active())

    def test_browser_cannot_publish_native_owner(self):
        req = SimpleNamespace(remote_addr="127.0.0.1",
            host="localhost:8088", scheme="http",
            mimetype="application/json", content_length=85,
            headers={"Origin": "http://localhost:8088",
                     "Sec-Fetch-Site": "same-origin"})
        self.assertFalse(nav.native_submit_allowed(req))
        self.assertTrue(nav.local_browser_request(req))
        req.headers = {"X-ACP-B3-Source": nav.SOURCE_HEADER}
        self.assertTrue(nav.native_submit_allowed(req))
        req.remote_addr = "192.168.1.9"
        self.assertFalse(nav.native_submit_allowed(req))
        self.assertFalse(nav.local_browser_request(req))
        main = MAIN.read_text(encoding="utf-8")
        self.assertIn('@app.route("/api/native-navigation/chrome-owner"', main)
        self.assertIn("b3_nav_bridge.native_submit_allowed(request)", main)
        self.assertIn("b3_nav_bridge.local_browser_request(request)", main)
        self.assertIn("chrome_owner_lease.publish(", main)
        self.assertIn("chrome_owner_lease.active()", main)

    def test_chromium_suppression_is_opt_in_and_expires_automatically(self):
        script = SCRIPT.read_text(encoding="utf-8")
        css = CSS.read_text(encoding="utf-8")
        template = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("'/api/native-navigation/chrome-owner'", script)
        self.assertIn("body?.active !== true", script)
        self.assertIn("document.hasFocus()", script)
        self.assertIn("window.ACPNavDrawer?.hide?.()", script)
        self.assertIn("release();", script)
        self.assertIn("window.addEventListener('blur', release)", script)
        self.assertIn("window.addEventListener('pagehide'", script)
        self.assertIn("setInterval", script)
        self.assertIn("body.acp-b4-gtk-owned:not(.nav-audio-open)", css)
        self.assertIn("visibility: hidden !important", css)
        self.assertIn("pointer-events: none !important", css)
        self.assertNotIn("display: none", css.split("body.acp-b4-gtk-owned", 1)[1])
        self.assertIn("js/shared-native-nav-owner.js", template)
        self.assertIn("css/shared-native-nav-owner.css", template)
        self.assertIn("20261026-b4-lease-v1", template)

    def test_gtk_only_heartbeats_when_mapped_and_acp_focused(self):
        src = GTK.read_text(encoding="utf-8")
        self.assertIn('parser.add_argument("--share-chrome"', src)
        self.assertIn('parser.error("--share-chrome requires --observe-foreground")', src)
        self.assertIn("uuid.uuid4().hex if share_chrome else None", src)
        self.assertIn("indicator.get_mapped()", src)
        self.assertIn("overlay_allowed(state[\"keyboard\"])", src)
        self.assertIn("observed[0] != \"acp\" or not indicator_mapped", src)
        self.assertIn("observe_and_renew_chrome, b1, focus_env", src)
        self.assertIn("ThreadPoolExecutor(max_workers=1", src)
        self.assertIn("urllib.request.urlopen(req, timeout=0.35)", src)
        for options in (
            ["--show", "--share-chrome"],
            ["--show", "--share-chrome", "--route-pages"],
        ):
            result = subprocess.run([sys.executable, str(GTK), *options],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--share-chrome requires --observe-foreground", result.stderr)
        # Nothing about this lease makes the previously accepted B3 preview a
        # source of GTK ownership messages unless the new option is selected.
        self.assertIn("if share_chrome:", src)
        self.assertIn("observed_foreground, b1, focus_env", src)


if __name__ == "__main__":
    unittest.main()
