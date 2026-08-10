from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-appliance-helpers.sh"
ALARM_SOURCE = ROOT / "scripts" / "a-clockwork-plex-alarm-audio-helper.sh"
NAME_SOURCE = ROOT / "scripts" / "a-clockwork-plex-shairport-name.py"


class ApplianceHelpersInstallerTests(unittest.TestCase):
    def run_installer(
        self,
        root: Path,
        *arguments: str,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        merged = os.environ.copy()
        if env:
            merged.update(env)
        return subprocess.run(
            ["bash", str(INSTALLER), "--root", str(root), *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=merged,
            check=False,
        )

    @staticmethod
    def target(root: Path, logical: str) -> Path:
        return root / logical.lstrip("/")

    def test_prepare_only_does_not_change_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = self.target(root, "/usr/local/bin/a-clockwork-plex-alarm-audio")
            existing.parent.mkdir(parents=True)
            existing.write_text("old helper\n", encoding="utf-8")

            result = self.run_installer(root, "--prepare-only", "--project-user", "clockuser")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(existing.read_text(encoding="utf-8"), "old helper\n")
            self.assertIn("No production file, service, route, mixer or PCM was changed", result.stdout)

    def test_guarded_activation_installs_runtime_sources_and_restricted_policies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                "INSTALL-APPLIANCE-HELPERS",
                "--project-user",
                "clockuser",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            alarm = self.target(root, "/usr/local/bin/a-clockwork-plex-alarm-audio")
            alarm_sudoers = self.target(root, "/etc/sudoers.d/a-clockwork-plex-alarm-audio")
            name = self.target(root, "/usr/local/bin/a-clockwork-plex-shairport-name")
            name_sudoers = self.target(root, "/etc/sudoers.d/a-clockwork-plex-shairport-name")

            self.assertEqual(alarm.read_bytes(), ALARM_SOURCE.read_bytes())
            self.assertEqual(name.read_bytes(), NAME_SOURCE.read_bytes())
            self.assertEqual(oct(alarm.stat().st_mode & 0o777), "0o755")
            self.assertEqual(oct(name.stat().st_mode & 0o777), "0o755")
            self.assertEqual(oct(alarm_sudoers.stat().st_mode & 0o777), "0o440")
            self.assertEqual(oct(name_sudoers.stat().st_mode & 0o777), "0o440")
            self.assertIn(
                "clockuser ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-alarm-audio release",
                alarm_sudoers.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "clockuser ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-shairport-name status",
                name_sudoers.read_text(encoding="utf-8"),
            )

    def test_wrong_token_and_invalid_user_are_rejected_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wrong = self.run_installer(
                root,
                "--activate",
                "--confirm",
                "WRONG",
                "--project-user",
                "clockuser",
            )
            invalid = self.run_installer(root, "--prepare-only", "--project-user", "bad user")

            self.assertEqual(wrong.returncode, 64)
            self.assertEqual(invalid.returncode, 64)
            self.assertFalse(
                self.target(root, "/usr/local/bin/a-clockwork-plex-alarm-audio").exists()
            )

    def test_injected_failure_restores_exact_prior_targets_and_absence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            alarm = self.target(root, "/usr/local/bin/a-clockwork-plex-alarm-audio")
            alarm_sudoers = self.target(root, "/etc/sudoers.d/a-clockwork-plex-alarm-audio")
            alarm.parent.mkdir(parents=True)
            alarm_sudoers.parent.mkdir(parents=True)
            alarm.write_bytes(b"old-alarm-helper\n")
            alarm_sudoers.write_bytes(b"old-policy\n")
            os.chmod(alarm, 0o700)
            os.chmod(alarm_sudoers, 0o400)

            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                "INSTALL-APPLIANCE-HELPERS",
                "--project-user",
                "clockuser",
                env={"ACP_HELPERS_TEST_FAIL_AFTER_INSTALL": "1"},
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(alarm.read_bytes(), b"old-alarm-helper\n")
            self.assertEqual(alarm_sudoers.read_bytes(), b"old-policy\n")
            self.assertEqual(oct(alarm.stat().st_mode & 0o777), "0o700")
            self.assertEqual(oct(alarm_sudoers.stat().st_mode & 0o777), "0o400")
            self.assertFalse(
                self.target(root, "/usr/local/bin/a-clockwork-plex-shairport-name").exists()
            )
            self.assertFalse(
                self.target(root, "/etc/sudoers.d/a-clockwork-plex-shairport-name").exists()
            )
            self.assertIn("restoring captured state", result.stderr)
            self.assertIn("pre-state restored", result.stderr)

    def test_installer_packages_existing_runtime_sources_without_reimplementing_them(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("a-clockwork-plex-alarm-audio-helper.sh", source)
        self.assertIn("a-clockwork-plex-shairport-name.py", source)
        self.assertIn("ACP_HELPERS_TEST_FAIL_AFTER_INSTALL", source)
        self.assertIn('[[ "$ROOT" != / && "${ACP_HELPERS_TEST_FAIL_AFTER_INSTALL:-0}" == 1 ]]', source)
        self.assertNotIn("def apply_name", source)
        self.assertNotIn("amixer", source)


if __name__ == "__main__":
    unittest.main()
