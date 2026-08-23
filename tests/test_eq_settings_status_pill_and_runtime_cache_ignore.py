from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class EqSettingsStatusPillAndRuntimeCacheIgnoreTests(unittest.TestCase):
    def test_master_equaliser_health_uses_pill_styling_and_top_right_layout(self) -> None:
        css = (ROOT / "app" / "static" / "css" / "audio-eq.css").read_text(encoding="utf-8")

        self.assertIn(".acp-eq-settings > .settings-card-heading {", css)
        self.assertIn("display: flex", css)
        self.assertIn("align-items: flex-start", css)
        self.assertIn("justify-content: space-between", css)
        self.assertIn(".acp-eq-health,\n#acp-eq-settings-health {", css)
        self.assertIn("border-radius: 999px", css)
        self.assertIn("#acp-eq-settings-health {", css)
        self.assertIn("flex: 0 0 auto", css)
        self.assertIn("align-self: flex-start", css)
        self.assertIn("white-space: nowrap", css)
        self.assertIn("#acp-eq-settings-health.is-ready", css)
        self.assertIn("#acp-eq-settings-health.is-warning", css)

    def test_lifetime_rainfall_cache_is_ignored_runtime_state(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

        self.assertIn("weather-rainfall-history.json", gitignore)
        self.assertIn("weather-rainfall-lifetime.json", gitignore)


if __name__ == "__main__":
    unittest.main()
