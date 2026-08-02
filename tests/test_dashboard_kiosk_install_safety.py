from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-dashboard-kiosk.sh"
LAUNCHER = ROOT / "scripts" / "launch-dashboard-kiosk.sh"


class DashboardKioskInstallSafetyTests(unittest.TestCase):
    def test_launcher_waits_for_dashboard_and_uses_dedicated_profile(self):
        text = LAUNCHER.read_text(encoding="utf-8")
        self.assertIn("http://localhost:8088/", text)
        self.assertIn("http://localhost:8088/api/state", text)
        self.assertIn("--kiosk", text)
        self.assertIn("--user-data-dir=", text)
        self.assertIn("a-clockwork-plex/chromium-profile", text)
        self.assertNotIn("localhost:32500", text)

    def test_installer_defaults_to_read_only_and_requires_confirmation(self):
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('MODE="check"', text)
        self.assertIn('CONFIRM_TOKEN="INSTALL-DASHBOARD-KIOSK"', text)
        self.assertIn("Check-only mode", text)
        self.assertIn('if [[ "$CONFIRM" != "$CONFIRM_TOKEN" ]]', text)
        self.assertIn("Run this as desktop user", text)

    def test_installer_is_scoped_to_browser_autostart(self):
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("localhost|127\\.0\\.0\\.1):32500", text)
        self.assertIn("chromium", text)
        self.assertIn("disabled-by-a-clockwork-plex", text)
        self.assertIn("BACKUP_DIR", text)
        self.assertIn("rollback()", text)
        self.assertNotIn("systemctl restart plexamp", text.lower())
        self.assertNotIn("systemctl restart shairport", text.lower())
        self.assertNotIn("install-shared-audio", text)
        self.assertNotIn("install-master-eq", text)

    def test_desktop_entry_targets_the_repository_launcher(self):
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("a-clockwork-plex-dashboard.desktop", text)
        self.assertIn('Exec=/usr/bin/env bash "$LAUNCHER"', text)
        self.assertIn("X-GNOME-Autostart-enabled=true", text)
        self.assertIn("desktop-file-validate", text)

    def test_shell_scripts_have_valid_syntax(self):
        for path in (INSTALLER, LAUNCHER):
            result = subprocess.run(
                ["bash", "-n", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"{path}: {result.stderr}")


if __name__ == "__main__":
    unittest.main()
