"""Guards for exact-version, non-installing Squeekboard OVERLAY source staging."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare-squeekboard-overlay.py"


def load():
    spec = importlib.util.spec_from_file_location("squeekboard_staging", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SqueekboardStagingTests(unittest.TestCase):
    def setUp(self):
        self.s = load()

    def test_plan_is_offline_and_mentions_non_installing_boundary(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--plan"], text=True, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Never stops/restarts Squeekboard", r.stdout)
        self.assertIn("--prepare", r.stdout)

    def test_exact_one_layer_substitution(self):
        original = 'aaa\n"layer", ZWLR_LAYER_SHELL_V1_LAYER_TOP,\nbbb\n'
        altered = self.s.patch_panel_text(original)
        self.assertEqual(altered.count("LAYER_OVERLAY"), 1)
        self.assertNotIn("LAYER_TOP", altered)
        self.assertEqual(altered.replace("LAYER_OVERLAY", "LAYER_TOP"), original)
        with self.assertRaises(self.s.PreparationError):
            self.s.patch_panel_text(original + original)
        with self.assertRaises(self.s.PreparationError):
            self.s.patch_panel_text(altered)

    def test_source_descriptor_requires_two_exact_hashes_and_no_duplicates(self):
        one, two = self.s.SOURCE_NAMES
        descriptor = (
            "Format: 3.0 (quilt)\n"
            "Checksums-Sha256:\n"
            f" {'a' * 64} 215399 {one}\n"
            f" {'b' * 64} 14336 {two}\n"
            "Files:\n"
        )
        checks = self.s.source_checksums(descriptor)
        self.assertEqual(checks[one], ("a" * 64, 215399))
        self.assertEqual(checks[two], ("b" * 64, 14336))
        with self.assertRaises(self.s.PreparationError):
            self.s.source_checksums(descriptor.replace(f" {two}\n", " different.tar.xz\n"))
        with self.assertRaises(self.s.PreparationError):
            self.s.source_checksums(descriptor.replace("Files:\n", f" {'b' * 64} 14336 {two}\nFiles:\n"))

    def test_refuses_existing_destination_without_download(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(self.s, "confirm_vendor"):
            dest = Path(tmp) / "ready"
            dest.mkdir()
            with mock.patch.object(self.s, "download", side_effect=AssertionError("Unexpected download")):
                with self.assertRaises(self.s.PreparationError):
                    self.s.prepare(dest)

    def test_user_not_root_and_vendor_baseline_checked_before_changes(self):
        with mock.patch.object(self.s.os, "geteuid", return_value=0):
            with self.assertRaises(self.s.PreparationError):
                self.s.confirm_vendor()


if __name__ == "__main__":
    unittest.main()
