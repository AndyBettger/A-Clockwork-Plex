"""Isolated, in-process GTK3 style-context hot-reload probe safety contracts."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/probe-squeekboard-gtk-hot-style.py"
SPEC = importlib.util.spec_from_file_location("acp_c3_gtk_hot_context", SOURCE)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class GTKStyleHotReloadProbeTests(unittest.TestCase):
    def test_colour_uses_exact_expected_css_rgb_values(self):
        class RGB:
            red = 0x12 / 255
            green = 0x34 / 255
            blue = 0x56 / 255
        self.assertEqual(probe.colour(RGB()), "#123456")
        self.assertEqual(probe.EXPECTED_BEFORE, "#123456")
        self.assertEqual(probe.EXPECTED_AFTER, "#abcdef")

    def test_probe_reuses_existing_disposable_resource_fixture(self):
        orig = probe.resource_probe()
        self.assertEqual(orig.RESOURCE, "/sm/puri/squeekboard/style.css")
        self.assertIn(b"#123456", orig.A)
        self.assertIn(b"#abcdef", orig.B)
        self.assertTrue(callable(orig.atomic_replace))

    def test_child_refuses_untrusted_overlay_without_importing_gtk(self):
        with tempfile.TemporaryDirectory() as tmp:
            css = Path(tmp) / "style.css"
            css.write_bytes(b"test")
            with mock.patch.dict("os.environ", {"G_RESOURCE_OVERLAYS": "/unsafe/override"}):
                self.assertEqual(probe.child(css), 2)
            self.assertEqual(css.read_bytes(), b"test")

    def test_isolated_environment_changes_only_the_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict("os.environ", {
                "G_RESOURCE_OVERLAYS": "/old/private",
                "XDG_CONFIG_HOME": "/real/user/config",
            }):
                env = probe.isolated_environment(Path(tmp))
                self.assertEqual(
                    env["G_RESOURCE_OVERLAYS"],
                    "/sm/puri/squeekboard=" + tmp
                )
                self.assertEqual(env["GDK_BACKEND"], "wayland")
                self.assertEqual(env["WAYLAND_DISPLAY"], "wayland-0")
                self.assertEqual(env["XDG_CONFIG_HOME"], "/real/user/config")
                import os
                self.assertEqual(os.environ["G_RESOURCE_OVERLAYS"], "/old/private")

    def test_one_style_context_and_same_css_provider_reloaded(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertEqual(text.count("context = Gtk.StyleContext.new()"), 1)
        self.assertEqual(text.count("provider = Gtk.CssProvider.new()"), 1)
        self.assertIn("context.get_color(Gtk.StateFlags.NORMAL)", text)
        self.assertIn("provider.load_from_resource(original.RESOURCE)", text)
        self.assertEqual(text.count("provider.load_from_resource(original.RESOURCE)"), 2)
        self.assertIn("context.invalidate()", text)
        self.assertIn("original.atomic_replace(css, original.B)", text)

    def test_invalidate_only_on_explicit_legacy_branch(self):
        import ast
        module = ast.parse(SOURCE.read_text(encoding="utf-8"))
        child = next(
            node for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name == "child"
        )
        invocations = [
            node for node in ast.walk(child)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "invalidate"
        ]
        self.assertEqual(len(invocations), 1)
        conditional = [
            node for node in ast.walk(child)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "manual_invalidate"
        ]
        self.assertEqual(len(conditional), 1)
        self.assertIn(invocations[0], list(ast.walk(conditional[0])))
        # Conservative existing probe is default; new automatic variant is opt-in.
        self.assertEqual(
            next(arg.value for arg in child.args.kw_defaults
                 if isinstance(arg, ast.Constant)),
            True,
        )

    def test_no_invalidate_variant_passes_flag_only_to_test_child(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertIn('parser.add_argument("--without-invalidate"', text)
        self.assertNotIn('actions.add_argument("--without-invalidate"', text)
        self.assertIn('manual_invalidate=not args.without_invalidate', text)
        self.assertIn('["--without-invalidate"] if args.without_invalidate else []', text)
        self.assertIn('provider.load_from_resource(original.RESOURCE)', text)
        self.assertIn('context.get_color(Gtk.StateFlags.NORMAL)', text)

    def test_combined_cli_flags_are_accepted_without_running_gtk(self):
        """Real argparse + parent branch, but mock subprocess; no GTK/OSK touched."""
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(probe.Path, "home", return_value=Path(tmp)), \
             mock.patch.object(probe.os, "geteuid", return_value=1000), \
             mock.patch.object(probe.sys, "argv", [
                 "probe-squeekboard-gtk-hot-style.py",
                 "--probe", "--without-invalidate",
             ]), \
             mock.patch.object(probe.subprocess, "run",
                               return_value=mock.Mock(
                                   returncode=0, stdout="", stderr=""
                               )) as runner:
            self.assertEqual(probe.main(), 0)
            runner.assert_called_once()
            cmd = runner.call_args.args[0]
            self.assertIn("--_child", cmd)
            self.assertIn("--without-invalidate", cmd)
            self.assertIn("G_RESOURCE_OVERLAYS", runner.call_args.kwargs["env"])

    def test_child_cli_accepts_without_invalidate_as_modifier(self):
        with mock.patch.object(probe.os, "geteuid", return_value=1000), \
             mock.patch.object(probe.sys, "argv", [
                 "probe-squeekboard-gtk-hot-style.py",
                 "--_child", "/not-used/style.css", "--without-invalidate",
             ]), \
             mock.patch.object(probe, "child", return_value=7) as child:
            self.assertEqual(probe.main(), 7)
            child.assert_called_once_with(
                Path("/not-used/style.css"), manual_invalidate=False
            )

    def test_never_restarts_or_rethemes_the_actual_keyboard(self):
        text = SOURCE.read_text(encoding="utf-8")
        for forbidden in (
            "systemctl", "systemd-run", "os.kill(", "pkill",
            "gsettings set", "dpkg -i", "apt-get install",
            "/usr/bin/squeekboard", "subprocess.Popen", ".unlink(",
            "squeekboard-c2-uk-theme-v1", "squeekboard-c2-gresource-v1",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)
        self.assertIn("with tempfile.TemporaryDirectory(", text)
        self.assertIn('directory / "style.css"', text)


if __name__ == "__main__":
    unittest.main()
