#!/usr/bin/env python3
"""Phase B3: opt-in native Plexamp navigation drawer / OSK visibility probe.

A short-lived GTK3 layer-shell preview, NOT the production shell. It reads
Squeekboard's read-only Visible D-Bus property but never controls the OSK.
Unknown keyboard state fails closed: no native overlay is displayed.
Navigation destinations are PREVIEW ONLY; the ACP button deliberately uses the
existing B1 compositor focus helper without changing any browser route.
No startup, desktop configuration, app state or audio changes.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
INDICATOR = HERE / "try-native-navigation-indicator.py"
OSK_SERVICE = "sm.puri.OSK0"
OSK_PATH = "/sm/puri/OSK0"
OSK_INTERFACE = "sm.puri.OSK0"
POLL_MS = 300
DBUS_TIMEOUT_MS = 250
DRAWER_BOTTOM_MARGIN = 8
DRAWER_HEIGHT = 70
OPEN_INDICATOR_EXTRA_GAP = 4
WORKSPACE_ITEMS = ("Home", "Weather", "News", "AirPlay", "Plexamp")
UTILITY_ITEMS = ("Audio", "Settings")
# The extra ACP escape is temporary and explicitly development-only.
NAV_ITEMS = WORKSPACE_ITEMS + UTILITY_ITEMS + ("ACP",)
MAX_SECONDS = 300


def load_indicator():
    spec = importlib.util.spec_from_file_location("acp_b3_indicator", INDICATOR)
    if not spec or not spec.loader:
        raise RuntimeError("Accepted B2 indicator helper is missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def keyboard_visible(bus, Gio, GLib, *, diagnostic: list[str] | None = None) -> bool | None:
    """Read the OSK's documented D-Bus Visible PROPERTY, never change its state.

    The method-only GetVisible call used in the first B3 preview is not exposed
    by all Squeekboard releases. Properties.Get returns a (v) carrying a 'b'.
    Preserve the strict fail-closed policy on missing services or bad replies.
    """
    try:
        response = bus.call_sync(
            OSK_SERVICE, OSK_PATH, "org.freedesktop.DBus.Properties", "Get",
            GLib.Variant("(ss)", (OSK_INTERFACE, "Visible")),
            GLib.VariantType.new("(v)"),
            Gio.DBusCallFlags.NO_AUTO_START, DBUS_TIMEOUT_MS, None,
        )
        if response is None:
            if diagnostic is not None:
                diagnostic.append("D-Bus Properties.Get returned no response")
            return None
        property_value = response.get_child_value(0).get_variant()
        if property_value.get_type_string() != "b":
            if diagnostic is not None:
                diagnostic.append("D-Bus Visible property was not a Boolean")
            return None
        visible = property_value.get_boolean()
        return visible if isinstance(visible, bool) else None
    except Exception as exc:
        # Unavailable D-Bus/OSK must not uncover navigation above the keyboard.
        if diagnostic is not None:
            diagnostic.append(f"{type(exc).__name__}: {str(exc).splitlines()[0][:240]}")
        return None


def overlay_allowed(visible: bool | None) -> bool:
    return visible is False


def drawer_width_for_screen(width: int, height: int) -> int:
    """Match nav.css compact drawer width (viewport minus 14px)."""
    compact = width <= 860 or height <= 680
    return min(1000 if compact else 940, max(320, width - (14 if compact else 20)))


def indicator_margin(drawer_open: bool) -> int:
    """Place the same navigation handle above the open drawer."""
    return DRAWER_HEIGHT + DRAWER_BOTTOM_MARGIN + OPEN_INDICATOR_EXTRA_GAP if drawer_open else 0


def make_layer_window(Gtk, LayerShell, width: int, height: int,
                      *, namespace: str, bottom: int):
    win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    win.set_title("ACP native navigation preview (temporary)")
    win.set_decorated(False)
    win.set_resizable(False)
    win.set_default_size(width, height)
    win.set_size_request(width, height)
    win.set_app_paintable(True)
    screen = win.get_screen()
    visual = screen.get_rgba_visual() if screen else None
    if visual is not None:
        win.set_visual(visual)
    LayerShell.init_for_window(win)
    LayerShell.set_namespace(win, namespace)
    LayerShell.set_layer(win, LayerShell.Layer.OVERLAY)
    LayerShell.set_keyboard_mode(win, LayerShell.KeyboardMode.NONE)
    LayerShell.set_anchor(win, LayerShell.Edge.BOTTOM, True)
    LayerShell.set_margin(win, LayerShell.Edge.BOTTOM, bottom)
    LayerShell.set_exclusive_zone(win, 0)
    return win


def present(Gtk, Gdk, GLib, Gio, LayerShell, bus, b2, *, seconds: int):
    if not LayerShell.is_supported():
        raise RuntimeError("The current compositor does not support GTK layer shell")
    display = Gdk.Display.get_default()
    width, height = b2.desktop_monitor_size(display)
    bar_width, bar_height = b2.bar_size_for_screen(width, height)
    drawer_width = drawer_width_for_screen(width, height)

    screen = Gdk.Screen.get_default()
    css = b"""
      window { background-color: transparent; }
      .acp-b3-hitbox { background-color: transparent; }
      .acp-b3-handle {
        background-color: rgba(247,249,255,0.74);
        border-radius: 999px;
        box-shadow: 0 0 16px rgba(255,255,255,0.18);
      }
      .acp-b3-handle.hover {
        background-color: rgba(247,249,255,0.94);
        box-shadow: 0 0 18px rgba(255,255,255,0.26);
      }
      .acp-b3-drawer {
        background-color: rgba(6,12,22,0.91);
        border: 1px solid rgba(255,255,255,0.18);
        border-radius: 18px;
        box-shadow: 0 18px 70px rgba(0,0,0,0.42);
      }
      .acp-b3-nav {
        background-color: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 13px;
        color: #f7f9ff;
        font-size: 16px;
        padding: 0 7px;
      }
      .acp-b3-nav:hover { background-color: rgba(247,249,255,0.18); }
      .acp-b3-active, .acp-b3-active:hover {
        color: #07101d;
        background-color: #f7f9ff;
        border-color: #f7f9ff;
        box-shadow: 0 0 18px rgba(247,249,255,0.22);
      }
      .acp-b3-utility { border-radius: 999px; font-size: 24px; padding: 0; }
      .acp-b3-utility-group {
        border-left: 1px solid rgba(247,249,255,0.22);
        padding-left: 6px;
      }
      .acp-b3-developer { font-size: 12px; border-style: dashed; }
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css)
    Gtk.StyleContext.add_provider_for_screen(
        screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    indicator = make_layer_window(
        Gtk, LayerShell, b2.PROBE_WIDTH, b2.PROBE_HEIGHT,
        namespace="acp-b3-indicator-test", bottom=0)
    hitbox = Gtk.EventBox()
    hitbox.set_visible_window(False)
    hitbox.set_size_request(b2.PROBE_WIDTH, b2.PROBE_HEIGHT)
    hitbox.get_style_context().add_class("acp-b3-hitbox")
    layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    layout.set_size_request(b2.PROBE_WIDTH, b2.PROBE_HEIGHT)
    handle = Gtk.EventBox()
    handle.set_size_request(bar_width, bar_height)
    handle.set_halign(Gtk.Align.CENTER)
    handle.set_valign(Gtk.Align.CENTER)
    handle.set_margin_bottom(b2.DEFAULT_EDGE_PADDING)
    handle.set_opacity(0.82)
    handle.get_style_context().add_class("acp-b3-handle")
    layout.pack_end(handle, False, False, 0)
    hitbox.add(layout)
    indicator.add(hitbox)

    drawer = make_layer_window(
        Gtk, LayerShell, drawer_width, DRAWER_HEIGHT,
        namespace="acp-b3-drawer-test", bottom=DRAWER_BOTTOM_MARGIN)
    body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
    body.set_border_width(6)
    body.get_style_context().add_class("acp-b3-drawer")
    workspaces = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
    utilities = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    utilities.get_style_context().add_class("acp-b3-utility-group")
    body.pack_start(workspaces, True, True, 0)
    body.pack_start(utilities, False, False, 0)
    drawer.add(body)

    state = {"drawer": False, "keyboard": None, "stopping": False}
    def stop_once(reason):
        if state["stopping"]:
            return False
        state["stopping"] = True
        print(f"ACP B3: {reason}", flush=True)
        if Gtk.main_level() > 0:
            Gtk.main_quit()
        return False

    def set_drawer_open(opened: bool):
        # Keep handle and drawer in step, as in ACP's accepted nav.css.
        state["drawer"] = opened
        LayerShell.set_margin(indicator, LayerShell.Edge.BOTTOM,
                              indicator_margin(opened))
        if opened:
            drawer.show_all()
        else:
            drawer.hide()

    def toggle_drawer(_widget, _event):
        if not overlay_allowed(state["keyboard"]):
            return True
        set_drawer_open(not state["drawer"])
        print("ACP B3: preview drawer " +
              ("opened" if state["drawer"] else "closed"), flush=True)
        return True

    def select_destination(_button, name):
        if not overlay_allowed(state["keyboard"]):
            return
        if name == "Plexamp":
            set_drawer_open(False)
            print("ACP B3: returned to Plexamp (drawer closed)", flush=True)
        elif name == "ACP":
            print("ACP B3: requesting existing ACP window focus", flush=True)
            if b2.focus_acp():
                stop_once("ACP focused, ending preview")
            else:
                print("ACP B3: ACP focus failed; preview remains available", flush=True)
        else:
            print(f"ACP B3: {name} selected (preview only; route not connected)", flush=True)

    for item in WORKSPACE_ITEMS:
        button = Gtk.Button(label=item)
        button.set_size_request(76, 56)
        button.get_style_context().add_class("acp-b3-nav")
        if item == "Plexamp":
            button.get_style_context().add_class("acp-b3-active")
        button.connect("clicked", select_destination, item)
        workspaces.pack_start(button, True, True, 0)

    for label, glyph in (("Audio", "♪"), ("Settings", "⚙")):
        button = Gtk.Button(label=glyph)
        button.set_tooltip_text(label)
        button.set_size_request(56, 56)
        button.get_style_context().add_class("acp-b3-nav")
        button.get_style_context().add_class("acp-b3-utility")
        button.connect("clicked", select_destination, label)
        utilities.pack_start(button, False, False, 0)

    # B3 still lacks actual ACP page selection; keep a small explicit escape.
    escape = Gtk.Button(label="ACP")
    escape.set_tooltip_text("Development only: focus existing ACP Chromium")
    escape.set_size_request(50, 56)
    escape.get_style_context().add_class("acp-b3-nav")
    escape.get_style_context().add_class("acp-b3-developer")
    escape.connect("clicked", select_destination, "ACP")
    utilities.pack_start(escape, False, False, 0)

    def on_enter(_widget, _event):
        handle.get_style_context().add_class("hover")
        handle.set_opacity(1.0)
        return False

    def on_leave(_widget, _event):
        handle.get_style_context().remove_class("hover")
        handle.set_opacity(0.82)
        return False

    hitbox.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK |
                      Gdk.EventMask.ENTER_NOTIFY_MASK |
                      Gdk.EventMask.LEAVE_NOTIFY_MASK)
    hitbox.connect("button-release-event", toggle_drawer)
    hitbox.connect("enter-notify-event", on_enter)
    hitbox.connect("leave-notify-event", on_leave)
    indicator.connect("destroy", lambda *_: stop_once("window closed"))

    def refresh_keyboard():
        current = keyboard_visible(bus, Gio, GLib)
        if current == state["keyboard"] and current is not None:
            return True
        state["keyboard"] = current
        if not overlay_allowed(current):
            set_drawer_open(False)
            indicator.hide()
            print("ACP B3: keyboard visible/unavailable: hiding ALL native navigation", flush=True)
        else:
            indicator.show_all()
            print("ACP B3: keyboard hidden: indicator restored", flush=True)
        return True

    # Verify Squeekboard before either Wayland window is displayed.
    if not overlay_allowed(keyboard_visible(bus, Gio, GLib)):
        raise RuntimeError("Cannot start preview while Squeekboard is visible or its state is unavailable")
    refresh_keyboard()
    GLib.timeout_add(POLL_MS, refresh_keyboard)
    GLib.timeout_add_seconds(seconds, lambda: stop_once("time limit reached; closing preview"))
    print(f"ACP B3: preview for at most {seconds}s, indicator {bar_width}x{bar_height}px;"
          " tap opens drawer; routes preview-only except Plexamp/ACP;"
          " hides when Squeekboard opens.", flush=True)
    try:
        Gtk.main()
    except KeyboardInterrupt:
        print("ACP B3: Ctrl+C received", flush=True)
    finally:
        drawer.destroy()
        indicator.destroy()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check-osk", action="store_true",
                        help="read Squeekboard visibility without showing any window")
    action.add_argument("--show", action="store_true",
                        help="start temporary drawer preview over existing native Plexamp")
    parser.add_argument("--seconds", type=int, default=90,
                        help="auto-close after 1-300 seconds (default 90)")
    args = parser.parse_args()
    if not 1 <= args.seconds <= MAX_SECONDS:
        parser.error("--seconds must be between 1 and 300")
    try:
        b2 = load_indicator()
        env = b2.desktop_environment(os.environ, os.getuid(), root=os.geteuid() == 0)
        os.environ.update(env)
        Gtk, Gdk, GLib, LayerShell = b2.load_gtk()
        from gi.repository import Gio
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        diagnostic: list[str] = []
        state = keyboard_visible(bus, Gio, GLib, diagnostic=diagnostic)
        if args.check_osk:
            print("ACP B3: Squeekboard Visible property:",
                  state if state is not None else "unavailable")
            if diagnostic:
                print("ACP B3: D-Bus diagnostic:", diagnostic[0])
            return 0 if state is not None else 1
        if not overlay_allowed(state):
            detail = f" ({diagnostic[0]})" if diagnostic else ""
            raise RuntimeError("Squeekboard visible or Visible property unavailable"
                               + detail + "; no native navigation overlay shown")
        present(Gtk, Gdk, GLib, Gio, LayerShell, bus, b2, seconds=args.seconds)
        return 0
    except (RuntimeError, OSError, b2.ProbeError) as exc:
        print("ACP B3: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
