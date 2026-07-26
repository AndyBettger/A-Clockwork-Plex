from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODE_WATCH = ROOT / "app" / "static" / "js" / "mode-watch.js"


class ModeWatchHandoffSafetyTests(unittest.TestCase):
    def test_airplay_start_cannot_be_overwritten_by_stale_plexamp_playing_state(self):
        text = MODE_WATCH.read_text(encoding="utf-8")
        self.assertIn("const airplayActive = status?.state?.airplay?.active === true;", text)
        self.assertIn("requestedMode === 'clock'", text)
        self.assertIn("&& !airplayActive", text)
        self.assertNotIn("requestedMode !== 'plexamp'", text)

    def test_dashboard_recovery_waits_for_the_real_plexamp_timeline(self):
        text = MODE_WATCH.read_text(encoding="utf-8")
        self.assertIn("fetch('/api/audio/live'", text)
        self.assertIn("payload?.live?.channels?.plexamp?.available === true", text)
        self.assertIn("if (await plexampPlayerReady())", text)
        self.assertIn("Date.now() - startedAt >= 60000", text)

    def test_ready_player_gets_a_hard_iframe_reconnect(self):
        text = MODE_WATCH.read_text(encoding="utf-8")
        self.assertIn("persistent-plexamp-frame", text)
        self.assertIn("frame.setAttribute('src', 'about:blank')", text)
        self.assertIn("target.searchParams.set('acp_reconnect'", text)
        self.assertIn("frame.setAttribute('src', target.toString())", text)

    def test_recovery_poll_is_cancelled_on_page_exit(self):
        text = MODE_WATCH.read_text(encoding="utf-8")
        self.assertIn("plexampRecoveryGeneration", text)
        self.assertIn("window.clearTimeout(plexampRecoveryTimer)", text)
        self.assertIn("window.addEventListener('pagehide'", text)


if __name__ == "__main__":
    unittest.main()
