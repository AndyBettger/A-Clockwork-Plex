"""B4.1 single GTK drawer: foreground observation only, no route takeover."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts/try-native-navigation-drawer.py"
FOCUS_HELPER = ROOT / "scripts/switch-native-plexamp-window.py"

spec = importlib.util.spec_from_file_location("acp_b4_read_only_drawer_test", SRC)
assert spec and spec.loader
drawer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drawer)


class SharedNativeNavigationFocusTests(unittest.TestCase):
    def setUp(self):
        self.b1 = drawer.load_window_helper()

    def test_uses_only_existing_b1_exact_app_ids_and_active_find(self):
        self.assertEqual(self.b1.APP_ID, "Plexamp")
        self.assertEqual(self.b1.BROWSER_ID, "chromium")
        self.assertTrue(FOCUS_HELPER.exists())
        history = []

        def invoke(_env, *args):
            history.append(args)
            listing = ("Plexamp: Plexamp\n"
                       "chromium: Weather - A Clockwork Plex - Chromium\n")
            if args == ("list",):
                return subprocess.CompletedProcess(args, 0, listing, "")
            if args[0] == "find":
                is_acp = "app_id:chromium" in args
                return subprocess.CompletedProcess(args, 0 if is_acp else 1, "", "")
            self.fail(f"B4 observation made an unexpected compositor mutation: {args}")

        with mock.patch.object(self.b1, "call_wlrctl", side_effect=invoke):
            observed = drawer.observed_foreground(self.b1, {})
        self.assertEqual(observed, ("acp", "Weather"))
        self.assertEqual(history[0], ("list",))
        self.assertEqual(history[1:], [
            ("find", "app_id:chromium",
             "title:Weather - A Clockwork Plex - Chromium", "state:active"),
            ("find", "app_id:Plexamp", "title:Plexamp", "state:active"),
        ])

    def test_native_plexamp_and_supported_acp_page_titles(self):
        b1 = mock.Mock(BROWSER_ID="chromium", APP_ID="Plexamp",
                       BROWSER_SUFFIX=" - A Clockwork Plex - Chromium",
                       WindowError=self.b1.WindowError)
        b1.windows.return_value = ("Home - A Clockwork Plex - Chromium", "Plexamp")
        b1.matches.side_effect = [False, True]
        self.assertEqual(drawer.observed_foreground(b1, {}), ("plexamp", "Plexamp"))
        cases = {
            "Home": "Home", "Clock": "Home", "Weather": "Weather",
            "News": "News", "AirPlay": "AirPlay", "AirPlay Ready": "AirPlay",
            "Settings": "Settings",
        }
        for title, label in cases.items():
            with self.subTest(title=title):
                b1.windows.return_value = (
                    title + " - A Clockwork Plex - Chromium", "Plexamp")
                b1.matches.side_effect = [True, False]
                self.assertEqual(drawer.observed_foreground(b1, {}), ("acp", label))

    def test_unknown_ambiguous_or_unavailable_window_fails_closed(self):
        b1 = mock.Mock(BROWSER_ID="chromium", APP_ID="Plexamp",
                       BROWSER_SUFFIX=" - A Clockwork Plex - Chromium",
                       WindowError=self.b1.WindowError)
        b1.windows.return_value = ("Home - A Clockwork Plex - Chromium", "Plexamp")
        for states in ([False, False], [True, True]):
            b1.matches.side_effect = list(states)
            self.assertIsNone(drawer.observed_foreground(b1, {}))
        b1.windows.return_value = ("Astronomy - A Clockwork Plex - Chromium", None)
        b1.matches.side_effect = [True]
        self.assertIsNone(drawer.observed_foreground(b1, {}))
        b1.windows.side_effect = self.b1.WindowError("duplicate/spoofed window")
        self.assertIsNone(drawer.observed_foreground(b1, {}))

    def test_option_is_deliberately_separate_from_b3_routing(self):
        for args in (
            ["--observe-foreground"],
            ["--show", "--observe-foreground", "--route-pages"],
            ["--show", "--observe-foreground", "--curtain-handoff", "--route-pages"],
        ):
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, str(SRC), *args],
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("--observe-foreground requires --show", result.stderr)
        help_result = subprocess.run([sys.executable, str(SRC), "--help"],
                                     capture_output=True, text=True)
        self.assertEqual(help_result.returncode, 0)
        self.assertIn("--observe-foreground", help_result.stdout)

    def test_b4_gtk_preview_is_read_only_and_keeps_b3_unchanged(self):
        source = SRC.read_text(encoding="utf-8")
        self.assertIn("B4_FOCUS_POLL_MS = 750", source)
        self.assertIn("ThreadPoolExecutor(max_workers=1", source)
        self.assertIn("GLib.timeout_add(B4_FOCUS_POLL_MS, refresh_foreground)", source)
        self.assertIn("focus_executor.submit(", source)
        self.assertIn("observed_foreground, b1, focus_env", source)
        self.assertIn("future.done()", source)
        self.assertIn("focus_executor.shutdown(wait=False, cancel_futures=True)", source)
        self.assertIn("if observe_foreground:", source)
        self.assertIn("observed only; no navigation action", source)
        self.assertIn('context.add_class("acp-b3-active")', source)
        self.assertIn('context.remove_class("acp-b3-active")', source)
        self.assertIn('if observed is None or not overlay_allowed(state["keyboard"]):',
                      source)
        self.assertIn('not observe_foreground or state["foreground"] is not None', source)
        self.assertIn('if item == "Plexamp" and not observe_foreground:', source)
        # Original B3 layout still scales plain Gtk.Button objects, not label
        # tuples. A B4 label/selection list must never break B3 geometry.
        self.assertEqual(source.count("utility_buttons.append(button)"), 1)
        self.assertIn("utility_button_labels.append(label)", source)
        self.assertIn("zip(utility_button_labels, utility_buttons)", source)
        self.assertIn("for button in utility_buttons:", source)
        self.assertIn('elif route_pages:', source)
        self.assertIn('start_curtained_focus(name, sequence)', source)
        # The B4.1 observer itself does not use or manipulate any window focus.
        observer = source.split("def observed_foreground(", 1)[1].split(
            "\ndef request_page_handoff", 1)[0]
        self.assertNotIn("b1.focus(", observer)
        self.assertNotIn("b2.focus_", observer)


if __name__ == "__main__":
    unittest.main()
