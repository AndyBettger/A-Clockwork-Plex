"""Phase B1 Wayland native Plexamp/ACP focus helper contract tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts/switch-native-plexamp-window.py"
spec = importlib.util.spec_from_file_location("acp_native_window_handoff_tests", SRC)
assert spec and spec.loader
handoff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handoff)


def completed(args: tuple[str, ...], *, out: str = "", code: int = 0):
    return subprocess.CompletedProcess(args, code, stdout=out, stderr="")


WINDOWS = (
    "Plexamp: Plexamp\n"
    "chromium: Home - A Clockwork Plex - Chromium\n"
)


class NativeWindowHandoffTests(unittest.TestCase):
    def test_identifies_both_physical_pi_window_ids_without_flatpak_id_confusion(self):
        seen = []
        def fake_call(_env, *args):
            seen.append(args)
            return completed(args, out=WINDOWS)
        with mock.patch.object(handoff, "call_wlrctl", side_effect=fake_call):
            acp, plexamp = handoff.windows({})
        self.assertEqual(acp, "Home - A Clockwork Plex - Chromium")
        self.assertEqual(plexamp, "Plexamp")
        self.assertEqual(seen, [("list",)])

    def test_only_exact_acp_page_titles_and_app_ids_are_trusted(self):
        others = (
            "chromium: Unrelated Browser Tab - Chromium\n"
            "firefox: Home - A Clockwork Plex - Chromium\n"
            "chromium: Arbitrary - A Clockwork Plex - Chromium\n"
            "com.plexamp.Plexamp: Plexamp\n"
            "Plexamp: Plexamp\n"
        )
        with mock.patch.object(handoff, "call_wlrctl",
                               return_value=completed(("list",), out=others)):
            acp, native = handoff.windows({})
        self.assertIsNone(acp)
        self.assertEqual(native, "Plexamp")

    def test_rejects_multiple_matching_acp_or_native_windows(self):
        for listing in (
            WINDOWS + "Plexamp: Plexamp\n",
            WINDOWS + "chromium: Weather - A Clockwork Plex - Chromium\n",
        ):
            with self.subTest(listing=listing), mock.patch.object(
                handoff, "call_wlrctl",
                return_value=completed(("list",), out=listing)
            ):
                with self.assertRaisesRegex(handoff.WindowError, "Multiple"):
                    handoff.windows({})

    def test_focus_to_acp_targets_exact_title_and_never_minimizes(self):
        observed = []
        def invoke(_env, *args):
            observed.append(args)
            if args[0] == "list":
                return completed(args, out=WINDOWS)
            return completed(args)
        with mock.patch.object(handoff, "call_wlrctl", side_effect=invoke):
            handoff.focus({}, "acp")
        self.assertIn(("focus", "app_id:chromium", "title:Home - A Clockwork Plex - Chromium"), observed)
        self.assertIn(("find", "app_id:chromium", "title:Home - A Clockwork Plex - Chromium"), observed)
        self.assertFalse(any(x[0] in ("minimize", "close", "fullscreen", "maximize") for x in observed))

    def test_focus_to_native_uses_actual_pi_wayland_id_not_flatpak_id(self):
        observed = []
        def invoke(_env, *args):
            observed.append(args)
            return completed(args, out=WINDOWS if args[0] == "list" else "")
        with mock.patch.object(handoff, "call_wlrctl", side_effect=invoke):
            handoff.focus({}, "plexamp")
        self.assertIn(("focus", "app_id:Plexamp", "title:Plexamp"), observed)
        self.assertNotIn(("focus", "app_id:com.plexamp.Plexamp", "title:Plexamp"), observed)

    def test_missing_target_does_nothing(self):
        with mock.patch.object(handoff, "call_wlrctl",
                               return_value=completed(("list",), out="Plexamp: Plexamp\n")) as run:
            with self.assertRaisesRegex(handoff.WindowError, "not available"):
                handoff.focus({}, "acp")
        run.assert_called_once()

    def test_failure_is_reported_not_hidden(self):
        def invoke(_env, *args):
            if args[0] == "list":
                return completed(args, out=WINDOWS)
            if args[0] == "focus":
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="compositor refused")
            return completed(args)
        with mock.patch.object(handoff, "call_wlrctl", side_effect=invoke):
            with self.assertRaisesRegex(handoff.WindowError, "compositor refused"):
                handoff.focus({}, "plexamp")

    def test_runtime_env_uses_actual_user_wayland_and_never_sudo(self):
        with mock.patch.object(handoff.os, "geteuid", return_value=0):
            with self.assertRaisesRegex(handoff.WindowError, "never sudo"):
                handoff.runtime_env()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake_runtime = root / "run" / "user" / "1000"
            fake_runtime.mkdir(parents=True)
            # Check validation policy without a live compositor.
            with mock.patch.object(handoff.os, "geteuid", return_value=1000), \
                 mock.patch.object(handoff.os, "getuid", return_value=1000), \
                 mock.patch.object(handoff, "Path", wraps=Path):
                with self.assertRaises(handoff.WindowError):
                    handoff.runtime_env()

    def test_script_read_only_except_exact_focus_request(self):
        script = SRC.read_text(encoding="utf-8")
        self.assertNotIn("flatpak kill", script)
        self.assertNotIn("systemctl stop", script)
        self.assertNotIn("wlrctl toplevel minimize", script)
        self.assertNotIn("subprocess.Popen", script)
        self.assertNotIn("os.kill(", script)


if __name__ == "__main__":
    unittest.main()
