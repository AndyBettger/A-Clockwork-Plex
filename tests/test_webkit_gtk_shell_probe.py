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
