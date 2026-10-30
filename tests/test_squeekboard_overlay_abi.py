"""Read-only ABI target preflight guards for the ARM64 Squeekboard experiment."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/inspect-squeekboard-overlay-artifact.py"


def load():
    spec = importlib.util.spec_from_file_location("acp_overlay_abi", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OverlayAbiInspectionTests(unittest.TestCase):
    def setUp(self):
        self.s = load()

    def test_pinned_artifact_digests_and_arm64_elf_sonames(self):
        self.assertEqual(
            "11e1c8ef40674503cb9a0b82a96086d8bbca319c99943b9061bc5629118166a6",
            self.s.EXPECTED["squeekboard-overlay-arm64"][1],
        )
        self.assertEqual(
            "f13e11f67b868d6f23beeeb607596fa99e05b5657c575526dcca43ca1ef1511e",
            self.s.EXPECTED["squeekboard_1.43.1-1+rpt1_arm64.deb"][1],
        )
        self.assertIn("libgnome-desktop-3.so.20", self.s.SONAMES)
        self.assertIn("libfeedback-0.0.so.0", self.s.SONAMES)

    def test_archive_checksum_tamper_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "test.zip"
            fake = {"squeekboard-overlay-arm64": b"TEST", "squeekboard_1.43.1-1+rpt1_arm64.deb": b"DEB"}
            expected = {
                name: (len(data), hashlib.sha256(data).hexdigest())
                for name, data in fake.items()
            }
            with zipfile.ZipFile(archive, "w") as zipped:
                for name, data in fake.items():
                    zipped.writestr(name, data)
            with mock.patch.object(self.s, "EXPECTED", expected):
                self.assertEqual(fake, self.s.checked_files(archive))
                expected["squeekboard-overlay-arm64"] = (4, "0" * 64)
                with self.assertRaisesRegex(self.s.InspectionError, "SHA-256 mismatch"):
                    self.s.checked_files(archive)

    def test_version_floor_and_alternatives_use_dpkg_read_only(self):
        def fake_run(args, **_kwargs):
            if args[:2] == ["dpkg-query", "-W"]:
                if args[-1] == "libc6":
                    return mock.Mock(returncode=0, stdout="installed\t2.41")
                return mock.Mock(returncode=1, stdout="")
            if args[:2] == ["dpkg", "--compare-versions"]:
                return mock.Mock(returncode=0 if args[2] == "2.41" else 1)
            raise AssertionError(f"Unexpected process call: {args}")
        with mock.patch.object(self.s.subprocess, "run", side_effect=fake_run):
            self.assertTrue(self.s.satisfied_dependency("libc6 (>= 2.39)"))
            self.assertEqual(
                ["missing-package (>= 1)"],
                self.s.missing_dependencies("libc6 (>= 2.39), missing-package (>= 1)"),
            )
            self.assertEqual([], self.s.missing_dependencies("missing-package | libc6"))
            with self.assertRaises(self.s.InspectionError):
                self.s.satisfied_dependency("unexpected [range]")

    def test_only_exact_needed_libs_accept_no_rpath(self):
        s = " 0x0000 (NEEDED) Shared library: [libglib-2.0.so.0]\n"
        self.assertEqual({"libglib-2.0.so.0"}, self.s.needed_sonames(s))
        cache = " libglib-2.0.so.0 (libc6,AArch64) => /lib/aarch64-linux-gnu/libglib-2.0.so.0\n"
        self.assertEqual([], self.s.missing_sonames({"libglib-2.0.so.0"}, cache))
        self.assertEqual(["libabsent.so.0"], self.s.missing_sonames({"libabsent.so.0"}, cache))

    def test_refuses_non_pi_or_root_without_touching_artifact(self):
        with mock.patch.object(self.s.platform, "machine", return_value="x86_64"):
            with self.assertRaises(self.s.InspectionError):
                self.s.inspect(Path("/nonexistent.zip"))
        with mock.patch.object(self.s.platform, "machine", return_value="aarch64"), \
             mock.patch.object(self.s.os, "geteuid", return_value=0):
            with self.assertRaises(self.s.InspectionError):
                self.s.inspect(Path("/nonexistent.zip"))


if __name__ == "__main__":
    unittest.main()
