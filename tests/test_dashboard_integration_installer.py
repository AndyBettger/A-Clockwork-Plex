from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-dashboard-integration.sh"


class DashboardIntegrationInstallerTests(unittest.TestCase):
    def run_installer(
        self,
        root: Path,
        *extra: str,
        env_extra: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        fake_bin = root / "test-bin"
        fake_bin.mkdir(parents=True, exist_ok=True)
        for command in ("systemd-analyze", "desktop-file-validate"):
            stub = fake_bin / command
            stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            stub.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [
                "bash",
                str(INSTALLER),
                "--root",
                str(root),
                "--project-user",
                "clockuser",
                "--project-dir",
                "/home/clockuser/A-Clockwork-Plex",
                *extra,
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    @staticmethod
    def unit_path(root: Path) -> Path:
        return root / "etc/systemd/system/a-clockwork-plex.service"

    @staticmethod
    def kiosk_path(root: Path) -> Path:
        return root / "home/clockuser/.config/autostart/a-clockwork-plex-dashboard.desktop"

    def test_source_contract_is_one_guarded_prepare_only_owner(self):
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("MODE=prepare-only", text)
        self.assertIn("INSTALL-DASHBOARD-INTEGRATION", text)
        self.assertIn("acp_transaction_capture_path", text)
        self.assertIn('acp_transaction_capture_service "$TRANSACTION" "$SERVICE_NAME"', text)
        self.assertIn("ACP_DASHBOARD_TEST_FAIL_AFTER_INSTALL", text)
        self.assertIn("/api/state", text)
        self.assertNotIn("install-dashboard-service.sh --apply", text)
        self.assertNotIn("install-dashboard-kiosk.sh --apply", text)

    def test_prepare_only_changes_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = self.run_installer(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Mode:            prepare-only", result.stdout)
            self.assertIn("No production file", result.stdout)
            self.assertFalse(self.unit_path(root).exists())
            self.assertFalse(self.kiosk_path(root).exists())

    def test_activation_requires_exact_confirmation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = self.run_installer(root, "--activate", "--confirm", "WRONG")
            self.assertEqual(result.returncode, 64)
            self.assertIn("INSTALL-DASHBOARD-INTEGRATION", result.stderr)
            self.assertFalse(self.unit_path(root).exists())
            self.assertFalse(self.kiosk_path(root).exists())

    def test_alternate_root_activation_installs_matching_service_and_kiosk(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                "INSTALL-DASHBOARD-INTEGRATION",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            unit = self.unit_path(root).read_text(encoding="utf-8")
            kiosk = self.kiosk_path(root).read_text(encoding="utf-8")
            self.assertIn("User=clockuser", unit)
            self.assertIn("Group=clockuser", unit)
            self.assertIn("WorkingDirectory=/home/clockuser/A-Clockwork-Plex", unit)
            self.assertIn(
                "ExecStart=/home/clockuser/A-Clockwork-Plex/venv/bin/python /home/clockuser/A-Clockwork-Plex/app/runner.py",
                unit,
            )
            self.assertIn("EnvironmentFile=-/etc/default/a-clockwork-plex-weather", unit)
            self.assertIn(
                'Exec=/usr/bin/env bash "/home/clockuser/A-Clockwork-Plex/scripts/launch-dashboard-kiosk.sh"',
                kiosk,
            )
            self.assertIn("X-GNOME-Autostart-enabled=true", kiosk)
            self.assertEqual(stat.S_IMODE(self.unit_path(root).stat().st_mode), 0o644)
            self.assertEqual(stat.S_IMODE(self.kiosk_path(root).stat().st_mode), 0o644)

    def test_injected_failure_restores_exact_previous_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            unit = self.unit_path(root)
            kiosk = self.kiosk_path(root)
            unit.parent.mkdir(parents=True, exist_ok=True)
            kiosk.parent.mkdir(parents=True, exist_ok=True)
            unit.write_text("old unit\n", encoding="utf-8")
            kiosk.write_text("old kiosk\n", encoding="utf-8")
            unit.chmod(0o600)
            kiosk.chmod(0o640)

            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                "INSTALL-DASHBOARD-INTEGRATION",
                env_extra={"ACP_DASHBOARD_TEST_FAIL_AFTER_INSTALL": "1"},
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("restoring captured state", result.stderr)
            self.assertEqual(unit.read_text(encoding="utf-8"), "old unit\n")
            self.assertEqual(kiosk.read_text(encoding="utf-8"), "old kiosk\n")
            self.assertEqual(stat.S_IMODE(unit.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(kiosk.stat().st_mode), 0o640)

    def test_injected_failure_restores_previous_absence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                "INSTALL-DASHBOARD-INTEGRATION",
                env_extra={"ACP_DASHBOARD_TEST_FAIL_AFTER_INSTALL": "1"},
            )
            self.assertEqual(result.returncode, 1)
            self.assertFalse(self.unit_path(root).exists())
            self.assertFalse(self.kiosk_path(root).exists())

    def test_shell_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(INSTALLER)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
