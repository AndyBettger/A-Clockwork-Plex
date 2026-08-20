from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIO_EQ = ROOT / "app" / "static" / "css" / "audio-eq.css"
BASE = ROOT / "app" / "templates" / "base.html"


class AudioEqDaytimeThemeStateTests(unittest.TestCase):
    def test_non_classic_bypass_button_uses_selected_theme(self) -> None:
        css = AUDIO_EQ.read_text(encoding="utf-8")
        self.assertIn(
            '.acp-eq-button:is(.is-active, [aria-pressed="true"])',
            css,
        )
        self.assertIn("border-color: var(--accent-strong) !important;", css)
        self.assertIn("background: var(--accent-strong) !important;", css)
        self.assertIn("color: var(--acp-theme-contrast) !important;", css)
        self.assertIn("box-shadow: 0 0 14px var(--acp-theme-glow) !important;", css)

    def test_non_classic_bypassed_status_uses_selected_theme(self) -> None:
        css = AUDIO_EQ.read_text(encoding="utf-8")
        self.assertIn(".acp-eq-strip.is-bypassed .acp-eq-health", css)
        self.assertIn("color: var(--accent-strong) !important;", css)
        self.assertIn("border-color: var(--acp-theme-control-border) !important;", css)
        self.assertIn("box-shadow: 0 0 0.8rem var(--acp-theme-soft) !important;", css)

    def test_classic_dark_bypass_baseline_remains_amber(self) -> None:
        css = AUDIO_EQ.read_text(encoding="utf-8")
        self.assertIn(".acp-eq-button.is-active,", css)
        self.assertIn("color: #ffd38c;", css)
        self.assertIn("border-color: rgba(255, 193, 91, 0.55);", css)
        self.assertIn("background: rgba(78, 48, 11, 0.75);", css)

    def test_audio_eq_asset_is_cache_busted(self) -> None:
        base = BASE.read_text(encoding="utf-8")
        self.assertIn("css/audio-eq.css", base)
        self.assertIn("20260820-eq-bypass-theme-v1", base)


if __name__ == "__main__":
    unittest.main()
