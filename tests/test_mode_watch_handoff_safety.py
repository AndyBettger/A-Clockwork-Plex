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

    def test_dashboard_recovery_reloads_the_persistent_plexamp_frame(self):
        text = MODE_WATCH.read_text(encoding="utf-8")
        self.assertIn("statusUnavailable = true", text)
        self.assertIn("const recoveredFromOutage = statusUnavailable;", text)
        self.assertIn("schedulePlexampFrameRecovery()", text)
        self.assertIn("persistent-plexamp-frame", text)
        self.assertIn("frame.setAttribute('src', source)", text)

    def test_recovery_reload_is_delayed_and_cancelled_on_page_exit(self):
        text = MODE_WATCH.read_text(encoding="utf-8")
        self.assertIn("}, 2500);", text)
        self.assertIn("window.clearTimeout(plexampRecoveryTimer)", text)
        self.assertIn("window.addEventListener('pagehide'", text)


if __name__ == "__main__":
    unittest.main()
