from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from pathlib import Path

from app.airplay_coordination import resolve_airplay_remote


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "app" / "runner.py"
COORDINATOR = ROOT / "app" / "static" / "js" / "airplay-control-coordinator.js"
HOOK_INSTALLER = ROOT / "scripts" / "install-airplay-hooks.sh"


class AirPlayStateResolutionTests(unittest.TestCase):
    def test_fresh_iphone_pause_beats_stale_mpris_playing(self):
        now = datetime.now()
        airplay = {
            "active": True,
            "started_at": (now - timedelta(minutes=2)).isoformat(),
            "metadata": {
                "last_event": "pause",
                "updated_at": (now - timedelta(seconds=2)).isoformat(),
            },
        }
        resolved = resolve_airplay_remote(
            airplay,
            {"available": True, "playback_status": "Playing"},
            now=now,
        )
        self.assertEqual(resolved["raw_playback_status"], "Playing")
        self.assertEqual(resolved["effective_playback_status"], "paused")
        self.assertEqual(resolved["playback_status_source"], "fresh-metadata-event")

    def test_newer_airplay_start_beats_stale_end_metadata(self):
        now = datetime.now()
        airplay = {
            "active": True,
            "started_at": now.isoformat(),
            "metadata": {
                "last_event": "active_state_end",
                "updated_at": (now - timedelta(milliseconds=200)).isoformat(),
            },
        }
        resolved = resolve_airplay_remote(
            airplay,
            {"available": True, "playback_status": "Paused"},
            now=now,
        )
        self.assertEqual(resolved["effective_playback_status"], "playing")
        self.assertEqual(resolved["playback_status_source"], "newer-session-start")

    def test_old_pause_event_does_not_override_current_mpris(self):
        now = datetime.now()
        airplay = {
            "active": True,
            "started_at": (now - timedelta(minutes=3)).isoformat(),
            "metadata": {
                "last_event": "pause",
                "updated_at": (now - timedelta(minutes=2)).isoformat(),
            },
        }
        resolved = resolve_airplay_remote(
            airplay,
            {"available": True, "playback_status": "Playing"},
            now=now,
        )
        self.assertEqual(resolved["effective_playback_status"], "playing")
        self.assertEqual(resolved["playback_status_source"], "mpris")

    def test_runner_registers_coordination_before_eq(self):
        text = RUNNER.read_text(encoding="utf-8")
        self.assertIn("register_airplay_coordination", text)
        self.assertLess(
            text.index("register_airplay_coordination(app)"),
            text.index("register_audio_eq(app)"),
        )

    def test_button_uses_effective_state_and_explicit_commands(self):
        text = COORDINATOR.read_text(encoding="utf-8")
        self.assertIn("effective_playback_status", text)
        self.assertIn("return 'pause'", text)
        self.assertIn("return 'play'", text)
        self.assertIn("JSON.stringify({ action })", text)
        self.assertNotIn("play_pause", text)
        self.assertNotIn("PlayPause", text)

    def test_start_hook_pauses_plexamp_before_publishing_airplay(self):
        text = HOOK_INSTALLER.read_text(encoding="utf-8")
        pause = text.index("$PLEXAMP_URL/player/playback/pause")
        start = text.index("$DASHBOARD_BASE/api/airplay/start")
        self.assertLess(pause, start)
        self.assertIn("cancelling stale handoffs", text)


if __name__ == "__main__":
    unittest.main()
