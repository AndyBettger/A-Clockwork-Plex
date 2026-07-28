from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "app" / "static" / "js" / "screen-projection.js"
MODE_WATCH = ROOT / "app" / "static" / "js" / "mode-watch.js"
BASE = ROOT / "app" / "templates" / "base.html"
RUNNER = ROOT / "app" / "runner.py"


class ScreenProjectionUiTests(unittest.TestCase):
    def test_screen_projection_client_has_valid_javascript_syntax(self):
        result = subprocess.run(
            ["node", "--check", str(CLIENT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_client_uses_screen_authority_and_never_controls_audio(self):
        text = CLIENT.read_text(encoding="utf-8")
        self.assertIn("fetch('/api/screen/state'", text)
        self.assertIn("post('apply'", text)
        self.assertIn("recommended_screen", text)
        self.assertNotIn("/api/airplay/control", text)
        self.assertNotIn("/player/playback/", text)
        self.assertNotIn("systemctl", text)

    def test_cross_origin_plexamp_activity_has_safe_detection_paths(self):
        text = CLIENT.read_text(encoding="utf-8")
        self.assertIn("IdleDetector.requestPermission()", text)
        self.assertIn("document.activeElement === frame", text)
        self.assertIn("plexamp-frame-active-heartbeat", text)
        self.assertIn("new MutationObserver(observeOpenState)", text)
        self.assertNotIn("frame.contentDocument", text)
        self.assertNotIn("frame.contentWindow.document", text)

    def test_legacy_idle_return_is_not_loaded(self):
        text = BASE.read_text(encoding="utf-8")
        self.assertIn("js/screen-projection.js", text)
        self.assertIn("20260728-screen-lease", text)
        self.assertNotIn("js/idle-return.js", text)

    def test_mode_watch_defers_to_screen_projection_and_does_not_infer_playback(self):
        text = MODE_WATCH.read_text(encoding="utf-8")
        self.assertIn("ACPScreenProjection?.shouldDeferModeSync", text)
        self.assertNotIn("plexampIsPlaying", text)
        self.assertNotIn("reassertPlexampMode", text)
        self.assertNotIn("airplayActive", text)

    def test_real_runner_registers_screen_projection_before_state_apis(self):
        text = RUNNER.read_text(encoding="utf-8")
        projection = text.index("register_screen_projection(app, application_state_hub, dashboard)")
        state_api = text.index("register_application_state_api(app, application_state_hub)")
        self.assertLess(projection, state_api)


if __name__ == "__main__":
    unittest.main()
