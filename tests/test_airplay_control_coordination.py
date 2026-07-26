from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app" / "templates" / "airplay.html"
RUNNER = ROOT / "app" / "runner.py"
IDLE_RETURN = ROOT / "app" / "static" / "js" / "idle-return.js"
HOOK_INSTALLER = ROOT / "scripts" / "install-airplay-hooks.sh"
COORDINATOR = ROOT / "app" / "playback_coordinator.py"
APPLICATION_STATE = ROOT / "app" / "application_state.py"
SHAIRPORT_SESSION = ROOT / "app" / "shairport_session.py"
CONFIG_EXAMPLE = ROOT / "config.example.json"
HOLD_HELPER = ROOT / "scripts" / "set-airplay-hold-seconds.py"


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
        application_text = APPLICATION_STATE.read_text(encoding="utf-8")
        self.assertIn('/api/playback/events', hook_text)
        self.assertIn('"event":"paused"', hook_text)
        self.assertIn("PlaybackCoordinator owns the configured hold", hook_text)
        self.assertNotIn("WATCHDOG_SECONDS", hook_text)
        self.assertNotIn("HOLD_TOKEN_FILE", hook_text)
        self.assertNotIn("hold_token_is_current", hook_text)
        self.assertIn("DEFAULT_AIRPLAY_HOLD_SECONDS = 600", coordinator_text)
        self.assertIn("configured_airplay_hold_seconds", application_text)
        self.assertIn("airplay_hold_seconds=hold_seconds", application_text)
        self.assertIn("playback-runtime.json", application_text)

    def test_pause_hold_duration_is_configurable_and_bounded(self):
        config = json.loads(CONFIG_EXAMPLE.read_text(encoding="utf-8"))
        self.assertEqual(config["airplay"]["pause_hold_seconds"], 600)
        application_text = APPLICATION_STATE.read_text(encoding="utf-8")
        helper_text = HOLD_HELPER.read_text(encoding="utf-8")
        self.assertIn("MIN_AIRPLAY_HOLD_SECONDS = 15", application_text)
        self.assertIn("MAX_AIRPLAY_HOLD_SECONDS = 86400", application_text)
        self.assertIn("MIN_SECONDS = 15", helper_text)
        self.assertIn("MAX_SECONDS = 86400", helper_text)
        self.assertIn("pause_hold_seconds", helper_text)

    def test_disconnect_is_polled_from_sender_not_play_end_hook(self):
        hook_text = HOOK_INSTALLER.read_text(encoding="utf-8")
        application_text = APPLICATION_STATE.read_text(encoding="utf-8")
        session_text = SHAIRPORT_SESSION.read_text(encoding="utf-8")
        self.assertNotIn("run_this_after_play_ends", hook_text)
        self.assertNotIn("session_timeout =", hook_text)
        self.assertIn("LEGACY_SESSION_END_WRAPPER", hook_text)
        self.assertIn('sudo rm -f "$LEGACY_SESSION_END_WRAPPER"', hook_text)
        self.assertIn("shairport_remote_status", application_text)
        self.assertIn("RemoteControl.Available", session_text)
        self.assertIn("mpris_service_available", session_text)
        self.assertIn("sender_available", session_text)

    def test_hooks_never_restart_audio_services(self):
        text = HOOK_INSTALLER.read_text(encoding="utf-8")
        self.assertNotIn("systemctl stop plexamp", text)
        self.assertNotIn("systemctl start plexamp", text)
        self.assertNotIn("systemctl restart plexamp", text)
        self.assertNotIn("systemctl restart shairport-sync.service\n", text.split("Then run:")[0])


if __name__ == "__main__":
    unittest.main()
