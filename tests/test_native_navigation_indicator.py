"""Phase B2 native Plexamp navigation indicator: safe opt-in labwc overlay tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts/try-native-navigation-indicator.py"
spec = importlib.util.spec_from_file_location("acp_native_nav_indicator_tests", SRC)
assert spec and spec.loader
indicator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(indicator)


class NativeNavigationIndicatorTests(unittest.TestCase):
    def test_command_is_help_safe_without_gtk_installed(self):
        result = subprocess.run([sys.executable, str(SRC), "--help"],
                                check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--show", result.stdout)
        self.assertIn("--check", result.stdout)
        self.assertIn("--tap-focus-acp", result.stdout)

    def test_development_probe_is_bounded_and_never_enabled_at_boot(self):
        self.assertEqual(indicator.DEFAULT_TIMEOUT, 120)
        self.assertLessEqual(indicator.MAX_TIMEOUT, 300)
        source = SRC.read_text(encoding="utf-8")
        for required in (
            "GtkLayerShell", "LayerShell.Layer.OVERLAY",
            "LayerShell.KeyboardMode.NONE", "LayerShell.set_exclusive_zone(window, 0)",
            "LayerShell.Edge.BOTTOM", "GLib.timeout_add_seconds",
        ):
            self.assertIn(required, source)
        for forbidden in (
            "systemctl enable", "systemctl start", "flatpak kill",
            "wlrctl toplevel minimize", "pkill", "sudo apt",
        ):
            self.assertNotIn(forbidden, source)

    def test_indicator_matches_acp_edge_geometry_and_avoids_media_controls(self):
        # Physical screenshot showed the centred white bar over transport controls.
        self.assertEqual(indicator.PROBE_WIDTH, 190)
        self.assertEqual(indicator.PROBE_HEIGHT, 16)
        self.assertEqual(indicator.BAR_WIDTH, 140)
        self.assertEqual(indicator.BAR_HEIGHT, 5)
        self.assertEqual(indicator.BOTTOM_MARGIN, 0)
        self.assertEqual(indicator.DEFAULT_EDGE_PADDING, 4)
        source = SRC.read_text(encoding="utf-8")
        self.assertIn("layout.pack_end(handle, False, False, 0)", source)
        self.assertIn("handle.set_margin_bottom(edge_padding)", source)
        self.assertIn("handle.set_halign(Gtk.Align.CENTER)", source)
        self.assertIn("handle.set_valign(Gtk.Align.CENTER)", source)
        self.assertIn("handle.set_opacity(0.82)", source)
        self.assertIn("background-color: transparent", source)
        self.assertIn("background-color: rgba(247, 249, 255, 0.74)", source)
        self.assertIn("border-radius: 999px", source)
        self.assertIn("box-shadow: 0 0 16px rgba(255, 255, 255, 0.18)", source)
        # Reuse the accepted browser shell's exact 140x5 dimensions and theme.
        acp_css = (ROOT / "app/static/css/nav.css").read_text(encoding="utf-8")
        self.assertIn(".nav-handle span {", acp_css)
        self.assertIn("width: 140px;", acp_css)
        self.assertIn("height: 5px;", acp_css)
        self.assertIn("background: rgba(247, 249, 255, 0.74)", acp_css)

    def test_responsive_size_and_hover_follow_acp_css(self):
        # The Pi screenshot corresponds to ACP's compact @media rule: 128x4,
        # not the full-screen 140x5 inherited by the initial GTK prototype.
        self.assertEqual(indicator.bar_size_for_screen(1280, 720), (140, 5))
        self.assertEqual(indicator.bar_size_for_screen(860, 720), (128, 4))
        self.assertEqual(indicator.bar_size_for_screen(1280, 680), (128, 4))
        self.assertEqual(indicator.bar_size_for_screen(800, 480), (128, 4))
        acp_css = (ROOT / "app/static/css/nav.css").read_text(encoding="utf-8")
        self.assertIn("@media (max-height: 680px), (max-width: 860px)", acp_css)
        self.assertIn("width: 128px;", acp_css)
        self.assertIn("height: 4px;", acp_css)
        source = SRC.read_text(encoding="utf-8")
        self.assertIn("handle.set_size_request(bar_width, bar_height)", source)
        self.assertIn('eventbox.connect("enter-notify-event", on_enter)', source)
        self.assertIn('eventbox.connect("leave-notify-event", on_leave)', source)
        self.assertIn('background-color: rgba(247, 249, 255, 0.94)', source)
        self.assertIn('handle.set_opacity(1.0)', source)

    def test_modern_monitor_geometry_and_primary_fallback(self):
        primary = mock.Mock()
        primary.get_geometry.return_value = mock.Mock(width=800, height=480)
        fallback = mock.Mock()
        fallback.get_geometry.return_value = mock.Mock(width=1280, height=720)
        display = mock.Mock()
        display.get_primary_monitor.return_value = primary
        display.get_monitor.return_value = fallback
        self.assertEqual(indicator.desktop_monitor_size(display), (800, 480))
        display.get_monitor.assert_not_called()
        display.get_primary_monitor.return_value = None
        self.assertEqual(indicator.desktop_monitor_size(display), (1280, 720))
        display.get_monitor.assert_called_once_with(0)
        display.get_monitor.return_value = None
        with self.assertRaisesRegex(indicator.ProbeError, "No active desktop monitor"):
            indicator.desktop_monitor_size(display)
        source = SRC.read_text(encoding="utf-8")
        self.assertNotIn("screen.get_width()", source)
        self.assertNotIn("screen.get_height()", source)
        self.assertIn("desktop_monitor_size(window.get_display())", source)

    def test_gtk_shutdown_only_requests_quit_inside_running_main_loop(self):
        # Tapping ACP previously called Gtk.main_quit, then destroy called it
        # again after the loop had returned, producing a Gtk-CRITICAL warning.
        source = SRC.read_text(encoding="utf-8")
        self.assertIn("if Gtk.main_level() > 0:", source)
        self.assertIn("if not destroyed:", source)
        self.assertIn("except KeyboardInterrupt:", source)
        self.assertNotIn('window.connect("destroy", Gtk.main_quit)', source)
        self.assertNotIn("GLib.timeout_add_seconds(seconds, lambda: (Gtk.main_quit()", source)

    def test_bad_padding_exits_without_starting_gtk(self):
        result = subprocess.run(
            [sys.executable, str(SRC), "--show", "--edge-padding", "11"],
            capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--edge-padding must be between 0 and 10", result.stderr)

    def test_missing_runtime_socket_fails_closed(self):
        with mock.patch.object(indicator.Path, "is_dir", return_value=False):
            with self.assertRaisesRegex(indicator.ProbeError, "No user desktop runtime"):
                indicator.desktop_environment({}, 1000)
        with mock.patch.object(indicator.Path, "is_dir", return_value=True), \
             mock.patch.object(indicator.Path, "is_socket", return_value=False):
            with self.assertRaisesRegex(indicator.ProbeError, "No active Wayland socket"):
                indicator.desktop_environment({}, 1000)

    def test_wrong_user_runtime_and_root_are_rejected(self):
        with self.assertRaisesRegex(indicator.ProbeError, "without sudo"):
            indicator.desktop_environment({}, 1000, root=True)
        with mock.patch.object(indicator.Path, "is_dir", return_value=True):
            with self.assertRaisesRegex(indicator.ProbeError, "Unexpected XDG_RUNTIME_DIR"):
                indicator.desktop_environment({"XDG_RUNTIME_DIR": "/run/user/999"}, 1000)
            with self.assertRaisesRegex(indicator.ProbeError, "local session socket"):
                indicator.desktop_environment({"WAYLAND_DISPLAY": "../../other/wayland"}, 1000)

    def test_valid_user_environment_preserves_other_values(self):
        with mock.patch.object(indicator.Path, "is_dir", return_value=True), \
             mock.patch.object(indicator.Path, "is_socket", return_value=True):
            result = indicator.desktop_environment({"HOME": "/home/pi"}, 1000)
        self.assertEqual(result["XDG_RUNTIME_DIR"], "/run/user/1000")
        self.assertEqual(result["WAYLAND_DISPLAY"], "wayland-0")
        self.assertEqual(result["GDK_BACKEND"], "wayland")
        self.assertEqual(result["HOME"], "/home/pi")

    def test_touch_focus_only_calls_existing_scoped_window_helper(self):
        successful = subprocess.CompletedProcess([], 0, "Compositor reports target focused: YES\n", "")
        with mock.patch.object(indicator.subprocess, "run", return_value=successful) as invoke:
            self.assertTrue(indicator.focus_acp())
        self.assertEqual(invoke.call_args.args[0], [
            "/usr/bin/python3", str(ROOT / "scripts/switch-native-plexamp-window.py"), "--to-acp",
        ])
        self.assertTrue(invoke.call_args.kwargs["capture_output"])
        self.assertTrue(invoke.call_args.kwargs["check"] is False)

    def test_failed_compositor_focus_does_not_claim_success(self):
        failed = subprocess.CompletedProcess([], 1, "", "Not found\n")
        with mock.patch.object(indicator.subprocess, "run", return_value=failed):
            self.assertFalse(indicator.focus_acp())


if __name__ == "__main__":
    unittest.main()
