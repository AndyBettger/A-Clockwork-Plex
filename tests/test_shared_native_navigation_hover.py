"""B4.3: ensure pointer hover cannot stick after joined Gtk.Fixed motion."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts/try-native-navigation-drawer.py"
spec = importlib.util.spec_from_file_location("acp_b43_hover", SRC)
assert spec and spec.loader
nav = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nav)


class SharedNativeNavigationHoverTests(unittest.TestCase):
    def test_reset_removes_hover_and_press_but_not_selected_class(self):
        flags = SimpleNamespace(PRELIGHT=1, ACTIVE=2)
        Gtk = SimpleNamespace(StateFlags=flags)
        buttons = [mock.Mock(), mock.Mock(), mock.Mock()]
        for button in buttons:
            button.get_style_context.return_value = mock.Mock()
        nav.reset_joined_hover_state(Gtk, buttons)
        for button in buttons:
            context = button.get_style_context.return_value
            self.assertEqual(context.remove_class.call_args_list, [
                mock.call("acp-b43-hover"),
                mock.call("acp-b43-pressed"),
            ])
            self.assertNotIn(mock.call("acp-b3-active"),
                             context.remove_class.call_args_list)
            button.unset_state_flags.assert_called_once_with(3)

    def test_joined_window_only_uses_explicit_transient_hover_css(self):
        source = SRC.read_text(encoding="utf-8")
        self.assertIn('indicator.get_style_context().add_class("acp-b43-joined")',
                      source)
        self.assertIn("if joined_motion:\n        indicator.get_style_context()", source)
        self.assertIn('clear_joined_button_hover()', source)
        self.assertIn("reset_joined_hover_state(Gtk, (*workspace_buttons, *utility_buttons))",
                      source)
        self.assertIn('button.get_style_context().add_class("acp-b43-hover")',
                      source)
        self.assertIn('button.get_style_context().add_class("acp-b43-pressed")',
                      source)
        self.assertIn('button.connect("enter-notify-event", on_joined_button_enter)',
                      source)
        self.assertIn('button.connect("leave-notify-event", on_joined_button_leave)',
                      source)
        self.assertIn('button.connect("button-release-event", on_joined_button_release)',
                      source)
        self.assertIn('button.connect("button-press-event", on_joined_button_press)',
                      source)
        # Clear on touch/click, page change, all slide frames, and close.
        self.assertIn('def select_destination(_button, name):\n        if joined_motion:\n            clear_joined_button_hover()', source)
        self.assertIn('if observed != state["foreground"]:\n                clear_joined_button_hover()', source)
        self.assertIn('def place_drawer_motion(fraction):\n        motion["fraction"] = max(0.0, min(1.0, fraction))\n        if joined_motion:\n            clear_joined_button_hover()', source)
        self.assertIn('def set_drawer_open(opened: bool, *, immediate: bool = False):\n        if joined_motion and not opened:', source)

    def test_live_palette_preserves_selected_page_over_hover_and_pressed(self):
        colors = {key: "rgba(20, 24, 28, 0.7)" for key in nav.PALETTE_NAMES}
        colors.update(curtain_background="#101b2e",
                      button_background="rgba(0, 10, 20, 0.7)",
                      button_hover_background="rgba(1, 30, 40, 0.8)",
                      button_pressed_background="rgba(2, 50, 60, 0.9)",
                      active_background="rgb(99, 220, 240)",
                      active_text="rgb(0, 20, 30)")
        css = nav.palette_css(colors).decode("ascii")
        start = css.index(".acp-b43-joined .acp-b3-nav,")
        hover = css.index(".acp-b43-joined .acp-b3-nav.acp-b43-hover")
        pressed = css.index(".acp-b43-joined .acp-b3-nav.acp-b43-pressed")
        selected = css.index(".acp-b43-joined .acp-b3-nav.acp-b3-active,")
        self.assertLess(start, hover)
        self.assertLess(hover, pressed)
        self.assertLess(pressed, selected)
        self.assertIn("background-color: rgba(0, 10, 20, 0.7);",
                      css[start:hover])
        self.assertIn("background-color: rgba(1, 30, 40, 0.8);",
                      css[hover:pressed])
        self.assertIn("background-color: rgba(2, 50, 60, 0.9);",
                      css[pressed:selected])
        self.assertIn("background-color: rgb(99, 220, 240);",
                      css[selected:])
        self.assertIn(".acp-b43-joined .acp-b3-nav.acp-b3-active.acp-b43-hover",
                      css[selected:])
        # Accepted B3 two-layer hover rules stay in their original palette.
        self.assertIn(".acp-b3-nav:hover, .acp-b3-nav:hover:focus", css)

    def test_classic_dark_joined_fallback_has_same_state_priority(self):
        source = SRC.read_text(encoding="utf-8")
        base = source.split('    css = b"""', 1)[1].split('    """', 1)[0]
        original = base.index(".acp-b3-nav:hover")
        reset = base.index(".acp-b43-joined .acp-b3-nav,")
        hover = base.index(".acp-b43-joined .acp-b3-nav.acp-b43-hover")
        pressed = base.index(".acp-b43-joined .acp-b3-nav.acp-b43-pressed")
        selected = base.index(".acp-b43-joined .acp-b3-nav.acp-b3-active,")
        self.assertLess(original, reset)
        self.assertLess(reset, hover)
        self.assertLess(hover, pressed)
        self.assertLess(pressed, selected)
        self.assertIn("background-color: #f7f9ff;", base[selected:])


if __name__ == "__main__":
    unittest.main()
