#!/usr/bin/env python3
"""Developer-only GTK3/WebKitGTK ACP rendering probe (issue #94).

This is NOT the production shell or a replacement for Chromium. It uses a
loopback-only GET/HEAD proxy to reject requests that would change the running
ACP backend. Pages can be inspected using F1-F5; controller POSTs, Settings
saves and same-document route transitions are intentionally not tested here.

No app services, Flatpak, CamillaDSP/ALSA, Squeekboard or autostart touched.
"""
from __future__ import annotations

import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import signal
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

ACP_HOST = "127.0.0.1"
ACP_PORT = 8088
PAGES = ("clock", "weather", "news", "airplay", "settings")
MAX_SECONDS = 300
FORWARD_HEADERS = ("Accept", "Accept-Language", "Cookie", "If-Modified-Since",
                   "If-None-Match", "Range", "User-Agent")
RESPONSE_HEADERS = ("Content-Type", "Content-Length", "Content-Encoding",
                    "Cache-Control", "ETag", "Last-Modified", "Set-Cookie",
                    "Location", "Vary", "Content-Range", "Accept-Ranges")

# EXPERIMENT ONLY. Force each Weather rain panel to include every contained
# gauge in its intrinsic size, while preserving the existing horizontal rail.
# Injected only into this ephemeral WebKit view when --rain-width-trial is set;
# never change accepted production Chromium styles.
RAIN_WIDTH_TRIAL_CSS = """
body.mode-weather .rain-overview-scroll > .rain-subpanel {
  flex: 0 0 auto !important;
  inline-size: max-content !important;
  max-inline-size: none !important;
}
body.mode-weather .rain-overview-scroll > .rain-subpanel > .rain-gauge-row {
  flex: 0 0 auto !important;
  inline-size: max-content !important;
}
body.mode-weather .rain-overview-scroll .rain-gauge-card {
  flex-shrink: 0 !important;
}
"""

# Read-only DOM geometry; reports CSS pixel positions, not VNC-scaled pixels.
# Positive overflow means a gauge extends beyond its owning subpanel.
RAIN_LAYOUT_METRICS_SCRIPT = r"""
(() => {
 const root = document.querySelector('.rain-overview-scroll');
 if (!root) return JSON.stringify({status: 'no-rain-layout'});
 const sections = [...root.querySelectorAll('.rain-subpanel')].map(panel => {
   const r = panel.getBoundingClientRect();
   const gauges = [...panel.querySelectorAll('.rain-gauge-card')];
   const last = gauges[gauges.length - 1]?.getBoundingClientRect();
   return {
     name: panel.classList.contains('rain-current-subpanel') ? 'today' : 'history',
     panelWidth: Math.round(r.width), gaugeCount: gauges.length,
     lastGaugeRight: last ? Math.round(last.right) : null,
     panelRight: Math.round(r.right),
     overflow: last ? Math.round(Math.max(0, last.right - r.right)) : 0
   };
 });
 return JSON.stringify({
   status: 'ok', viewport: window.innerWidth,
   railWidth: Math.round(root.getBoundingClientRect().width),
   railScrollWidth: root.scrollWidth, sections
 });
})()
"""


def valid_proxy_path(raw: str) -> bool:
    """Accept relative origin paths only, never absolute or network URLs."""
    if not raw.startswith("/") or raw.startswith("//") or "\\" in raw:
        return False
    if any(ch in raw for ch in ("\r", "\n", "\x00")):
        return False
    parsed = urlsplit(raw)
    return parsed.scheme == "" and parsed.netloc == ""


def make_proxy_handler(upstream_port: int = ACP_PORT):
    blocked_once: set[tuple[str, str]] = set()
    blocked_lock = threading.Lock()

    class ReadOnlyACPProxy(BaseHTTPRequestHandler):
        server_version = "ACP-WebKit-ReadOnly/0.1"

        def log_message(self, fmt, *args):
            # send_error() also calls log_message(); never print a write twice.
            return

        def do_GET(self):
            self._relay()

        def do_HEAD(self):
            self._relay()

        def do_POST(self):
            self._reject_write()

        def do_PUT(self):
            self._reject_write()

        def do_PATCH(self):
            self._reject_write()

        def do_DELETE(self):
            self._reject_write()

        def _reject_write(self):
            route = self.path.split("?", 1)[0]
            key = (self.command, route)
            with blocked_lock:
                first = key not in blocked_once
                if first:
                    blocked_once.add(key)
            if first:
                print(f"ACP WebKit probe: blocked {self.command} {route} "
                      "(further repeats suppressed)", flush=True)
            self.send_error(405, "Read-only WebKit preview: writes disabled")

        def _relay(self):
            if not valid_proxy_path(self.path):
                self.send_error(400, "Only local paths are permitted")
                return
            headers = {key: value for key in FORWARD_HEADERS
                       if (value := self.headers.get(key)) is not None}
            # Keep Flask URL generation on the preview's temporary origin.
            headers["Host"] = self.headers.get("Host", ACP_HOST)
            connection = http.client.HTTPConnection(ACP_HOST, upstream_port, timeout=5)
            try:
                connection.request(self.command, self.path, headers=headers)
                response = connection.getresponse()
                payload = response.read() if self.command == "GET" else b""
                self.send_response(response.status)
                for key in RESPONSE_HEADERS:
                    for value in response.headers.get_all(key, []):
                        self.send_header(key, value)
                self.end_headers()
                if self.command == "GET" and payload:
                    self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                # Browsers may abandon an in-flight GET when F1–F5 navigates.
                # This is an ordinary cancelled consumer, not a Flask failure.
                return
            except (OSError, http.client.HTTPException) as exc:
                try:
                    self.send_error(502, "ACP service unavailable")
                except OSError:
                    pass
                print(f"ACP WebKit probe: upstream error ({type(exc).__name__})",
                      flush=True)
            finally:
                connection.close()

    return ReadOnlyACPProxy


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true",
                      help="Check packages and ACP availability without opening a window.")
    mode.add_argument("--show", action="store_true",
                      help="Open the temporary GTK3/WebKit rendering probe.")
    parser.add_argument("--page", choices=PAGES, default="clock")
    parser.add_argument("--seconds", type=int, default=120)
    parser.add_argument("--width", type=int, default=853)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fullscreen", action="store_true",
                        help="Opt in to fullscreen; windowed by default.")
    parser.add_argument("--rain-width-trial", action="store_true",
                        help="Apply experimental WebKit-only Rain panel sizing; "
                             "production CSS stays unchanged.")
    args = parser.parse_args(argv)
    if not 10 <= args.seconds <= MAX_SECONDS:
        parser.error("--seconds must be between 10 and 300")
    if not 480 <= args.width <= 3840 or not 320 <= args.height <= 2160:
        parser.error("window dimensions out of bounded probe range")
    return args


def probe_backend():
    connection = http.client.HTTPConnection(ACP_HOST, ACP_PORT, timeout=3)
    try:
        connection.request("HEAD", "/clock")
        response = connection.getresponse()
        response.read()
        print(f"ACP WebKit probe: local ACP HEAD /clock HTTP {response.status}",
              flush=True)
        return 200 <= response.status < 400
    except OSError as exc:
        print(f"ACP WebKit probe: backend unavailable ({exc})", flush=True)
        return False
    finally:
        connection.close()


def load_gtk_webkit():
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("WebKit2", "4.1")
        from gi.repository import Gtk, Gdk, GLib, WebKit2
        return Gtk, Gdk, GLib, WebKit2
    except (ImportError, ValueError) as exc:
        print(f"ACP WebKit probe: GTK/WebKit GI unavailable: {exc}", flush=True)
        print("Check: dpkg-query -W python3-gi gir1.2-gtk-3.0 "
              "gir1.2-webkit2-4.1 (do not install blindly).", flush=True)
        return None


def desktop_environment():
    if os.geteuid() == 0:
        print("ACP WebKit probe: run as your desktop user, not root.", flush=True)
        return False
    runtime = os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    candidates = []
    if os.environ.get("WAYLAND_DISPLAY"):
        candidates.append(os.environ["WAYLAND_DISPLAY"])
    candidates.append("wayland-0")
    try:
        candidates.extend(p.name for p in sorted(Path(runtime).glob("wayland-*")))
    except OSError:
        pass
    for name in dict.fromkeys(candidates):
        candidate = name if os.path.isabs(name) else str(Path(runtime) / name)
        if Path(candidate).exists():
            try:
                stat = Path(candidate).stat()
                if not socket_is_socket(stat.st_mode):
                    continue
            except OSError:
                continue
            os.environ["WAYLAND_DISPLAY"] = name
            os.environ.setdefault("GDK_BACKEND", "wayland")
            bus = Path(runtime) / "bus"
            if bus.exists():
                os.environ.setdefault("DBUS_SESSION_BUS_ADDRESS", "unix:path=" + str(bus))
            return True
    print(f"ACP WebKit probe: no usable Wayland socket under {runtime}", flush=True)
    return False


def socket_is_socket(mode: int):
    import stat
    return stat.S_ISSOCK(mode)


def renderer_diagnostic(environment=None):
    """Describe process-local WebKit rendering switches, without setting any."""
    values = os.environ if environment is None else environment
    if values.get("WEBKIT_DISABLE_DMABUF_RENDERER") == "1":
        return ("DMA-BUF renderer disabled (compatibility fallback; "
                "may reduce animation performance)")
    if values.get("WEBKIT_DMABUF_RENDERER_FORCE_SHM") == "1":
        return ("DMA-BUF renderer enabled, shared-memory buffer transport "
                "(experimental performance comparison)")
    return "default DMA-BUF buffer transport"


def start_proxy():
    server = ThreadingHTTPServer((ACP_HOST, 0), make_proxy_handler())
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever,
                              name="acp-webkit-probe-proxy", daemon=True)
    thread.start()
    return server, thread


def show_window(args, Gtk, Gdk, GLib, WebKit2):
    if not desktop_environment():
        return 2
    try:
        initialised = Gtk.init_check()
    except Exception as exc:
        print(f"ACP WebKit probe: GTK cannot connect to labwc ({exc})", flush=True)
        return 2
    if initialised is False or (isinstance(initialised, tuple) and not initialised[0]):
        print("ACP WebKit probe: GTK display initialization failed", flush=True)
        return 2

    server, worker = start_proxy()
    url_root = f"http://127.0.0.1:{server.server_port}"
    # Each WebKit top-level navigation has its own clock; the elapsed time
    # since window creation is NOT an individual page loading measurement.
    navigation = {"started": time.monotonic()}
    window = Gtk.Window(title="A Clockwork Plex — WebKitGTK dev probe")
    window.set_default_size(args.width, args.height)
    webview = WebKit2.WebView.new_with_context(WebKit2.WebContext.new_ephemeral())
    if args.rain_width_trial:
        sheet = WebKit2.UserStyleSheet.new(
            RAIN_WIDTH_TRIAL_CSS, WebKit2.UserContentInjectedFrames.TOP_FRAME,
            WebKit2.UserStyleLevel.USER, None, None)
        webview.get_user_content_manager().add_style_sheet(sheet)
        print("ACP WebKit probe: trial Rain width stylesheet injected "
              "(this WebView only; server CSS unchanged)", flush=True)
    rgba = Gdk.RGBA()
    rgba.parse("#02040a")
    webview.set_background_color(rgba)
    window.add(webview)

    def quit_if_running():
        # GTK's SIGINT fallback may already have stopped the main loop.
        if Gtk.main_level() > 0:
            Gtk.main_quit()
        return False

    window.connect("destroy", lambda *_: quit_if_running())

    def report_rain_layout(view):
        # WebKitGTK >=2.40 supports this read-only evaluation API. The probe
        # runs against the same temporary origin and does not alter the DOM.
        def finished(result_view, result, _data):
            try:
                value = result_view.evaluate_javascript_finish(result)
                print("ACP WebKit probe: rain layout " + value.to_string(),
                      flush=True)
            except Exception as exc:
                print(f"ACP WebKit probe: rain layout measurement unavailable "
                      f"({type(exc).__name__}: {exc})", flush=True)
        try:
            view.evaluate_javascript(
                RAIN_LAYOUT_METRICS_SCRIPT, -1, None, None, None, finished, None)
        except Exception as exc:
            print(f"ACP WebKit probe: rain layout evaluation unavailable "
                  f"({type(exc).__name__}: {exc})", flush=True)
        return False

    def on_load(view, event):
        if event == WebKit2.LoadEvent.STARTED:
            navigation["started"] = time.monotonic()
        elif event == WebKit2.LoadEvent.FINISHED:
            # FINISHED is the WebKit load event, not a first-paint/FPS metric.
            elapsed = time.monotonic() - navigation["started"]
            print(f"ACP WebKit probe: document load finished in {elapsed:.2f}s, "
                  f"title={view.get_title()!r}", flush=True)
            actual_window = window.get_size()
            actual_view = (view.get_allocated_width(), view.get_allocated_height())
            print(f"ACP WebKit probe: GTK window {actual_window[0]}x{actual_window[1]}, "
                  f"WebView {actual_view[0]}x{actual_view[1]} "
                  f"(requested {args.width}x{args.height})", flush=True)
            if actual_view[1] < args.height - 2 or actual_view[0] < args.width - 2:
                print("ACP WebKit probe: content viewport is smaller than requested "
                      "(window decorations or compositor size); use --fullscreen "
                      "to compare at the actual panel resolution.", flush=True)
            if view.get_uri() and urlsplit(view.get_uri()).path == "/weather":
                GLib.timeout_add(700, report_rain_layout, view)

    def on_failure(_view, _event, uri, error):
        print(f"ACP WebKit probe: LOAD FAILED {uri}: {error}", flush=True)
        return False

    def on_navigation(_view, decision, decision_type):
        if decision_type != WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            return False
        uri = decision.get_request().get_uri()
        if uri.startswith(url_root + "/"):
            return False
        print(f"ACP WebKit probe: external navigation blocked: {uri}",
              flush=True)
        decision.ignore()
        return True

    def on_key(_widget, event):
        key = Gdk.keyval_name(event.keyval)
        if key in ("Escape", "q", "Q") and (key == "Escape" or
                                            event.state & Gdk.ModifierType.CONTROL_MASK):
            quit_if_running()
            return True
        pages = {f"F{i+1}": page for i, page in enumerate(PAGES)}
        if key in pages:
            # A fresh GET of each existing ACP document: this stage tests
            # rendering, not same-document navigation or transition state.
            page = pages[key]
            print(f"ACP WebKit probe: displaying /{page} (GET only)", flush=True)
            webview.load_uri(url_root + "/" + page)
            return True
        return False

    webview.connect("load-changed", on_load)
    webview.connect("load-failed", on_failure)
    webview.connect("decide-policy", on_navigation)
    window.connect("key-press-event", on_key)
    window.show_all()
    if args.fullscreen:
        window.fullscreen()
    print("ACP WebKit probe: temporary, ephemeral WebKit window; "
          "GET/HEAD-only localhost proxy, backend writes refused.", flush=True)
    print("ACP WebKit probe: F1 Clock | F2 Weather | F3 News | "
          "F4 AirPlay | F5 Settings | Esc exit", flush=True)
    print(f"ACP WebKit probe: windowed={not args.fullscreen}, "
          f"limit={args.seconds}s; existing Chromium/Flatpak untouched.",
          flush=True)
    print("ACP WebKit probe: renderer " + renderer_diagnostic(), flush=True)
    print("ACP WebKit probe: Rain width trial " +
          ("ON (ephemeral WebKit only)" if args.rain_width_trial else "OFF"),
          flush=True)
    if os.environ.get("WEBKIT_SHOW_FPS") == "1":
        print("ACP WebKit probe: WebKit FPS indicator requested "
              "(if supported by installed build)", flush=True)
    webview.load_uri(url_root + "/" + args.page)
    GLib.timeout_add_seconds(args.seconds, quit_if_running)
    try:
        Gtk.main()
    except KeyboardInterrupt:
        # PyGObject can surface Ctrl+C while unregistering its SIGINT
        # fallback, even after the main loop was already told to quit.
        print("ACP WebKit probe: interrupted by Ctrl+C", flush=True)
    finally:
        # A second Ctrl+C while shutdown() waits on the proxy thread should
        # not cause a traceback or leave the temporary loopback port open.
        prior_sigint = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)
            window.destroy()
            print("ACP WebKit probe: bounded session ended; no services changed.",
                  flush=True)
        finally:
            signal.signal(signal.SIGINT, prior_sigint)
    return 0


def main(argv=None):
    args = parse_args(argv)
    if os.geteuid() == 0:
        print("ACP WebKit probe: do not run with sudo.", flush=True)
        return 2
    backend_ok = probe_backend()
    libraries = load_gtk_webkit()
    if args.check:
        print("ACP WebKit probe: readiness " +
              ("PASS" if backend_ok and libraries else "BLOCKED"), flush=True)
        return 0 if backend_ok and libraries else 2
    if not backend_ok or libraries is None:
        print("ACP WebKit probe: display not started; preflight failed.",
              flush=True)
        return 2
    return show_window(args, *libraries)


if __name__ == "__main__":
    sys.exit(main())
