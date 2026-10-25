"""Phase B3 opt-in native overlay drawer: keyboard visibility and safe preview."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts/try-native-navigation-drawer.py"
spec = importlib.util.spec_from_file_location("acp_b3_drawer_test", SRC)
assert spec and spec.loader
drawer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drawer)


class NativeNavigationDrawerTests(unittest.TestCase):
    def test_help_and_invalid_timeout_do_not_touch_display(self):
        result = subprocess.run([sys.executable, str(SRC), "--help"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--check-osk", result.stdout)
        self.assertIn("--show", result.stdout)
        bad = subprocess.run([sys.executable, str(SRC), "--show", "--seconds", "301"],
                             capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("between 1 and 300", bad.stderr)

    def test_visibility_property_is_readonly_and_fail_closed(self):
        bus = mock.Mock()
        gio = mock.Mock()
        glib = mock.Mock()
        reply = bus.call_sync.return_value
        boolean_value = reply.get_child_value.return_value.get_variant.return_value
        boolean_value.get_type_string.return_value = "b"
        boolean_value.get_boolean.return_value = False
        self.assertIs(drawer.keyboard_visible(bus, gio, glib), False)
        call = bus.call_sync.call_args
        self.assertEqual(call.args[:4], (
            "sm.puri.OSK0", "/sm/puri/OSK0",
            "org.freedesktop.DBus.Properties", "Get"))
        glib.Variant.assert_called_once_with(
            "(ss)", ("sm.puri.OSK0", "Visible"))
        glib.VariantType.new.assert_called_once_with("(v)")
        self.assertIs(call.args[6], gio.DBusCallFlags.NO_AUTO_START)
        self.assertEqual(call.args[7], drawer.DBUS_TIMEOUT_MS)
        reply.get_child_value.assert_called_with(0)
        boolean_value.get_boolean.return_value = True
        self.assertIs(drawer.keyboard_visible(bus, gio, glib), True)
        boolean_value.get_type_string.return_value = "s"
        issues = []
        self.assertIsNone(drawer.keyboard_visible(bus, gio, glib, diagnostic=issues))
        self.assertIn("not a Boolean", issues[0])
        bus.call_sync.return_value = None
        issues = []
        self.assertIsNone(drawer.keyboard_visible(bus, gio, glib, diagnostic=issues))
        self.assertIn("no response", issues[0])
        bus.call_sync.side_effect = RuntimeError("service not available")
        issues = []
        self.assertIsNone(drawer.keyboard_visible(bus, gio, glib, diagnostic=issues))
        self.assertIn("service not available", issues[0])
        self.assertTrue(drawer.overlay_allowed(False))
        self.assertFalse(drawer.overlay_allowed(True))
        self.assertFalse(drawer.overlay_allowed(None))

    def test_dev_preview_never_controls_keyboard_or_chromium_navigation(self):
        source = SRC.read_text(encoding="utf-8")
        for required in (
            '"org.freedesktop.DBus.Properties", "Get"',
            'GLib.Variant("(ss)", (OSK_INTERFACE, "Visible"))',
            'GLib.VariantType.new("(v)")',
            "LayerShell.Layer.OVERLAY", "LayerShell.KeyboardMode.NONE",
            "LayerShell.set_exclusive_zone(win, 0)",
            "indicator.hide()", "drawer.hide()", "GLib.timeout_add(POLL_MS, refresh_keyboard)",
            "GLib.timeout_add_seconds(seconds", 'b2.focus_acp()',
            "overlay_allowed(keyboard_visible(bus, Gio, GLib))",
        ):
            self.assertIn(required, source)
        for forbidden in (
            "SetVisible", "systemctl enable", "systemctl start", "flatpak kill",
            "pkill", "sudo apt", "window.location", "wlrctl toplevel minimize",
            "os.system", "subprocess.Popen",
        ):
            self.assertNotIn(forbidden, source)

    def test_native_drawer_glide_is_opt_in_and_keyboard_handoff_interrupts(self):
        # The drawer's Wayland surface must NEVER start off-screen.
        self.assertEqual(drawer.drawer_motion_margins(0, 69, 8), (8, 0))
        self.assertEqual(drawer.drawer_motion_margins(1, 69, 8), (8, 81))
        self.assertEqual(drawer.drawer_motion_margins(.5, 69, 8), (8, 40))
        self.assertEqual(drawer.drawer_motion_margins(-5, 69, 8), (8, 0))
        self.assertEqual(drawer.drawer_motion_margins(5, 69, 8), (8, 81))
        self.assertEqual(drawer.drawer_motion_ease(0), 0)
        self.assertEqual(drawer.drawer_motion_ease(1), 1)
        self.assertGreater(drawer.drawer_motion_ease(.5), .5)
        src = SRC.read_text(encoding="utf-8")
        self.assertIn('parser.add_argument("--animate-drawer"', src)
        self.assertIn('parser.error("--animate-drawer requires --show")', src)
        self.assertIn("animate_drawer: bool = False", src)
        self.assertIn('motion["epoch"] += 1', src)
        self.assertIn('motion["epoch"] != epoch', src)
        self.assertIn("GLib.timeout_add(DRAWER_MOTION_TICK_MS, motion_tick)", src)
        self.assertIn("set_drawer_open(False, immediate=True)", src)
        self.assertIn("place_drawer_motion(0.0)", src)
        self.assertIn("DRAWER_MOTION_MS = 180", src)
        self.assertIn("revealer = Gtk.Revealer()", src)
        self.assertIn("Gtk.RevealerTransitionType.SLIDE_UP", src)
        self.assertIn("revealer.set_reveal_child(opened)", src)
        self.assertIn("revealer.set_transition_duration(0)", src)
        self.assertIn("revealer.set_valign(Gtk.Align.END)", src)
        self.assertIn("drawer.add(revealer)", src)
        self.assertIn("drawer.add(shell)", src)  # unchanged instant path
        self.assertNotIn("round(-height + travel * fraction)", src)
        self.assertIn("shell.set_size_request(px(\"drawer_width\"), layout[\"height\"])", src)
        # Any generated bottom margin for panel remains at its safe inset.
        for height in (40, 69, 220):
            for bottom in (0, 8, 60):
                for fraction in (-1, 0, .2, .5, 1, 2):
                    panel, handle = drawer.drawer_motion_margins(fraction, height, bottom)
                    self.assertEqual(panel, bottom)
                    self.assertGreaterEqual(handle, 0)
                    self.assertLessEqual(handle, height + bottom + drawer.OPEN_INDICATOR_EXTRA_GAP)

    def test_acp_drawer_geometry_and_groups(self):
        self.assertEqual(drawer.drawer_width_for_screen(800, 480), 786)
        self.assertEqual(drawer.drawer_width_for_screen(1280, 720), 940)
        self.assertEqual(drawer.DRAWER_HEIGHT, 70)
        self.assertEqual(drawer.DRAWER_BOTTOM_MARGIN, 8)
        self.assertEqual(drawer.indicator_margin(False), 0)
        self.assertEqual(drawer.indicator_margin(True), 82)
        self.assertEqual(drawer.WORKSPACE_ITEMS, (
            "Home", "Weather", "News", "AirPlay", "Plexamp"))
        self.assertEqual(drawer.UTILITY_ITEMS, ("Audio", "Settings"))
        src = SRC.read_text(encoding="utf-8")
        self.assertNotIn('Gtk.Label(label="A Clockwork Plex', src)
        self.assertIn("set_drawer_open(not state[\"drawer\"])", src)
        self.assertIn("LayerShell.set_margin(indicator, LayerShell.Edge.BOTTOM", src)
        self.assertIn("set_drawer_open(False, immediate=True)\n            indicator.hide()", src)
        self.assertIn("acp-b3-active", src)
        self.assertIn("acp-b3-utility-group", src)
        self.assertIn('escape.set_tooltip_text("Development only:', src)

    def test_local_page_routing_requires_opt_in(self):
        with mock.patch.object(drawer.urllib.request, "urlopen") as send:
            reply = send.return_value.__enter__.return_value
            reply.status = 200
            reply.read.return_value = b'{"ok":true,"sequence":7}'
            self.assertEqual(drawer.request_page_handoff("Weather"), 7)
            req = send.call_args.args[0]
            self.assertEqual(req.full_url, drawer.NAVIGATION_URL)
            self.assertEqual(req.get_method(), "POST")
            self.assertIn(b'"destination": "weather"', req.data)
            self.assertFalse(drawer.request_page_handoff("Plexamp"))
        source = SRC.read_text()
        self.assertIn('parser.add_argument("--route-pages"', source)
        self.assertIn("route_pages=args.route_pages", source)
        self.assertIn("sequence = request_page_handoff(name)", source)
        self.assertIn("GLib.timeout_add(HANDOFF_POLL_MS, await_prepared)", source)
        self.assertIn('if phase == "ready":', source)

    def test_curtain_requires_explicit_route_mode_and_releases_on_timeout(self):
        invalid = [
            ["--show", "--curtain-handoff"],
            ["--check-osk", "--route-pages", "--curtain-handoff"],
        ]
        for options in invalid:
            result = subprocess.run(
                [sys.executable, str(SRC), *options],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("requires --show and --route-pages", result.stderr)
        source = SRC.read_text(encoding="utf-8")
        for required in (
            "curtain_handoff: bool = False",
            "LayerShell.set_anchor(curtain, LayerShell.Edge.TOP, True)",
            "curtain.show_all()",
            "GLib.timeout_add(CURTAIN_FOCUS_SETTLE_MS, focus_then_watch)",
            'if phase == "painted":',
            "CURTAIN_PAINT_WAIT_SECONDS = 2.5",
            'curtain.hide()',
            "curtain.destroy()",
        ):
            self.assertIn(required, source)
        self.assertIn("LayerShell.KeyboardMode.NONE", source)
        self.assertNotIn("subprocess.Popen", source)

    def test_native_drawer_is_hidden_before_curtain_and_restored_on_focus_failure(self):
        source = SRC.read_text(encoding="utf-8")
        start = source.index("    def start_curtained_focus(name, sequence):")
        end = source.index("    def select_destination(_button, name):", start)
        focus = source[start:end]
        self.assertLess(focus.index("set_drawer_open(False, immediate=True)"),
                        focus.index("curtain.show_all()"))
        self.assertLess(focus.index("indicator.hide()"), focus.index("curtain.show_all()"))
        self.assertIn('state["curtain_active"] = True', focus)
        self.assertIn('state["curtain_active"] = False', focus)
        self.assertIn("indicator.show_all()\n                    set_drawer_open(True)", focus)
        self.assertIn('if not state["curtain_active"]:', source)
        self.assertIn("cover.set_opacity(1.0)", focus)
        self.assertIn("cover.set_opacity(max(0.0,", source)
        self.assertNotIn("curtain.set_opacity(", source)

    def test_status_probe_requires_ready_phase(self):
        with mock.patch.object(drawer.urllib.request, "urlopen") as send:
            reply = send.return_value.__enter__.return_value
            reply.status = 200
            reply.read.return_value = b'{"ok":true,"state":"ready"}'
            self.assertEqual(drawer.handoff_status(7), "ready")
            req = send.call_args.args[0]
            self.assertIn("sequence=7", req.full_url)
            self.assertEqual(req.get_header("X-acp-b3-source"), "native-gtk-b3-dev")
            reply.read.return_value = b'{"ok":true,"state":"painted"}'
            self.assertEqual(drawer.handoff_status(7), "painted")
            reply.read.return_value = b'{"ok":true,"state":"bogus"}'
            self.assertEqual(drawer.handoff_status(7), "unavailable")

    def test_opt_in_computed_palette_cannot_inject_css(self):
        colors = {key: "rgb(10, 20, 30)" for key in drawer.PALETTE_NAMES}
        self.assertTrue(drawer.valid_palette(colors))
        css = drawer.palette_css(colors)
        self.assertIn(b"background-color: rgb(10, 20, 30)", css)
        self.assertNotIn(b"@import", css)
        for invalid in (
            {**colors, "active_text": "red; } * { opacity:0;"},
            {**colors, "handle_color": "url(http://example.com)"},
            {**colors, "drawer_border": None},
            {**colors, "unexpected": "rgb(1,2,3)"},
        ):
            self.assertFalse(drawer.valid_palette(invalid))
            with self.assertRaises(ValueError):
                drawer.palette_css(invalid)
        with mock.patch.object(drawer.urllib.request, "urlopen") as send:
            reply = send.return_value.__enter__.return_value
            reply.status = 200
            reply.read.return_value = __import__("json").dumps(
                {"ok": True, "palette": colors},
            ).encode()
            self.assertEqual(drawer.fetch_theme_palette(), colors)
            self.assertEqual(send.call_args.args[0].get_method(), "GET")

    def test_palette_opt_in_and_existing_navigation_untouched(self):
        src = SRC.read_text(encoding="utf-8")
        self.assertIn('parser.add_argument("--theme-from-acp"', src)
        self.assertIn('if theme_from_acp:', src)
        self.assertIn('GLib.timeout_add(PALETTE_REFRESH_MS, refresh_palette)', src)
        self.assertIn('theme_from_acp=args.theme_from_acp', src)
        bad = subprocess.run([sys.executable, str(SRC), "--check-osk",
                              "--theme-from-acp"], capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("--theme-from-acp requires --show", bad.stderr)
        self.assertIn('curtain_handoff: bool = False,', src)
        self.assertIn('Squeekboard', src)

    def test_presentation_is_explicit_opt_in_and_fails_closed_on_zoom(self):
        source = SRC.read_text(encoding="utf-8")
        self.assertIn('parser.add_argument("--presentation-from-acp"', source)
        self.assertIn('presentation_from_acp=args.presentation_from_acp', source)
        for args in (["--check-osk", "--presentation-from-acp"],
                     ["--show", "--presentation-from-acp"]):
            result = subprocess.run([sys.executable, str(SRC), *args],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("requires --show and --theme-from-acp", result.stderr)
        values = {
            "viewport_width": 1280, "viewport_height": 720,
            "drawer_width": 940, "drawer_height": 76,
            "drawer_bottom": 8, "drawer_padding": 8,
            "workspace_gap": 8, "utility_gap": 6,
            "button_height": 62, "utility_size": 62,
            "font_size": 21.8, "night_brightness": 0.18,
            "astronomy_night": True,
        }
        self.assertTrue(drawer.valid_presentation(values))
        self.assertEqual(drawer.presentation_scale(values, 1280, 720), 1.0)
        self.assertEqual(drawer.presentation_scale(values, 1920, 1080), 1.5)
        self.assertIsNone(drawer.presentation_scale(values, 1280, 800))
        self.assertIsNone(drawer.presentation_scale(values, 9000, 5000))
        self.assertFalse(drawer.valid_presentation({**values, "font_size": True}))
        self.assertFalse(drawer.valid_presentation({**values, "astronomy_night": False}))
        self.assertIn(b"font-size: 22px", drawer.presentation_css(values, 1.0))

    def test_astronomy_night_brightness_preblends_rgb_not_alpha(self):
        self.assertEqual(drawer.night_darken_color("rgb(255, 64, 64)", 0.18),
                         "rgb(46, 12, 12)")
        self.assertEqual(drawer.night_darken_color(
            "rgba(96, 0, 0, 0.62)", 0.18), "rgba(17, 0, 0, 0.62)")
        self.assertEqual(drawer.night_darken_color("#FF4040", 0.5),
                         "rgb(128, 32, 32)")
        colors = {name: "rgba(255, 64, 64, 0.88)"
                  for name in drawer.PALETTE_NAMES}
        metrics = {
            "viewport_width": 1280, "viewport_height": 720,
            "drawer_width": 940, "drawer_height": 76,
            "drawer_bottom": 8, "drawer_padding": 8,
            "workspace_gap": 8, "utility_gap": 6,
            "button_height": 62, "utility_size": 62,
            "font_size": 21.8, "night_brightness": 0.2,
            "astronomy_night": True,
        }
        shaded = drawer.presentation_palette(colors, metrics)
        self.assertEqual(shaded["handle_color"], "rgba(51, 0, 0, 0.88)")
        self.assertEqual(colors["handle_color"], "rgba(255, 64, 64, 0.88)")
        self.assertEqual(drawer.presentation_palette(
            colors, {**metrics, "astronomy_night": False,
                     "night_brightness": 1}), colors)
        self.assertIn("LayerShell.set_margin(drawer, LayerShell.Edge.BOTTOM",
                      SRC.read_text())

    def test_native_compact_workspaces_match_acp_css_spacing(self):
        src = SRC.read_text(encoding="utf-8")
        nav_css = (ROOT / "app/static/css/nav.css").read_text()
        self.assertIn("body.pack_start(workspaces, True, True, 0)", src)
        self.assertIn("workspaces.pack_start(button, False, False, 0)", src)
        self.assertNotIn("workspaces.pack_start(button, True, True, 0)", src)
        self.assertIn("set_spacing(px(\"workspace_gap\"))", src)
        self.assertIn("set_spacing(px(\"utility_gap\"))", src)
        self.assertIn("font-weight: 700;", src)
        self.assertIn('font-family: "Atkinson Hyperlegible", "DejaVu Sans", sans-serif;', src)
        self.assertIn("flex: 1 1 auto;", nav_css)
        self.assertIn(".nav-workspaces {", nav_css)
        self.assertIn("gap: 5px;", nav_css)

    def test_native_navigation_font_uses_pango_bold_and_local_font_fallback(self):
        src = SRC.read_text(encoding="utf-8")
        typography = (ROOT / "app/static/css/typography.css").read_text()
        self.assertIn('--ui-font: "Atkinson Hyperlegible"', typography)
        self.assertIn("label = Gtk.Label(label=item)", src)
        self.assertIn("workspace_labels.append(label)", src)
        self.assertIn("from gi.repository import GdkPixbuf, Pango", src)
        self.assertIn("apply_navigation_labels(Pango, workspace_labels,", src)

        pango_context = mock.Mock()
        pango_context.list_families.return_value = [
            mock.Mock(get_name=lambda: "DejaVu Sans"),
            mock.Mock(get_name=lambda: "Atkinson Hyperlegible"),
        ]
        self.assertEqual(drawer.choose_navigation_font(pango_context),
                         "Atkinson Hyperlegible")
        pango_context.list_families.return_value = [
            mock.Mock(get_name=lambda: "DejaVu Sans"),
        ]
        self.assertEqual(drawer.choose_navigation_font(pango_context),
                         "DejaVu Sans")
        pango_context.list_families.side_effect = AttributeError("No font map")
        self.assertEqual(drawer.choose_navigation_font(pango_context),
                         "DejaVu Sans")

        Pango = mock.Mock()
        Pango.Weight.BOLD = 700
        Pango.SCALE = 1024
        Pango.AttrList.side_effect = lambda: mock.Mock()
        label = mock.Mock()
        drawer.apply_navigation_labels(Pango, [label], "DejaVu Sans", 18.72)
        Pango.attr_family_new.assert_called_with("DejaVu Sans")
        Pango.attr_weight_new.assert_called_with(700)
        Pango.attr_size_new_absolute.assert_called_with(19 * 1024)
        label.set_attributes.assert_called_once()
        drawer.apply_navigation_labels(Pango, [label], "DejaVu Sans", 500)
        Pango.attr_size_new_absolute.assert_called_with(50 * 1024)

    def test_gtk_utilities_use_acp_svg_pixbuf_not_cairo_foreign_converter(self):
        source = SRC.read_text(encoding="utf-8")
        nav_template = (ROOT / "app/templates/_nav.html").read_text()
        self.assertIn("for label in UTILITY_ITEMS:", source)
        self.assertIn("glyph = Gtk.Image()", source)
        self.assertIn("utility_images.append((label, glyph))", source)
        self.assertIn("button.get_accessible().set_name(label)", source)
        self.assertNotIn("Gtk.DrawingArea()", source)
        self.assertNotIn('glyph.connect("draw"', source)
        self.assertIn('GdkPixbuf.PixbufLoader.new_with_type("svg")', source)
        self.assertIn('viewBox="0 0 24 24"', nav_template)
        for label in ("Audio", "Settings"):
            result = drawer.utility_svg(label, "rgb(255, 64, 64)")
            self.assertIn(b'viewBox="0 0 24 24"', result)
            self.assertIn(b'stroke="#ff4040"', result)
            self.assertIn(b'<path', result)
        self.assertIn(b'<circle', drawer.utility_svg("Settings", "rgb(255,0,0)"))
        with self.assertRaises(ValueError):
            drawer.utility_svg("Unknown", "rgb(255,0,0)")
        self.assertEqual(drawer.svg_colour("rgba(255, 92, 92, 0.8)"),
                         "#ff5c5c")
        self.assertEqual(drawer.svg_colour('red; } window { opacity:0'), "#f7f9ff")

    def test_utility_icons_pixbuf_loader_and_safe_fallback(self):
        Gtk = mock.Mock()
        GdkPixbuf = mock.Mock()
        loader = GdkPixbuf.PixbufLoader.new_with_type.return_value
        fake_icon = mock.Mock()
        loader.get_pixbuf.return_value = fake_icon
        img_audio, img_settings = mock.Mock(), mock.Mock()
        icons = [("Audio", img_audio), ("Settings", img_settings)]
        self.assertTrue(drawer.refresh_utility_images(
            Gtk, GdkPixbuf, icons, "rgb(255, 64, 64)"))
        img_audio.set_from_pixbuf.assert_called_once_with(fake_icon)
        img_settings.set_from_pixbuf.assert_called_once_with(fake_icon)
        self.assertEqual(loader.write.call_count, 2)
        loader.write.assert_any_call(drawer.utility_svg("Audio", "rgb(255, 64, 64)"))
        loader.write.assert_any_call(drawer.utility_svg("Settings", "rgb(255, 64, 64)"))
        loader.close.assert_called()
        loader.write.side_effect = RuntimeError("No SVG pixbuf module")
        self.assertFalse(drawer.refresh_utility_images(
            Gtk, GdkPixbuf, icons, "rgb(255, 64, 64)"))
        img_audio.set_from_icon_name.assert_called_once_with(
            "audio-volume-high-symbolic", Gtk.IconSize.DIALOG)
        img_settings.set_from_icon_name.assert_called_once_with(
            "emblem-system-symbolic", Gtk.IconSize.DIALOG)

    def test_dynamic_palette_owns_gtk_hover_focus_and_pressed_colours(self):
        # Confirm the dynamic ACP palette overrides the static GTK :hover
        # selector (which previously turned red navigation buttons grey).
        colors = {key: "rgb(15, 0, 0)" for key in drawer.PALETTE_NAMES}
        colors.update(button_background="rgba(96, 0, 0, 0.62)",
                      button_border="rgba(255, 72, 72, 0.24)",
                      button_text="rgb(255, 92, 92)",
                      active_background="rgb(255, 64, 64)",
                      active_text="rgb(26, 0, 0)")
        generated = drawer.palette_css(colors).decode("ascii")
        for selector in (
            ".acp-b3-nav:hover", ".acp-b3-nav:focus",
            ".acp-b3-nav:hover:focus", ".acp-b3-nav:backdrop",
            ".acp-b3-nav:active", ".acp-b3-nav:checked",
            ".acp-b3-nav:hover:active", ".acp-b3-nav:focus:active",
            ".acp-b3-active:hover", ".acp-b3-active:focus",
            ".acp-b3-active:active", ".acp-b3-active:checked",
            ".acp-b3-active:hover:active",
        ):
            self.assertIn(selector, generated)
        # The effective red button background and text must occur inside
        # the :hover selector's own rules, not only in the normal rule.
        hover_rule = generated.split(".acp-b3-nav:backdrop {", 1)[1].split("}", 1)[0]
        self.assertIn("background-color: rgba(96, 0, 0, 0.62);", hover_rule)
        self.assertIn("border-color: rgba(255, 72, 72, 0.24);", hover_rule)
        self.assertIn("color: rgb(255, 92, 92);", hover_rule)
        self.assertIn("background-image: none;", hover_rule)
        active_rule = generated.split(".acp-b3-active:focus:active {", 1)[1].split("}", 1)[0]
        self.assertIn("background-color: rgb(255, 64, 64);", active_rule)
        self.assertIn("color: rgb(26, 0, 0);", active_rule)
        source = SRC.read_text(encoding="utf-8")
        self.assertIn("provider.load_from_data(css", source)
        self.assertIn("palette_css(applied)", source)

    def test_drawer_has_window_backed_frame_and_theme_safe_pressed_state(self):
        source = SRC.read_text(encoding="utf-8")
        self.assertIn("shell = Gtk.EventBox()", source)
        self.assertIn("shell.set_visible_window(True)", source)
        self.assertIn('shell.get_style_context().add_class("acp-b3-drawer")', source)
        self.assertIn("shell.add(body)", source)
        self.assertIn("drawer.add(shell)", source)
        self.assertNotIn('body.get_style_context().add_class("acp-b3-drawer")', source)
        self.assertIn(".acp-b3-nav:active, .acp-b3-nav:checked", source)
        self.assertIn("background-image: none;", source)
        self.assertIn("background-color: {value['button_background']}", source)
        colors = {key: "rgb(15, 0, 0)" for key in drawer.PALETTE_NAMES}
        css = drawer.palette_css(colors)
        self.assertIn(b".acp-b3-nav:active", css)
        self.assertIn(b"background-color: rgb(15, 0, 0)", css)
        self.assertIn(b".acp-b3-active:active", css)


    def test_astronomy_red_multiply_matches_bright_and_dimmed_acp_screenshots(self):
        # ACP's multiply overlay eliminates the blue/green channels *after*
        # the nav brightness filter. Pure RGBA pre-darkening alone went pink.
        self.assertEqual(drawer.astronomy_red_color("rgb(255, 64, 64)", .8),
                         "rgb(204, 0, 0)")
        self.assertEqual(drawer.astronomy_red_color("rgb(255, 64, 64)", .53),
                         "rgb(135, 0, 0)")
        self.assertEqual(drawer.astronomy_red_color("rgba(96, 0, 0, 0.62)", .8),
                         "rgba(77, 0, 0, 0.62)")
        self.assertEqual(drawer.astronomy_red_color("rgba(255, 64, 64, 0.88)", .53),
                         "rgba(135, 0, 0, 0.88)")
        self.assertEqual(drawer.night_darken_color("rgb(255, 64, 64)", .8),
                         "rgb(204, 51, 51)")
        # This is opt-in: default accepted colour snapshot remains untouched.
        pal = {key: "rgb(255, 64, 64)" for key in drawer.PALETTE_NAMES}
        self.assertEqual(drawer.presentation_palette(pal, None), pal)

    def test_routes_are_explicitly_preview_only(self):
        self.assertEqual(drawer.NAV_ITEMS, (
            "Home", "Weather", "News", "AirPlay", "Plexamp",
            "Audio", "Settings", "ACP",
        ))
        source = SRC.read_text(encoding="utf-8")
        self.assertIn("route not connected", source)
        self.assertIn('if name == "Plexamp":', source)
        self.assertIn('elif name == "ACP":', source)
        self.assertLessEqual(drawer.MAX_SECONDS, 300)
        self.assertGreaterEqual(drawer.POLL_MS, 200)


if __name__ == "__main__":
    unittest.main()
