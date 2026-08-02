from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "app" / "static" / "js" / "display-dimming.js"
STYLE = ROOT / "app" / "static" / "css" / "display-dimming.css"
BASE = ROOT / "app" / "templates" / "base.html"
SETTINGS = ROOT / "app" / "static" / "js" / "settings-completion.js"
INTERACTION_SETTINGS = ROOT / "app" / "static" / "js" / "settings-night-interaction.js"
BACKEND = ROOT / "app" / "settings_unified_scheduled.py"
EXAMPLE = ROOT / "config.example.json"


class DisplayDimmingTests(unittest.TestCase):
    def test_client_has_valid_javascript_syntax(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is not installed.")
        for path in (CLIENT, SETTINGS, INTERACTION_SETTINGS):
            result = subprocess.run(
                [node, "--check", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"{path}: {result.stderr}")

    def test_schedule_handles_daytime_and_cross_midnight_ranges(self):
        text = CLIENT.read_text(encoding="utf-8")
        self.assertIn("if (start < end) return current >= start && current < end", text)
        self.assertIn("return current >= start || current < end", text)
        self.assertIn("if (start === end) return true", text)

    def test_alarm_screen_is_never_dimmed(self):
        client = CLIENT.read_text(encoding="utf-8")
        style = STYLE.read_text(encoding="utf-8")
        self.assertIn("!alarmVisible()", client)
        self.assertIn('data-active-page="alarm"', style)
        self.assertIn("mode-alarm", style)
        self.assertIn("filter: none !important", style)

    def test_first_touch_keeps_night_mode_and_is_not_consumed(self):
        text = CLIENT.read_text(encoding="utf-8")
        self.assertIn("document.addEventListener('pointerdown', observeLocalInteraction, true)", text)
        self.assertIn("interact(settings.wakeSeconds, 'document-input')", text)
        self.assertNotIn("event.preventDefault()", text)
        self.assertNotIn("event.stopImmediatePropagation()", text)
        self.assertNotIn("clickBlockUntil", text)
        self.assertIn("dimRequired()", text)
        self.assertNotIn("!temporarilyAwake()", text)

    def test_plexamp_iframe_activity_uses_linux_input_monitor(self):
        text = CLIENT.read_text(encoding="utf-8")
        self.assertIn("pollLinuxInputActivity", text)
        self.assertIn("/api/screen/state?visible_surface=", text)
        self.assertIn("input_activity?.sequence", text)
        self.assertIn("'linux-input-monitor'", text)
        self.assertIn("window.setInterval(pollLinuxInputActivity, 1000)", text)

    def test_idle_and_interaction_levels_and_styles_are_separate(self):
        client = CLIENT.read_text(encoding="utf-8")
        backend = BACKEND.read_text(encoding="utf-8")
        example = EXAMPLE.read_text(encoding="utf-8")
        base = BASE.read_text(encoding="utf-8")
        settings = INTERACTION_SETTINGS.read_text(encoding="utf-8")
        for key in (
            "night_dim_active_level_percent",
            "night_dim_active_style",
        ):
            self.assertIn(key, client)
            self.assertIn(key, backend)
            self.assertIn(key, example)
            self.assertIn(key.replace("_", "-"), base)
            self.assertIn(key, settings)
        self.assertIn("activeLevelPercent: 35", client)
        self.assertIn("activeStyle: 'same'", client)
        self.assertIn("Night interaction brightness", settings)

    def test_classic_and_astronomy_styles_are_explicit_and_pure_red(self):
        client = CLIENT.read_text(encoding="utf-8")
        style = STYLE.read_text(encoding="utf-8")
        backend = BACKEND.read_text(encoding="utf-8")
        self.assertIn("style: 'classic'", client)
        self.assertIn("acp-night-style-classic", client)
        self.assertIn("acp-night-style-astronomy", client)
        self.assertIn("body.acp-night-style-classic", style)
        self.assertIn("body.acp-night-style-astronomy", style)
        self.assertIn("background: rgb(255, 0, 0)", style)
        self.assertIn("grayscale(1) brightness(var(--acp-night-brightness))", style)
        self.assertNotIn("sepia(1)", style)
        self.assertNotIn("hue-rotate", style)
        self.assertIn('_NIGHT_STYLES = {"classic", "astronomy"}', backend)

    def test_settings_and_backend_share_the_full_dimming_model(self):
        settings = SETTINGS.read_text(encoding="utf-8")
        interaction = INTERACTION_SETTINGS.read_text(encoding="utf-8")
        backend = BACKEND.read_text(encoding="utf-8")
        example = EXAMPLE.read_text(encoding="utf-8")
        for key in (
            "night_dim_enabled",
            "night_dim_start",
            "night_dim_end",
            "night_dim_level_percent",
            "night_dim_active_level_percent",
            "night_dim_wake_seconds",
            "night_clock_mode",
            "night_burn_in_shift",
        ):
            self.assertIn(key, settings + interaction)
            self.assertIn(key, backend)
            self.assertIn(key, example)
        self.assertIn("night_dim_style", backend)
        self.assertIn("night_dim_active_style", backend)

    def test_base_loads_global_dimming_before_page_content_and_settings_patch_last(self):
        text = BASE.read_text(encoding="utf-8")
        self.assertIn("display-dimming.js", text)
        self.assertIn("display-dimming.css", text)
        self.assertIn("acp-night-dim-overlay", text)
        self.assertIn("settings-night-interaction.js", text)
        self.assertLess(text.index("display-dimming.js"), text.index("<body"))
        self.assertLess(text.index("settings-display-sections.js"), text.index("settings-night-interaction.js"))


if __name__ == "__main__":
    unittest.main()
