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
import json
import re
import time
import urllib.request
import urllib.error

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
NAVIGATION_URL = "http://127.0.0.1:8088/api/native-navigation/request"
STATUS_URL = "http://127.0.0.1:8088/api/native-navigation/status"
PALETTE_URL = "http://127.0.0.1:8088/api/native-navigation/palette"
PALETTE_REFRESH_MS = 4000
PRESENTATION_URL = "http://127.0.0.1:8088/api/native-navigation/presentation"
PREPARE_TIMEOUT_SECONDS = 10.0
HANDOFF_POLL_MS = 180
CURTAIN_FOCUS_SETTLE_MS = 85
CURTAIN_PAINT_WAIT_SECONDS = 2.5
CURTAIN_FADE_STEP_MS = 40
CURTAIN_FADE_STEPS = 5
# Explicitly opt-in; ACP's navigation reveal duration is 180ms.
DRAWER_MOTION_MS = 180
DRAWER_MOTION_TICK_MS = 20


def request_page_handoff(label: str) -> int | None:
    """Issue only an allowlisted local command; return its server sequence."""
    routes = {
        "Home": "clock", "Weather": "weather", "News": "news",
        "AirPlay": "airplay", "Settings": "settings", "Audio": "audio",
    }
    destination = routes.get(label)
    if not destination:
        return None
    payload = json.dumps({"destination": destination}).encode("utf-8")
    req = urllib.request.Request(
        NAVIGATION_URL, data=payload, method="POST",
        headers={"Content-Type": "application/json",
                 "X-ACP-B3-Source": "native-gtk-b3-dev"},
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as response:
            data = json.load(response)
            sequence = data.get("sequence")
            if (response.status != 200 or data.get("ok") is not True
                    or type(sequence) is not int or sequence < 1):
                print("ACP B3: destination rejected by ACP", flush=True)
                return None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        print(f"ACP B3: local route unavailable: {exc}", flush=True)
        return None
    return sequence


def handoff_status(sequence: int) -> str:
    """Read our own bounded loopback handoff state; no route mutations."""
    url = f"{STATUS_URL}?sequence={sequence}"
    req = urllib.request.Request(
        url, method="GET", headers={"X-ACP-B3-Source": "native-gtk-b3-dev"},
    )
    try:
        with urllib.request.urlopen(req, timeout=0.35) as response:
            data = json.load(response)
            state = data.get("state")
            if (response.status == 200 and data.get("ok") is True
                    and state in ("queued", "taken", "ready", "painted", "expired")):
                return state
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        pass
    return "unavailable"


PALETTE_NAMES = frozenset((
    "drawer_background", "drawer_border", "button_background",
    "button_hover_background", "button_border", "button_text", "active_background", "active_text",
    "handle_color", "utility_border",
))
PALETTE_COLOR = re.compile(r"(?:rgba?\([\d.,%\s]+\)|#[\da-fA-F]{6,8}|transparent)\Z")


def valid_palette(value) -> bool:
    return (type(value) is dict and set(value) == PALETTE_NAMES
            and all(type(color) is str and len(color) <= 64
                    and PALETTE_COLOR.fullmatch(color) for color in value.values()))


def fetch_theme_palette() -> dict[str, str] | None:
    """Read only the ephemeral Chromium CSS snapshot; never write settings."""
    req = urllib.request.Request(
        PALETTE_URL, method="GET",
        headers={"X-ACP-B3-Source": "native-gtk-b3-dev"},
    )
    try:
        with urllib.request.urlopen(req, timeout=0.35) as response:
            payload = json.load(response)
        palette = payload.get("palette")
        if payload.get("ok") is True and valid_palette(palette):
            return palette
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        pass
    return None


def palette_css(value: dict[str, str]) -> bytes:
    """Only allow already validated CSS *color* literals, never raw CSS text."""
    if not valid_palette(value):
        raise ValueError("Unsafe or incomplete ACP navigation palette")
    return (f"""
      .acp-b3-drawer {{
        background-color: {value['drawer_background']};
        border-color: {value['drawer_border']};
      }}
      /* Preserve ACP's actual theme behaviour: Classic Dark has a
         brighter neutral hover/pressed fill; themed buttons do not. Both
         values are supplied by the validated Chromium palette snapshot.
         Override GTK's built-in grey in every pseudo-state. */
      .acp-b3-nav, .acp-b3-nav:focus, .acp-b3-nav:backdrop {{
        background-image: none;
        background-color: {value['button_background']};
        border-color: {value['button_border']};
        color: {value['button_text']};
        box-shadow: none;
      }}
      .acp-b3-nav:active, .acp-b3-nav:checked,
      .acp-b3-nav:hover, .acp-b3-nav:hover:focus,
      .acp-b3-nav:hover:active, .acp-b3-nav:focus:active,
      .acp-b3-nav:hover:checked, .acp-b3-nav:backdrop:hover {{
        background-image: none;
        background-color: {value['button_hover_background']};
        border-color: {value['button_border']};
        color: {value['button_text']};
        box-shadow: none;
      }}
      .acp-b3-active, .acp-b3-active:hover, .acp-b3-active:focus,
      .acp-b3-active:hover:focus, .acp-b3-active:backdrop,
      .acp-b3-active:active, .acp-b3-active:checked,
      .acp-b3-active:hover:active, .acp-b3-active:focus:active {{
        background-image: none;
        background-color: {value['active_background']};
        border-color: {value['active_background']};
        color: {value['active_text']};
      }}
      .acp-b3-handle {{ background-color: {value['handle_color']}; }}
      .acp-b3-handle.hover {{ background-color: {value['handle_color']}; }}
      .acp-b3-utility-group {{ border-left-color: {value['utility_border']}; }}
    """).encode("ascii")


PRESENTATION_NUMBERS = {
    "viewport_width": (320, 5000), "viewport_height": (240, 3000),
    "drawer_width": (200, 5000), "drawer_height": (40, 220),
    "drawer_bottom": (0, 60), "drawer_padding": (0, 32),
    "workspace_gap": (0, 40), "utility_gap": (0, 40),
    "button_height": (24, 140), "utility_size": (24, 140),
    "font_size": (8, 40), "night_brightness": (0.05, 1.0),
}


def valid_presentation(value) -> bool:
    return (type(value) is dict
            and set(value) == set(PRESENTATION_NUMBERS) | {"astronomy_night"}
            and type(value["astronomy_night"]) is bool
            and all(type(value[key]) in (int, float) and low <= value[key] <= high
                    for key, (low, high) in PRESENTATION_NUMBERS.items())
            and value["drawer_width"] <= value["viewport_width"]
            and value["drawer_height"] <= value["viewport_height"]
            and (value["astronomy_night"] or value["night_brightness"] == 1.0))


def fetch_acp_presentation() -> dict | None:
    req = urllib.request.Request(
        PRESENTATION_URL, method="GET",
        headers={"X-ACP-B3-Source": "native-gtk-b3-dev"},
    )
    try:
        with urllib.request.urlopen(req, timeout=0.35) as response:
            payload = json.load(response)
        data = payload.get("presentation")
        if payload.get("ok") is True and valid_presentation(data):
            return data
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        pass
    return None


def presentation_scale(data, monitor_width: int, monitor_height: int) -> float | None:
    """GTK geometry is physical display logical px; reject inconsistent zoom."""
    if not valid_presentation(data):
        return None
    x = monitor_width / data["viewport_width"]
    y = monitor_height / data["viewport_height"]
    if not (0.5 <= x <= 2.5 and 0.5 <= y <= 2.5):
        return None
    if abs(x - y) > 0.05 * max(x, y):
        return None
    return (x + y) / 2.0


_RGB_COLOR = re.compile(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})(?:\s*,\s*([\d.]+))?\s*\)\Z")


def night_darken_color(value: str, factor: float) -> str:
    """Simulate Chromium's nav filter: brightness(), preserving alpha.

    GTK3 layer-shell cannot apply the browser's CSS filter. Multiplying RGB
    components instead of making the whole drawer transparent avoids revealing
    Plexamp controls through the darkened navigation background.
    """
    match = _RGB_COLOR.fullmatch(value)
    if match:
        rgb = [min(255, round(int(match.group(n)) * factor)) for n in (1, 2, 3)]
        return (f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {match.group(4)})"
                if match.group(4) is not None
                else f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})")
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        rgb = [round(int(value[i:i + 2], 16) * factor) for i in (1, 3, 5)]
        return "rgb(" + ", ".join(map(str, rgb)) + ")"
    return value


def astronomy_red_color(value: str, factor: float) -> str:
    """Match ACP brightness followed by Astronomy Red's multiply blend.

    ACP's fullscreen red multiply overlay zeroes the green/blue channels *after*
    applying brightness to its nav. Native GTK cannot use that global browser
    overlay, so convert only the preview's already-validated colour tokens.
    Preserve alpha to keep the existing rounded translucent panels intact.
    """
    shaded = night_darken_color(value, factor)
    match = _RGB_COLOR.fullmatch(shaded)
    if match:
        red = match.group(1)
        alpha = match.group(4)
        return (f"rgba({red}, 0, 0, {alpha})" if alpha is not None
                else f"rgb({red}, 0, 0)")
    return shaded


def presentation_palette(palette: dict, presentation: dict | None) -> dict:
    if not valid_palette(palette):
        raise ValueError("Invalid colour palette")
    if not valid_presentation(presentation) or not presentation["astronomy_night"]:
        return dict(palette)
    return {key: astronomy_red_color(color, presentation["night_brightness"])
            for key, color in palette.items()}


def choose_navigation_font(pango_context) -> str:
    """Prefer ACP's Atkinson face when available to GTK/Pango."""
    try:
        families = {family.get_name().casefold()
                    for family in pango_context.list_families()}
    except (AttributeError, TypeError):
        families = set()
    return ("Atkinson Hyperlegible"
            if "atkinson hyperlegible" in families else "DejaVu Sans")


def apply_navigation_labels(Pango, labels, family: str, size_px: float):
    """Set real Pango font attributes, independent of GTK theme button CSS.

    ACP loads Atkinson Hyperlegible as a Chromium web font; GTK can use it
    only if the same face is also installed as a system font.
    """
    size = max(8, min(50, round(size_px)))
    for label in labels:
        attrs = Pango.AttrList()
        attrs.insert(Pango.attr_family_new(family))
        attrs.insert(Pango.attr_weight_new(Pango.Weight.BOLD))
        attrs.insert(Pango.attr_size_new_absolute(size * Pango.SCALE))
        label.set_attributes(attrs)


def presentation_css(presentation: dict, scale: float) -> bytes:
    if not valid_presentation(presentation) or scale is None:
        return b""
    font = max(8, min(50, round(presentation["font_size"] * scale)))
    return f".acp-b3-nav {{ font-size: {font}px; }}".encode("ascii")


ACP_NAV_SVG_PATHS = {
    "Audio": (
        '<path d="M4 9.25h3.25L11.5 5.5v13l-4.25-3.75H4z"/>'
        '<path d="M15 8.25a5 5 0 0 1 0 7.5"/>'
        '<path d="M17.75 5.5a8.75 8.75 0 0 1 0 13"/>'
    ),
    "Settings": (
        '<path d="M9.6 3.35 10.2 2h3.6l.6 1.35 1.55.65 '
        '1.38-.53 2.55 2.55-.53 1.38L20 8.95l1.35.6v3.6'
        'L20 13.75l-.65 1.55.53 1.38-2.55 2.55-1.38-.53'
        '-1.55.65-.6 1.35h-3.6l-.6-1.35-1.55-.65-1.38.53'
        '-2.55-2.55.53-1.38L4 13.75l-1.35-.6v-3.6L4 8.95'
        'l.65-1.55-.53-1.38 2.55-2.55 1.38.53z"/>'
        '<circle cx="12" cy="11.35" r="3.1"/>'
    ),
}


def svg_colour(value: str) -> str:
    """Convert validated RGB components to safe CSS hexadecimal."""
    m = _RGB_COLOR.fullmatch(value)
    if m:
        channels = [int(m.group(i)) for i in (1, 2, 3)]
        if all(0 <= ch <= 255 for ch in channels):
            return "#" + "".join(f"{ch:02x}" for ch in channels)
    return "#f7f9ff"


def utility_svg(label: str, color: str) -> bytes:
    """ACP's original SVG paths, without a Cairo foreign-struct callback."""
    if label not in ACP_NAV_SVG_PATHS:
        raise ValueError("Unknown ACP utility icon")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="none" stroke="' + svg_colour(color) + '" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        + ACP_NAV_SVG_PATHS[label] + '</svg>'
    ).encode("ascii")


def load_utility_pixbuf(GdkPixbuf, label: str, color: str):
    """GTK pixbuf SVG loader; never invokes the PyGObject Cairo converter."""
    loader = GdkPixbuf.PixbufLoader.new_with_type("svg")
    loader.write(utility_svg(label, color))
    loader.close()
    pixbuf = loader.get_pixbuf()
    if pixbuf is None:
        raise ValueError("SVG pixbuf produced no image")
    return pixbuf


def refresh_utility_images(Gtk, GdkPixbuf, images, color: str) -> bool:
    """Always show usable stock icons if an optional SVG loader is missing."""
    exact = True
    for label, image in images:
        try:
            image.set_from_pixbuf(load_utility_pixbuf(GdkPixbuf, label, color))
        except Exception:
            exact = False
            fallback = ("audio-volume-high-symbolic" if label == "Audio"
                        else "emblem-system-symbolic")
            image.set_from_icon_name(fallback, Gtk.IconSize.DIALOG)
    return exact


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


def drawer_motion_margins(fraction: float, height: int, bottom: int) -> tuple[int, int]:
    """Return safe panel inset and animated handle inset.

    The panel must NEVER leave the screen via a negative layer-shell
    margin: on the Pi's labwc compositor it failed to become visible again.
    A GTK3 Revealer animates the panel contents inside the fixed surface.
    """
    fraction = max(0.0, min(1.0, float(fraction)))
    return bottom, round((height + bottom + OPEN_INDICATOR_EXTRA_GAP) * fraction)


def drawer_motion_ease(fraction: float) -> float:
    t = max(0.0, min(1.0, float(fraction)))
    return 1.0 - (1.0 - t) ** 3


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


def present(Gtk, Gdk, GLib, Gio, LayerShell, bus, b2, *, seconds: int,
            route_pages: bool = False, curtain_handoff: bool = False,
            theme_from_acp: bool = False, presentation_from_acp: bool = False,
            animate_drawer: bool = False):
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
        background-image: none;
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
        font-weight: 700;
        padding: 0 7px;
      }
      .acp-b3-nav label {
        font-family: "Atkinson Hyperlegible", "DejaVu Sans", sans-serif;
        font-weight: 700;
      }
      .acp-b3-nav:hover { background-color: rgba(247,249,255,0.18); }
      /* Suppress stock GTK grey pressed backgrounds in Astronomy Red. */
      .acp-b3-nav:active, .acp-b3-nav:checked,
      .acp-b3-nav:hover:active {
        background-image: none;
        background-color: rgba(255,255,255,0.08);
        color: #f7f9ff;
        border-color: rgba(255,255,255,0.15);
        box-shadow: none;
      }
      .acp-b3-active, .acp-b3-active:hover,
      .acp-b3-active:active, .acp-b3-active:checked {
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
      .acp-b3-curtain { background-color: #09111f; }
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
    # Visible-window GTK paint surface owns rounded frame and dark panel.
    shell = Gtk.EventBox()
    shell.set_visible_window(True)
    shell.get_style_context().add_class("acp-b3-drawer")
    workspaces = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
    utilities = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    utilities.get_style_context().add_class("acp-b3-utility-group")
    body.pack_start(workspaces, True, True, 0)
    body.pack_start(utilities, False, False, 0)
    shell.add(body)
    revealer = None
    if animate_drawer:
        # Keep Wayland layer surface in its accepted, visible bottom position.
        # Gtk.Revealer moves/clips its child, avoiding an off-screen layer
        # surface that labwc never remapped during the first B3 motion trial.
        shell.set_size_request(drawer_width, DRAWER_HEIGHT)
        revealer = Gtk.Revealer()
        revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        revealer.set_transition_duration(DRAWER_MOTION_MS)
        revealer.set_halign(Gtk.Align.FILL)
        revealer.set_valign(Gtk.Align.END)
        revealer.set_reveal_child(False)
        revealer.add(shell)
        drawer.add(revealer)
    else:
        drawer.add(shell)

    # Opt-in cover belongs to GTK's overlay layer, above both toplevels.
    # Map it BEFORE compositor focus changes, then release after an ACP paint
    # acknowledgment; the accepted B3 drawer remains unchanged by default.
    curtain = None
    if curtain_handoff:
        curtain = make_layer_window(
            Gtk, LayerShell, width, height,
            namespace="acp-b3-handoff-curtain-test", bottom=0)
        LayerShell.set_anchor(curtain, LayerShell.Edge.TOP, True)
        LayerShell.set_anchor(curtain, LayerShell.Edge.LEFT, True)
        LayerShell.set_anchor(curtain, LayerShell.Edge.RIGHT, True)
        cover = Gtk.EventBox()
        cover.set_size_request(width, height)
        cover.get_style_context().add_class("acp-b3-curtain")
        curtain.add(cover)

    state = {"drawer": False, "keyboard": None, "stopping": False,
             "handoff_pending": False, "curtain_active": False}
    last_palette = {"value": None}
    last_presentation = {"value": None}
    layout = {"height": DRAWER_HEIGHT, "bottom": DRAWER_BOTTOM_MARGIN}
    motion = {"fraction": 0.0, "epoch": 0}
    workspace_buttons = []
    utility_buttons = []
    utility_images = []
    workspace_labels = []
    from gi.repository import GdkPixbuf, Pango
    nav_font = {"family": None}
    icon_loader_warned = {"value": False}

    def update_styles():
        palette = last_palette["value"]
        metrics = last_presentation["value"] if presentation_from_acp else None
        scale = presentation_scale(metrics, width, height) if metrics else None
        applied = presentation_palette(palette, metrics if scale else None) if palette else None
        provider.load_from_data(css
            + (palette_css(applied) if applied else b"")
            + (presentation_css(metrics, scale) if scale else b""))
        font_px = metrics["font_size"] * scale if scale else 16
        if workspace_labels:
            if nav_font["family"] is None:
                nav_font["family"] = choose_navigation_font(
                    workspace_labels[0].get_pango_context())
                print("ACP B3: navigation label font: " + nav_font["family"]
                      + (" Bold (ACP font available locally)"
                         if nav_font["family"] == "Atkinson Hyperlegible"
                         else " Bold (Atkinson web font unavailable to GTK)"),
                      flush=True)
            apply_navigation_labels(Pango, workspace_labels,
                                    nav_font["family"], font_px)
        icon_color = applied["button_text"] if applied else "rgb(247,249,255)"
        exact = refresh_utility_images(Gtk, GdkPixbuf, utility_images, icon_color)
        if not exact and not icon_loader_warned["value"]:
            icon_loader_warned["value"] = True
            print("ACP B3: SVG pixbuf unavailable; using GTK symbolic icons", flush=True)

    def refresh_palette():
        snapshot = fetch_theme_palette()
        if snapshot == last_palette["value"]:
            return True
        last_palette["value"] = snapshot
        update_styles()
        print("ACP B3: navigation theme " +
              ("synced from Chromium" if snapshot else "default Classic Dark fallback"),
              flush=True)
        return True

    def place_drawer_motion(fraction):
        motion["fraction"] = max(0.0, min(1.0, fraction))
        panel_bottom, handle_bottom = drawer_motion_margins(
            motion["fraction"], layout["height"], layout["bottom"])
        # All panel motion belongs to Gtk.Revealer, never the Wayland surface.
        LayerShell.set_margin(drawer, LayerShell.Edge.BOTTOM, panel_bottom)
        LayerShell.set_margin(indicator, LayerShell.Edge.BOTTOM, handle_bottom)

    def refresh_presentation():
        snapshot = fetch_acp_presentation()
        if snapshot == last_presentation["value"]:
            return True
        last_presentation["value"] = snapshot
        scale = presentation_scale(snapshot, width, height) if snapshot else None
        if scale is None:
            layout.update(height=DRAWER_HEIGHT, bottom=DRAWER_BOTTOM_MARGIN)
            drawer.set_size_request(drawer_width, DRAWER_HEIGHT)
            LayerShell.set_margin(drawer, LayerShell.Edge.BOTTOM, DRAWER_BOTTOM_MARGIN)
            if animate_drawer:
                shell.set_size_request(drawer_width, DRAWER_HEIGHT)
            body.set_border_width(6)
            workspaces.set_spacing(5)
            utilities.set_spacing(4)
            for button in workspace_buttons:
                button.set_size_request(76, 56)
            for button in utility_buttons:
                button.set_size_request(56, 56)
            print("ACP B3: presentation unavailable/mismatched; using tested geometry", flush=True)
        else:
            px = lambda name: round(snapshot[name] * scale)
            layout.update(height=px("drawer_height"), bottom=px("drawer_bottom"))
            drawer.set_size_request(px("drawer_width"), layout["height"])
            LayerShell.set_margin(drawer, LayerShell.Edge.BOTTOM, layout["bottom"])
            if animate_drawer:
                shell.set_size_request(px("drawer_width"), layout["height"])
            body.set_border_width(px("drawer_padding"))
            workspaces.set_spacing(px("workspace_gap"))
            utilities.set_spacing(px("utility_gap"))
            for button in workspace_buttons:
                button.set_size_request(76, px("button_height"))
            for button in utility_buttons:
                button.set_size_request(px("utility_size"), px("button_height"))
            print(f"ACP B3: presentation {px('drawer_width')}x{layout['height']}px "
                  f"at bottom {layout['bottom']}px; Astronomy night "
                  f"{'on' if snapshot['astronomy_night'] else 'off'}; "
                  f"brightness {snapshot['night_brightness']:.2f}", flush=True)
        if animate_drawer:
            place_drawer_motion(motion["fraction"])
        elif state["drawer"]:
            LayerShell.set_margin(indicator, LayerShell.Edge.BOTTOM,
                                  layout["height"] + layout["bottom"]
                                  + OPEN_INDICATOR_EXTRA_GAP)
        update_styles()
        return True
    def stop_once(reason):
        if state["stopping"]:
            return False
        state["stopping"] = True
        print(f"ACP B3: {reason}", flush=True)
        if Gtk.main_level() > 0:
            Gtk.main_quit()
        return False

    def set_drawer_open(opened: bool, *, immediate: bool = False):
        # Each new request invalidates older ticks, including on OSK/focus.
        state["drawer"] = opened
        motion["epoch"] += 1
        if not animate_drawer or immediate:
            motion["fraction"] = float(opened)
            if animate_drawer:
                place_drawer_motion(motion["fraction"])
                # OSK and focus handoff must always win immediately.
                revealer.set_transition_duration(0)
                if opened:
                    drawer.show_all()
                revealer.set_reveal_child(opened)
                if not opened:
                    drawer.hide()
                revealer.set_transition_duration(DRAWER_MOTION_MS)
            else:
                LayerShell.set_margin(indicator, LayerShell.Edge.BOTTOM,
                    (layout["height"] + layout["bottom"] + OPEN_INDICATOR_EXTRA_GAP)
                    if opened else 0)
                if opened:
                    drawer.show_all()
                else:
                    drawer.hide()
            return

        target, start, epoch = float(opened), motion["fraction"], motion["epoch"]
        # Gtk.Revealer owns the actual panel slide. The indicator alone
        # changes positive layer-shell margins, matching its bottom position.
        revealer.set_transition_duration(max(1, round(
            DRAWER_MOTION_MS * abs(target - start))))
        if opened:
            place_drawer_motion(start)
            drawer.show_all()
        revealer.set_reveal_child(opened)
        if abs(start - target) < 0.001:
            place_drawer_motion(target)
            if not opened:
                drawer.hide()
            return
        began = time.monotonic()
        # Reversals take a proportionate part of the 180ms full travel.
        duration = DRAWER_MOTION_MS / 1000.0 * abs(target - start)

        def motion_tick():
            if state["stopping"] or motion["epoch"] != epoch:
                return False
            phase = min(1.0, (time.monotonic() - began) / duration)
            place_drawer_motion(start + (target - start) * drawer_motion_ease(phase))
            if phase >= 1.0:
                if not opened:
                    drawer.hide()
                return False
            return True

        GLib.timeout_add(DRAWER_MOTION_TICK_MS, motion_tick)

    def toggle_drawer(_widget, _event):
        if not overlay_allowed(state["keyboard"]):
            return True
        set_drawer_open(not state["drawer"])
        print("ACP B3: preview drawer " +
              ("opened" if state["drawer"] else "closed"), flush=True)
        return True

    def fade_and_finish(reason):
        """Release a temporary Wayland cover, never leave a locked overlay."""
        if curtain is None:
            stop_once(reason)
            return
        steps = {"remaining": CURTAIN_FADE_STEPS}

        def fade_step():
            if state["stopping"]:
                return False
            steps["remaining"] -= 1
            cover.set_opacity(max(0.0, steps["remaining"] / CURTAIN_FADE_STEPS))
            if steps["remaining"] <= 0:
                curtain.hide()
                stop_once(reason)
                return False
            return True

        GLib.timeout_add(CURTAIN_FADE_STEP_MS, fade_step)

    def start_curtained_focus(name, sequence):
        """Keep the old Chromium framebuffer covered until repaint opportunity."""
        if curtain is None:
            return False
        # Never composite two navigation drawers over each other during fade.
        # ACP will own its drawer once the Chromium destination is focused.
        set_drawer_open(False, immediate=True)
        indicator.hide()
        state["curtain_active"] = True
        cover.set_opacity(1.0)
        curtain.show_all()
        print("ACP B3: native drawer and handle hidden; curtain mapped before focus", flush=True)

        def focus_then_watch():
            if state["stopping"]:
                return False
            if not b2.focus_acp():
                curtain.hide()
                state["curtain_active"] = False
                state["handoff_pending"] = False
                if overlay_allowed(state["keyboard"]):
                    indicator.show_all()
                    set_drawer_open(True)
                print("ACP B3: focus failed; native navigation restored", flush=True)
                return False
            painted_deadline = time.monotonic() + CURTAIN_PAINT_WAIT_SECONDS
            print("ACP B3: ACP focused behind curtain; awaiting painted ack", flush=True)

            def wait_for_paint():
                if state["stopping"]:
                    return False
                phase = handoff_status(sequence)
                if phase == "painted":
                    print("ACP B3: Chromium painted acknowledgment; fading curtain", flush=True)
                    fade_and_finish(f"{name} painted and focused; closing native preview")
                    return False
                if time.monotonic() >= painted_deadline or phase == "expired":
                    print(f"ACP B3: paint acknowledgment missing ({phase}); releasing curtain safely", flush=True)
                    fade_and_finish(f"{name} focus completed; painted state not confirmed")
                    return False
                return True

            GLib.timeout_add(HANDOFF_POLL_MS, wait_for_paint)
            return False

        # Give the newly mapped Wayland overlay a compositor frame before
        # promoting Chromium; no change to ACP's own transition duration.
        GLib.timeout_add(CURTAIN_FOCUS_SETTLE_MS, focus_then_watch)
        return True

    def select_destination(_button, name):
        if not overlay_allowed(state["keyboard"]) or state["handoff_pending"]:
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
        elif route_pages:
            print(f"ACP B3: {name} selected; preparing ACP navigation in background", flush=True)
            sequence = request_page_handoff(name)
            if sequence is not None:
                state["handoff_pending"] = True
                deadline = time.monotonic() + PREPARE_TIMEOUT_SECONDS

                def await_prepared():
                    if state["stopping"]:
                        return False
                    if not overlay_allowed(state["keyboard"]):
                        # The OSK keeps navigation hidden, even during handoff.
                        if time.monotonic() >= deadline:
                            state["handoff_pending"] = False
                            print("ACP B3: keyboard still open; handoff cancelled", flush=True)
                            return False
                        return True
                    phase = handoff_status(sequence)
                    if phase == "ready":
                        print(f"ACP B3: {name} ready in Chromium; focusing ACP", flush=True)
                        if curtain_handoff:
                            start_curtained_focus(name, sequence)
                        else:
                            state["handoff_pending"] = False
                            if b2.focus_acp():
                                stop_once(f"{name} prepared and focused; closing native preview")
                            else:
                                print("ACP B3: focus failed; native preview remains available", flush=True)
                        return False
                    if phase == "expired" or time.monotonic() >= deadline:
                        state["handoff_pending"] = False
                        print(f"ACP B3: {name} not ready ({phase}); staying in Plexamp", flush=True)
                        return False
                    return True

                GLib.timeout_add(HANDOFF_POLL_MS, await_prepared)
        else:
            print(f"ACP B3: {name} selected (preview only; route not connected)", flush=True)

    for item in WORKSPACE_ITEMS:
        button = Gtk.Button()
        label = Gtk.Label(label=item)
        label.set_halign(Gtk.Align.CENTER)
        label.set_valign(Gtk.Align.CENTER)
        button.add(label)
        workspace_labels.append(label)
        button.set_size_request(76, 56)
        button.get_style_context().add_class("acp-b3-nav")
        if item == "Plexamp":
            button.get_style_context().add_class("acp-b3-active")
        button.connect("clicked", select_destination, item)
        # ACP's CSS flex row keeps each button at its content/natural width,
        # and assigns the remaining free width to the *workspace group*.
        # Expanding each individual GTK button was stretching all five across
        # the drawer and leaving no separation before the utilities.
        workspaces.pack_start(button, False, False, 0)
        workspace_buttons.append(button)

    for label in UTILITY_ITEMS:
        button = Gtk.Button()
        button.set_tooltip_text(label)
        button.get_accessible().set_name(label)
        button.set_size_request(56, 56)
        button.get_style_context().add_class("acp-b3-nav")
        button.get_style_context().add_class("acp-b3-utility")
        glyph = Gtk.Image()
        glyph.set_size_request(24, 24)
        glyph.set_halign(Gtk.Align.CENTER)
        glyph.set_valign(Gtk.Align.CENTER)
        button.add(glyph)
        utility_images.append((label, glyph))
        button.connect("clicked", select_destination, label)
        utilities.pack_start(button, False, False, 0)
        utility_buttons.append(button)

    # B3 still lacks actual ACP page selection; keep a small explicit escape.
    escape = Gtk.Button(label="ACP")
    escape.set_tooltip_text("Development only: focus existing ACP Chromium")
    escape.set_size_request(50, 56)
    escape.get_style_context().add_class("acp-b3-nav")
    escape.get_style_context().add_class("acp-b3-developer")
    escape.connect("clicked", select_destination, "ACP")
    utilities.pack_start(escape, False, False, 0)

    # Initialise icons even if no ACP palette has arrived.
    update_styles()

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
            set_drawer_open(False, immediate=True)
            indicator.hide()
            print("ACP B3: keyboard visible/unavailable: hiding ALL native navigation", flush=True)
        else:
            if not state["curtain_active"]:
                indicator.show_all()
                print("ACP B3: keyboard hidden: indicator restored", flush=True)
        return True

    # The panel layer surface stays at its normal positive inset. Only
    # its GTK child is initially concealed, and the indicator starts low.
    if animate_drawer:
        place_drawer_motion(0.0)

    # Verify Squeekboard before either Wayland window is displayed.
    if not overlay_allowed(keyboard_visible(bus, Gio, GLib)):
        raise RuntimeError("Cannot start preview while Squeekboard is visible or its state is unavailable")
    refresh_keyboard()
    GLib.timeout_add(POLL_MS, refresh_keyboard)
    if theme_from_acp:
        refresh_palette()
        GLib.timeout_add(PALETTE_REFRESH_MS, refresh_palette)
    if presentation_from_acp:
        refresh_presentation()
        GLib.timeout_add(PALETTE_REFRESH_MS, refresh_presentation)
    GLib.timeout_add_seconds(seconds, lambda: stop_once("time limit reached; closing preview"))
    print(f"ACP B3: preview for at most {seconds}s, indicator {bar_width}x{bar_height}px;"
          " tap opens drawer; "
          + ("ACP page handoff ENABLED" if route_pages else "routes preview-only except Plexamp/ACP")
          + ("; native drawer glide ENABLED" if animate_drawer else "; instant drawer")
          + "; hides when Squeekboard opens.", flush=True)
    try:
        Gtk.main()
    except KeyboardInterrupt:
        print("ACP B3: Ctrl+C received", flush=True)
    finally:
        if curtain is not None:
            curtain.destroy()
        drawer.destroy()
        indicator.destroy()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check-osk", action="store_true",
                        help="read Squeekboard visibility without showing any window")
    action.add_argument("--show", action="store_true",
                        help="start temporary drawer preview over existing native Plexamp")
    parser.add_argument("--route-pages", action="store_true",
                        help="explicitly enable loopback ACP page handoff (default preview-only)")
    parser.add_argument("--curtain-handoff", action="store_true",
                        help="experimental GTK cover until Chromium confirms painted focus")
    parser.add_argument("--theme-from-acp", action="store_true",
                        help="opt in to read-only live ACP drawer colour synchronisation")
    parser.add_argument("--presentation-from-acp", action="store_true",
                        help="experimental geometry/night brightness from ACP, requires --theme-from-acp")
    parser.add_argument("--animate-drawer", action="store_true",
                        help="opt-in 180ms GTK child slide + indicator glide; default unchanged")
    parser.add_argument("--seconds", type=int, default=90,
                        help="auto-close after 1-300 seconds (default 90)")
    args = parser.parse_args()
    if not 1 <= args.seconds <= MAX_SECONDS:
        parser.error("--seconds must be between 1 and 300")
    if args.curtain_handoff and (not args.route_pages or not args.show):
        parser.error("--curtain-handoff requires --show and --route-pages")
    if args.theme_from_acp and not args.show:
        parser.error("--theme-from-acp requires --show")
    if args.presentation_from_acp and not (args.theme_from_acp and args.show):
        parser.error("--presentation-from-acp requires --show and --theme-from-acp")
    if args.animate_drawer and not args.show:
        parser.error("--animate-drawer requires --show")
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
        present(Gtk, Gdk, GLib, Gio, LayerShell, bus, b2, seconds=args.seconds,
                route_pages=args.route_pages, curtain_handoff=args.curtain_handoff,
                theme_from_acp=args.theme_from_acp,
                presentation_from_acp=args.presentation_from_acp,
                animate_drawer=args.animate_drawer)
        return 0
    except (RuntimeError, OSError, b2.ProbeError) as exc:
        print("ACP B3: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
