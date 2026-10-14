"""Read-only alarm presentation and Linux input parity for future C3 scheduler."""
from __future__ import annotations

from datetime import datetime, timedelta
import importlib.util
from pathlib import Path
import sys
import unittest
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app/squeekboard_night_observation_plan.py"
spec = importlib.util.spec_from_file_location("acp_squeekboard_night_observation_plan_test", SOURCE)
assert spec and spec.loader
model = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = model
spec.loader.exec_module(model)
UK = ZoneInfo("Europe/London")
NOW = datetime(2026, 10, 14, 3, 59, tzinfo=UK)


def payload(sequence: int):
    return {"screen": {"input_activity": {
        "authority": "linux-input-activity-monitor", "sequence": sequence,
        "last_activity_at": NOW.isoformat(timespec="milliseconds"),
    }}}


def observe(seq: int | None, baseline: int | None, **kwargs):
    defaults = dict(
        screen_snapshot=payload(seq) if seq is not None else None,
        last_sequence=baseline, now=NOW,
        night_enabled=True, night_scheduled=True,
        browser_alarm_visible=False, preview_until=None, wake_seconds=5,
    )
    defaults.update(kwargs)
    return model.linux_input_step(**defaults)


class C3NightObservationParityTests(unittest.TestCase):
    def test_browser_alarm_and_ringing_server_request_agree(self):
        d = model.alarm_observation(
            browser_alarm_visible=True, scheduler_status={
                "screen_required": True, "active_phase": "ringing",
            },
        )
        self.assertEqual(d.agreement, "agree")
        self.assertTrue(d.safe_for_shadow_suppression)
        self.assertTrue(d.browser_visible)

    def test_idle_alarm_agreement_does_not_suppress_night(self):
        d = model.alarm_observation(
            browser_alarm_visible=False, scheduler_status={
                "screen_required": False, "active_phase": "idle",
            },
        )
        self.assertTrue(d.safe_for_shadow_suppression)
        self.assertFalse(d.browser_visible)

    def test_alarm_request_is_not_proof_of_browser_presentation(self):
        for browser, server in ((False, True), (True, False)):
            with self.subTest(browser=browser, server=server):
                d = model.alarm_observation(
                    browser_alarm_visible=browser,
                    scheduler_status={"screen_required": server},
                )
                self.assertEqual(d.agreement, "disagree")
                self.assertFalse(d.safe_for_shadow_suppression)

    def test_unknown_alarm_presentation_or_status_never_claims_parity(self):
        for browser, status in (
            (None, {"screen_required": True}),
            (True, None),
            (True, {"active_phase": "ringing"}),
        ):
            d = model.alarm_observation(
                browser_alarm_visible=browser, scheduler_status=status,
            )
            self.assertEqual(d.agreement, "incomplete")
            self.assertFalse(d.safe_for_shadow_suppression)

    def test_bad_alarm_inputs_rejected_without_guessing(self):
        for browser, status in (
            (1, {"screen_required": True}),
            (True, {"screen_required": "true"}),
            (False, []),
        ):
            with self.subTest(browser=browser, status=status), \
                 self.assertRaises(ValueError):
                model.alarm_observation(
                    browser_alarm_visible=browser, scheduler_status=status,
                )

    def test_first_linux_activity_snapshot_only_sets_baseline(self):
        d = observe(41, None)
        self.assertEqual((d.next_sequence, d.action, d.wake_until),
                         (41, "initial-baseline", None))

    def test_higher_sequence_requests_bounded_wake_deadline(self):
        d = observe(45, 41)
        self.assertEqual(d.next_sequence, 45)
        self.assertEqual(d.action, "activity-observed")
        self.assertEqual(d.wake_until, NOW + timedelta(seconds=5))

    def test_same_sequence_never_resets_interaction_clock(self):
        d = observe(41, 41)
        self.assertEqual(d.action, "unchanged")
        self.assertIsNone(d.wake_until)

    def test_restarting_linux_monitor_rebaselines_without_false_wake(self):
        d = observe(0, 41)
        self.assertEqual(d.action, "device-sequence-reset")
        self.assertEqual(d.next_sequence, 0)
        self.assertIsNone(d.wake_until)

    def test_preview_tap_consumes_sequence_without_double_interaction(self):
        d = observe(42, 41, preview_until=NOW + timedelta(seconds=8))
        self.assertEqual(d.action, "preview-input-suppressed")
        self.assertEqual(d.next_sequence, 42)
        self.assertIsNone(d.wake_until)
        expired = observe(43, 42, preview_until=NOW - timedelta(milliseconds=1))
        self.assertEqual(expired.action, "activity-observed")

    def test_browser_poll_gates_do_not_advance_baseline(self):
        for changes in (
            dict(night_enabled=False),
            dict(browser_alarm_visible=True),
            dict(night_scheduled=False),
        ):
            with self.subTest(changes=changes):
                d = observe(None, 9, **changes)
                self.assertEqual((d.next_sequence, d.action, d.wake_until),
                                 (9, "poll-gated", None))
        # Browser explicitly refuses Linux-input polling during a disabled
        # schedule even if a local preview happens to have been requested.
        disabled_preview = observe(
            None, 9, night_enabled=False,
            preview_until=NOW + timedelta(seconds=8),
        )
        self.assertEqual(disabled_preview.action, "poll-gated")

    def test_preview_while_schedule_outside_window_may_poll_if_enabled(self):
        d = observe(
            50, 49, night_scheduled=False,
            preview_until=NOW + timedelta(seconds=8),
        )
        self.assertEqual(d.action, "preview-input-suppressed")
        self.assertEqual(d.next_sequence, 50)

    def test_defensive_rejection_of_missing_and_non_monotonic_data(self):
        bad_payloads = (
            None, {}, {"screen": None}, {"screen": {}},
            {"screen": {"input_activity": {"sequence": -1}}},
            {"screen": {"input_activity": {"sequence": 3.5}}},
            {"screen": {"input_activity": {"sequence": "7"}}},
            {"screen": {"input_activity": {"sequence": True}}},
        )
        for value in bad_payloads:
            with self.subTest(value=value), self.assertRaises(ValueError):
                observe(1, 0, screen_snapshot=value)

    def test_validation_of_clock_deadlines_wake_seconds_and_bool_inputs(self):
        cases = (
            {"now": datetime(2026, 10, 14, 3, 59)},
            {"preview_until": datetime(2026, 10, 14, 4, 0)},
            {"last_sequence": -1},
            {"last_sequence": True},
            {"night_enabled": 1},
            {"night_scheduled": None},
            {"browser_alarm_visible": "false"},
            {"wake_seconds": 4},
            {"wake_seconds": 301},
        )
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                observe(1, 0, **changes)

    def test_original_js_browser_input_and_alarm_contracts_still_match(self):
        js = (ROOT / "app/static/js/display-dimming.js").read_text()
        alarm = (ROOT / "app/alarm_runtime.py").read_text()
        activity = (ROOT / "app/input_activity.py").read_text()
        projection = (ROOT / "app/screen_projection_activity.py").read_text()
        self.assertIn("function alarmVisible()", js)
        self.assertIn("window.location.pathname === '/alarm'", js)
        self.assertIn("function pollLinuxInputActivity()", js)
        self.assertIn("lastInputSequence === null || sequence < lastInputSequence", js)
        self.assertIn("if (previewing()) return;", js)
        self.assertIn("interact(settings.wakeSeconds, 'linux-input-monitor')", js)
        self.assertIn('status["screen_required"] = bool(', alarm)
        self.assertIn('"sequence": self._sequence', activity)
        self.assertIn('"input_activity": input_activity', projection)

    def test_module_has_no_keyboard_css_service_or_network_side_effects(self):
        code = SOURCE.read_text()
        for forbidden in (
            "systemctl", "subprocess", "requests.", "urllib",
            "style.css", "G_RESOURCE_OVERLAYS", "os.system", "socket.",
            "flask", "os.environ", "Path(", "open(", "write_text(",
            "alarm_scheduler.status(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code)


if __name__ == "__main__":
    unittest.main()
