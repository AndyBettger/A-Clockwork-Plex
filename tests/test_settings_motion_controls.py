from __future__ import annotations

import unittest
from pathlib import Path

from app.settings_unified import VALID_TRANSITIONS


ROOT = Path(__file__).resolve().parents[1]
SETTINGS_TEMPLATE = ROOT / "app" / "templates" / "settings.html"
DISPLAY_JS = ROOT / "app" / "static" / "js" / "settings-display-sections.js"
SETTINGS_IPAD_JS = ROOT / "app" / "static" / "js" / "settings-ipad.js"
SETTINGS_SELECTS_JS = ROOT / "app" / "static" / "js" / "settings-selects.js"
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
            "spatial-row",
            "instant",
        }
        self.assertTrue(expected.issubset(VALID_TRANSITIONS))

    def test_settings_exposes_all_nine_motion_choices_before_hydration(self):
        template = SETTINGS_TEMPLATE.read_text(encoding="utf-8")
        source = DISPLAY_JS.read_text(encoding="utf-8")
        values = (
            "grow-fade",
            "crossfade",
            "horizontal-slide",
            "vertical-lift",
            "cover-reveal",
            "zoom",
            "blur-dissolve",
            "spatial-row",
            "instant",
        )
        for value in values:
            self.assertIn(f'<option value="{value}">', template)
            self.assertIn(f"['{value}',", source)
        self.assertNotIn("style.replaceChildren", source)
        self.assertIn("style.appendChild(option)", source)

    def test_settings_hydration_preserves_unlisted_saved_select_values(self):
        client = SETTINGS_IPAD_JS.read_text(encoding="utf-8")
        selects = SETTINGS_SELECTS_JS.read_text(encoding="utf-8")

        self.assertIn("function ensureSavedSelectOption(control, value)", client)
        self.assertIn("option.dataset.settingsSnapshotValue = 'true'", client)
        self.assertIn("Current saved value", client)
        self.assertIn("function applyControlValue(control, value)", client)
        self.assertIn("function hydrateControls(root, settings", client)
        self.assertIn("acp:settings-hydrated", client)
        self.assertIn("acp:settings-hydrated", selects)
        self.assertIn("applyControlValue", client)
        self.assertIn("hydrateControls", client)

    def test_page_and_navigation_durations_are_restored_as_independent_sliders(self):
        source = DISPLAY_JS.read_text(encoding="utf-8")
        settings = SETTINGS_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("['display.transition_duration_ms', '2000', '50'", source)
        self.assertIn("['display.navigation_transition_duration_ms', '1000', '20'", source)
        self.assertIn("['display.navigation_inactivity_seconds', '30', '1'", source)
        self.assertIn("const currentValue = String(duration.value ?? '').trim()", source)
        self.assertIn("duration.min = '0'", source)
        self.assertIn("duration.max = maximum", source)
        self.assertIn("duration.step = step", source)
        self.assertIn("duration.type = 'range'", source)
        self.assertIn("duration.value = currentValue", source)
        self.assertLess(source.index("duration.max = maximum"), source.index("duration.type = 'range'"))
        self.assertLess(source.index("duration.step = step"), source.index("duration.type = 'range'"))
        self.assertLess(source.index("duration.type = 'range'"), source.index("duration.value = currentValue"))
        self.assertIn("duration.removeAttribute('data-keyboard')", source)

        self.assertIn('data-setting-path="display.navigation_transition_duration_ms"', settings)
        self.assertIn('data-setting-output="display.navigation_transition_duration_ms"', settings)
        self.assertIn('data-setting-path="display.navigation_inactivity_seconds"', settings)
        self.assertIn('data-setting-output="display.navigation_inactivity_seconds"', settings)
        self.assertIn('data-setting-path="display.navigation_presentation"', settings)
        self.assertIn('<option value="overlay">Overlay content</option>', settings)
        self.assertIn('<option value="lift">Lift content</option>', settings)

    def test_transition_duration_has_visible_exact_value_and_hydration_repaint(self):
        settings = (ROOT / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
        client = SETTINGS_IPAD_JS.read_text(encoding="utf-8")

        self.assertIn('data-setting-output="display.transition_duration_ms"', settings)
        self.assertIn('data-setting-output="display.navigation_transition_duration_ms"', settings)
        self.assertIn('data-setting-output="display.navigation_inactivity_seconds"', settings)
        self.assertIn("'display.transition_duration_ms', 'display.navigation_transition_duration_ms'", client)
        self.assertIn("path === 'display.navigation_inactivity_seconds'", client)
        self.assertIn("seconds <= 0 ? 'Never'", client)
        self.assertIn("Math.round(number)", client)
        self.assertIn("window.ACPSettingsRangeTheme?.refresh?.()", client)

    def test_autosaved_display_settings_project_into_long_lived_shell(self):
        source = SETTINGS_IPAD_JS.read_text(encoding="utf-8")
        self.assertIn("function syncLiveShellSettings(settings)", source)
        self.assertIn("window.ACPDashboardPreferences?.write?.({", source)
        self.assertIn("transitionStyle: display.transition_style", source)
        self.assertIn("transitionDurationMs: display.transition_duration_ms", source)
        self.assertIn("navigationTransitionDurationMs: display.navigation_transition_duration_ms", source)
        self.assertIn("navigationInactivitySeconds: display.navigation_inactivity_seconds", source)
        self.assertIn("navigationPresentation: display.navigation_presentation", source)
        self.assertIn("syncLiveShellSettings(loadedSettings)", source)
        self.assertIn("acp:settings-saved", source)

    def test_dashboard_preferences_read_live_values_after_bootstrap(self):
        source = PREFERENCES_JS.read_text(encoding="utf-8")
        self.assertIn("root.dataset.transitionStyle || root.dataset.serverTransitionStyle", source)
        self.assertIn("root.dataset.transitionDurationMs || root.dataset.serverTransitionDurationMs", source)
        self.assertIn(
            "root.dataset.navigationTransitionDurationMs || root.dataset.serverNavigationTransitionDurationMs",
            source,
        )
        self.assertIn(
            "root.dataset.navigationInactivitySeconds || root.dataset.serverNavigationInactivitySeconds",
            source,
        )
        self.assertIn(
            "root.dataset.navigationPresentation || root.dataset.serverNavigationPresentation",
            source,
        )
        self.assertIn("normaliseNavigationInactivity", source)
        self.assertIn("normaliseNavigationPresentation", source)
        self.assertIn("--acp-navigation-transition-duration", source)
        self.assertIn("root.dataset.clockFormat || root.dataset.serverClockFormat", source)
        self.assertIn("root.dataset.startupMode || root.dataset.serverStartupMode", source)
        self.assertIn("root.dataset.idleReturnMode || root.dataset.serverIdleReturnMode", source)


if __name__ == "__main__":
    unittest.main()
