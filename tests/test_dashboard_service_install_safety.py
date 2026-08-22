from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-dashboard-service.sh"
INSPECTOR = ROOT / "scripts" / "inspect-application-state.sh"
UNIT = ROOT / "systemd" / "a-clockwork-plex.service"


class DashboardServiceInstallSafetyTests(unittest.TestCase):
    def test_repository_unit_uses_runner_entrypoint(self):
        text = UNIT.read_text(encoding="utf-8")
        self.assertIn("app/runner.py", text)
        self.assertNotIn("app/main.py", text)

    def test_repository_unit_is_a_portable_template(self):
        text = UNIT.read_text(encoding="utf-8")
        self.assertIn("User=ACP_PROJECT_USER", text)
        self.assertIn("Group=ACP_PROJECT_USER", text)
        self.assertIn("WorkingDirectory=/ACP_PROJECT_DIR", text)
        self.assertNotIn("/home/andy", text)
        self.assertNotIn("User=andy", text)
        self.assertNotIn("Group=andy", text)

    def test_installer_defaults_to_check_only(self):
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('MODE="check"', text)
        self.assertIn('if [[ "$MODE" == "check" ]]', text)
        self.assertIn("Check-only mode", text)

    def test_apply_requires_explicit_confirmation(self):
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('CONFIRM_TOKEN="INSTALL-DASHBOARD-RUNNER"', text)
        self.assertIn('if [[ "$CONFIRM" != "$CONFIRM_TOKEN" ]]', text)

    def test_installer_renders_selected_project_user_and_repository_path(self):
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("--project-user", text)
        self.assertIn("EXPECTED_UNIT", text)
        self.assertIn('User=$PROJECT_USER', text)
        self.assertIn('Group=$PROJECT_USER', text)
        self.assertIn('WorkingDirectory=$ROOT_DIR', text)
        self.assertIn('$ROOT_DIR/venv/bin/python $ROOT_DIR/app/runner.py', text)
        self.assertIn('cmp -s "$EXPECTED_UNIT" "$TARGET_UNIT"', text)
        self.assertIn('systemd-analyze verify "$EXPECTED_UNIT"', text)
        self.assertIn('0644 "$EXPECTED_UNIT" "$TARGET_UNIT"', text)

    def test_installer_verifies_route_and_rolls_back(self):
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("/api/state", text)
        self.assertIn("rollback()", text)
        self.assertIn('sudo systemctl daemon-reload', text)
        self.assertIn('sudo systemctl restart "$SERVICE_NAME"', text)
        self.assertNotIn("restart plexamp", text.lower())
        self.assertNotIn("restart shairport", text.lower())

    def test_inspector_reports_stale_unit_and_repair_command(self):
        text = INSPECTOR.read_text(encoding="utf-8")
        self.assertIn("STALE OR MISSING", text)
        self.assertIn("install-dashboard-service.sh --apply", text)
        self.assertIn("FAIL: the running service does not expose /api/state", text)

    def test_shell_scripts_have_valid_syntax(self):
        for path in (INSTALLER, INSPECTOR):
            result = subprocess.run(
                ["bash", "-n", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"{path}: {result.stderr}")


if __name__ == "__main__":
    unittest.main()
