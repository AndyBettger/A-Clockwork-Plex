"""C3 build gate: hash-pinned, off-device only, immutable C2 artifact."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/ci/apply-squeekboard-hot-css-build-patch.py"
BUILDER = ROOT / "scripts/ci/build-squeekboard-hot-css-arm64.sh"
OLD_BUILDER = ROOT / "scripts/ci/build-squeekboard-overlay-arm64.sh"
OLD_WORKFLOW = ROOT / ".github/workflows/squeekboard-overlay-arm64.yml"
C3_WORKFLOW = ROOT / ".github/workflows/squeekboard-hot-css-arm64.yml"
FIXTURE = ROOT / "tests/test_squeekboard_hot_css_source_patch.py"
PATCHER = ROOT / "scripts/ci/patch-squeekboard-hot-css.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


build = load(HELPER, "acp_c3_disposable_compiler_gate")
sample = load(FIXTURE, "acp_c3_build_source_fixture").sample_vendor
patch = load(PATCHER, "acp_c3_build_source_patch")


class C3CompilerGateTests(unittest.TestCase):
    def test_pinned_sha256_matches_real_vendor_and_proposed_source_audit(self):
        self.assertEqual(
            build.VENDOR_C_SHA256,
            "bc1076aa72c9b56ab752bd84815593c1228f13e74033de87f231597b27e97353",
        )
        self.assertEqual(
            build.PATCHED_C_SHA256,
            "f4f45a776e11cc3d1e35631e5f19451e7746a6e53173467bf46580c688759f40",
        )

    def test_pure_source_patch_matches_fixture_pins(self):
        source = sample().encode("utf-8")
        expected = patch.patch_keyboard_source(source.decode("utf-8")).encode("utf-8")
        actual = build.generate_checked_patch(
            source,
            expected_vendor=hashlib.sha256(source).hexdigest(),
            expected_candidate=hashlib.sha256(expected).hexdigest(),
        )
        self.assertEqual(actual, expected)
        self.assertEqual(source, sample().encode("utf-8"))

    def test_refuses_unknown_vendor_source_sha(self):
        with self.assertRaisesRegex(build.CandidateBuildError, "Vendor C SHA-256"):
            build.generate_checked_patch(sample().encode("utf-8"))
        with self.assertRaisesRegex(build.CandidateBuildError, "Vendor C SHA-256"):
            build.generate_checked_patch(b"not even C source")

    def test_refuses_mismatching_post_patch_hash(self):
        original = sample().encode("utf-8")
        with self.assertRaisesRegex(build.CandidateBuildError, "Candidate C SHA-256"):
            build.generate_checked_patch(
                original,
                expected_vendor=hashlib.sha256(original).hexdigest(),
                expected_candidate="0"*64,
            )

    def test_rejects_non_ci_and_unexpected_source_roots_without_touching_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "squeekboard-source"
            (root / "eek").mkdir(parents=True)
            cfile = root / build.RELATIVE_C
            cfile.write_text(sample())
            with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": ""}):
                with self.assertRaisesRegex(build.CandidateBuildError, "GitHub Actions"):
                    build.validate_disposable_ci_environment(root)
            self.assertEqual(cfile.read_text(), sample())

    def test_builder_shell_syntax_and_hard_denial_on_the_pi(self):
        result = subprocess.run(["bash", "-n", str(BUILDER)],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        env = dict(os.environ)
        env.pop("GITHUB_ACTIONS", None)
        result = subprocess.run(
            ["bash", str(BUILDER)], capture_output=True, text=True,
            env=env, timeout=5, check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Refusing", result.stderr)

    def test_separate_candidate_builder_has_full_ci_build_and_abi_contract(self):
        text = BUILDER.read_text()
        for marker in (
            "GITHUB_ACTIONS:-", "-f /.dockerenv", '$(uname -m)',
            '$(dpkg --print-architecture)', "CARGO_NET_OFFLINE=true",
            "runuser -u acp-builder", "dpkg-buildpackage --build=binary",
            "dpkg-checkbuilddeps", "readelf -d", "readelf --version-info",
            "sha256sum", "apply-squeekboard-hot-css-build-patch.py",
            "PATCH-ATTESTATION.txt", "squeekboard-c3-hot-css-arm64.deb",
            "squeekboard-c3-hot-css-arm64", "PROVENANCE.txt",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)
        self.assertNotIn('cp "$PKG" "$ARTIFACTS/"', text)
        self.assertNotIn('ARTIFACTS="$REPO/artifacts/squeekboard-overlay"', text)
        for bad in ("dpkg -i ", "systemctl", "pkill", "flatpak kill", "sudo ",
                    "ssh ", "scp ", "rsync"):
            with self.subTest(bad=bad):
                self.assertNotIn(bad, text)

    def test_new_workflow_never_deploys_or_triggers_on_regular_commits(self):
        text = C3_WORKFLOW.read_text()
        for required in (
            "ubuntu-24.04-arm", "debian:trixie", "workflow_dispatch:",
            "feature/acp-shell-native-plexamp",
            ".github/workflows/squeekboard-hot-css-arm64.yml",
            "scripts/ci/build-squeekboard-hot-css-arm64.sh",
            "squeekboard-c3-hot-css-arm64-test-only", "contents: read",
            "actions/upload-artifact@v4", "paths:",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        for disallowed in (
            "pull_request:", "branches: [main]", "dpkg -i ",
            "ssh ", "scp ", "rsync", "sudo ",
            "scripts/ci/build-squeekboard-overlay-arm64.sh",
        ):
            with self.subTest(disallowed=disallowed):
                self.assertNotIn(disallowed, text)

    def test_off_device_helper_never_manages_keyboard_or_accepted_source(self):
        s = HELPER.read_text()
        for bad in ("systemctl", "pkill", "gsettings set", "dpkg -i ",
                    "/usr/bin/squeekboard", "subprocess.Popen",
                    "squeekboard-c2-gresource-v1", "squeekboard-overlay-arm64"):
            with self.subTest(bad=bad):
                self.assertNotIn(bad, s)
        self.assertIn("acp-squeekboard-c3-arm64-", s)
        self.assertIn('source_tree.name != "squeekboard-source"', s)
        self.assertIn('staging.parent != Path("/tmp")', s)

    def test_accepted_old_builder_and_workflow_not_modified_by_new_builder(self):
        combined = OLD_BUILDER.read_text() + OLD_WORKFLOW.read_text()
        self.assertNotIn("apply-squeekboard-hot-css-build-patch", combined)
        self.assertNotIn("squeekboard-c3-hot-css", combined)


if __name__ == "__main__":
    unittest.main()
