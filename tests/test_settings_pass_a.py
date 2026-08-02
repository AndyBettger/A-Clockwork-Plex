from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

from app.settings_unified_scheduled import _clock_card_slot_count


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "app" / "templates" / "base.html"
CLIENT = ROOT / "app" / "static" / "js" / "settings-pass-a.js"
STYLE = ROOT / "app" / "static" / "css" / "settings-pass-a.css"
SAFE_LINKS = ROOT / "app" / "static" / "js" / "kiosk-safe-links.js"
SCHEDULED_SETTINGS = ROOT / "app" / "settings_unified_scheduled.py"


class SettingsPassATests(unittest.TestCase):
    def test_new_clients_have_valid_javascript_syntax(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is not installed.")
        for path in (CLIENT, SAFE_LINKS):
            result = subprocess.run(
                [node, "--check", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"{path}: {result.stderr}")

    def test_clock_card_slot_groups_match_the_compact_clock_layout(self):
        current = [
            "outdoor_temp",
            "indoor_temp",
            "humidity",
            "indoor_humidity",
            "wind_speed",
            "wind_gust",
            "daily_rain",
            "event_rain",
            "pressure",
            "solar",
            "uv",
            "max_daily_gust",
            "barometer",
        ]
        self.assertEqual(_clock_card_slot_count(current), 8)
        self.assertEqual(
            _clock_card_slot_count(current + ["extra_ninth_slot"]),
            9,
        )

    def test_clock_card_limit_is_guarded_in_browser_and_backend(self):
        client = CLIENT.read_text(encoding="utf-8")
        backend = SCHEDULED_SETTINGS.read_text(encoding="utf-8")
        self.assertIn("MAX_CLOCK_CARD_SLOTS = 8", client)
        self.assertIn("button.disabled = blocked", client)
        self.assertIn("8 of ${MAX_CLOCK_CARD_SLOTS}", client)
        self.assertIn("_MAX_CLOCK_CARD_SLOTS = 8", backend)
        self.assertIn("Clock weather cards support at most", backend)

    def test_keyboard_scrolls_the_real_settings_detail_owner(self):
        client = CLIENT.read_text(encoding="utf-8")
        style = STYLE.read_text(encoding="utf-8")
        self.assertIn("target.closest('.settings-detail')", client)
        self.assertIn("detail.scrollBy", client)
        self.assertIn("--settings-keyboard-height", client)
        self.assertIn("body.keyboard-open .settings-detail", style)
        self.assertIn("scroll-padding-bottom", style)

    def test_first_paint_and_new_assets_are_wired(self):
        base = BASE.read_text(encoding="utf-8")
        self.assertIn('<html lang="en-GB" class="acp-document-booting"', base)
        self.assertIn("settings-pass-a.css", base)
        self.assertIn("settings-pass-a.js", base)
        self.assertIn("20260802-kiosk-address-panel", base)

    def test_external_navigation_is_forbidden_from_the_kiosk_client(self):
        client = SAFE_LINKS.read_text(encoding="utf-8")
        self.assertNotIn("window.open", client)
        self.assertIn("showExternalAddress", client)
        self.assertIn("Copy address", client)
        self.assertIn("The kiosk never leaves the dashboard", client)


if __name__ == "__main__":
    unittest.main()
