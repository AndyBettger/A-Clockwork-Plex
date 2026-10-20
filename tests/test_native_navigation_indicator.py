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
