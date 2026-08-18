from __future__ import annotations

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
        self.assertIn("W: ['b', 'c', 'e', 'f', 'j', 'k']", source)
        self.assertNotIn("W: ['b', 'c', 'd', 'e', 'f', 'j', 'k']", source)


if __name__ == "__main__":
    unittest.main()
