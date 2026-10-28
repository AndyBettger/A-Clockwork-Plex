"""B4.3 opt-in single-surface handle + drawer motion (no display required)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
from types import ModuleType
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts/try-native-navigation-drawer.py"
spec = importlib.util.spec_from_file_location("b43_joined_navigation", SRC)
assert spec and spec.loader
nav = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nav)


class SharedNativeNavigationMotionTests(unittest.TestCase):
    def test_cairo_foreign_region_registration_is_required_before_gtk_overlay(self):
        # A pycairo import alone was present on the Pi, but GDK could not
        # marshal cairo.Region until gi.require_foreign("cairo", "Region")
        # and the separate Debian python3-gi-cairo module were available.
        events = []
        fake_gi = ModuleType("gi")
        def register(namespace, symbol):
            events.append((namespace, symbol))
        fake_gi.require_foreign = register
        fake_cairo = ModuleType("cairo")
        class Rect:
            def __init__(self, *args):
                self.coords = args
        class Region:
            def __init__(self, rectangles):
                self.rectangles = rectangles
        fake_cairo.RectangleInt = Rect
        fake_cairo.Region = Region
        with mock.patch.dict(sys.modules, {"gi": fake_gi, "cairo": fake_cairo}):
            self.assertIs(nav.load_joined_cairo_region(), fake_cairo)
        self.assertEqual(events, [("cairo", "Region")])

    def test_missing_cairo_foreign_converter_fails_before_window_is_mapped(self):
        fake_gi = ModuleType("gi")
        def missing(_namespace, _symbol):
            raise ImportError("gi._gi_cairo not installed")
        fake_gi.require_foreign = missing
        fake_cairo = ModuleType("cairo")
        with mock.patch.dict(sys.modules, {"gi": fake_gi, "cairo": fake_cairo}):
            with self.assertRaisesRegex(RuntimeError, "python3-gi-cairo"):
                nav.load_joined_cairo_region()
        src = SRC.read_text(encoding="utf-8")
        self.assertIn("cairo_module = load_joined_cairo_region() if joined_motion else None", src)
        self.assertIn("if not joined_motion or state[\"stopping\"]", src)
        self.assertIn('stop_once(f"joined input mask unavailable', src)

    def test_joined_closed_handle_and_panel_start_offscreen(self):
        self.assertEqual(
            nav.joined_motion_positions(839, 97, 128, 16, 69, 8, 4, 0),
            ((355, 81, 128, 16), (0, 101, 839, 69)))
        self.assertEqual(
            nav.joined_motion_input_rects(839, 97, 128, 16, 69, 8, 4, 0),
            [(355, 81, 128, 16)])

    def test_handle_and_complete_panel_travel_as_one_rigid_group(self):
        # Every frame positions both *whole widgets*. The gap stays exactly
        # 4px, including when half of the panel is below the screen edge.
        previous = None
        for fraction in (0, .25, .5, .75, 1):
            with self.subTest(fraction=fraction):
                handle, panel = nav.joined_motion_positions(
                    839, 97, 128, 16, 69, 8, 4, fraction)
                self.assertEqual(panel[1] - (handle[1] + handle[3]), 4)
                self.assertEqual(panel[3], 69)
                self.assertEqual(handle[2:], (128, 16))
                self.assertEqual(panel[2], 839)
                if previous is not None:
                    previous_handle, previous_panel = previous
                    self.assertEqual(
                        handle[1] - previous_handle[1],
                        panel[1] - previous_panel[1])
                previous = handle, panel
        self.assertEqual(nav.joined_motion_positions(
            839, 97, 128, 16, 69, 8, 4, 1),
            ((355, 0, 128, 16), (0, 20, 839, 69)))

    def test_partial_touch_regions_only_cover_visible_panel_and_handle(self):
        self.assertEqual(
            nav.joined_motion_input_rects(839, 97, 128, 16, 69, 8, 4, .5),
            [(355, 40, 128, 16), (0, 60, 839, 37)])
        self.assertEqual(
            nav.joined_motion_input_rects(839, 97, 128, 16, 69, 8, 4, 1),
            [(355, 0, 128, 16), (0, 20, 839, 69)])
        for fraction in (-5, 0, .05, .4, .95, 1, 20):
            with self.subTest(fraction=fraction):
                regions = nav.joined_motion_input_rects(
                    839, 97, 128, 16, 69, 8, 4, fraction)
                self.assertIn(len(regions), (1, 2))
                self.assertGreaterEqual(regions[0][1], 0)
                if len(regions) == 2:
                    self.assertGreaterEqual(
                        regions[1][1] - (regions[0][1] + 16), 4)
                    self.assertLessEqual(
                        regions[1][1] + regions[1][3], 97)

    def test_joined_mode_requires_opt_in_navigation_and_animation(self):
        for args in (
            ["--show", "--joined-motion"],
            ["--show", "--observe-foreground", "--joined-motion"],
            ["--show", "--navigate-shared", "--joined-motion"],
            ["--show", "--observe-foreground", "--share-chrome",
             "--navigate-shared", "--theme-from-acp",
             "--presentation-from-acp", "--joined-motion"],
        ):
            with self.subTest(args=args):
                p = subprocess.run([sys.executable, str(SRC), *args],
                                   capture_output=True, text=True)
                self.assertNotEqual(p.returncode, 0)
                # The CLI must reject unsupported combinations before
                # importing GTK or opening an overlay window.
                self.assertIn("error:", p.stderr)

    def test_joined_visuals_use_a_clipped_fixed_surface_not_a_revealer(self):
        src = SRC.read_text(encoding="utf-8")
        self.assertIn('namespace=("acp-b43-joined-navigation-test" if joined_motion', src)
        self.assertIn("drawer = (indicator if joined_motion else make_layer_window(", src)
        self.assertIn("joined_canvas = Gtk.Fixed()", src)
        self.assertIn("joined_clip = Gtk.ScrolledWindow()", src)
        self.assertIn("joined_clip.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)", src)
        self.assertIn("joined_clip.set_propagate_natural_height(False)", src)
        self.assertIn("joined_clip.set_min_content_height(joint_height)", src)
        self.assertIn("joined_clip.set_max_content_height(joint_height)", src)
        self.assertIn("joined_clip.set_kinetic_scrolling(False)", src)
        self.assertIn("joined_clip.add(joined_canvas)", src)
        self.assertIn("joined_canvas.put(hitbox, closed_handle[0], closed_handle[1])", src)
        self.assertIn("joined_canvas.put(shell, closed_panel[0], closed_panel[1])", src)
        self.assertIn("joined_canvas.move(hitbox, moving_handle[0], moving_handle[1])", src)
        self.assertIn("joined_canvas.move(shell, moving_panel[0], moving_panel[1])", src)
        self.assertIn("return phase < 1.0", src)
        self.assertIn("place_drawer_motion(fraction)", src)
        self.assertIn("drawer_motion_ease(phase)", src)
        self.assertIn("if drawer is not indicator:", src)
        # The old two-surface Revealer is NOT changed by joined opt-in.
        self.assertIn("elif animate_drawer:", src)
        self.assertIn("Gtk.RevealerTransitionType.SLIDE_UP", src)
        self.assertIn("drawer.add(revealer)", src)
        self.assertIn('namespace="acp-b3-drawer-test"', src)
        self.assertIn('else "acp-b3-indicator-test"), bottom=0)', src)

    def test_closed_panel_must_not_expand_joined_layer_window(self):
        # The previous Gtk.Viewport had no maximum content height. Its
        # Gtk.Fixed child requested room for the offscreen panel, so GTK
        # rendered a permanently open drawer and moved only a few pixels.
        src = SRC.read_text(encoding="utf-8")
        self.assertNotIn("joined_clip = Gtk.Viewport()", src)
        for part in (
            "joined_clip.set_min_content_height(joined_size[\"height\"])",
            "joined_clip.set_max_content_height(joined_size[\"height\"])",
            "joined_clip.set_max_content_width(joined_size[\"width\"])",
            "joined_clip.get_vadjustment().set_value(0)",
            "actual_height = indicator.get_allocated_height()",
            'if abs(actual_height - expected_height) > 2:',
            "joined clipping geometry mismatch",
        ):
            with self.subTest(part=part):
                self.assertIn(part, src)

    def test_transparent_input_is_restricted_and_fail_closed(self):
        src = SRC.read_text(encoding="utf-8")
        self.assertIn("def refresh_joined_input_region():", src)
        self.assertIn('gi.require_foreign("cairo", "Region")', src)
        self.assertIn("python3-gi-cairo", src)
        self.assertIn("cairo_module.RectangleInt(*rect)", src)
        self.assertIn("input_shape_combine_region(region, 0, 0)", src)
        self.assertIn('joined_clip.connect("size-allocate"', src)
        self.assertIn("GLib.idle_add(refresh_joined_input_region)", src)
        self.assertIn("stop_once(f\"joined input mask unavailable", src)
        self.assertIn("if joined_motion:\n            moving_handle, moving_panel", src)
        self.assertIn("GLib.idle_add(refresh_joined_input_region)", src)
        self.assertIn("if joined_motion and not (navigate_shared and animate_drawer)", src)
        self.assertIn('parser.add_argument("--joined-motion"', src)
        self.assertIn("parser.error(\"--joined-motion requires --navigate-shared", src)


if __name__ == "__main__":
    unittest.main()
