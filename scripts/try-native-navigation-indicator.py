#!/usr/bin/env python3
"""Phase B2: temporary GTK3 layer-shell native Plexamp bottom-indicator probe.

Runs as the desktop user from SSH. Never installs/starts a service, modifies
labwc or ACP settings, changes the keyboard, or changes audio/player state.
Default interaction is observational. --tap-focus-acp deliberately requests
focus of the *existing* ACP Chromium toplevel through the accepted B1 helper.
There is no independent navigation drawer; that belongs to Chromium.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

PROBE_WIDTH = 190
PROBE_HEIGHT = 22
BAR_WIDTH = 140
BAR_HEIGHT = 5
BOTTOM_MARGIN = 0
DEFAULT_EDGE_PADDING = 2
DEFAULT_TIMEOUT = 120
MAX_TIMEOUT = 300

ROOT = Path(__file__).resolve().parent
FOCUS_HELPER = ROOT / "switch-native-plexamp-window.py"


class ProbeError(Exception):
    pass


def desktop_environment(env: dict[str, str], uid: int, *, root: bool = False) -> dict[str, str]:
    """Resolve the current Pi labwc session without starting another display."""
    if root:
        raise ProbeError("Run as desktop user, without sudo.")
    runtime = Path(f"/run/user/{uid}")
    if not runtime.is_dir():
        raise ProbeError("No user desktop runtime; log into labwc before running.")
    configured_runtime = env.get("XDG_RUNTIME_DIR")
    if configured_runtime and Path(configured_runtime) != runtime:
        raise ProbeError("Unexpected XDG_RUNTIME_DIR; refusing another user's desktop.")
    wayland = env.get("WAYLAND_DISPLAY") or "wayland-0"
    if "/" in wayland:
        raise ProbeError("WAYLAND_DISPLAY must be a local session socket name.")
    if not (runtime / wayland).is_socket():
        raise ProbeError(f"No active Wayland socket: {wayland}")
    result = dict(env)
    result["XDG_RUNTIME_DIR"] = str(runtime)
    result["WAYLAND_DISPLAY"] = wayland
    result["GDK_BACKEND"] = "wayland"
    if (runtime / "bus").is_socket():
        result["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={runtime}/bus"
    return result


def load_gtk():
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("GtkLayerShell", "0.1")
        from gi.repository import Gtk, Gdk, GLib, GtkLayerShell
        return Gtk, Gdk, GLib, GtkLayerShell
    except (ImportError, ValueError) as exc:
        raise ProbeError(
            "GTK Layer Shell Python bindings missing. Install only "
            "gir1.2-gtklayershell-0.1 from Raspberry Pi OS packages."
        ) from exc


def focus_acp() -> bool:
    """One scoped compositor focus request; no web/audio/service calls."""
    result = subprocess.run(
        ["/usr/bin/python3", str(FOCUS_HELPER), "--to-acp"],
        capture_output=True, text=True, timeout=12, check=False,
    )
    if result.stdout:
        print(result.stdout.strip(), flush=True)
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr, flush=True)
    return result.returncode == 0


def present(Gtk, Gdk, GLib, LayerShell, seconds: int, *, tap_focus_acp: bool,
            edge_padding: int = DEFAULT_EDGE_PADDING) -> None:
    if not LayerShell.is_supported():
        raise ProbeError("labwc has no advertised zwlr_layer_shell_v1 support.")

    window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    window.set_title("ACP Native Navigation Indicator (test only)")
    window.set_decorated(False)
    window.set_resizable(False)
    window.set_default_size(PROBE_WIDTH, PROBE_HEIGHT)
    window.set_size_request(PROBE_WIDTH, PROBE_HEIGHT)
    window.set_app_paintable(True)
    screen = window.get_screen()
    visual = screen.get_rgba_visual() if screen else None
    if visual is not None:
        window.set_visual(visual)

    # All layer-shell configuration must occur BEFORE this window is realized.
    LayerShell.init_for_window(window)
    LayerShell.set_namespace(window, "acp-native-nav-indicator-dev")
    LayerShell.set_layer(window, LayerShell.Layer.OVERLAY)
    LayerShell.set_keyboard_mode(window, LayerShell.KeyboardMode.NONE)
    LayerShell.set_anchor(window, LayerShell.Edge.BOTTOM, True)
    LayerShell.set_margin(window, LayerShell.Edge.BOTTOM, BOTTOM_MARGIN)
    LayerShell.set_exclusive_zone(window, 0)  # Never move/resize Plexamp.

    # Match ACP's real handle: a transparent touch target and 140x5px bar.
    # No dark backdrop over the native Plexamp playback buttons.
    css = b"""
        window, .acp-native-probe { background-color: transparent; }
        .acp-native-probe-hitbox { background-color: transparent; }
        .acp-native-probe-indicator {
            background-color: rgba(247, 249, 255, 0.82);
            border-radius: 3px;
        }
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css)
    Gtk.StyleContext.add_provider_for_screen(
        screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

    eventbox = Gtk.EventBox()
    eventbox.set_visible_window(False)
    eventbox.set_size_request(PROBE_WIDTH, PROBE_HEIGHT)
    eventbox.get_style_context().add_class("acp-native-probe-hitbox")

    # Centered handle, same visual vocabulary as ACP's existing home indicator.
    layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    layout.set_halign(Gtk.Align.CENTER)
    layout.set_valign(Gtk.Align.FILL)
    layout.set_size_request(PROBE_WIDTH, PROBE_HEIGHT)
    handle = Gtk.EventBox()
    handle.set_size_request(BAR_WIDTH, BAR_HEIGHT)
    handle.set_margin_bottom(edge_padding)
    handle.get_style_context().add_class("acp-native-probe-indicator")
    # Place the visible line near the bottom edge rather than centred in the
    # hitbox; the previous centred line covered Plexamp transport controls.
    layout.pack_end(handle, False, False, 0)
    eventbox.add(layout)
    window.add(eventbox)

    stopping = False
    destroyed = False

    def stop_once(reason: str) -> bool:
        nonlocal stopping
        if stopping:
            return False
        stopping = True
        print(f"ACP native indicator: {reason}", flush=True)
        # Prevent a second gtk_main_quit after main() has already returned.
        if Gtk.main_level() > 0:
            Gtk.main_quit()
        return False

    def on_destroy(_window):
        nonlocal destroyed
        destroyed = True
        stop_once("window closed")

    def tapped(_widget, _event):
        print("ACP native indicator: TAP observed", flush=True)
        if tap_focus_acp:
            if focus_acp():
                stop_once("ACP focused; closing probe")
            else:
                print("ACP native indicator: focus failed; leaving probe visible.", flush=True)
        return True

    eventbox.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)
    eventbox.connect("button-release-event", tapped)
    window.connect("destroy", on_destroy)
    GLib.timeout_add_seconds(seconds, lambda: stop_once("time limit reached; closing probe"))
    window.show_all()
    print(
        "ACP native indicator: visible for at most "
        f"{seconds}s; {PROBE_WIDTH}x{PROBE_HEIGHT}px; edge gap {edge_padding}px; tap "
        f"{'focuses ACP then exits' if tap_focus_acp else 'prints a diagnostic only'}.",
        flush=True,
    )
    try:
        Gtk.main()
    except KeyboardInterrupt:
        # PyGObject's Gtk.main() SIGINT fallback may raise on context exit
        # even after its own GTK quit has been requested.
        print("ACP native indicator: Ctrl+C received; closing probe.", flush=True)
    finally:
        if not destroyed:
            window.destroy()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true", help="verify GTK bindings/layer protocol without showing a window")
    modes.add_argument("--show", action="store_true", help="show a temporary bottom home indicator")
    parser.add_argument("--seconds", type=int, default=DEFAULT_TIMEOUT,
                        help=f"automatically close the window after 1-{MAX_TIMEOUT} seconds (default {DEFAULT_TIMEOUT})")
    parser.add_argument("--tap-focus-acp", action="store_true",
                        help="on tap, ask labwc to focus ACP then close this indicator")
    parser.add_argument("--edge-padding", type=int, default=DEFAULT_EDGE_PADDING,
                        help="visual bar distance from bottom of touch target (0-10 pixels; default 2)")
    args = parser.parse_args()
    if not 1 <= args.seconds <= MAX_TIMEOUT:
        parser.error(f"--seconds must be between 1 and {MAX_TIMEOUT}")
    if args.tap_focus_acp and not args.show:
        parser.error("--tap-focus-acp requires --show")
    if not 0 <= args.edge_padding <= 10:
        parser.error("--edge-padding must be between 0 and 10")
    try:
        env = desktop_environment(os.environ, os.getuid(), root=os.geteuid() == 0)
        os.environ.update(env)
        Gtk, Gdk, GLib, LayerShell = load_gtk()
        if args.check:
            print("GTK3:", Gtk.MAJOR_VERSION, Gtk.MINOR_VERSION, Gtk.MICRO_VERSION)
            print("GTK Layer Shell supported:", bool(LayerShell.is_supported()))
            print("Wayland socket:", env["WAYLAND_DISPLAY"])
            return 0 if LayerShell.is_supported() else 1
        present(Gtk, Gdk, GLib, LayerShell, args.seconds,
                tap_focus_acp=args.tap_focus_acp, edge_padding=args.edge_padding)
        return 0
    except (ProbeError, OSError, subprocess.TimeoutExpired) as exc:
        print("ACP native indicator: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
