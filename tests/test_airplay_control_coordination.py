from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app" / "templates" / "airplay.html"
RUNNER = ROOT / "app" / "runner.py"
IDLE_RETURN = ROOT / "app" / "static" / "js" / "idle-return.js"
HOOK_INSTALLER = ROOT / "scripts" / "install-airplay-hooks.sh"


class AirPlayControlCoordinationTests(unittest.TestCase):
    def test_temporary_browser_coordinator_is_not_loaded(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("airplay-live.js", text)
        self.assertNotIn("airplay-control-coordinator.js", text)
        self.assertNotIn("airplay-pause-hold.js", text)
        self.assertNotIn("airplay-play-state-sync.js", text)
        self.assertNotIn("airplay-volume-hold.js", text)

    def test_runner_uses_application_state_hub_not_airplay_patch_layer(self):
        text = RUNNER.read_text(encoding="utf-8")
        self.assertIn("build_default_application_state_hub", text)
        self.assertIn("register_application_state_api", text)
        self.assertNotIn("register_airplay_coordination", text)

    def test_generic_idle_return_respects_held_airplay_session(self):
        text = IDLE_RETURN.read_text(encoding="utf-8")
        self.assertIn("statusPayload?.state?.airplay?.active === true", text)
        self.assertIn("held media sessions count as activity", text)

    def test_hook_installer_has_valid_shell_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(HOOK_INSTALLER)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_pause_hold_is_temporarily_owned_by_session_hook(self):
        text = HOOK_INSTALLER.read_text(encoding="utf-8")
        self.assertIn('WATCHDOG_SECONDS="\\${AIRPLAY_DASHBOARD_PAUSE_WATCHDOG_SECONDS:-600}"', text)
        self.assertIn("AirPlay paused/stopped with sender available", text)
        self.assertIn("HOLD_TOKEN_FILE", text)
        self.assertIn("hold_token_is_current", text)
        self.assertIn("AirPlay sender disconnected during pause hold", text)
        self.assertNotIn("dashboard pause heartbeat", text.lower())

    def test_hooks_never_restart_audio_services(self):
        text = HOOK_INSTALLER.read_text(encoding="utf-8")
        self.assertNotIn("systemctl stop plexamp", text)
        self.assertNotIn("systemctl start plexamp", text)
        self.assertNotIn("systemctl restart plexamp", text)
        self.assertNotIn("systemctl restart shairport-sync.service\n", text.split("Then run:")[0])


if __name__ == "__main__":
    unittest.main()
