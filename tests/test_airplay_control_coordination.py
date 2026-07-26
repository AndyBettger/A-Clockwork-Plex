from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app" / "templates" / "airplay.html"
RUNNER = ROOT / "app" / "runner.py"
IDLE_RETURN = ROOT / "app" / "static" / "js" / "idle-return.js"
HOOK_INSTALLER = ROOT / "scripts" / "install-airplay-hooks.sh"
COORDINATOR = ROOT / "app" / "playback_coordinator.py"


class AirPlayControlCoordinationTests(unittest.TestCase):
    def test_temporary_browser_coordinator_is_not_loaded(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("airplay-live.js", text)
        self.assertNotIn("airplay-control-coordinator.js", text)
        self.assertNotIn("airplay-pause-hold.js", text)
        self.assertNotIn("airplay-play-state-sync.js", text)
        self.assertNotIn("airplay-volume-hold.js", text)

    def test_runner_starts_and_stops_playback_coordinator(self):
        text = RUNNER.read_text(encoding="utf-8")
        self.assertIn("build_default_application_state_hub", text)
        self.assertIn("playback_coordinator.start()", text)
        self.assertIn("playback_coordinator.shutdown()", text)
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

    def test_pause_hold_is_owned_by_playback_coordinator(self):
        hook_text = HOOK_INSTALLER.read_text(encoding="utf-8")
        coordinator_text = COORDINATOR.read_text(encoding="utf-8")
        self.assertIn('/api/playback/events', hook_text)
        self.assertIn('"event":"paused"', hook_text)
        self.assertIn("PlaybackCoordinator owns the 600s hold", hook_text)
        self.assertNotIn("WATCHDOG_SECONDS", hook_text)
        self.assertNotIn("HOLD_TOKEN_FILE", hook_text)
        self.assertNotIn("hold_token_is_current", hook_text)
        self.assertIn("DEFAULT_AIRPLAY_HOLD_SECONDS = 600", coordinator_text)
        self.assertIn("playback-runtime.json", (ROOT / "app" / "application_state.py").read_text(encoding="utf-8"))

    def test_hooks_never_restart_audio_services(self):
        text = HOOK_INSTALLER.read_text(encoding="utf-8")
        self.assertNotIn("systemctl stop plexamp", text)
        self.assertNotIn("systemctl start plexamp", text)
        self.assertNotIn("systemctl restart plexamp", text)
        self.assertNotIn("systemctl restart shairport-sync.service\n", text.split("Then run:")[0])


if __name__ == "__main__":
    unittest.main()
