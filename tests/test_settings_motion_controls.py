from __future__ import annotations

import unittest
from pathlib import Path

from app.settings_unified import VALID_TRANSITIONS


ROOT = Path(__file__).resolve().parents[1]
DISPLAY_JS = ROOT / "app" / "static" / "js" / "settings-display-sections.js"
SETTINGS_IPAD_JS = ROOT / "app" / "static" / "js" / "settings-ipad.js"
PREFERENCES_JS = ROOT / "app" / "static" / "js" / "dashboard-preferences-bootstrap.js"


class SettingsMotionControlsTests(unittest.TestCase):
    def test_backend_accepts_every_transition_supported_by_dashboard(self):
        expected = {
            "grow-fade",
            "crossfade",
            "horizontal-slide",
            "vertical-lift",
            "cover-reveal",
            "zoom",
            "blur-dissolve",
            "instant",
        }
        self.assertTrue(expected.issubset(VALID_TRANSITIONS))

    def test_settings_restores_all_eight_motion_choices_before_custom_selects(self):
        source = DISPLAY_JS.read_text(encoding="utf-8")
        for value in (
            "grow-fade",
            "crossfade",
            "horizontal-slide",
            "vertical-lift",
            "cover-reveal",
            "zoom",
            "blur-dissolve",
            "instant",
        ):
            self.assertIn(f"['{value}',", source)
        self.assertIn("style.replaceChildren", source)

    def test_transition_duration_is_restored_as_slider_without_default_range_clamp(self):
        source = DISPLAY_JS.read_text(encoding="utf-8")
        self.assertIn("const currentValue = String(duration.value ?? '').trim()", source)
        self.assertIn("duration.min = '0'", source)
        self.assertIn("duration.max = '2000'", source)
        self.assertIn("duration.step = '50'", source)
        self.assertIn("duration.type = 'range'", source)
        self.assertIn("duration.value = currentValue", source)
        self.assertLess(source.index("duration.max = '2000'"), source.index("duration.type = 'range'"))
        self.assertLess(source.index("duration.step = '50'"), source.index("duration.type = 'range'"))
        self.assertLess(source.index("duration.type = 'range'"), source.index("duration.value = currentValue"))
        self.assertIn("duration.removeAttribute('data-keyboard')", source)

    def test_transition_duration_has_visible_exact_value_and_hydration_repaint(self):
        settings = (ROOT / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
        client = SETTINGS_IPAD_JS.read_text(encoding="utf-8")

        self.assertIn('data-setting-output="display.transition_duration_ms"', settings)
        self.assertIn("path === 'display.transition_duration_ms'", client)
        self.assertIn("Math.round(number)", client)
        self.assertIn("window.ACPSettingsRangeTheme?.refresh?.()", client)

    def test_autosaved_display_settings_project_into_long_lived_shell(self):
        source = SETTINGS_IPAD_JS.read_text(encoding="utf-8")
        self.assertIn("function syncLiveShellSettings(settings)", source)
        self.assertIn("window.ACPDashboardPreferences?.write?.({", source)
        self.assertIn("transitionStyle: display.transition_style", source)
        self.assertIn("transitionDurationMs: display.transition_duration_ms", source)
        self.assertIn("syncLiveShellSettings(loadedSettings)", source)
        self.assertIn("acp:settings-saved", source)

    def test_dashboard_preferences_read_live_values_after_bootstrap(self):
        source = PREFERENCES_JS.read_text(encoding="utf-8")
        self.assertIn("root.dataset.transitionStyle || root.dataset.serverTransitionStyle", source)
        self.assertIn("root.dataset.transitionDurationMs || root.dataset.serverTransitionDurationMs", source)
        self.assertIn("root.dataset.clockFormat || root.dataset.serverClockFormat", source)
        self.assertIn("root.dataset.startupMode || root.dataset.serverStartupMode", source)
        self.assertIn("root.dataset.idleReturnMode || root.dataset.serverIdleReturnMode", source)


if __name__ == "__main__":
    unittest.main()
