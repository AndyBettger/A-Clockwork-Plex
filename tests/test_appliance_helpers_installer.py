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
MIXER_SOURCE = ROOT / "scripts" / "a-clockwork-plex-audio-mixer.py"


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
            mixer = self.target(root, "/usr/local/bin/a-clockwork-plex-audio-mixer")
            mixer_sudoers = self.target(root, "/etc/sudoers.d/a-clockwork-plex-audio-mixer")
            mixer_defaults = self.target(root, "/etc/default/a-clockwork-plex-audio")

            self.assertEqual(alarm.read_bytes(), ALARM_SOURCE.read_bytes())
            self.assertEqual(name.read_bytes(), NAME_SOURCE.read_bytes())
            self.assertEqual(mixer.read_bytes(), MIXER_SOURCE.read_bytes())
            self.assertEqual(oct(alarm.stat().st_mode & 0o777), "0o755")
            self.assertEqual(oct(name.stat().st_mode & 0o777), "0o755")
            self.assertEqual(oct(mixer.stat().st_mode & 0o777), "0o755")
            self.assertEqual(oct(alarm_sudoers.stat().st_mode & 0o777), "0o440")
            self.assertEqual(oct(name_sudoers.stat().st_mode & 0o777), "0o440")
            self.assertEqual(oct(mixer_sudoers.stat().st_mode & 0o777), "0o440")
            self.assertEqual(oct(mixer_defaults.stat().st_mode & 0o777), "0o644")
            self.assertIn(
                "clockuser ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-alarm-audio release",
                alarm_sudoers.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "clockuser ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-shairport-name status",
                name_sudoers.read_text(encoding="utf-8"),
            )
            mixer_policy = mixer_sudoers.read_text(encoding="utf-8")
            self.assertIn(
                "clockuser ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-audio-mixer status",
                mixer_policy,
            )
            self.assertIn(
                "clockuser ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-audio-mixer set *",
                mixer_policy,
            )
            self.assertIn(
                "clockuser ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-audio-mixer live *",
                mixer_policy,
            )
            defaults = mixer_defaults.read_text(encoding="utf-8")
            self.assertIn("ALSA_CARD=Pro", defaults)
            self.assertIn("ALSA_DEVICE=0", defaults)
            self.assertIn("SAMPLE_RATE=44100", defaults)
            self.assertIn("CHANNELS=2", defaults)

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
            self.assertFalse(
                self.target(root, "/usr/local/bin/a-clockwork-plex-audio-mixer").exists()
            )
            self.assertFalse(
                self.target(root, "/etc/sudoers.d/a-clockwork-plex-audio-mixer").exists()
            )
            self.assertFalse(
                self.target(root, "/etc/default/a-clockwork-plex-audio").exists()
            )
            self.assertIn("restoring captured state", result.stderr)
            self.assertIn("pre-state restored", result.stderr)

    def test_protected_post_install_verification_uses_root_boundary(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")

        self.assertIn("verify_regular_file()", source)
        self.assertIn("verify_mode()", source)
        self.assertIn("verify_contains()", source)
        self.assertIn('acp_run_root test -f "$physical"', source)
        self.assertIn('acp_run_root test -L "$physical"', source)
        self.assertIn("acp_run_root stat -c '%a'", source)
        self.assertIn('acp_run_root grep -Fq -- "$expected" "$physical"', source)
        self.assertIn("Installed helper target is not a regular non-symlink file", source)
        self.assertIn("Installed helper policy is missing required rule", source)
        self.assertNotIn('[[ -f "$(acp_path "$installed")"', source)
        self.assertNotIn('grep -Fq "$PROJECT_USER ALL=(root)', source)

    def test_installer_packages_existing_runtime_sources_without_reimplementing_them(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("a-clockwork-plex-alarm-audio-helper.sh", source)
        self.assertIn("a-clockwork-plex-shairport-name.py", source)
        self.assertIn("a-clockwork-plex-audio-mixer.py", source)
        self.assertIn("ACP_HELPERS_TEST_FAIL_AFTER_INSTALL", source)
        self.assertIn('[[ "$ROOT" != / && "${ACP_HELPERS_TEST_FAIL_AFTER_INSTALL:-0}" == 1 ]]', source)
        self.assertIn("prime_mixer_controls()", source)
        self.assertIn("acp_master acp_plexamp acp_airplay acp_alarm", source)
        self.assertNotIn("def apply_name", source)
        self.assertNotIn("amixer", source)


if __name__ == "__main__":
    unittest.main()
