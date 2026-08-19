from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "app" / "templates" / "base.html"
AIRPLAY_TEMPLATE = ROOT / "app" / "templates" / "airplay.html"
COMPONENTS = ROOT / "app" / "static" / "css" / "daytime-theme-components.css"
MARQUEE = ROOT / "app" / "static" / "js" / "airplay-title-marquee.js"


class ThemeComponentAndAirPlayMarqueeFollowupTests(unittest.TestCase):
    def test_component_theme_layer_loads_after_curated_palette(self) -> None:
        base = BASE.read_text(encoding="utf-8")
        self.assertIn("daytime-theme-components.css", base)
        self.assertIn("20260819-theme-components-v1", base)
        self.assertLess(
            base.index("css/daytime-themes.css"),
            base.index("css/daytime-theme-components.css"),
        )

    def test_component_layer_is_non_classic_and_plexamp_safe(self) -> None:
        css = COMPONENTS.read_text(encoding="utf-8")
        self.assertIn(':not([data-daytime-theme="classic_dark"])', css)
        self.assertIn('body:not([data-active-page="plexamp"])', css)
        self.assertNotIn('html[data-daytime-theme="classic_dark"] body', css)
        self.assertIn("Semantic warning/error colours", css)

    def test_weather_legacy_accents_follow_theme_variables(self) -> None:
        css = COMPONENTS.read_text(encoding="utf-8")
        for selector in (
            ".weather-forecast-scrollbar-thumb",
            ".rain-gauge span",
            ".barometer-reading-card.is-relative",
            ".barometer-forecast-card",
            ".barometer-forecast-graphic",
            ".compass",
        ):
            self.assertIn(selector, css)
        self.assertIn("linear-gradient(90deg, var(--accent), var(--accent-strong))", css)
        self.assertIn("linear-gradient(180deg, var(--accent-strong), var(--accent))", css)

    def test_airplay_ready_pulses_follow_selected_palette(self) -> None:
        css = COMPONENTS.read_text(encoding="utf-8")
        self.assertIn('body[data-active-page="airplay"] .airplay-pulse', css)
        self.assertIn("border-color: var(--accent);", css)
        self.assertIn("box-shadow: 0 0 22px var(--acp-theme-soft);", css)

    def test_audio_knobs_eq_and_calibrated_faders_are_theme_owned(self) -> None:
        css = COMPONENTS.read_text(encoding="utf-8")
        for token in (
            "--acp-eq-cyan: var(--accent)",
            ".nav-trim-knob::before",
            ".nav-trim-knob > span::before",
            "input.acp-calibrated-fader::-webkit-slider-runnable-track",
            "input.acp-calibrated-fader::-webkit-slider-thumb",
            "input.acp-calibrated-fader::-moz-range-progress",
            ".acp-eq-knob::before",
            ".acp-eq-settings-band input[type=\"range\"]",
        ):
            self.assertIn(token, css)

    def test_settings_dropdowns_statuses_alarm_enabled_and_about_are_theme_owned(self) -> None:
        css = COMPONENTS.read_text(encoding="utf-8")
        for token in (
            "[data-settings-sidebar-state]",
            ".acp-settings-select-menu",
            ".acp-settings-select-option.is-selected",
            ".alarm-enabled-toggle:not(.is-off)",
            "[data-settings-subpage=\"audio:trims\"] .settings-live-trim header output",
            ".settings-about-mark",
            ".settings-link-card",
        ):
            self.assertIn(token, css)
        self.assertIn("background: var(--accent-strong);", css)
        self.assertIn("color: var(--acp-theme-contrast);", css)

    def test_marquee_ignores_identical_status_repaints_and_is_cache_busted(self) -> None:
        marquee = MARQUEE.read_text(encoding="utf-8")
        template = AIRPLAY_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("lastMeasuredText", marquee)
        self.assertIn("lastMeasuredWidth", marquee)
        self.assertIn("text === lastMeasuredText && width === lastMeasuredWidth", marquee)
        self.assertIn("Do not reset the CSS", marquee)
        self.assertIn("20260819-longform-title-v2", template)

    def test_marquee_javascript_has_valid_syntax(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is not installed.")
        result = subprocess.run(
            [node, "--check", str(MARQUEE)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
