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
BACKEND = ROOT / "app" / "settings_unified_scheduled.py"
EXAMPLE = ROOT / "config.example.json"


class DisplayDimmingTests(unittest.TestCase):
    def test_client_has_valid_javascript_syntax(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is not installed.")
        for path in (CLIENT, SETTINGS):
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

    def test_touch_to_wake_consumes_the_first_interaction(self):
        text = CLIENT.read_text(encoding="utf-8")
        self.assertIn("event.preventDefault()", text)
        self.assertIn("event.stopImmediatePropagation()", text)
        self.assertIn("clickBlockUntil", text)
        self.assertIn("wake()", text)
        self.assertNotIn("|| previewing() || alarmVisible()", text)

    def test_classic_and_astronomy_styles_are_explicit(self):
        client = CLIENT.read_text(encoding="utf-8")
        style = STYLE.read_text(encoding="utf-8")
        backend = BACKEND.read_text(encoding="utf-8")
        base = BASE.read_text(encoding="utf-8")
        self.assertIn("style: 'classic'", client)
        self.assertIn("night_dim_style", client)
        self.assertIn("acp-night-style-classic", client)
        self.assertIn("acp-night-style-astronomy", client)
        self.assertIn("body.acp-night-style-classic", style)
        self.assertIn("body.acp-night-style-astronomy", style)
        self.assertIn("grayscale(1) contrast(1.08)", style)
        self.assertNotIn("sepia(1)", style)
        self.assertNotIn("hue-rotate", style)
        self.assertIn('_NIGHT_DIM_STYLES = {"classic", "astronomy"}', backend)
        self.assertIn("data-night-dim-style", base)

    def test_settings_and_backend_share_the_full_dimming_model(self):
        settings = SETTINGS.read_text(encoding="utf-8")
        backend = BACKEND.read_text(encoding="utf-8")
        example = EXAMPLE.read_text(encoding="utf-8")
        for key in (
            "night_dim_enabled",
            "night_dim_start",
            "night_dim_end",
            "night_dim_level_percent",
            "night_dim_wake_seconds",
            "night_clock_mode",
            "night_burn_in_shift",
        ):
            self.assertIn(key, settings)
            self.assertIn(key, backend)
            self.assertIn(key, example)
        self.assertIn("night_dim_style", backend)

    def test_base_loads_global_dimming_before_page_content(self):
        text = BASE.read_text(encoding="utf-8")
        self.assertIn("display-dimming.js", text)
        self.assertIn("display-dimming.css", text)
        self.assertIn("acp-night-dim-overlay", text)
        self.assertLess(text.index("display-dimming.js"), text.index("<body"))


if __name__ == "__main__":
    unittest.main()
