"""B4 GTK/WebKit developer probe: no GTK/display or ACP service required."""
from __future__ import annotations

import http.client
from contextlib import redirect_stdout
from io import StringIO
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
from pathlib import Path
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "try-webkit-gtk-shell.py"
SPEC = importlib.util.spec_from_file_location("acp_webkit_probe", SCRIPT)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class Upstream(BaseHTTPRequestHandler):
    writes = 0

    def log_message(self, *_args):
        pass

    def do_GET(self):
        data = b"<html><body>ACP probe test page</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Length", "8")
        self.end_headers()

    def do_POST(self):
        type(self).writes += 1
        self.send_response(204)
        self.end_headers()


class WebKitProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.origin = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        cls.origin_thread = threading.Thread(target=cls.origin.serve_forever, daemon=True)
        cls.origin_thread.start()
        cls.proxy = ThreadingHTTPServer(
            ("127.0.0.1", 0), probe.make_proxy_handler(cls.origin.server_port))
        cls.proxy_thread = threading.Thread(target=cls.proxy.serve_forever, daemon=True)
        cls.proxy_thread.start()

    @classmethod
    def tearDownClass(cls):
        for server, worker in ((cls.proxy, cls.proxy_thread),
                               (cls.origin, cls.origin_thread)):
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def request(self, method, path, body=None):
        client = http.client.HTTPConnection("127.0.0.1", self.proxy.server_port, timeout=2)
        try:
            client.request(method, path, body=body)
            response = client.getresponse()
            return response.status, response.read(), response.getheader("Content-Type")
        finally:
            client.close()

    def test_read_only_proxy_get_preserves_html_and_type(self):
        status, data, content_type = self.request("GET", "/clock")
        self.assertEqual(status, 200)
        self.assertIn(b"ACP probe test page", data)
        self.assertEqual(content_type, "text/html")

    def test_head_is_allowed(self):
        status, body, _ = self.request("HEAD", "/weather")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")

    def test_post_and_other_writes_do_not_reach_acp(self):
        start = Upstream.writes
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            status, _, _ = self.request(method, "/api/mode/weather", "{}")
            self.assertEqual(status, 405, method)
        self.assertEqual(Upstream.writes, start)

    def test_repeated_write_denials_emit_one_diagnostic_per_endpoint(self):
        output = StringIO()
        with redirect_stdout(output):
            for _ in range(3):
                self.assertEqual(self.request("POST", "/api/osk/c3/theme-sync")[0], 405)
            for _ in range(2):
                self.assertEqual(self.request("POST", "/api/native-navigation/palette")[0], 405)
        logs = output.getvalue()
        self.assertEqual(logs.count("blocked POST /api/osk/c3/theme-sync"), 1)
        self.assertEqual(logs.count("blocked POST /api/native-navigation/palette"), 1)
        self.assertIn("further repeats suppressed", logs)

    def test_only_relative_origin_paths_allowed(self):
        for value in ("https://example.com/", "//example.com/x",
                      "relative", "/hello\\world", "/x\x00y"):
            self.assertFalse(probe.valid_proxy_path(value))
        for value in ("/", "/clock", "/api/surfaces/news?a=1", "/static/css/nav.css"):
            self.assertTrue(probe.valid_proxy_path(value))

    def test_explicit_opt_in_and_bounded_lifetime(self):
        with self.assertRaises(SystemExit):
            probe.parse_args([])
        with self.assertRaises(SystemExit):
            probe.parse_args(["--check", "--show"])
        with self.assertRaises(SystemExit):
            probe.parse_args(["--show", "--seconds", "3600"])
        with self.assertRaises(SystemExit):
            probe.parse_args(["--show", "--page", "plexamp"])
        args = probe.parse_args(["--show", "--page", "weather",
                                "--seconds", "180"])
        self.assertFalse(args.fullscreen)
        self.assertEqual(args.page, "weather")
        self.assertEqual(args.seconds, 180)

    def test_ephemeral_context_not_ordinary_persistent_browser(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("WebKit2.WebContext.new_ephemeral()", src)
        self.assertIn("WebKit2.WebView.new_with_context(", src)
        self.assertIn("Gtk.main_quit()", src)
        self.assertIn("GLib.timeout_add_seconds(args.seconds", src)
        self.assertIn('url_root + "/" + args.page', src)

    def test_sigint_cleanup_is_idempotent_when_gtk_loop_already_stopped(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("if Gtk.main_level() > 0:", src)
        self.assertIn("except KeyboardInterrupt:", src)
        self.assertIn("GLib.timeout_add_seconds(args.seconds, quit_if_running)", src)
        self.assertIn('window.connect("destroy", lambda *_: quit_if_running())', src)

    def test_per_navigation_timing_and_live_viewport_logging(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('if event == WebKit2.LoadEvent.STARTED:', src)
        self.assertIn('navigation["started"] = time.monotonic()', src)
        self.assertIn('elif event == WebKit2.LoadEvent.FINISHED:', src)
        self.assertIn('elapsed = time.monotonic() - navigation["started"]', src)
        self.assertIn('document load finished in {elapsed:.2f}s', src)
        self.assertIn('window.get_size()', src)
        self.assertIn('view.get_allocated_width()', src)
        self.assertIn('view.get_allocated_height()', src)
        self.assertNotIn('page rendered in ', src)

    def test_cancelled_document_requests_are_not_backend_failures(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('except (BrokenPipeError, ConnectionResetError):', src)
        self.assertIn('ordinary cancelled consumer', src)
        self.assertIn('self.send_error(502, "ACP service unavailable")', src)
        self.assertIn('WEBKIT_DISABLE_DMABUF_RENDERER', src)
        self.assertNotIn('os.environ["WEBKIT_DISABLE_DMABUF_RENDERER"]', src)

    def test_renderer_comparison_switches_are_read_only_and_exclusive(self):
        self.assertIn("default DMA-BUF", probe.renderer_diagnostic({}))
        self.assertIn(
            "compatibility fallback",
            probe.renderer_diagnostic({"WEBKIT_DISABLE_DMABUF_RENDERER": "1"}))
        self.assertIn(
            "shared-memory buffer transport",
            probe.renderer_diagnostic({"WEBKIT_DMABUF_RENDERER_FORCE_SHM": "1"}))
        self.assertIn(
            "compatibility fallback",
            probe.renderer_diagnostic({"WEBKIT_DISABLE_DMABUF_RENDERER": "1",
                                       "WEBKIT_DMABUF_RENDERER_FORCE_SHM": "1"}))
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn('os.environ["WEBKIT_DMABUF_RENDERER_FORCE_SHM"]', src)
        self.assertNotIn('os.environ["WEBKIT_DISABLE_DMABUF_RENDERER"]', src)
        self.assertIn('os.environ.get("WEBKIT_SHOW_FPS") == "1"', src)

    def test_viewport_diagnostic_recommends_fullscreen_without_mutating_css(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("if actual_view[1] < args.height - 2", src)
        self.assertIn("window decorations or compositor size", src)
        self.assertIn("use --fullscreen", src)
        self.assertIn("actual_view = (view.get_allocated_width()", src)
        self.assertIn('if args.fullscreen:', src)

    def test_rain_width_trial_is_explicit_and_scoped_to_ephemeral_webkit(self):
        self.assertFalse(probe.parse_args(["--show"]).rain_width_trial)
        self.assertTrue(probe.parse_args(
            ["--show", "--page", "weather", "--rain-width-trial"]).rain_width_trial)
        self.assertIn("body.mode-weather .rain-overview-scroll", probe.RAIN_WIDTH_TRIAL_CSS)
        self.assertIn("inline-size: max-content !important;", probe.RAIN_WIDTH_TRIAL_CSS)
        self.assertNotIn("body.mode-weather .screen", probe.RAIN_WIDTH_TRIAL_CSS)
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("(args.rain_width_trial, RAIN_WIDTH_TRIAL_CSS, \"Rain width\")", src)
        self.assertIn("WebKit2.UserStyleSheet.new(", src)
        self.assertIn("WebKit2.UserContentInjectedFrames.TOP_FRAME", src)
        self.assertIn("WebKit2.UserStyleLevel.USER", src)
        self.assertIn("webview.get_user_content_manager().add_style_sheet(sheet)", src)
        self.assertNotIn("write_text(", src)
        self.assertNotIn("write_bytes(", src)

    def test_read_only_weather_geometry_reports_panel_overflow(self):
        src = SCRIPT.read_text(encoding="utf-8")
        script = probe.RAIN_LAYOUT_METRICS_SCRIPT
        self.assertIn("document.querySelector('.rain-overview-scroll')", script)
        self.assertIn("querySelectorAll('.rain-subpanel')", script)
        self.assertIn("querySelectorAll('.rain-gauge-card')", script)
        self.assertIn("last.right - r.right", script)
        self.assertIn("railScrollWidth: root.scrollWidth", script)
        self.assertIn("railScrollLeft: Math.round(root.scrollLeft)", script)
        self.assertIn("snapType: getComputedStyle(root).scrollSnapType", script)
        self.assertIn("touchAction: getComputedStyle(root).touchAction", script)
        self.assertIn("view.evaluate_javascript(", src)
        self.assertIn("value.to_string()", src)
        self.assertIn('urlsplit(view.get_uri()).path == "/weather"', src)
        self.assertIn("GLib.timeout_add(700, report_rain_layout, view)", src)
        self.assertIn("GLib.timeout_add_seconds(12, report_rain_layout, view)", src)

    def test_rain_width_grid_content_sizes_entire_first_panel(self):
        css = probe.RAIN_WIDTH_TRIAL_CSS
        self.assertIn("min-inline-size: max-content !important;", css)
        self.assertIn("grid-auto-flow: column !important;", css)
        self.assertIn("grid-auto-columns: clamp(150px, 21vw, 190px) !important;", css)
        self.assertIn("grid-template-columns: none !important;", css)
        self.assertIn("body.mode-weather .rain-overview-scroll", css)
        self.assertNotIn("body.mode-clock", css)

    def test_rain_intrinsic_width_grid_flexes_to_match_tallest_history_panel(self):
        css = probe.RAIN_WIDTH_TRIAL_CSS
        # The panel width experiment must not leave Today at its minimum
        # content height while History's taller gauge row stretches.
        row_selector = ("body.mode-weather .rain-overview-scroll > "
                        ".rain-subpanel > .rain-gauge-row")
        row = css.split(row_selector, 1)[1].split("}", 1)[0]
        self.assertIn("grid-auto-flow: column !important;", row)
        self.assertIn("grid-auto-columns: clamp(150px, 21vw, 190px) !important;", row)
        self.assertIn("inline-size: max-content !important;", row)
        self.assertIn("flex: 1 1 auto !important;", row)
        self.assertIn("align-items: stretch !important;", row)
        self.assertNotIn("flex: 0 0 auto !important;", row)
        self.assertIn("flex-shrink: 0 !important;", css)

    def test_rain_metrics_compare_actual_panel_row_card_and_gauge_heights(self):
        script = probe.RAIN_LAYOUT_METRICS_SCRIPT
        for token in ("panelHeight: Math.round(r.height)",
                      "rowHeight: rowBox ? Math.round(rowBox.height) : 0",
                      "minCardHeight: Math.min(...cardHeights)",
                      "maxCardHeight: Math.max(...cardHeights)",
                      "minGaugeHeight: Math.min(...fillHeights)",
                      "maxGaugeHeight: Math.max(...fillHeights)",
                      "last.right - r.right"):
            with self.subTest(token=token):
                self.assertIn(token, script)
        self.assertNotIn("style.height =", script)
        self.assertNotIn("style.minHeight =", script)

    def test_rain_touch_trial_is_opt_in_and_removes_spring_back(self):
        self.assertFalse(probe.parse_args(["--show"]).rain_touch_trial)
        self.assertTrue(probe.parse_args(["--show", "--rain-touch-trial"]).rain_touch_trial)
        css = probe.RAIN_TOUCH_TRIAL_CSS
        self.assertIn("scroll-snap-type: none !important;", css)
        self.assertIn("scroll-snap-align: none !important;", css)
        self.assertIn("touch-action: pan-x !important;", css)
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("(args.rain_touch_trial, RAIN_TOUCH_TRIAL_CSS, \"Rain touch/no-snap\")", src)
        self.assertIn("webview.get_user_content_manager().add_style_sheet(sheet)", src)
        self.assertNotIn("root.scrollLeft =", src)
        self.assertNotIn("window.scrollTo(", src)

    def test_flick_trial_is_independent_and_default_off(self):
        normal = probe.parse_args(["--show", "--page", "weather"])
        self.assertFalse(normal.weather_flick_trial)
        self.assertTrue(probe.parse_args(
            ["--show", "--weather-flick-trial"]).weather_flick_trial)
        css = probe.WEATHER_FLICK_TRIAL_CSS
        self.assertIn(".rain-overview-scroll, .weather-forecast-strip", css)
        self.assertIn("scroll-snap-type: none !important;", css)
        self.assertIn("touch-action: pan-y !important;", css)
        self.assertIn("scroll-snap-align: none !important;", css)
        self.assertNotIn("body.mode-clock", css)

    def test_flick_trial_handles_only_horizontal_touch_and_keeps_vertical_native(self):
        js = probe.WEATHER_FLICK_TRIAL_SCRIPT
        self.assertIn("if (event.touches.length !== 1", js)
        self.assertIn("event.target.closest(selector)", js)
        self.assertIn("event.target instanceof Element", js)
        self.assertIn("event.target.closest(selector)", js)
        self.assertIn("gesture.axis = Math.abs(dx) >= Math.abs(dy) * 1.2", js)
        self.assertIn("if (gesture.axis !== 'horizontal') return;", js)
        self.assertIn("if (event.cancelable) event.preventDefault();", js)
        self.assertIn("gesture.strip.scrollLeft = Math.min(maxScroll,", js)
        self.assertIn("Math.max(0, gesture.startScroll - dx)", js)
        self.assertIn("status.finishes += 1;", js)
        self.assertIn("status.cancels += 1;", js)
        self.assertNotIn("requestAnimationFrame(", js)
        self.assertNotIn("setInterval(", js)
        self.assertNotIn("fetch(", js)

    def test_flick_script_is_webkit_only_and_metrics_are_read_only(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("if args.weather_flick_trial:", src)
        self.assertIn("WebKit2.UserScript.new(", src)
        self.assertIn("WebKit2.UserScriptInjectionTime.END", src)
        self.assertIn("add_script(injected)", src)
        self.assertIn("WEATHER_FLICK_TRIAL_SCRIPT", src)
        self.assertIn("WEATHER_FLICK_TRIAL_CSS", src)
        script = probe.RAIN_LAYOUT_METRICS_SCRIPT
        self.assertIn("flick: window.__acpWebkitFlickMetrics || null", script)
        self.assertIn("document.querySelectorAll('.weather-forecast-strip')", script)
        self.assertIn("scrollLeft: Math.round(strip.scrollLeft)", script)
        self.assertNotIn("strip.scrollLeft =", script)

    def test_surface_transition_trial_is_explicit_opt_in(self):
        normal = probe.parse_args(["--show"])
        self.assertFalse(normal.surface_transition_trial)
        self.assertEqual(normal.surface_transition_mode, "spatial")
        sample = probe.parse_args([
            "--show", "--surface-transition-trial",
            "--surface-transition-mode", "configured",
        ])
        self.assertTrue(sample.surface_transition_trial)
        self.assertEqual(sample.surface_transition_mode, "configured")
        with self.assertRaises(SystemExit):
            probe.parse_args([
                "--show", "--surface-transition-mode", "configured",
            ])
        with self.assertRaises(SystemExit):
            probe.parse_args([
                "--show", "--surface-transition-trial",
                "--surface-transition-mode", "invalid",
            ])

    def test_surface_transition_bridge_uses_production_mounted_host(self):
        js = probe.SURFACE_TRANSITION_TRIAL_SCRIPT
        self.assertIn("window.ACPSurfaceHost", js)
        self.assertIn("host?.canNavigate?.(target)", js)
        self.assertIn("await host.navigate(target, options)", js)
        self.assertIn("window.ACPWorkspaceTopology?.acpSurfaceOrder?.()", js)
        self.assertIn("options.spatialCommitDirection = direction", js)
        self.assertIn("history: false", js)
        self.assertIn("source: 'webkit-read-only-surface-trial'", js)
        self.assertIn("['clock', 'weather', 'news', 'airplay', 'settings']", js)
        self.assertNotIn("location.assign", js)
        self.assertNotIn("location.reload", js)
        self.assertNotIn("fetch(", js)
        self.assertNotIn("POST", js)

    def test_surface_transition_status_includes_outcome_and_same_document(self):
        js = probe.SURFACE_TRANSITION_TRIAL_SCRIPT
        metrics = probe.SURFACE_TRANSITION_METRICS_SCRIPT
        self.assertIn("document.addEventListener('acp:surface-changed'", js)
        self.assertIn("document.addEventListener('acp:surface-settled'", js)
        self.assertIn("performance.now() - started", js)
        self.assertIn("sameDocument: location.href === href", js)
        self.assertIn("host.supportsViewTransitions?.()", js)
        self.assertIn("state.failures += 1", js)
        self.assertIn("window.ACPApplicationSurfaces?.surfaces?.()", metrics)
        self.assertIn("transitionInFlight: host?.isTransitioning?.()", metrics)
        self.assertIn("requests: trial?.state.requests", metrics)
        self.assertIn("failures: trial?.state.failures", metrics)

    def test_surface_transition_keyboard_switch_does_not_replace_original_get_path(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("if args.surface_transition_trial:", src)
        self.assertIn("WebKit2.UserScriptInjectionTime.END", src)
        self.assertIn("SURFACE_TRANSITION_TRIAL_SCRIPT", src)
        self.assertIn('json.dumps(page)', src)
        self.assertIn("GLib.timeout_add_seconds(3, report_surface_layout, webview)", src)
        self.assertIn("SURFACE_TRANSITION_METRICS_SCRIPT", src)
        self.assertIn('webview.load_uri(url_root + "/" + page)', src)
        self.assertIn('self.send_error(405, "Read-only WebKit preview: writes disabled")',
                      src)
        self.assertNotIn("systemctl restart", src)

    def test_repeated_ctrl_c_cannot_interrupt_proxy_cleanup(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("prior_sigint = signal.getsignal(signal.SIGINT)", src)
        self.assertIn("signal.signal(signal.SIGINT, signal.SIG_IGN)", src)
        self.assertIn("signal.signal(signal.SIGINT, prior_sigint)", src)
        self.assertIn("server.shutdown()", src)
        self.assertIn("server.server_close()", src)
        self.assertIn("window.destroy()", src)

    def test_preserve_existing_chromium_and_native_player(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("systemctl", src)
        self.assertNotIn("flatpak kill", src)
        self.assertNotIn("wlrctl toplevel", src)
        self.assertNotIn("CamillaDSP", src.split("def main")[1])
        self.assertNotIn("sudo apt install", src)
        self.assertEqual(probe.PAGES,
                         ("clock", "weather", "news", "airplay", "settings"))


if __name__ == "__main__":
    unittest.main()
