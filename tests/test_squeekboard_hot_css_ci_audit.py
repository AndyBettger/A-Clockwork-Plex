"""Guard separate C3 ARM64 source-only CI audit against build/device actions."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/ci/run-squeekboard-hot-css-source-audit.sh"
WORKFLOW = ROOT / ".github/workflows/squeekboard-hot-css-source-audit.yml"
OLD_BUILDER = ROOT / "scripts/ci/build-squeekboard-overlay-arm64.sh"
OLD_WORKFLOW = ROOT / ".github/workflows/squeekboard-overlay-arm64.yml"


class SourceOnlyAuditCIGuards(unittest.TestCase):
    def test_bash_syntax_valid(self):
        result = subprocess.run(
            ["bash", "-n", str(RUNNER)], capture_output=True, text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_runner_fails_closed_outside_disposable_arm64_container(self):
        env = dict(os.environ)
        env.pop("GITHUB_ACTIONS", None)
        result = subprocess.run(
            ["bash", str(RUNNER)], capture_output=True,
            text=True, check=False, env=env, timeout=5,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Refusing: source audit must run inside", result.stderr)

    def test_runner_verifies_pinned_raspberry_pi_debian_source(self):
        text = RUNNER.read_text()
        for term in (
            'GITHUB_ACTIONS:-',
            ' -f /.dockerenv',
            '$(dpkg --print-architecture)',
            '$(uname -m)',
            'id -u',
            "prepare-squeekboard-overlay-source.py",
            'SOURCE="$ROOT/vendor/squeekboard-source"',
            "--source-tree",
            "--show-diff",
            "SOURCE PATCH COMPATIBILITY: PASS",
            "PROVENANCE.txt",
            "SOURCE-ONLY-AUDIT.txt",
            "SUMMARY.txt",
        ):
            with self.subTest(term=term):
                self.assertIn(term, text)

    def test_runner_never_builds_installs_or_changes_the_keyboard(self):
        text = RUNNER.read_text()
        for forbidden in (
            "dpkg-buildpackage", "dpkg -i", "dpkg-deb --extract",
            "cargo ", "rustc ", "systemctl", "sudo ", "ssh ",
            "scp ", "rsync", "pkill", "killall", "systemctl --user",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)
        self.assertIn('ARTIFACTS="$REPO/artifacts/squeekboard-hot-css-source-audit"', text)
        self.assertNotIn("artifacts/squeekboard-overlay", text)

    def test_workflow_is_feature_branch_only_one_time_bootstrap(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("ubuntu-24.04-arm", text)
        self.assertIn("debian:trixie", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("feature/acp-shell-native-plexamp", text)
        self.assertIn("squeekboard-hot-css-source-audit.yml", text)
        self.assertIn("branches:", text)
        self.assertIn("paths:", text)
        self.assertIn("contents: read", text)
        self.assertIn("actions/upload-artifact@v4", text)
        self.assertIn("run-squeekboard-hot-css-source-audit.sh", text)
        for forbidden in (
            "pull_request:", "branches: [main]", "dpkg-buildpackage",
            "docker build", "squeekboard-overlay-arm64.sh",
            "ssh ", "scp ", "rsync", "sudo ",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_accepted_overlay_workflow_and_builder_remain_unmodified_by_hot_audit(self):
        old = OLD_BUILDER.read_text() + OLD_WORKFLOW.read_text()
        for forbidden in ("run-squeekboard-hot-css-source-audit",
                          "audit-squeekboard-hot-css-source",
                          "patch-squeekboard-hot-css"):
            self.assertNotIn(forbidden, old)


if __name__ == "__main__":
    unittest.main()
