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
        self.assertIn("set_drawer_open(False)\n            indicator.hide()", src)
        self.assertIn("acp-b3-active", src)
        self.assertIn("acp-b3-utility-group", src)
        self.assertIn('escape.set_tooltip_text("Development only:', src)

    def test_local_page_routing_requires_opt_in(self):
        with mock.patch.object(drawer.urllib.request, "urlopen") as send:
            reply = send.return_value.__enter__.return_value
            reply.status = 200
            reply.read.return_value = b'{"ok":true}'
            self.assertTrue(drawer.request_page_handoff("Weather"))
            req = send.call_args.args[0]
            self.assertEqual(req.full_url, drawer.NAVIGATION_URL)
            self.assertEqual(req.get_method(), "POST")
            self.assertIn(b'"destination": "weather"', req.data)
            self.assertFalse(drawer.request_page_handoff("Plexamp"))
        source = SRC.read_text()
        self.assertIn('parser.add_argument("--route-pages"', source)
        self.assertIn("route_pages=args.route_pages", source)
        self.assertIn("if request_page_handoff(name):", source)

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
