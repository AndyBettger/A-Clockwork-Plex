"""Verify C3 audit performs only an in-memory, exactly reversible source patch."""
from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts/ci/audit-squeekboard-hot-css-source.py"
FIXTURE = ROOT / "tests/test_squeekboard_hot_css_source_patch.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = load(AUDIT, "acp_c3_read_only_vendor_audit")
sample_vendor = load(FIXTURE, "acp_c3_known_shape_fixture").sample_vendor


class PinnedCSourceAuditTests(unittest.TestCase):
    def source(self, folder: Path, text: str | None = None) -> Path:
        root = folder / "squeekboard-source"
        (root / "eek").mkdir(parents=True)
        (root / "eek/eek-gtk-keyboard.c").write_text(
            sample_vendor() if text is None else text, encoding="utf-8"
        )
        return root

    def test_exact_five_reversible_source_insertions(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.source(Path(directory))
            original = (source / audit.KEYBOARD_SOURCE).read_bytes()
            result = audit.verify_source_tree(source)
            self.assertEqual(result["insertions"], 5)
            self.assertEqual((source / audit.KEYBOARD_SOURCE).read_bytes(), original)
            self.assertEqual(result["original_sha256"], __import__("hashlib").sha256(original).hexdigest())
            self.assertNotEqual(result["candidate_sha256"], result["original_sha256"])
            self.assertIn("acp_squeekboard_start_css_watch", result["diff"])

    def test_refuses_symlinked_source_root(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.source(Path(directory))
            link = Path(directory) / "alias"
            link.symlink_to(source, target_is_directory=True)
            with self.assertRaisesRegex(audit.AuditError, "symlinked"):
                audit.verify_source_tree(link)

    def test_refuses_symlinked_vendor_file(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.source(Path(directory))
            target = source / audit.KEYBOARD_SOURCE
            copied = source / "original.c"
            copied.write_bytes(target.read_bytes())
            target.unlink()
            target.symlink_to(copied)
            with self.assertRaisesRegex(audit.AuditError, "symlinked"):
                audit.verify_source_tree(source)
            self.assertEqual(copied.read_text(), sample_vendor())

    def test_rejects_mutated_or_incompatible_vendor_c(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.source(Path(directory), sample_vendor().replace(
                "priv->renderer = eek_renderer_new (", "priv->renderer = arbitrary_new (",
            ))
            with self.assertRaisesRegex(audit.AuditError, "unique vendor structure"):
                audit.verify_source_tree(source)

    def test_rejects_binary_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.source(Path(directory))
            (source / audit.KEYBOARD_SOURCE).write_bytes(b"\xff" * 1500)
            with self.assertRaisesRegex(audit.AuditError, "Vendor source audit refused"):
                audit.verify_source_tree(source)

    def test_cli_plan_and_diff_does_not_write_or_compile(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.source(Path(directory))
            before = (source / audit.KEYBOARD_SOURCE).read_bytes()
            output = io.StringIO()
            with mock.patch.object(sys, "argv", [
                str(AUDIT), "--source-tree", str(source), "--show-diff"
            ]), contextlib.redirect_stdout(output):
                self.assertEqual(audit.main(), 0)
            self.assertIn("SOURCE PATCH COMPATIBILITY: PASS", output.getvalue())
            self.assertIn("=== BEGIN PROPOSED SOURCE DIFF ===", output.getvalue())
            self.assertEqual(before, (source / audit.KEYBOARD_SOURCE).read_bytes())

    def test_cli_sha_pin_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.source(Path(directory))
            output = io.StringIO()
            with mock.patch.object(sys, "argv", [
                str(AUDIT), "--source-tree", str(source),
                "--expected-vendor-sha256", "0" * 64,
            ]), contextlib.redirect_stderr(output):
                self.assertEqual(audit.main(), 2)
            self.assertIn("did not match expected pin", output.getvalue())

    def test_auditor_does_not_replace_accepted_ci_build_or_touch_keyboard(self):
        source = AUDIT.read_text(encoding="utf-8")
        for bad in (
            "systemctl", "systemd-run", "pkill", "os.kill(",
            "subprocess.run", "subprocess.Popen", "gsettings set", "dpkg -i",
            ".write_text(", ".write_bytes(", "/usr/bin/squeekboard",
            "squeekboard-c2-gresource-v1/palettes",
        ):
            with self.subTest(bad=bad):
                self.assertNotIn(bad, source)
        old_ci = (ROOT / "scripts/ci/build-squeekboard-overlay-arm64.sh").read_text()
        old_prepare = (ROOT / "scripts/ci/prepare-squeekboard-overlay-source.py").read_text()
        self.assertNotIn("audit-squeekboard-hot-css-source.py", old_ci)
        self.assertNotIn("audit-squeekboard-hot-css-source.py", old_prepare)


if __name__ == "__main__":
    unittest.main()
