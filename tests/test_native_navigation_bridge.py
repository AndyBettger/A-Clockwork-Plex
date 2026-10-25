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
        # Verify that the native navigation invocation requests a non-animated
        # background commit, without coupling this regression to JS layout.
        self.assertRegex(
            bridge,
            r"window\.ACPNavigate\('/' \+ command\.destination,\s*\{"
            r"\s*source:\s*'native-plexamp-b3',\s*animate:\s*false,?\s*\}\)",
        )
        self.assertIn("...options,\n        history: true,", transitions)
        self.assertIn("if (options.animate === false) return false;", surface_host)
        self.assertIn("document.startViewTransition(commit)", surface_host)
        # Existing ACP-to-ACP navigation still offers View Transitions.
        self.assertIn("const transition = document.startViewTransition(commit)", surface_host)
        self.assertIn("motionEnabled(options)", surface_host)

    def test_native_ready_requires_screen_controller_lease_and_visible_surface(self):
        bridge = (ROOT / "app/static/js/native-navigation-bridge.js").read_text()
        # The native route must not focus Chromium on a stale Clock/underlay.
        self.assertIn("function readyForHandoff(command)", bridge)
        self.assertIn("window.ACPNavigationState?.activeRoute?.() !== route", bridge)
        self.assertIn("window.ACPSurfaceHost?.activeRoute?.() !== route", bridge)
        self.assertIn("window.ACPPlexamp?.isVisiblyOpen?.() === true", bridge)
        self.assertIn("window.ACPScreenProjection?.state?.()", bridge)
        self.assertIn("projection?.recommended_screen !== destination", bridge)
        self.assertIn("projection?.lease?.active !== true", bridge)
        self.assertIn("projection?.lease?.manual_surface !== destination", bridge)
        self.assertIn("'.acp-mounted-surface-' + destination + ':not([hidden])'", bridge)
        self.assertIn("if (!command || !readyForHandoff(command)) return;", bridge)
        self.assertIn("if (!document.hasFocus() || !readyForHandoff(command)", bridge)
        self.assertIn("const MAX_AGE_MS = 12000", bridge)
        self.assertIn("const MAX_STAGE_ATTEMPTS = 6", bridge)
        # Audio is an in-drawer utility, not a registered ACP page/lease.
        self.assertIn("if (command.destination === 'audio')", bridge)

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
        colors["curtain_background"] = "#101b2e"
        colors["drawer_background"] = "rgba(6, 12, 22, 0.91)"
        colors["button_hover_background"] = "rgba(255, 255, 255, 0.22)"
        colors["button_pressed_background"] = "rgba(255, 255, 255, 0.30)"
        snapshot.publish(colors)
        self.assertEqual(snapshot.read(), colors)
        colors["drawer_background"] = "rgb(0, 0, 0)"
        self.assertEqual(snapshot.read()["drawer_background"],
                         "rgba(6, 12, 22, 0.91)")
        for bad in (
            {}, {"drawer_background": "rgb(0, 0, 0)"},
            {**colors, "handle_color": "red; } window { opacity: 0"},
            {**colors, "utility_border": None},
            {**colors, "curtain_background": "rgba(16, 27, 46, 0.5)"},
            {**colors, "curtain_background": "#101b2e!important"},
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
        self.assertIn("button_hover_background: buttonHover", script)
        self.assertIn("button_pressed_background: buttonPressed", script)
        self.assertIn("curtain_background: curtainFill", script)
        self.assertIn("getPropertyValue('--acp-b3-curtain-fill')", script)
        self.assertIn("--acp-nav-hover-fill", script)
        self.assertIn("--acp-nav-pressed-fill", script)
        self.assertIn(".nav-button:not(.is-active)", script)
        self.assertIn('lastPaletteAttemptAt < 4000', script)
        self.assertIn("void publishPalette();", script)
        self.assertIn("/api/native-navigation/palette", script)
        self.assertIn('browser_palette_allowed(request)', main)
        self.assertIn('native_status_allowed(request)', main)
        self.assertIn('palette_snapshot.publish(', main)
        self.assertIn('palette_snapshot.read()', main)

    def test_transiently_busy_native_route_is_retried_without_reposting(self):
        script = (ROOT / "app/static/js/native-navigation-bridge.js").read_text()
        self.assertIn("const STAGE_RETRY_MS = 1200", script)
        self.assertIn("const MAX_STAGE_ATTEMPTS = 6", script)
        self.assertIn("staging.sequence !== command.sequence", script)
        self.assertIn("if (readyForHandoff(command) || staging.inFlight", script)
        self.assertIn("window.ACPNavigationState?.isPresenting?.()", script)
        self.assertIn("stagePendingHandoff();", script)
        self.assertEqual(script.count("fetch('/api/native-navigation/next'"), 1)

    def test_native_curtain_uses_css_theme_colours_not_gtk_theme_guesses(self):
        base = (ROOT / "app/templates/base.html").read_text()
        token = (ROOT / "app/static/css/acp-design-tokens.css").read_text()
        day = (ROOT / "app/static/css/daytime-themes.css").read_text()
        night = (ROOT / "app/static/css/night-navigation-closure.css").read_text()
        self.assertIn("--acp-b3-curtain-fill: #101b2e", token)
        for name in ("midnight_blue", "amber_terminal", "green_phosphor",
                     "aubergine", "steel_cyan", "crimson_glow"):
            block = day.split('html[data-daytime-theme="' + name
                              + '"] body:not([data-active-page="plexamp"]) {', 1)[1]
            self.assertRegex(block.split("}", 1)[0],
                             r"--acp-b3-curtain-fill: #[0-9a-f]{6};")
        self.assertIn("--acp-b3-curtain-fill: #300000", night)
        self.assertIn("20261025-b3-curtain-theme-v1", base)
        self.assertIn('r"#[0-9a-fA-F]{6}"', PATH.read_text())

    def test_all_curated_nav_themes_define_hover_and_press_colours(self):
        theme = (ROOT / "app/static/css/daytime-themes.css").read_text()
        follow = (ROOT / "app/static/css/daytime-theme-followup.css").read_text()
        nav = (ROOT / "app/static/css/nav.css").read_text()
        night = (ROOT / "app/static/css/night-navigation-closure.css").read_text()
        for name in ("midnight_blue", "amber_terminal", "green_phosphor",
                     "aubergine", "steel_cyan", "crimson_glow"):
            block = theme.split('html[data-daytime-theme="' + name + '"] body:not([data-active-page="plexamp"]) {', 1)[1]
            block = block.split('}', 1)[0]
            self.assertIn('--acp-nav-hover-fill:', block)
            self.assertIn('--acp-nav-pressed-fill:', block)
        self.assertIn('nav-button:not(.is-active):hover', follow)
        self.assertIn('nav-button:not(.is-active):active', follow)
        self.assertIn('nav-button:not(.is-active):active', nav)
        self.assertIn('--acp-nav-hover-fill: rgba(135, 0, 0, 0.78)', night)
        self.assertIn('--acp-nav-pressed-fill: rgba(176, 0, 0, 0.86)', night)

    def test_astronomy_red_owns_nav_after_daytime_theme_important_css(self):
        base = (ROOT / "app/templates/base.html").read_text()
        night = (ROOT / "app/static/css/night-navigation-closure.css").read_text()
        original = (ROOT / "app/static/css/display-dimming.css").read_text()
        followup = (ROOT / "app/static/css/daytime-theme-followup.css").read_text()
        self.assertLess(base.index("css/daytime-theme-followup.css"),
                        base.index("css/night-navigation-closure.css"))
        self.assertIn("20261025-b3-pointer-feedback-v1", base)
        self.assertIn(".nav-drawer .nav-button", followup)
        self.assertIn("!important", followup)
        self.assertIn(
            "body.acp-night-style-astronomy.acp-night-dim-active"
            ":not(.mode-alarm):not([data-active-page=\"alarm\"])",
            night,
        )
        self.assertIn("#nav-drawer .nav-button.is-active", night)
        self.assertIn("background: rgb(255, 64, 64) !important", night)
        self.assertIn("background: rgba(96, 0, 0, 0.62) !important", night)
        self.assertIn("#nav-drawer .nav-utilities", night)
        self.assertIn("rgba(20, 0, 0, 0.96)", night)
        self.assertIn("--acp-night-brightness", original)
        self.assertNotIn("filter:", night)
        # No non-night selector may override daytime, alarm or Classic night.
        for selector in night.split("{")[:-1]:
            if "body." in selector:
                self.assertIn("acp-night-style-astronomy", selector)

    def test_effective_astronomy_night_colours_share_loaded_dimming_stylesheet(self):
        dim = (ROOT / "app/static/css/display-dimming.css").read_text()
        template = (ROOT / "app/templates/base.html").read_text()
        handle_selector = ("body.acp-night-style-astronomy."
                           "acp-night-dim-active .nav-handle span")
        nav_selector = ("body.acp-night-style-astronomy."
                        "acp-night-dim-active:not(.mode-alarm):"
                        "not([data-active-page=\"alarm\"]) #nav-drawer")
        self.assertIn(handle_selector, dim)
        self.assertIn(nav_selector, dim)
        self.assertIn(f"{nav_selector} .nav-button", dim)
        self.assertIn("background: rgba(20, 0, 0, 0.96) !important", dim)
        self.assertIn("background: rgba(96, 0, 0, 0.62) !important", dim)
        self.assertIn("background: rgb(255, 64, 64) !important", dim)
        self.assertIn("20261023-b3-night-nav-in-dimming-v7", template)
        self.assertNotIn("filter:", dim[dim.index("B3 23 Oct physical failure follow-up"):
                                     dim.index("body.acp-night-style-astronomy.acp-night-dim-active .nav-handle span")])

    def test_presentation_snapshot_rejects_unbounded_values_and_expires(self):
        now = [20.0]
        store = nav.PresentationSnapshot(lambda: now[0])
        metrics = {
            "viewport_width": 1280, "viewport_height": 720,
            "drawer_width": 940, "drawer_height": 76,
            "drawer_bottom": 8, "drawer_padding": 8,
            "workspace_gap": 8, "utility_gap": 6,
            "button_height": 62, "utility_size": 62,
            "font_size": 21.8, "night_brightness": 0.18,
            "astronomy_night": True,
        }
        self.assertIsNone(store.read())
        store.publish(metrics)
        self.assertEqual(store.read(), metrics)
        metrics["drawer_width"] = 5
        self.assertEqual(store.read()["drawer_width"], 940)
        bad_samples = [
            {**metrics, "drawer_width": 5001},
            {**metrics, "viewport_width": 700, "drawer_width": 940},
            {**metrics, "font_size": "21px"},
            {**metrics, "utility_size": True},
            {**metrics, "night_brightness": 2.0},
            {**metrics, "astronomy_night": False},
            {**metrics, "astronomy_night": False, "night_brightness": .18},
            {**metrics, "extra_css": "window { color: red; }"},
        ]
        for candidate in bad_samples:
            with self.assertRaises(nav.NavigationError):
                store.publish(candidate)
        now[0] += nav.PALETTE_MAX_AGE_SECONDS + 1
        self.assertIsNone(store.read())

    def test_presentation_uses_palette_loopback_guards_and_existing_timer(self):
        source = (ROOT / "app/static/js/native-navigation-bridge.js").read_text()
        main = (ROOT / "app/main.py").read_text()
        template = (ROOT / "app/templates/base.html").read_text()
        self.assertIn('window.getComputedStyle(document.documentElement)', source)
        self.assertIn('getBoundingClientRect().height', source)
        self.assertIn("'--acp-night-brightness'", source)
        self.assertIn("document.body.classList.contains('acp-night-style-astronomy')", source)
        self.assertIn("document.body.dataset.activePage !== 'alarm'", source)
        self.assertIn('/api/native-navigation/presentation', source)
        self.assertIn("if (validMeasurements)", source)
        self.assertIn("void publishPalette();", source)
        self.assertEqual(source.count("window.setInterval(poll, 600)"), 1)
        self.assertIn("@app.route(\"/api/native-navigation/presentation\"", main)
        self.assertIn('browser_palette_allowed(request)', main)
        self.assertIn('native_status_allowed(request)', main)
        self.assertIn('presentation_snapshot.publish(', main)
        self.assertIn('presentation_snapshot.read()', main)
        self.assertIn("20261025-b3-lease-readiness-v1", template)

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
