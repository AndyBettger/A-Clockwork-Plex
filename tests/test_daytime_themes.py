from __future__ import annotations

import json
import unittest
from pathlib import Path

from app import settings_unified_scheduled


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "app" / "templates" / "base.html"
BOOTSTRAP = ROOT / "app" / "static" / "js" / "dashboard-preferences-bootstrap.js"
DISPLAY_SETTINGS = ROOT / "app" / "static" / "js" / "settings-display-sections.js"
THEMES = ROOT / "app" / "static" / "css" / "daytime-themes.css"
NIGHT = ROOT / "app" / "static" / "css" / "display-dimming.css"
CONFIG_EXAMPLE = ROOT / "config.example.json"

THEME_VALUES = (
    "classic_dark",
    "midnight_blue",
    "amber_terminal",
    "green_phosphor",
    "aubergine",
    "steel_cyan",
)


class DaytimeThemeTests(unittest.TestCase):
    def test_server_normaliser_accepts_curated_themes_and_falls_back_to_classic(self) -> None:
        self.assertEqual(settings_unified_scheduled._DAYTIME_THEMES, set(THEME_VALUES))
        for theme in THEME_VALUES:
            with self.subTest(theme=theme):
                self.assertEqual(settings_unified_scheduled._daytime_theme(theme), theme)
        self.assertEqual(settings_unified_scheduled._daytime_theme("mystery"), "classic_dark")

    def test_fresh_configuration_defaults_to_classic_dark(self) -> None:
        config = json.loads(CONFIG_EXAMPLE.read_text(encoding="utf-8"))
        self.assertEqual(config["dashboard"]["daytime_theme"], "classic_dark")

    def test_unified_settings_publishes_and_persists_daytime_theme(self) -> None:
        source = (ROOT / "app" / "settings_unified_scheduled.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count('"daytime_theme"'), 3)
        self.assertIn('dashboard.get("daytime_theme")', source)
        self.assertIn('source.get("daytime_theme")', source)

    def test_first_paint_bootstrap_owns_theme_dataset(self) -> None:
        base = BASE.read_text(encoding="utf-8")
        bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
        self.assertIn('data-server-daytime-theme="{{ config.dashboard.daytime_theme', base)
        self.assertIn("daytime-themes.css", base)
        self.assertIn("20260819-curated-themes-v1", base)
        self.assertIn("const daytimeThemes = new Set", bootstrap)
        self.assertIn("normaliseDaytimeTheme", bootstrap)
        self.assertIn("root.dataset.daytimeTheme", bootstrap)
        self.assertIn("root.dataset.serverDaytimeTheme", bootstrap)
        for theme in THEME_VALUES:
            self.assertIn(f"'{theme}'", bootstrap)

    def test_settings_replaces_placeholder_with_six_choice_live_preview(self) -> None:
        source = DISPLAY_SETTINGS.read_text(encoding="utf-8")
        self.assertIn('data-setting-path="display.daytime_theme"', source)
        self.assertIn("data-daytime-theme-setting", source)
        self.assertIn("ACPDashboardPreferences?.write?.({ daytimeTheme: select.value })", source)
        self.assertIn('data-action="discard-settings"', source)
        for theme, label in (
            ("classic_dark", "Classic Dark"),
            ("midnight_blue", "Midnight Blue"),
            ("amber_terminal", "Amber Terminal"),
            ("green_phosphor", "Green Phosphor"),
            ("aubergine", "Aubergine"),
            ("steel_cyan", "Steel Cyan"),
        ):
            self.assertIn(f"['{theme}', '{label}']", source)
        self.assertNotIn("deliberately deferred until after the guarded production-EQ phase", source)

    def test_non_classic_palettes_exclude_plexamp_and_leave_v3_geometry_untouched(self) -> None:
        css = THEMES.read_text(encoding="utf-8")
        for theme in THEME_VALUES[1:]:
            self.assertIn(f'html[data-daytime-theme="{theme}"] body:not([data-active-page="plexamp"])', css)
        self.assertIn(':not([data-daytime-theme="classic_dark"])', css)
        self.assertNotIn('html[data-daytime-theme="classic_dark"] body', css)
        self.assertIn("selected V3 14-segment geometry stays untouched", css)
        self.assertNotIn(".persistent-plexamp-frame", css)

    def test_night_modes_compose_over_the_selected_daytime_palette(self) -> None:
        theme_css = THEMES.read_text(encoding="utf-8")
        night_css = NIGHT.read_text(encoding="utf-8")
        self.assertIn("Classic Dark deliberately has no override block", theme_css)
        self.assertIn("Scheduled Classic night dimming is a black overlay", theme_css)
        self.assertIn("Astronomy", theme_css)
        self.assertIn("body.acp-night-style-classic #acp-night-dim-overlay", night_css)
        self.assertIn("background: #000;", night_css)
        self.assertIn("body.acp-night-style-astronomy #acp-night-dim-overlay", night_css)
        self.assertIn("background: rgb(255, 0, 0);", night_css)
        self.assertIn("filter: grayscale(1) brightness(var(--acp-night-brightness));", night_css)


if __name__ == "__main__":
    unittest.main()
