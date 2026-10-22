"""Phase B3 native navigation mailbox: local-only, short-lived, one-use."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "app/native_navigation_bridge.py"
spec = importlib.util.spec_from_file_location("b3_native_nav_bridge", PATH)
assert spec and spec.loader
nav = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nav)


class NativeNavigationBridgeTests(unittest.TestCase):
    def test_destination_whitelist_and_single_consumption(self):
        clock = mock.Mock(return_value=50.0)
        mailbox = nav.NavigationMailbox(clock)
        for target in nav.ALLOWED_DESTINATIONS:
            number = mailbox.offer({"destination": target})
            self.assertEqual(mailbox.take(), {"sequence": number, "destination": target})
            self.assertIsNone(mailbox.take())
        for payload in (None, "clock", {}, {"destination": "plexamp"},
                        {"destination": "/settings"}, {"destination": "clock", "extra": 2},
                        {"destination": "http://evil"}, {"destination": 4}):
            with self.assertRaises(nav.NavigationError):
                mailbox.offer(payload)

    def test_ready_requires_matching_consumed_command(self):
        now = [150.0]
        box = nav.NavigationMailbox(lambda: now[0])
        seq = box.offer({"destination": "weather"})
        self.assertEqual(box.status(seq), "queued")
        self.assertFalse(box.confirm_ready(seq, "weather"))
        self.assertFalse(box.confirm_ready(seq + 1, "weather"))
        self.assertEqual(box.take()["sequence"], seq)
        self.assertEqual(box.status(seq), "taken")
        self.assertFalse(box.confirm_ready(seq, "clock"))
        self.assertTrue(box.confirm_ready(seq, "weather"))
        self.assertEqual(box.status(seq), "ready")
        now[0] += 13
        self.assertEqual(box.status(seq), "expired")
        self.assertFalse(box.confirm_ready(seq, "weather"))

    def test_painted_requires_matching_ready_command_and_expires(self):
        now = [100.0]
        box = nav.NavigationMailbox(lambda: now[0])
        seq = box.offer({"destination": "weather"})
        self.assertFalse(box.confirm_painted(seq, "weather"))
        self.assertEqual(box.take()["sequence"], seq)
        self.assertFalse(box.confirm_painted(seq, "weather"))
        self.assertTrue(box.confirm_ready(seq, "weather"))
        self.assertFalse(box.confirm_painted(seq + 1, "weather"))
        self.assertFalse(box.confirm_painted(seq, "clock"))
        self.assertTrue(box.confirm_painted(seq, "weather"))
        self.assertEqual(box.status(seq), "painted")
        now[0] += 13.0
        self.assertFalse(box.confirm_painted(seq, "weather"))
        self.assertEqual(box.status(seq), "expired")

    def test_browser_ack_and_native_status_permissions(self):
        req = SimpleNamespace(remote_addr="127.0.0.1", host="localhost:8088",
            scheme="http", headers={"Origin": "http://localhost:8088",
                "Sec-Fetch-Site": "same-origin"}, mimetype="application/json",
            content_length=39)
        self.assertTrue(nav.browser_ready_allowed(req))
        req.headers["Origin"] = "http://evil.example"
        self.assertFalse(nav.browser_ready_allowed(req))
        req.headers = {"X-ACP-B3-Source": nav.SOURCE_HEADER}
        self.assertTrue(nav.native_status_allowed(req))
        req.headers["Sec-Fetch-Site"] = "cross-site"
        self.assertFalse(nav.native_status_allowed(req))

    def test_expiration_and_monotonic_sequence(self):
        now = [100.0]
        m = nav.NavigationMailbox(lambda: now[0])
        first = m.offer({"destination": "clock"})
        now[0] += 13
        self.assertIsNone(m.take())
        self.assertIsNone(m.take())
        later = m.offer({"destination": "weather"})
        self.assertEqual(later, first + 1)
        self.assertEqual(m.take()["destination"], "weather")

    def test_local_peer_guards_and_native_json_requirements(self):
        req = SimpleNamespace(remote_addr="127.0.0.1", host="localhost:8088",
            headers={"X-ACP-B3-Source": nav.SOURCE_HEADER},
            mimetype="application/json", content_length=25)
        self.assertTrue(nav.native_submit_allowed(req))
        for ip, host in (("192.168.1.8", "localhost:8088"),
                         ("127.0.0.1", "acp.local:8088"),
                         ("127.0.0.1", "evil.example:8088")):
            req.remote_addr, req.host = ip, host
            self.assertFalse(nav.native_submit_allowed(req))
        req.remote_addr, req.host = "127.0.0.1", "localhost:8088"
        for name, value in (("Origin", "http://evil.example"),
                            ("Forwarded", "for=203.0.113.1"),
                            ("Sec-Fetch-Site", "cross-site")):
            req.headers[name] = value
            self.assertFalse(nav.native_submit_allowed(req))
            del req.headers[name]
        req.headers.clear()
        self.assertFalse(nav.native_submit_allowed(req))

    def test_native_background_preparation_does_not_start_view_transition(self):
        bridge = (ROOT / "app/static/js/native-navigation-bridge.js").read_text()
        transitions = (ROOT / "app/static/js/page-transitions.js").read_text()
        surface_host = (ROOT / "app/static/js/acp-surface-host.js").read_text()
        self.assertIn("source: 'native-plexamp-b3',\n          animate: false,", bridge)
        self.assertIn("...options,\n        history: true,", transitions)
        self.assertIn("if (options.animate === false) return false;", surface_host)
        self.assertIn("document.startViewTransition(commit)", surface_host)
        # Existing ACP-to-ACP navigation still offers View Transitions.
        self.assertIn("const transition = document.startViewTransition(commit)", surface_host)
        self.assertIn("motionEnabled(options)", surface_host)

    def test_browser_painted_ack_is_after_focus_and_two_frames(self):
        js = (ROOT / "app/static/js/native-navigation-bridge.js").read_text()
        self.assertIn("window.requestAnimationFrame(() => window.requestAnimationFrame(resolve))", js)
        self.assertIn("!document.hasFocus()", js)
        self.assertIn("/api/native-navigation/painted", js)
        self.assertIn("window.addEventListener('focus', reportPainted)", js)
        self.assertIn("window.sessionStorage.removeItem(STORAGE_KEY)", js)
        self.assertIn('confirm_painted', PATH.read_text())

    def test_weather_paint_ack_requires_settled_forecast_and_real_panel(self):
        bridge = (ROOT / "app/static/js/native-navigation-bridge.js").read_text()
        weather = (ROOT / "app/static/js/weather-forecast.js").read_text()
        template = (ROOT / "app/templates/base.html").read_text()
        self.assertIn("function weatherContentReady()", bridge)
        self.assertIn("function contentReadyForPaint(command)", bridge)
        self.assertIn("!contentReadyForPaint(command)", bridge)
        self.assertIn(".acp-mounted-surface-weather:not([hidden])", bridge)
        self.assertIn(".weather-detail-page", bridge)
        self.assertIn("page.dataset.acpForecastSettled !== 'true'", bridge)
        self.assertIn(".weather-forecast-panel .weather-forecast-card", bridge)
        self.assertIn(".weather-detail-grid .detail-panel, .weather-panel", bridge)
        self.assertIn("rect.width > 12 && rect.height > 12", bridge)
        self.assertIn("anchor.dataset.acpForecastSettled = 'true';", weather)
        self.assertIn(".then((payload) => {\n      render(payload);", weather)
        self.assertIn(".catch(() => {", weather)
        # Cache-busting versions change when the bridge/forecast JS changes.
        # Assert that both scripts have a version rather than pinning a stale
        # revision from an earlier B3 milestone.
        self.assertRegex(
            template, r"filename='js/native-navigation-bridge\.js', v='[^']+'"
        )
        self.assertRegex(
            template, r"filename='js/weather-forecast\.js', v='[^']+'"
        )

    def test_native_palette_exact_colours_and_expiration(self):
        now = [10.0]
        snapshot = nav.PaletteSnapshot(lambda: now[0])
        self.assertIsNone(snapshot.read())
        colors = {key: "rgb(10, 20, 30)" for key in nav.PALETTE_KEYS}
        colors["drawer_background"] = "rgba(6, 12, 22, 0.91)"
        snapshot.publish(colors)
        self.assertEqual(snapshot.read(), colors)
        colors["drawer_background"] = "rgb(0, 0, 0)"
        self.assertEqual(snapshot.read()["drawer_background"],
                         "rgba(6, 12, 22, 0.91)")
        for bad in (
            {}, {"drawer_background": "rgb(0, 0, 0)"},
            {**colors, "handle_color": "red; } window { opacity: 0"},
            {**colors, "utility_border": None},
        ):
            with self.assertRaises(nav.NavigationError):
                snapshot.publish(bad)
        now[0] += 21
        self.assertIsNone(snapshot.read())

    def test_local_palette_endpoint_and_browser_source(self):
        req = SimpleNamespace(remote_addr="127.0.0.1", host="localhost:8088",
            scheme="http", headers={"Origin": "http://localhost:8088",
                "Sec-Fetch-Site": "same-origin"}, mimetype="application/json",
            content_length=500)
        self.assertTrue(nav.browser_palette_allowed(req))
        req.headers["Origin"] = "http://other-host:8088"
        self.assertFalse(nav.browser_palette_allowed(req))
        req.headers["Origin"] = "http://localhost:8088"
        req.remote_addr = "192.168.10.10"
        self.assertFalse(nav.browser_palette_allowed(req))
        script = (ROOT / "app/static/js/native-navigation-bridge.js").read_text()
        main = (ROOT / "app/main.py").read_text()
        self.assertIn('window.getComputedStyle(node)', script)
        self.assertIn(".nav-button:not(.is-active)", script)
        self.assertIn('lastPaletteAttemptAt < 4000', script)
        self.assertIn("void publishPalette();", script)
        self.assertIn("/api/native-navigation/palette", script)
        self.assertIn('browser_palette_allowed(request)', main)
        self.assertIn('native_status_allowed(request)', main)
        self.assertIn('palette_snapshot.publish(', main)
        self.assertIn('palette_snapshot.read()', main)

    def test_dashboard_hooks_present_and_no_boot_activation(self):
        template = (ROOT / "app/templates/base.html").read_text()
        js = (ROOT / "app/static/js/native-navigation-bridge.js").read_text()
        main = (ROOT / "app/main.py").read_text()
        self.assertIn("js/native-navigation-bridge.js", template)
        self.assertIn("ACPNavigate('/' + command.destination", js)
        self.assertIn("ACPNavDrawer?.show?.()", js)
        self.assertIn("ACPNavDrawer?.ensureAudioPanel?.()", js)
        self.assertIn("@app.route(\"/api/native-navigation/request\"", main)
        self.assertIn("@app.route(\"/api/native-navigation/next\"", main)
        self.assertIn("@app.route(\"/api/native-navigation/ready\"", main)
        self.assertIn("@app.route(\"/api/native-navigation/painted\"", main)
        self.assertIn("@app.route(\"/api/native-navigation/status\"", main)
        self.assertIn("ACPNavigationState?.activeRoute?.()", js)
        self.assertIn("ACPNavigationState?.isPresenting?.()", js)
        self.assertIn("sessionStorage", js)
        self.assertIn("/api/native-navigation/ready", js)
        self.assertNotIn("window.location.assign", js)
        self.assertNotIn("subprocess", PATH.read_text())


if __name__ == "__main__":
    unittest.main()
