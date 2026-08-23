from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "migrate-dashboard-browser-auth.sh"


class DashboardBrowserAuthMigrationTests(unittest.TestCase):
    def test_script_has_valid_shell_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_default_is_read_only_and_apply_requires_confirmation(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('MODE="check"', text)
        self.assertIn('CONFIRM_TOKEN="IMPORT-PLEXAMP-BROWSER-AUTH"', text)
        self.assertIn("Check-only mode: no browser data was changed", text)
        self.assertIn('if [[ "$CONFIRM" != "$CONFIRM_TOKEN" ]]', text)

    def test_migration_preserves_kiosk_profile_and_excludes_session_restore(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("a-clockwork-plex/chromium-profile", text)
        self.assertIn("Local Storage", text)
        self.assertIn("IndexedDB", text)
        self.assertIn("Network/Cookies", text)
        self.assertIn("BACKUP_DIR", text)
        self.assertIn("rollback()", text)
        self.assertIn("Current Session", text)
        self.assertIn("Current Tabs", text)
        self.assertIn("Last Session", text)
        self.assertIn("Last Tabs", text)
        self.assertNotIn("--restore-last-session", text)

    def test_apply_refuses_to_copy_while_chromium_is_running(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("pgrep -u", text)
        self.assertIn("Chromium is still running", text)

    def test_script_never_touches_services_or_audio(self):
        text = SCRIPT.read_text(encoding="utf-8").lower()
        self.assertNotIn("systemctl", text)
        self.assertNotIn("shairport", text)
        self.assertNotIn("alsa", text)
        self.assertNotIn("install-master-eq", text)


if __name__ == "__main__":
    unittest.main()
