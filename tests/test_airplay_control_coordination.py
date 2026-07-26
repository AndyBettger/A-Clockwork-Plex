from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app" / "templates" / "airplay.html"
COORDINATOR = ROOT / "app" / "static" / "js" / "airplay-control-coordinator.js"
IDLE_RETURN = ROOT / "app" / "static" / "js" / "idle-return.js"
HOOK_INSTALLER = ROOT / "scripts" / "install-airplay-hooks.sh"


class AirPlayControlCoordinationTests(unittest.TestCase):
    def test_airplay_page_loads_one_playback_command_owner(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("airplay-control-coordinator.js", text)
        self.assertNotIn("airplay-pause-hold.js", text)
        self.assertNotIn("airplay-play-state-sync.js", text)
        self.assertNotIn("airplay-volume-hold.js", text)

    def test_visible_button_sends_explicit_idempotent_actions(self):
        text = COORDINATOR.read_text(encoding="utf-8")
        self.assertIn("return 'pause'", text)
        self.assertIn("return 'play'", text)
        self.assertIn("JSON.stringify({ action })", text)
        self.assertNotIn("play_pause", text)
        self.assertNotIn("PlayPause", text)

    def test_coordinator_blocks_legacy_bubbling_toggle_handler(self):
        text = COORDINATOR.read_text(encoding="utf-8")
        self.assertIn("event.stopImmediatePropagation()", text)
        self.assertIn("{ capture: true }", text)
        self.assertIn("applyAuthoritativeRemote(payload.remote)", text)

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

    def test_pause_hold_is_owned_by_session_hook_not_browser_heartbeat(self):
        text = HOOK_INSTALLER.read_text(encoding="utf-8")
        self.assertIn('WATCHDOG_SECONDS="\\${AIRPLAY_DASHBOARD_PAUSE_WATCHDOG_SECONDS:-600}"', text)
        self.assertIn("AirPlay paused/stopped with sender available", text)
        self.assertIn("HOLD_TOKEN_FILE", text)
        self.assertIn("hold_token_is_current", text)
        self.assertIn("AirPlay sender disconnected during pause hold", text)
        self.assertNotIn("last_change", text)
        self.assertNotIn("age <= 20", text)
        self.assertNotIn("dashboard pause heartbeat", text.lower())

    def test_hooks_never_restart_audio_services(self):
        text = HOOK_INSTALLER.read_text(encoding="utf-8")
        self.assertNotIn("systemctl stop plexamp", text)
        self.assertNotIn("systemctl start plexamp", text)
        self.assertNotIn("systemctl restart plexamp", text)
        self.assertNotIn("systemctl restart shairport-sync.service\n", text.split("Then run:")[0])


if __name__ == "__main__":
    unittest.main()
