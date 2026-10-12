"""CI builder guards: strict source hashes, ARM64 container-only and artifact-only output."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PYTHON_BUILDER = ROOT / "scripts/ci/prepare-squeekboard-overlay-source.py"
BASH_BUILDER = ROOT / "scripts/ci/build-squeekboard-overlay-arm64.sh"
WORKFLOW = ROOT / ".github/workflows/squeekboard-overlay-arm64.yml"


def load():
    spec = importlib.util.spec_from_file_location("squeekboard_ci_source", PYTHON_BUILDER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SqueekboardCiBuilderTests(unittest.TestCase):
    def test_source_baseline_matches_commissioned_pi(self):
        builder = load()
        self.assertEqual("1.43.1-1+rpt1", builder.PI_VERSION)
        self.assertEqual(
            "2983685254b5d5b81ce36d9277172a041502737450dee416a6f805b82d51c203",
            builder.BEFORE_SHA256,
        )
        self.assertEqual(
            "61d977ba7d7805f58dc57126b2fa410c6115af172889724f3e55cd444d9df916",
            builder.AFTER_SHA256,
        )

    def test_source_staging_never_overwrites_existing_destination(self):
        builder = load()
        with tempfile.TemporaryDirectory() as tmp:
            already = Path(tmp) / "source"
            already.mkdir()
            fake = mock.Mock()
            with self.assertRaisesRegex(RuntimeError, "Destination exists"):
                builder.stage_source(already, helper=fake)
            fake.download.assert_not_called()

    def test_build_script_syntax_and_pi_guard(self):
        self.assertEqual(
            subprocess.run(["bash", "-n", str(BASH_BUILDER)], capture_output=True).returncode,
            0,
        )
        body = BASH_BUILDER.read_text(encoding="utf-8")
        for term in (
            '"${GITHUB_ACTIONS:-}" != "true"',
            "-f /.dockerenv",
            '$(dpkg --print-architecture)',
            '$(uname -m)',
            'dpkg-buildpackage --build=binary',
            "CARGO_NET_OFFLINE=true",
            "runuser -u acp-builder",
            "readelf -d",
            "readelf --version-info",
            'apt-get -y -o APT::Install-Recommends=false satisfy "$DEPENDS"',
        ):
            with self.subTest(term=term):
                self.assertIn(term, body)
        for bad in ("systemctl", "flatpak kill", "pkill", "dpkg -i", "apt-get upgrade"):
            with self.subTest(bad=bad):
                self.assertNotIn(bad, body)

    def test_workflow_has_narrow_push_trigger_and_no_deploy(self):
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("ubuntu-24.04-arm", content)
        self.assertIn("debian:trixie", content)
        self.assertIn("on:\\n  workflow_dispatch:", content)
        self.assertNotIn("pull_request:", content)
        self.assertNotIn("  push:", content)
        self.assertIn("workflow_dispatch:", content)
        self.assertIn("actions/upload-artifact@v4", content)
        self.assertIn("timeout-minutes:", content)
        self.assertIn("contents: read", content)
        self.assertIn("artifact", content)
        for bad in ("rsync", "scp ", "ssh ", "deploy", "sudo apt"):
            self.assertNotIn(bad, content.lower())


if __name__ == "__main__":
    unittest.main()
