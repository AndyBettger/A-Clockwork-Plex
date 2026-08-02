from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALARM = ROOT / "app" / "static" / "js" / "alarm-active.js"
DIM_STYLE = ROOT / "app" / "static" / "css" / "display-dimming.css"
SETTINGS = ROOT / "app" / "static" / "js" / "settings-completion.js"
SETTINGS_STYLE = ROOT / "app" / "static" / "css" / "settings-completion.css"
SAFE_LINKS = ROOT / "app" / "static" / "js" / "kiosk-safe-links.js"
SAFE_LINK_STYLE = ROOT / "app" / "static" / "css" / "kiosk-safe-links.css"
BASE = ROOT / "app" / "templates" / "base.html"


class SettingsPolishFollowupTests(unittest.TestCase):
    def test_new_clients_have_valid_javascript_syntax(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is not installed.")
        for path in (ALARM, SETTINGS, SAFE_LINKS):
            result = subprocess.run(
                [node, "--check", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"{path}: {result.stderr}")

    def test_night_overlay_filters_to_red_with_multiply_blending(self):
        text = DIM_STYLE.read_text(encoding="utf-8")
        self.assertIn("background: rgb(122, 0, 0)", text)
        self.assertIn("mix-blend-mode: multiply", text)
        self.assertIn('body[data-active-page="alarm"]', text)

    def test_alarm_page_uses_global_clock_format_without_24_hour_override(self):
        text = ALARM.read_text(encoding="utf-8")
        self.assertIn("window.ACPTime?.formatTime", text)
        self.assertIn("acp:clock-format-changed", text)
        self.assertNotIn("hour12: false", text)

    def test_forecast_last_fetched_uses_global_time_authority(self):
        text = SETTINGS.read_text(encoding="utf-8")
        self.assertIn("renderForecastFetchedTime", text)
        self.assertIn("window.ACPTime?.formatDateTime", text)
        self.assertIn("Last fetched ${formatted}", text)
        self.assertIn("acp:clock-format-changed", text)

    def test_settings_text_stacks_and_about_42_badge_are_explicit(self):
        client = SETTINGS.read_text(encoding="utf-8")
        style = SETTINGS_STYLE.read_text(encoding="utf-8")
        self.assertIn("settings-about-42-badge", client)
        self.assertIn("badge.textContent = '42'", client)
        self.assertIn("settings-about-message-row", style)
        self.assertIn("border-radius: 50%", style)
        self.assertIn(".setting-toggle > span > strong", style)
        self.assertIn("display: block", style)

    def test_external_links_require_a_deliberate_hold(self):
        client = SAFE_LINKS.read_text(encoding="utf-8")
        style = SAFE_LINK_STYLE.read_text(encoding="utf-8")
        base = BASE.read_text(encoding="utf-8")
        self.assertIn("HOLD_MS = 1400", client)
        self.assertIn("event.preventDefault()", client)
        self.assertIn("Press and hold to open externally", client)
        self.assertIn("window.open(url, '_blank'", client)
        self.assertIn("kiosk-safe-links.js", base)
        self.assertIn("kiosk-safe-links.css", base)
        self.assertIn("data-kiosk-link-hint", style)


if __name__ == "__main__":
    unittest.main()
