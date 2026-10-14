"""No-side-effect parity gates for the future *Python* ACP night authority."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys
import unittest
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app/squeekboard_night_schedule_plan.py"
spec = importlib.util.spec_from_file_location("acp_squeekboard_night_schedule_plan_test", SOURCE)
assert spec and spec.loader
plan = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = plan
spec.loader.exec_module(plan)
UK = ZoneInfo("Europe/London")


class C3ReadOnlyScheduleParityTests(unittest.TestCase):
    @staticmethod
    def display(start="22:00", end="07:00", enabled=True):
        return {
            "night_dim_enabled": enabled,
            "night_dim_start": start,
            "night_dim_end": end,
        }

    def at(self, hour, minute=0, *, day=14, month=10, year=2026, fold=0):
        return datetime(year, month, day, hour, minute, tzinfo=UK, fold=fold)

    def check(self, settings, moment, *, alarm=False, preview=False):
        return plan.schedule_plan(settings, moment, alarm_visible=alarm,
                                  preview_active=preview)

    def test_overnight_start_inclusive_end_exclusive(self):
        settings = self.display()
        for hour, minute, expect in (
            (21, 59, False), (22, 0, True), (23, 59, True),
            (0, 0, True), (6, 59, True), (7, 0, False),
            (7, 1, False),
        ):
            with self.subTest(hour=hour, minute=minute):
                result = self.check(settings, self.at(hour, minute))
                self.assertEqual(result.scheduled, expect)
                self.assertEqual(result.active, expect)

    def test_daytime_non_wrapping_window(self):
        cfg = self.display("09:30", "17:15")
        for minute, expect in ((9 * 60 + 29, False), (570, True),
                               (17 * 60 + 14, True), (17 * 60 + 15, False)):
            with self.subTest(minute=minute):
                out = self.check(cfg, self.at(minute // 60, minute % 60))
                self.assertEqual(out.scheduled, expect)

    def test_equal_start_and_end_means_full_day_only_when_enabled(self):
        cfg = self.display("06:45", "06:45")
        for hour in (0, 6, 7, 13, 23):
            self.assertTrue(self.check(cfg, self.at(hour)).active)
        cfg["night_dim_enabled"] = False
        self.assertFalse(self.check(cfg, self.at(13)).active)

    def test_explicit_alarm_suppression_does_not_lie_about_schedule(self):
        out = self.check(self.display(), self.at(23), alarm=True)
        self.assertTrue(out.scheduled)
        self.assertFalse(out.active)
        self.assertTrue(out.alarm_visible)
        self.assertEqual(out.reason, "alarm suppresses night")

    def test_preview_is_ephemeral_explicit_browser_input_not_derived_from_schedule(self):
        cfg = self.display(enabled=False)
        day = self.at(14)
        out = self.check(cfg, day, preview=True)
        self.assertFalse(out.scheduled)
        self.assertTrue(out.preview)
        self.assertTrue(out.active)
        suppressed = self.check(cfg, day, preview=True, alarm=True)
        self.assertFalse(suppressed.active)
        self.assertFalse(self.check(cfg, day).active)

    def test_europe_london_bst_and_gmt_injected_utc_instants(self):
        cfg = self.display("01:15", "02:15")
        # 2026-10-25: the local 01:30 occurs twice across fall-back.
        first = datetime(2026, 10, 25, 1, 30, tzinfo=UK, fold=0)
        second = datetime(2026, 10, 25, 1, 30, tzinfo=UK, fold=1)
        self.assertNotEqual(first.utcoffset(), second.utcoffset())
        for instant in (first, second, first.astimezone(timezone.utc),
                        second.astimezone(timezone.utc)):
            with self.subTest(instant=instant):
                result = self.check(cfg, instant)
                self.assertTrue(result.active)
                self.assertEqual(result.local_clock[:16], "2026-10-25 01:30")
        self.assertIn("BST", self.check(cfg, first).local_clock)
        self.assertIn("GMT", self.check(cfg, second).local_clock)

    def test_spring_forward_uses_observed_local_minutes_only(self):
        cfg = self.display("01:15", "02:15")
        # Europe/London jumps 01:00 GMT -> 02:00 BST on 2026-03-29.
        before = datetime(2026, 3, 29, 0, 59, tzinfo=timezone.utc)
        after = datetime(2026, 3, 29, 1, 0, tzinfo=timezone.utc)
        self.assertFalse(self.check(cfg, before).active)
        self.assertTrue(self.check(cfg, after).active)
        self.assertIn("02:00 BST", self.check(cfg, after).local_clock)

    def test_all_inputs_validated_fail_closed(self):
        cfg = self.display()
        invalid = (
            dict(cfg, night_dim_enabled=1),
            dict(cfg, night_dim_start="25:00"),
            dict(cfg, night_dim_end="7:00"),
            dict(cfg, night_dim_end="11:60"),
            dict(cfg, night_dim_start="22:00; rm -rf ."),
            {"night_dim_enabled": True},
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.check(value, self.at(23))
        with self.assertRaises(ValueError):
            self.check(cfg, datetime(2026, 10, 14, 23))
        with self.assertRaises(ValueError):
            plan.schedule_plan(cfg, self.at(23), alarm_visible=1)
        with self.assertRaises(ValueError):
            plan.schedule_plan(cfg, self.at(23), alarm_visible=False,
                               preview_active=1)

    def test_readonly_model_mirrors_exact_js_contract_without_any_service_or_css_io(self):
        js = (ROOT / "app/static/js/display-dimming.js").read_text()
        module = SOURCE.read_text()
        self.assertIn("if (start === end) return true", js)
        self.assertIn("if (start < end) return current >= start && current < end", js)
        self.assertIn("return current >= start || current < end", js)
        self.assertIn("return !alarmVisible() && (scheduledNow() || previewing())", js)
        self.assertIn('ZoneInfo("Europe/London")', module)
        self.assertIn("return current >= start or current < end", module)
        self.assertNotIn("systemctl", module)
        self.assertNotIn("subprocess", module)
        self.assertNotIn("style.css", module)
        self.assertNotIn("flask", module.lower())
        self.assertNotIn("window.", module)


if __name__ == "__main__":
    unittest.main()
