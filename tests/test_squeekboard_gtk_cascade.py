"""The GTK3 Squeekboard palette probe is isolated and read-only."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SRC = Path(__file__).resolve().parents[1] / "scripts/inspect-squeekboard-gtk-cascade.py"
MODULE = importlib.util.spec_from_file_location("acp_c2_cascade_probe", SRC)
assert MODULE and MODULE.loader
probe = importlib.util.module_from_spec(MODULE)
MODULE.loader.exec_module(probe)


class ProbeSafety(unittest.TestCase):
    def test_palette_expected_text_colour(self):
        with tempfile.TemporaryDirectory() as temp:
            css = Path(temp) / "gtk.css"
            css.write_text("sq_view {color: #001122;}\n"
                           "sq_view sq_button {background: #010203; color: #Eef7FF;}\n")
            self.assertEqual(probe.expected_colour(css), "#eef7ff")
            css.write_text("sq_view {background: #000000;}")
            with self.assertRaisesRegex(RuntimeError, "text-colour rule"):
                probe.expected_colour(css)

    def test_color_rounding(self):
        class RGB:
            red = 238 / 255
            green = 247 / 255
            blue = 1
        self.assertEqual(probe.format_colour(RGB()), "#eef7ff")

    def test_environment_only_for_child(self):
        with mock.patch.dict("os.environ", {"XDG_CONFIG_HOME": "/home/user/real-gtk"}):
            env = probe.child_environment()
            self.assertEqual(env["GDK_BACKEND"], "wayland")
            self.assertEqual(env["WAYLAND_DISPLAY"], "wayland-0")
            self.assertTrue(env["XDG_CONFIG_HOME"].endswith("themes/midnight_blue"))
            import os
            self.assertEqual(os.environ["XDG_CONFIG_HOME"], "/home/user/real-gtk")

    def test_rejects_symlinks_and_missing_palette(self):
        with tempfile.TemporaryDirectory() as temp:
            original = Path(temp) / "real"
            target = original / "midnight_blue/gtk-3.0/gtk.css"
            target.parent.mkdir(parents=True)
            target.write_text("sq_view sq_button { color: #ffffff; }")
            alias = Path(temp) / "alias"
            alias.mkdir()
            (alias / "midnight_blue").symlink_to(original / "midnight_blue")
            with mock.patch.object(probe, "STAGE", alias):
                with self.assertRaisesRegex(RuntimeError, "unsafe"):
                    probe.palette_path()

    def test_read_only_no_install_or_service_changes(self):
        source = SRC.read_text()
        for forbidden in ("os.kill(", "pkill", "systemctl", "systemd-run", "gsettings set",
                          "subprocess.Popen", "sudo ", "apt install", ".write_text("):
            self.assertNotIn(forbidden, source)
        self.assertIn("--_child", source)
        self.assertIn("Gtk.StyleContext.add_provider_for_screen", source)
        self.assertIn("Gtk.STYLE_PROVIDER_PRIORITY_USER", source)


if __name__ == "__main__":
    unittest.main()
