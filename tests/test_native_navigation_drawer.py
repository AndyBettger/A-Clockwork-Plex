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

    def test_visibility_is_readonly_and_fail_closed(self):
        bus = mock.Mock()
        gio = mock.Mock()
        glib = mock.Mock()
        glib.VariantType.new.return_value = "(b)"
        bus.call_sync.return_value.unpack.return_value = (False,)
        self.assertIs(drawer.keyboard_visible(bus, gio, glib), False)
        call = bus.call_sync.call_args
        self.assertEqual(call.args[:4], (
            "sm.puri.OSK0", "/sm/puri/OSK0", "sm.puri.OSK0", "GetVisible"))
        self.assertEqual(call.args[6], drawer.DBUS_TIMEOUT_MS)
        bus.call_sync.return_value.unpack.return_value = (True,)
        self.assertIs(drawer.keyboard_visible(bus, gio, glib), True)
        bus.call_sync.return_value.unpack.return_value = ("false",)
        self.assertIsNone(drawer.keyboard_visible(bus, gio, glib))
        bus.call_sync.side_effect = RuntimeError("missing service")
        self.assertIsNone(drawer.keyboard_visible(bus, gio, glib))
        self.assertTrue(drawer.overlay_allowed(False))
        self.assertFalse(drawer.overlay_allowed(True))
        self.assertFalse(drawer.overlay_allowed(None))

    def test_dev_preview_never_controls_keyboard_or_chromium_navigation(self):
        source = SRC.read_text(encoding="utf-8")
        for required in (
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

    def test_routes_are_explicitly_preview_only(self):
        self.assertEqual(drawer.NAV_ITEMS, (
            "Clock", "Weather", "News", "AirPlay", "Plexamp",
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
