"""Safety tests for the Squeekboard read-only preflight."""
from __future__ import annotations
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import subprocess
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts/inspect-squeekboard-theme-layout.py"
spec = importlib.util.spec_from_file_location("acp_squeekboard_theme_inventory", FILE)
assert spec and spec.loader
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


class SqueekboardThemeInventoryTests(unittest.TestCase):
    def test_inventory_commands_are_read_only(self):
        calls = []
        def fake_run(args, **kwargs):
            calls.append((args, kwargs))
            return subprocess.CompletedProcess(args, 0, "test-value\n", "")
        with mock.patch.object(inventory.shutil, "which", return_value="/usr/bin/mock"), \
             mock.patch.object(inventory.subprocess, "run", side_effect=fake_run):
            out = io.StringIO()
            with redirect_stdout(out):
                inventory.inspect()
        expected = {"dpkg-query", "pgrep", "gsettings", "localectl"}
        self.assertEqual({args[0] for args, _ in calls}, expected)
        for args, kwargs in calls:
            self.assertEqual(kwargs["timeout"], 8)
            self.assertFalse(kwargs["check"])
            self.assertTrue(kwargs["capture_output"])
            self.assertIn(args[0], expected)
        self.assertIn("READ ONLY", out.getvalue())
        self.assertIn("NO keyboard processes", out.getvalue())

    def test_does_not_read_layout_or_gtk_css_content(self):
        with mock.patch.object(Path, "is_dir", return_value=False):
            self.assertEqual(inventory.layouts_in(Path("/tmp/missing")), "(directory absent)")
        with mock.patch.object(Path, "exists", return_value=True), \
             mock.patch.object(Path, "is_symlink", return_value=False), \
             mock.patch.object(Path, "is_file", return_value=True):
            self.assertIn("contents not read", inventory.gtk_css_state(Path("/tmp/gtk.css")))

    def test_uses_the_real_vendor_layout_directory(self):
        names = [str(path) for path in inventory.SYSTEM_LAYOUTS]
        self.assertIn("/usr/share/misc/squeekboard/keyboards", names)
        self.assertNotIn("/usr/share/misc/squeekboard/keyboards", [str(inventory.USER_LAYOUT)])

    def test_missing_external_layouts_do_not_imply_no_builtin_layouts(self):
        # The known Squeekboard resource loader embeds fallbacks in its binary.
        text = FILE.read_text(encoding="utf-8")
        self.assertIn("keyboard layouts may be embedded in the binary", text)
        self.assertIn("SQUEEKBOARD_KEYBOARDSDIR", text)
        self.assertIn('probe("dpkg-query", "-L", "squeekboard")', text)

    def test_reports_real_acp_palette_ids(self):
        palettes = inventory.acp_palettes()
        for name in ("classic_dark", "midnight_blue", "amber_terminal",
                     "green_phosphor", "aubergine", "steel_cyan", "crimson_glow"):
            self.assertIn(name, palettes)


if __name__ == "__main__":
    unittest.main()
