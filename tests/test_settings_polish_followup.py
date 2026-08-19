from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALARM = ROOT / "app" / "static" / "js" / "alarm-active.js"
ALARM_TEMPLATE = ROOT / "app" / "templates" / "alarm.html"
DIM_STYLE = ROOT / "app" / "static" / "css" / "display-dimming.css"
SETTINGS = ROOT / "app" / "static" / "js" / "settings-completion.js"
DISPLAY_SECTIONS = ROOT / "app" / "static" / "js" / "settings-display-sections.js"
NIGHT_INTERACTION = ROOT / "app" / "static" / "js" / "settings-night-interaction.js"
SETTINGS_STYLE = ROOT / "app" / "static" / "css" / "settings-completion.css"
SAFE_LINKS = ROOT / "app" / "static" / "js" / "kiosk-safe-links.js"
SAFE_LINK_STYLE = ROOT / "app" / "static" / "css" / "kiosk-safe-links.css"
BASE = ROOT / "app" / "templates" / "base.html"


class SettingsPolishFollowupTests(unittest.TestCase):
    def test_new_clients_have_valid_javascript_syntax(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is not installed.")
        for path in (ALARM, SETTINGS, DISPLAY_SECTIONS, NIGHT_INTERACTION, SAFE_LINKS):
            result = subprocess.run(
                [node, "--check", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"{path}: {result.stderr}")

    def test_night_overlay_offers_classic_and_pure_red_astronomy_modes(self):
        text = DIM_STYLE.read_text(encoding="utf-8")
        self.assertIn("--acp-night-brightness", text)
        self.assertIn("grayscale(1) brightness(var(--acp-night-brightness))", text)
        self.assertNotIn("sepia(1)", text)
        self.assertNotIn("hue-rotate", text)
        self.assertIn("body.acp-night-style-classic", text)
        self.assertIn("body.acp-night-style-astronomy", text)
        self.assertIn("background: rgb(255, 0, 0)", text)
        self.assertIn("mix-blend-mode: multiply", text)
        self.assertIn('body[data-active-page="alarm"]', text)

    def test_display_is_split_into_four_main_subpages(self):
        client = DISPLAY_SECTIONS.read_text(encoding="utf-8")
        base = BASE.read_text(encoding="utf-8")
        for key in ("display:clock", "display:night", "display:theme", "display:motion"):
            self.assertIn(key, client)
        self.assertIn("Classic dim", client)
        self.assertIn("Astronomy red", client)
        self.assertIn('data-setting-path="display.night_dim_style"', client)
        self.assertIn('data-setting-path="display.night_dim_active_style"', client)
        self.assertIn("Same as idle", client)
        self.assertIn('data-setting-path="display.daytime_theme"', client)
        for label in (
            "Classic Dark",
            "Midnight Blue",
            "Amber Terminal",
            "Green Phosphor",
            "Aubergine",
            "Steel Cyan",
        ):
            self.assertIn(label, client)
        self.assertIn("Plexamp keeps its own appearance", client)
        self.assertIn("Classic dim darkens the selected daytime palette", client)
        self.assertIn("settings-display-sections.js", base)
        self.assertIn("daytime-themes.css", base)
        self.assertIn("settings-night-interaction.js", base)

    def test_alarm_page_uses_global_clock_format_without_24_hour_override(self):
        client = ALARM.read_text(encoding="utf-8")
        template = ALARM_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("window.ACPTime?.formatTime", client)
        self.assertIn("acp:clock-format-changed", client)
        self.assertNotIn("hour12: false", client)
        self.assertIn("js/acp-time.js", template)
        self.assertIn("data-server-clock-format", template)

    def test_forecast_last_fetched_uses_global_time_authority(self):
        text = SETTINGS.read_text(encoding="utf-8")
        self.assertIn("renderForecastFetchedTime", text)
        self.assertIn("window.ACPTime?.formatDateTime", text)
        self.assertIn("Last fetched ${formatted}", text)
        self.assertIn("acp:clock-format-changed", text)

    def test_forecast_time_authority_cannot_observe_its_own_output(self):
        text = SETTINGS.read_text(encoding="utf-8")
        self.assertNotIn("formattingForecastMessage", text)
        self.assertNotIn("new MutationObserver", text)
        self.assertIn("if (message.textContent !== nextText)", text)
        self.assertIn("message.dataset.acpForecastFetchedAt !== status.fetched_at", text)

    def test_settings_text_stacks_and_about_42_badge_are_explicit(self):
        client = SETTINGS.read_text(encoding="utf-8")
        style = SETTINGS_STYLE.read_text(encoding="utf-8")
        self.assertIn("settings-about-42-badge", client)
        self.assertIn("badge.textContent = '42'", client)
        self.assertIn("settings-about-mark", style)
        self.assertIn("settings-about-hero", style)
        self.assertIn("border-radius: 50%", style)
        self.assertIn(".setting-toggle > span > strong", style)
        self.assertIn(".settings-link-card > strong", style)
        self.assertIn("display: block", style)

    def test_external_links_never_leave_the_kiosk(self):
        client = SAFE_LINKS.read_text(encoding="utf-8")
        style = SAFE_LINK_STYLE.read_text(encoding="utf-8")
        base = BASE.read_text(encoding="utf-8")
        self.assertIn("HOLD_MS = 1400", client)
        self.assertIn("event.preventDefault()", client)
        self.assertIn("Press and hold to view the address", client)
        self.assertIn("kiosk-link-modal", client)
        self.assertIn("navigator.clipboard.writeText", client)
        self.assertNotIn("window.open", client)
        self.assertIn("The kiosk never leaves the dashboard", client)
        self.assertIn("kiosk-safe-links.js", base)
        self.assertIn("kiosk-safe-links.css", base)
        self.assertIn(".kiosk-link-modal", style)
        self.assertIn("data-kiosk-link-hint", style)


if __name__ == "__main__":
    unittest.main()