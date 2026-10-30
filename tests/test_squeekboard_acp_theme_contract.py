"""Read-only ACP/Squeekboard palette selection and Classic Dark default."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts/plan-squeekboard-acp-theme.py"
SPEC = importlib.util.spec_from_file_location("acp_c2_palette_contract", SRC)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
# dataclass reads sys.modules at creation time.
import sys
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class ACPSqueekboardThemeContractTests(unittest.TestCase):
    def test_classic_dark_is_default_and_unknown_palette_fallback(self):
        for supplied in ("", "not_a_theme", None, "Midnight Blue", [], {}):
            with self.subTest(supplied=supplied):
                decision = module.select_palette(supplied)
                self.assertEqual(decision.palette, "classic_dark")
                self.assertEqual(decision.daytime_theme, "classic_dark")
        self.assertEqual(module.FALLBACK_THEME, "classic_dark")

    def test_all_seven_daytime_palettes_resolve(self):
        for name in module.DAYTIME_THEMES:
            with self.subTest(name=name):
                d = module.select_palette(name, {"active": False})
                self.assertEqual(d.palette, name)
                self.assertFalse(d.night_active)
        self.assertEqual(len(module.DAYTIME_THEMES), 7)

    def test_scheduled_alone_is_not_actual_night_mode(self):
        d = module.select_palette("midnight_blue", {
            "scheduled": True, "effectiveStyle": "astronomy", "active": False,
            "interacting": True,
        })
        self.assertEqual(d.palette, "midnight_blue")
        self.assertFalse(d.interacting)

    def test_night_classic_idle_and_interaction(self):
        for name in module.DAYTIME_THEMES:
            with self.subTest(name=name):
                for interacting in (False, True):
                    d = module.select_palette(name, {
                        "active": True, "interacting": interacting,
                        "effectiveStyle": "classic",
                    })
                    suffix = "active" if interacting else "idle"
                    self.assertEqual(d.palette, f"{name}_night_classic_{suffix}")
                    self.assertEqual(d.interacting, interacting)

    def test_astronomy_idle_and_interaction_is_independent_of_day_palette(self):
        for day in ("classic_dark", "midnight_blue", "green_phosphor"):
            for interacting in (False, True):
                d = module.select_palette(day, {
                    "active": True, "interacting": interacting,
                    "effectiveStyle": "astronomy",
                })
                suffix = "active" if interacting else "idle"
                self.assertEqual(d.palette, "astronomy_night_" + suffix)

    def test_unknown_or_missing_night_style_fails_to_classic(self):
        d = module.select_palette("midnight_blue", {
            "active": True, "interacting": True, "effectiveStyle": "same",
        })
        self.assertEqual(d.palette, "midnight_blue_night_classic_active")
        self.assertEqual(
            module.select_palette("classic_dark", {"active": True}).palette,
            "classic_dark_night_classic_idle",
        )

    def test_selection_exactly_matches_palette_inventory(self):
        known = set(module.stylesheet_inventory())
        self.assertEqual(len(known), 23)
        generated = set()
        for name in module.DAYTIME_THEMES:
            generated.add(module.select_palette(name, {"active": False}).palette)
            for interacting in (False, True):
                for appearance in ("classic", "astronomy"):
                    generated.add(module.select_palette(name, {
                        "active": True, "interacting": interacting,
                        "effectiveStyle": appearance,
                    }).palette)
        self.assertEqual(known, generated)

    def test_no_runtime_keyboard_or_os_setting_changes(self):
        src = SRC.read_text(encoding="utf-8")
        for forbidden in ("systemd-run", "systemctl", "os.kill(", "pkill",
                          "gsettings set", "dpkg -i", "sudo ", "subprocess.Popen",
                          ".write_text(", ".unlink(", "requests.post("):
            self.assertNotIn(forbidden, src)
        js = (ROOT / "app/static/js/display-dimming.js").read_text(encoding="utf-8")
        for contract_field in ("active: dimRequired()", "interacting: interactionActive",
                               "effectiveStyle: effectiveStyle()"):
            self.assertIn(contract_field, js)
        ui = (ROOT / "app/static/js/settings-display-sections.js").read_text()
        self.assertIn("display.daytime_theme", ui)
        self.assertIn("'classic_dark'", ui)


if __name__ == "__main__":
    unittest.main()
