from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-nfc-listener.sh"
VENDOR = ROOT / "vendor" / "plexamp-nfc-listener"
CONFIRMATION = "INSTALL-NFC-LISTENER"
UPSTREAM_COMMIT = "8f5f04213b22cfb5affc6931cb2db91fd07de537"
UPSTREAM_BLOB = "5f87b477bfdac27a34373cb7708af8236c33c2ab"


class NfcListenerInstallerTests(unittest.TestCase):
    def run_installer(
        self,
        root: Path | None = None,
        *arguments: str,
        fail_after_install: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        if fail_after_install:
            env["ACP_NFC_TEST_FAIL_AFTER_INSTALL"] = "1"
        argv = ["bash", str(INSTALLER)]
        if root is not None:
            argv.extend(["--root", str(root), "--project-dir", "/project"])
        argv.extend(arguments)
        return subprocess.run(
            argv,
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def test_shell_syntax_and_default_prepare_only_are_safe(self) -> None:
        syntax = subprocess.run(
            ["bash", "-n", str(INSTALLER)], capture_output=True, text=True, check=False
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)

        result = self.run_installer(None, "--project-user", "clockuser")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("guarded NFC listener plan", result.stdout)
        self.assertIn(UPSTREAM_COMMIT, result.stdout)
        self.assertIn("No production file, service, package", result.stdout)

    def test_vendored_runtime_is_bound_to_exact_upstream_identity(self) -> None:
        provenance = (VENDOR / "SOURCE.md").read_text(encoding="utf-8")
        self.assertIn(UPSTREAM_COMMIT, provenance)
        self.assertIn(UPSTREAM_BLOB, provenance)

        result = subprocess.run(
            ["git", "hash-object", str(VENDOR / "nfc_listener.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), UPSTREAM_BLOB)
        self.assertTrue((VENDOR / "LICENSE").read_text(encoding="utf-8").startswith("MIT License"))

    def test_unit_is_project_user_aware_and_uses_dedicated_nfc_venv(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")

        self.assertIn("SupplementaryGroups=i2c gpio spi", source)
        self.assertIn('NFC_PYTHON="$PROJECT_DIR/nfc-venv/bin/python"', source)
        self.assertIn("PLEXAMP_DISPLAY_SWITCH_COMMAND", source)
        self.assertIn("scripts/nfc-plexamp-mode.sh", source)
        self.assertIn("http://localhost:8088/api/mode/plexamp", source)
        self.assertIn("After=network-online.target plexamp.service a-clockwork-plex.service", source)

    def test_installer_does_not_import_legacy_kiosk_airplay_or_plexamp_handoff_ownership(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")

        forbidden = (
            "/etc/shairport-sync.conf",
            ".config/autostart",
            "systemctl stop plexamp.service",
            "systemctl start plexamp.service",
            "apt upgrade",
            "apt-get upgrade",
            "rpi-update",
        )
        for token in forbidden:
            self.assertNotIn(token, source)

    def test_alternate_root_activation_installs_rendered_unit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                CONFIRMATION,
                "--project-user",
                "clockuser",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            unit = root / "etc/systemd/system/nfc-listener.service"
            text = unit.read_text(encoding="utf-8")
            self.assertIn("User=clockuser", text)
            self.assertIn("WorkingDirectory=/project", text)
            self.assertIn("ExecStart=/project/nfc-venv/bin/python", text)
            self.assertIn("vendor/plexamp-nfc-listener/nfc_listener.py", text)

    def test_injected_failure_restores_exact_prior_unit_and_absence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unit = root / "etc/systemd/system/nfc-listener.service"
            unit.parent.mkdir(parents=True)
            original = b"[Unit]\nDescription=old-nfc\n"
            unit.write_bytes(original)
            unit.chmod(0o600)

            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                CONFIRMATION,
                "--project-user",
                "clockuser",
                fail_after_install=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(unit.read_bytes(), original)
            self.assertEqual(unit.stat().st_mode & 0o777, 0o600)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                CONFIRMATION,
                "--project-user",
                "clockuser",
                fail_after_install=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "etc/systemd/system/nfc-listener.service").exists())

    def test_wrong_confirmation_never_installs_unit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                "WRONG",
                "--project-user",
                "clockuser",
            )
            self.assertEqual(result.returncode, 64)
            self.assertFalse((root / "etc/systemd/system/nfc-listener.service").exists())


if __name__ == "__main__":
    unittest.main()
