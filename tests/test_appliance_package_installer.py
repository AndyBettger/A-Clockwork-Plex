from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-appliance-packages.sh"
CONFIRMATION = "INSTALL-APPLIANCE-PACKAGES"


class AppliancePackageInstallerTests(unittest.TestCase):
    def make_root(self, directory: str) -> tuple[Path, Path]:
        root = Path(directory)
        project = root / "project"
        project.mkdir(parents=True)
        fake_python = root / "fake-python"
        fake_python.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "if [[ ${1:-} == -m && ${2:-} == venv ]]; then\n"
            "  target=$3\n"
            "  mkdir -p \"$target/bin\"\n"
            "  cp \"$0\" \"$target/bin/python\"\n"
            "  chmod 0755 \"$target/bin/python\"\n"
            "  printf 'candidate\\n' >\"$target/candidate.txt\"\n"
            "  exit 0\n"
            "fi\n"
            "if [[ ${1:-} == -m && ${2:-} == pip ]]; then\n"
            "  venv=$(cd \"$(dirname \"$0\")/..\" && pwd)\n"
            "  if [[ ${3:-} == install ]]; then printf 'installed\\n' >\"$venv/requirements-installed.txt\"; fi\n"
            "  exit 0\n"
            "fi\n"
            "if [[ ${1:-} == -c ]]; then exit 0; fi\n"
            "exit 1\n",
            encoding="utf-8",
        )
        fake_python.chmod(0o755)
        return root, fake_python

    def run_installer(
        self,
        root: Path,
        *arguments: str,
        fake_python: Path | None = None,
        fail_after_swap: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        if fake_python is not None:
            env["ACP_PACKAGES_TEST_PYTHON"] = str(fake_python)
        if fail_after_swap:
            env["ACP_PACKAGES_TEST_FAIL_AFTER_SWAP"] = "1"
        return subprocess.run(
            ["bash", str(INSTALLER), "--root", str(root), *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def test_prepare_only_is_read_only_and_states_rollback_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _ = self.make_root(directory)
            result = self.run_installer(root, "--prepare-only", "--audio", "direct")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("rollback never runs apt remove, purge or autoremove", result.stdout)
            self.assertIn("Prepare-only complete", result.stdout)
            self.assertFalse((root / "project/venv").exists())

    def test_wrong_confirmation_is_rejected_before_package_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, fake_python = self.make_root(directory)
            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                "WRONG",
                "--audio",
                "direct",
                fake_python=fake_python,
            )

            self.assertEqual(result.returncode, 64)
            self.assertIn(CONFIRMATION, result.stderr)
            self.assertNotIn("A Clockwork Plex package/artifact report", result.stdout)
            self.assertFalse((root / "project/venv").exists())

    def test_alternate_root_activation_swaps_in_complete_venv_without_apt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, fake_python = self.make_root(directory)
            old = root / "project/venv"
            old.mkdir()
            (old / "old.txt").write_text("old\n", encoding="utf-8")

            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                CONFIRMATION,
                "--audio",
                "direct",
                fake_python=fake_python,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            venv = root / "project/venv"
            self.assertFalse((venv / "old.txt").exists())
            self.assertEqual((venv / "candidate.txt").read_text(encoding="utf-8"), "candidate\n")
            self.assertEqual(
                (venv / "requirements-installed.txt").read_text(encoding="utf-8"),
                "installed\n",
            )
            self.assertIn("APT mutation skipped by design", result.stdout)
            self.assertIn("APT_ROLLBACK_POLICY=RETAIN-ADDITIVE-PREREQUISITES", result.stdout)
            self.assertIn("VENV_ROLLBACK_POLICY=EXACT-PRESTATE-ON-STAGE-FAILURE", result.stdout)

    def test_injected_failure_restores_exact_previous_venv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, fake_python = self.make_root(directory)
            venv = root / "project/venv"
            nested = venv / "nested"
            nested.mkdir(parents=True)
            marker = nested / "old.txt"
            marker.write_bytes(b"exact-old-state\n")
            marker.chmod(0o640)

            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                CONFIRMATION,
                "--audio",
                "direct",
                fake_python=fake_python,
                fail_after_swap=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(marker.read_bytes(), b"exact-old-state\n")
            self.assertEqual(stat.S_IMODE(marker.stat().st_mode), 0o640)
            self.assertFalse((venv / "candidate.txt").exists())
            self.assertIn("Venv pre-state restored", result.stderr)

    def test_injected_failure_restores_exact_prior_absence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, fake_python = self.make_root(directory)
            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                CONFIRMATION,
                "--audio",
                "direct",
                fake_python=fake_python,
                fail_after_swap=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "project/venv").exists())

    def test_production_policy_is_additive_and_test_overrides_are_nonproduction_only(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")

        self.assertIn("sudo -- apt-get update", source)
        self.assertIn("sudo -- apt-get install -y --no-install-recommends", source)
        self.assertNotIn("apt-get remove", source)
        self.assertNotIn("apt-get purge", source)
        self.assertNotIn("apt-get autoremove", source)
        self.assertIn("ACP_PACKAGES_TEST_PYTHON is forbidden on the production root", source)
        self.assertIn('[[ "$ROOT" != / && "${ACP_PACKAGES_TEST_FAIL_AFTER_SWAP:-0}" == 1 ]]', source)


if __name__ == "__main__":
    unittest.main()
