"""Tests for non-installing, exact-source Squeekboard build-dependency planning."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "plan-squeekboard-build-deps.py"


def load():
    spec = importlib.util.spec_from_file_location("squeekboard_build_plan", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SqueekboardBuildPlanTests(unittest.TestCase):
    def setUp(self):
        self.s = load()

    def test_only_source_stanza_parsed_including_alternatives(self):
        control = (
            "Source: squeekboard\nBuild-Depends:\n cargo,\n libglib2.0-dev,\n"
            " librust-xkbcommon-0.8-dev | rustc,\n debhelper-compat (= 13),\n"
            "Standards-Version: 4.7.0\n\nPackage: squeekboard\nDepends: unrelated\n"
        )
        actual = self.s.build_depends(control)
        self.assertIn("libglib2.0-dev", actual)
        self.assertIn("debhelper-compat (= 13)", actual)
        self.assertIn("| rustc", actual)
        self.assertNotIn("unrelated", actual)
        with self.assertRaises(self.s.PlanError):
            self.s.build_depends("Source: not-squeekboard\nBuild-Depends: cargo\n")

    def test_wrong_or_missing_source_refuses_apt_simulation(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            with mock.patch.object(self.s.shutil, "which", return_value="/usr/bin/apt-get"):
                fake_runner = mock.Mock()
                with self.assertRaises(self.s.PlanError):
                    self.s.preview(stage=stage, runner=fake_runner)
                fake_runner.assert_not_called()

    def test_valid_source_uses_only_apt_simulation(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            (stage / "squeekboard-source/src").mkdir(parents=True)
            (stage / "squeekboard-source/debian").mkdir(parents=True)
            panel = stage / "squeekboard-source/src/panel.c"
            panel.write_text(self.s.LAYER + "\n", encoding="utf-8")
            panel_hash = self.s.sha256(panel)
            (stage / "PROVENANCE.txt").write_text(
                f"Source: Raspberry Pi Squeekboard {self.s.VERSION}\n"
                f"Installed vendor binary SHA-256: {self.s.EXPECTED_VENDOR_BINARY_SHA256}\n"
                f"src/panel.c after SHA-256: {panel_hash}\n", encoding="utf-8"
            )
            (stage / "squeekboard-source/debian/control").write_text(
                "Source: squeekboard\nBuild-Depends:\n cargo,\n rustc,\n libgtk-3-dev,\n"
                "Standards-Version: 4.7.0\n", encoding="utf-8",
            )
            with mock.patch.object(self.s, "EXPECTED_PANEL_SHA256", panel_hash), \
                 mock.patch.object(self.s.shutil, "which", return_value="/usr/bin/apt-get"):
                fake_runner = mock.Mock(return_value=mock.Mock(returncode=0))
                code = self.s.preview(stage=stage, runner=fake_runner)
            self.assertEqual(0, code)
            args = fake_runner.call_args.args[0]
            self.assertEqual(args[:2], ["apt-get", "--simulate"])
            self.assertIn("satisfy", args)
            self.assertIn("cargo", args[-1])
            self.assertNotIn("sudo", args)
            self.assertNotIn("install", args)

    def test_changed_patch_refuses_apt(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            (stage / "squeekboard-source/src").mkdir(parents=True)
            (stage / "squeekboard-source/debian").mkdir(parents=True)
            (stage / "squeekboard-source/src/panel.c").write_text(
                self.s.UNPATCHED_LAYER, encoding="utf-8"
            )
            (stage / "squeekboard-source/debian/control").write_text(
                "Source: squeekboard\nBuild-Depends: cargo\n", encoding="utf-8"
            )
            (stage / "PROVENANCE.txt").write_text("Source: Raspberry Pi Squeekboard 1.43.1-1+rpt1", encoding="utf-8")
            with self.assertRaises(self.s.PlanError):
                self.s.validate_stage(stage)


if __name__ == "__main__":
    unittest.main()
