from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FinalClockUiPolishTests(unittest.TestCase):
    def test_audio_nav_button_matches_shared_button_typography(self) -> None:
        css = (ROOT / "app/static/css/audio-polish.css").read_text(encoding="utf-8")
        rule = re.search(r"\.nav-audio-button\s*\{(?P<body>[^}]*)\}", css, re.S)
        self.assertIsNotNone(rule)
        body = rule.group("body")
        self.assertIn("font-family: inherit;", body)
        self.assertIn("font-size: clamp(0.88rem, 2.05vmin, 1.05rem);", body)
        self.assertIn("font-weight: 700;", body)

    def test_zero_uses_slash_and_w_has_no_bottom_segment(self) -> None:
        source = (ROOT / "app/static/js/segment-display.js").read_text(encoding="utf-8")
        self.assertIn("'0': ['a', 'b', 'c', 'd', 'e', 'f', 'i', 'j']", source)
        self.assertIn("O: ['a', 'b', 'c', 'd', 'e', 'f']", source)
        self.assertIn("W: ['b', 'c', 'e', 'f', 'j', 'k']", source)
        self.assertNotIn("W: ['b', 'c', 'd', 'e', 'f', 'j', 'k']", source)

    def test_selected_version_three_segment_geometry_is_the_shared_runtime_source(self) -> None:
        source = (ROOT / "app/static/js/segment-display.js").read_text(encoding="utf-8")
        template = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")
        editable = (ROOT / "docs/airplay-segment-cell.svg").read_text(encoding="utf-8")

        self.assertIn(
            "m 17.001147,1.9000002 -1.240955,-1.40000004 -11.5231512,-4e-8",
            source,
        )
        self.assertIn(
            "M 9.8,16.000001 7.3,14.5 H 3.7 L 2.2,16.000001",
            source,
        )
        self.assertIn(
            "M 8.5,27.400001 10.000662,28.888992 11.5,27.400001",
            source,
        )
        self.assertIn("20260819-segment-v3", template)
        self.assertIn("selected Version 3 geometry", editable)
        self.assertIn("app/static/js/segment-display.js", editable)
        self.assertNotIn("app/static/js/airplay-mini-clock.js", editable)

    def test_clock_alarm_annunciator_uses_scheduler_next_occurrence(self) -> None:
        template = (ROOT / "app/templates/clock.html").read_text(encoding="utf-8")
        client = (ROOT / "app/static/js/clock-dashboard.js").read_text(encoding="utf-8")
        scheduler = (ROOT / "app/alarm_scheduler.py").read_text(encoding="utf-8")
        style = (ROOT / "app/static/css/clock-dashboard.css").read_text(encoding="utf-8")

        self.assertIn('id="clock-alarm-annunciator"', template)
        self.assertIn('<svg viewBox="0 0 64 64"', template)
        self.assertIn('transform="rotate(20 32 32)"', template)
        self.assertIn("M53 30 59 30", template)
        self.assertIn("ALARM_INDICATOR_WITHIN_MS = 12 * 60 * 60 * 1000", client)
        self.assertIn("status?.alarm_scheduler?.next_occurrence", client)
        self.assertIn("nextOccurrence?.scheduled_for", client)
        self.assertIn("nextOccurrence?.when", client)
        self.assertIn('"scheduled_for": scheduled.isoformat(timespec="seconds")', scheduler)
        self.assertIn("mode === 'any_future'", client)
        self.assertIn("'within_12h'", client)
        self.assertIn("bell.classList.toggle('is-active', state.active)", client)
        self.assertIn(".clock-alarm-annunciator.is-active", style)
        self.assertIn("color: var(--segment-on);", style)
        self.assertIn("opacity: 0.60;", style)
        self.assertIn("drop-shadow(0 0 2.8px currentColor)", style)
        self.assertNotIn("drop-shadow(0 0 11px currentColor)", style)
        self.assertNotIn("drop-shadow(0 0 20px currentColor)", style)
        self.assertIn("rgba(247, 249, 255, 0.055)", style)
        self.assertIn("pointer-events: none;", style)

    def test_clock_alarm_indicator_mode_is_a_unified_setting(self) -> None:
        settings_client = (ROOT / "app/static/js/settings-clock-cards.js").read_text(
            encoding="utf-8"
        )
        settings_backend = (ROOT / "app/settings_unified_scheduled.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("display.alarm_indicator_mode", settings_client)
        self.assertIn("Next alarm within 12 hours", settings_client)
        self.assertIn("Any future alarm", settings_client)
        self.assertIn('_ALARM_INDICATOR_MODES = {"within_12h", "any_future"}', settings_backend)
        self.assertIn('"alarm_indicator_mode": _alarm_indicator_mode(', settings_backend)

    def test_fresh_config_uses_twelve_hour_indicator_and_ten_percent_alarm_start(self) -> None:
        config = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
        self.assertEqual(config["dashboard"]["alarm_indicator_mode"], "within_12h")
        self.assertEqual(config["alarm"]["defaults"]["start_percent"], 10)
        self.assertEqual(config["alarm"]["alarms"][0]["volume"]["start_percent"], 10)


if __name__ == "__main__":
    unittest.main()
