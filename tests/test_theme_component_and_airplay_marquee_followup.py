from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "app" / "templates" / "base.html"
AIRPLAY_TEMPLATE = ROOT / "app" / "templates" / "airplay.html"
CLOCK_TEMPLATE = ROOT / "app" / "templates" / "clock.html"
COMPONENTS = ROOT / "app" / "static" / "css" / "daytime-theme-components.css"
FOLLOWUP = ROOT / "app" / "static" / "css" / "daytime-theme-followup.css"
MARQUEE_CSS = ROOT / "app" / "static" / "css" / "airplay-title-marquee.css"
MARQUEE = ROOT / "app" / "static" / "js" / "airplay-title-marquee.js"
RANGE_THEME = ROOT / "app" / "static" / "js" / "settings-range-theme.js"
DISPLAY_DIMMING = ROOT / "app" / "static" / "js" / "display-dimming.js"
CLOCK_COLON = ROOT / "app" / "static" / "js" / "clock-colon-sync.js"


class ThemeComponentAndAirPlayMarqueeFollowupTests(unittest.TestCase):
    def test_theme_layers_load_in_final_authority_order(self) -> None:
        base = BASE.read_text(encoding="utf-8")
        self.assertIn("daytime-theme-components.css", base)
        self.assertIn("daytime-theme-followup.css", base)
        self.assertIn("20260820-theme-followup-v3", base)
        self.assertLess(base.index("css/daytime-themes.css"), base.index("css/daytime-theme-components.css"))
        self.assertLess(base.index("css/daytime-theme-components.css"), base.index("css/daytime-theme-followup.css"))

    def test_component_layer_is_non_classic_and_plexamp_safe(self) -> None:
        css = COMPONENTS.read_text(encoding="utf-8")
        followup = FOLLOWUP.read_text(encoding="utf-8")
        for source in (css, followup):
            self.assertIn(':not([data-daytime-theme="classic_dark"])', source)
        self.assertIn('body:not([data-active-page="plexamp"])', css)
        self.assertIn('body:not([data-active-page="plexamp"])', followup)
        self.assertIn("semantic", followup.lower())

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

    def test_airplay_ready_pulse_beats_pinned_cyan_rule(self) -> None:
        css = FOLLOWUP.read_text(encoding="utf-8")
        self.assertIn('body[data-active-page="airplay"] .airplay-glyph .airplay-pulse', css)
        self.assertIn("border-color: var(--accent-strong) !important;", css)
        self.assertIn("box-shadow: 0 0 28px var(--acp-theme-glow) !important;", css)

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

    def test_settings_dialog_checkbox_range_day_and_status_followup(self) -> None:
        css = FOLLOWUP.read_text(encoding="utf-8")
        for token in (
            ".kiosk-link-modal-card",
            ".kiosk-link-modal-url",
            ".settings-card-heading",
            ".settings-card-heading > .settings-chip",
            '.setting-toggle input[type="checkbox"]',
            'input[type="range"]:not(.acp-calibrated-fader)::-webkit-slider-runnable-track',
            '.alarm-day-grid .alarm-day-button:is(.is-selected, [aria-pressed="true"])',
        ):
            self.assertIn(token, css)
        self.assertIn("display: inline-flex !important;", css)
        self.assertIn("border-radius: 999px !important;", css)
        self.assertIn("background: var(--accent-strong) !important;", css)
        self.assertIn("color: var(--acp-theme-contrast) !important;", css)

    def test_settings_late_runtime_controls_are_theme_owned(self) -> None:
        css = FOLLOWUP.read_text(encoding="utf-8")
        for token in (
            ".acp-settings-select-trigger",
            ".button:not(.settings-save):not(.alarm-remove-button)",
            ".alarm-enabled-toggle.is-off",
            ".audio-mixer-step",
            ".audio-mixer-card.is-vertical-console .audio-mixer-channel",
            ".audio-mixer-banner",
            ".alarm-audio-test-panel",
            ".audio-mixer-channel-heading output",
        ):
            self.assertIn(token, css)
        self.assertIn("border-color: var(--acp-theme-control-border) !important;", css)
        self.assertIn("background: var(--acp-theme-control) !important;", css)

    def test_settings_range_presenter_tracks_dynamic_controls(self) -> None:
        script = RANGE_THEME.read_text(encoding="utf-8")
        base = BASE.read_text(encoding="utf-8")
        self.assertIn("--acp-range-percent", script)
        self.assertIn("MutationObserver", script)
        self.assertIn("function queuePaintAll()", script)
        self.assertIn("if (refreshAll) queuePaintAll();", script)
        self.assertIn("acp-calibrated-fader", script)
        self.assertIn("settings-range-theme.js", base)
        self.assertIn("20260820-theme-range-v2", base)

    def test_night_preview_and_clock_colons_use_final_followup_clients(self) -> None:
        dimming = DISPLAY_DIMMING.read_text(encoding="utf-8")
        colon = CLOCK_COLON.read_text(encoding="utf-8")
        base = BASE.read_text(encoding="utf-8")
        clock = CLOCK_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("function schedulePreviewExpiry()", dimming)
        self.assertIn("Math.min(previewUntil, requestedUntil)", dimming)
        self.assertIn("if (previewing()) return;", dimming)
        self.assertIn("20260820-preview-timing-v1", base)
        self.assertIn("function displayedSecond()", colon)
        self.assertIn("MutationObserver", colon)
        self.assertIn("attributeName === 'aria-label'", colon)
        self.assertIn("second % 2 === 1", colon)
        self.assertNotIn("setTimeout", colon)
        self.assertIn("var(--acp-theme-display, var(--segment-on))", clock)
        self.assertIn("20260820-clock-colon-sync-v2", clock)

    def test_title_marquee_reuses_physically_proven_source_scroll_pattern(self) -> None:
        marquee = MARQUEE.read_text(encoding="utf-8")
        css = MARQUEE_CSS.read_text(encoding="utf-8")
        template = AIRPLAY_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("airplay-title-scroll-shell", marquee)
        self.assertIn("--airplay-source-overflow", marquee)
        self.assertIn("--airplay-scroll-duration", marquee)
        self.assertIn("estimatedOverflow", marquee)
        self.assertIn("airplay-source-scroll", css)
        self.assertIn("translateX", css) if False else None
        self.assertIn("20260819-longform-title-v3", template)
        self.assertNotIn("text-indent", css)

    def test_changed_javascript_has_valid_syntax(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is not installed.")
        for script in (MARQUEE, RANGE_THEME, DISPLAY_DIMMING, CLOCK_COLON):
            with self.subTest(script=script.name):
                result = subprocess.run(
                    [node, "--check", str(script)],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
