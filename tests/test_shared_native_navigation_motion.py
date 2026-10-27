"""B4.3 opt-in single-surface handle + drawer motion (no display required)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts/try-native-navigation-drawer.py"
spec = importlib.util.spec_from_file_location("b43_joined_navigation", SRC)
assert spec and spec.loader
nav = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nav)


class SharedNativeNavigationMotionTests(unittest.TestCase):
    def test_joined_closed_click_area_is_only_centred_handle(self):
        self.assertEqual(
            nav.joined_motion_input_rects(839, 113, 128, 24, 0),
            [(355, 89, 128, 24)])
        self.assertEqual(
            nav.joined_motion_input_rects(839, 113, 128, 24, -500),
            [(355, 89, 128, 24)])

    def test_joined_open_and_partial_input_areas_cannot_overlap(self):
        # No transparent full-screen click blocker; two directly adjacent
        # rectangles, from the same GTK allocation. Within the revealed
        # rectangle, GTK handles the gap/panel widget hit-testing.
        for amount in (1, 15, 44, 89, 500):
            with self.subTest(amount=amount):
                rects = nav.joined_motion_input_rects(839, 113, 128, 24, amount)
                self.assertEqual(len(rects), 2)
                handle, drawer = rects
                self.assertEqual(handle[1] + handle[3], drawer[1])
                self.assertEqual(drawer[1] + drawer[3], 113)
                self.assertEqual(drawer[2], 839)
                self.assertGreaterEqual(handle[1], 0)
                self.assertLessEqual(drawer[3], 89)

    def test_joined_mode_requires_opt_in_navigation_and_animation(self):
        for args in (
            ["--show", "--joined-motion"],
            ["--show", "--observe-foreground", "--joined-motion"],
            ["--show", "--navigate-shared", "--joined-motion"],
        ):
            with self.subTest(args=args):
                p = subprocess.run([sys.executable, str(SRC), *args],
                                   capture_output=True, text=True)
                self.assertNotEqual(p.returncode, 0)
                # The CLI must reject unsupported combinations before
                # importing GTK or opening an overlay window.
                self.assertIn("error:", p.stderr)

    def test_joined_visuals_share_a_single_gtk_layer_window(self):
        src = SRC.read_text(encoding="utf-8")
        self.assertIn('namespace=("acp-b43-joined-navigation-test" if joined_motion', src)
        self.assertIn("drawer = (indicator if joined_motion else make_layer_window(", src)
        self.assertIn("joined_stack.pack_start(hitbox, False, False, 0)", src)
        self.assertIn("joined_stack.pack_start(revealer, False, False, 0)", src)
        self.assertIn("joined_stack.set_valign(Gtk.Align.END)", src)
        self.assertIn("joined_reveal_content.pack_start(gap, False, False, 0)", src)
        self.assertIn("joined_reveal_content.pack_start(shell, False, False, 0)", src)
        self.assertIn("joined_reveal_content.pack_start(joined_bottom_padding", src)
        self.assertIn("if drawer is not indicator:", src)
        # Existing separate Wayland surfaces remain for accepted B3/B4.1/B4.2.
        self.assertIn('namespace="acp-b3-drawer-test"', src)
        self.assertIn('else "acp-b3-indicator-test"), bottom=0)', src)

    def test_transparent_input_is_restricted_and_fail_closed(self):
        src = SRC.read_text(encoding="utf-8")
        self.assertIn("def refresh_joined_input_region():", src)
        self.assertIn("cairo_module.RectangleInt(*rect)", src)
        self.assertIn("input_shape_combine_region(region, 0, 0)", src)
        self.assertIn("revealer.connect(\"size-allocate\"", src)
        self.assertIn("GLib.idle_add(refresh_joined_input_region)", src)
        self.assertIn("stop_once(f\"joined input mask unavailable", src)
        self.assertIn("if joined_motion:\n            refresh_joined_input_region()", src)
        self.assertIn("GLib.idle_add(refresh_joined_input_region)", src)
        self.assertIn("if joined_motion and not (navigate_shared and animate_drawer)", src)
        self.assertIn('parser.add_argument("--joined-motion"', src)
        self.assertIn("parser.error(\"--joined-motion requires --navigate-shared", src)


if __name__ == "__main__":
    unittest.main()
