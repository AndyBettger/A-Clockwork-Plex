"""Disposable GLib CSS relookup proof never touches accepted keyboard resources."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/probe-squeekboard-live-css-lookup.py"
SPEC = importlib.util.spec_from_file_location("acp_c3_css_relookup", SCRIPT)
assert SPEC and SPEC.loader
reload = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reload)


class CSSResourceReloadSafetyTests(unittest.TestCase):
    def test_atomic_replacement_does_not_change_path_or_leave_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            css = Path(tmp) / "style.css"
            css.write_bytes(reload.A)
            reload.atomic_replace(css, reload.B)
            self.assertEqual(css.read_bytes(), reload.B)
            self.assertFalse((Path(tmp) / ".acp-probe-next.css").exists())

    def test_atomic_replacement_refuses_wrong_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            css = Path(tmp) / "gtk.css"
            css.write_bytes(reload.A)
            with self.assertRaisesRegex(RuntimeError, "Unsafe"):
                reload.atomic_replace(css, reload.B)
            self.assertEqual(css.read_bytes(), reload.A)

    def test_atomic_replacement_refuses_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "actual.css"
            target.write_bytes(reload.A)
            link = Path(tmp) / "style.css"
            link.symlink_to(target)
            with self.assertRaisesRegex(RuntimeError, "Unsafe"):
                reload.atomic_replace(link, reload.B)
            self.assertEqual(target.read_bytes(), reload.A)

    def test_atomic_replacement_refuses_stale_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            css = Path(tmp) / "style.css"
            css.write_bytes(reload.A)
            staging = Path(tmp) / ".acp-probe-next.css"
            staging.write_bytes(b"unexpected")
            with self.assertRaisesRegex(RuntimeError, "Unexpected"):
                reload.atomic_replace(css, reload.B)
            self.assertEqual(css.read_bytes(), reload.A)

    def test_child_requires_exact_private_environment(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.dict("os.environ", {"G_RESOURCE_OVERLAYS": "/bad/path"}):
            css = Path(tmp) / "style.css"
            css.write_bytes(reload.A)
            self.assertEqual(reload.lookup_in_child(css), 2)
            self.assertEqual(css.read_bytes(), reload.A)

    def test_probe_has_no_keyboard_management_side_effects(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for blocked in (
            "systemctl", "systemd-run", "os.kill(", "pkill", "sudo ",
            "dpkg -i", "gsettings set", "/usr/bin/squeekboard",
            "subprocess.Popen", ".unlink(", "/etc/gtk",
            "squeekboard-c2-gresource-v1/palettes",
        ):
            with self.subTest(blocked=blocked):
                self.assertNotIn(blocked, source)
        self.assertIn('Gio.resources_lookup_data(', source)
        self.assertIn("provider_after.load_from_resource(RESOURCE)", source)
        self.assertIn("with tempfile.TemporaryDirectory(", source)


if __name__ == "__main__":
    unittest.main()
