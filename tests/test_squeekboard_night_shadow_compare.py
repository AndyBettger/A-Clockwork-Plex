"""Offline C3 shadow diagnostics never become a second keyboard controller."""
from __future__ import annotations

from datetime import datetime
import importlib.util
from pathlib import Path
import sys
import unittest
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
SOURCE = ROOT / "app/squeekboard_night_shadow_compare.py"
spec = importlib.util.spec_from_file_location("acp_c3_night_shadow_test", SOURCE)
assert spec and spec.loader
shadow = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = shadow
spec.loader.exec_module(shadow)
UK = ZoneInfo("Europe/London")
AT = datetime(2026, 10, 14, 23, 30, 20, tzinfo=UK)


def settings(**kwargs):
    return dict({
        "night_dim_enabled": True,
        "night_dim_start": "22:00",
        "night_dim_end": "07:00",
        "night_dim_style": "classic",
        "night_dim_active_style": "same",
        "night_dim_wake_seconds": 5,
    }, **kwargs)


def browser(**kwargs):
    return dict({
        "enabled": True, "start": "22:00", "end": "07:00",
        "style": "classic", "activeStyle": "same",
        "wakeSeconds": 5, "scheduled": True,
        "active": True, "previewing": False,
        "interacting": False, "effectiveStyle": "classic",
    }, **kwargs)


def snapshot(seq=5):
    return {"screen": {"input_activity": {"sequence": seq}}}


def check(**kwargs):
    base = {
        "server_settings": settings(),
        "browser_status": browser(),
        "browser_alarm_visible": False,
        "server_alarm_status": {"screen_required": False},
        "observed_at": AT,
    }
    base.update(kwargs)
    return shadow.compare(**base)


class NightShadowReadOnlyTests(unittest.TestCase):
    def test_agreement_without_input_snapshot_is_explicitly_inconclusive(self):
        result = check()
        self.assertEqual(result.verdict, "inconclusive")
        self.assertEqual(result.comparisons["scheduled"], "match")
        self.assertEqual(result.comparisons["active"], "match")
        self.assertEqual(result.comparisons["alarm_presentation"], "agree")
        self.assertEqual(result.comparisons["linux_input"], "unknown")
        self.assertIn("diagnostic-only", result.as_dict()["authority"])

    def test_agreement_with_input_baseline_is_observed_not_acted_on(self):
        result = check(screen_snapshot=snapshot(), prior_input_sequence=None)
        self.assertEqual(result.verdict, "match")
        self.assertEqual(result.comparisons["linux_input"], "initial-baseline")
        self.assertTrue(any("no wake scheduled" in l for l in result.limitations))

    def test_mismatched_schedule_flag_is_reported_not_overridden(self):
        result = check(browser_status=browser(scheduled=False, active=False))
        self.assertEqual(result.verdict, "mismatch")
        self.assertIn("scheduled", result.disagreements)
        self.assertIn("active", result.disagreements)

    def test_browser_settings_drift_makes_schedule_inconclusive(self):
        result = check(browser_status=browser(start="21:00"))
        self.assertEqual(result.comparisons["settings"], "mismatch")
        self.assertEqual(result.comparisons["scheduled"], "unknown")
        self.assertEqual(result.verdict, "mismatch")
        self.assertNotIn("active", result.disagreements)

    def test_alarm_requested_does_not_claim_browser_is_showing_it(self):
        result = check(server_alarm_status={"screen_required": True})
        self.assertEqual(result.comparisons["alarm_presentation"], "disagree")
        self.assertEqual(result.comparisons["active"], "unknown")
        self.assertEqual(result.verdict, "inconclusive")

    def test_browser_alarm_and_requested_alarm_agree_and_suppress(self):
        result = check(
            browser_alarm_visible=True,
            server_alarm_status={"screen_required": True},
            browser_status=browser(active=False),
            screen_snapshot=snapshot(),
        )
        self.assertEqual(result.verdict, "match")
        self.assertEqual(result.comparisons["active"], "match")
        self.assertEqual(result.comparisons["linux_input"], "poll-gated")

    def test_stale_browser_alarm_active_is_mismatch(self):
        result = check(
            browser_alarm_visible=True,
            server_alarm_status={"screen_required": True},
            browser_status=browser(active=True),
        )
        self.assertIn("active", result.disagreements)

    def test_same_browser_preview_is_accepted_only_as_explicit_state(self):
        cfg = settings(night_dim_enabled=False)
        b = browser(enabled=False, scheduled=False, previewing=True, active=True)
        result = check(server_settings=cfg, browser_status=b,
                       observed_at=datetime(2026, 10, 14, 14, tzinfo=UK),
                       screen_snapshot=snapshot(7), prior_input_sequence=6)
        self.assertEqual(result.comparisons["active"], "match")
        self.assertEqual(result.comparisons["linux_input"], "poll-gated")
        self.assertEqual(result.verdict, "match")

    def test_effective_style_is_checked_against_actual_browser_active_style(self):
        cfg = settings(night_dim_style="astronomy",
                       night_dim_active_style="classic")
        b = browser(style="astronomy", activeStyle="classic",
                    interacting=True, effectiveStyle="classic")
        self.assertEqual(check(server_settings=cfg, browser_status=b)
                         .comparisons["effective_style"], "match")
        wrong = browser(style="astronomy", activeStyle="classic",
                        interacting=True, effectiveStyle="astronomy")
        self.assertIn("effective_style", check(server_settings=cfg,
                                               browser_status=wrong).disagreements)

    def test_near_boundary_never_claims_schedule_parity(self):
        for hour, minute, sec in ((21, 59, 58), (22, 0, 2),
                                  (6, 59, 59), (7, 0, 1)):
            moment = datetime(2026, 10, 14, hour, minute, sec, tzinfo=UK)
            with self.subTest(moment=moment):
                result = check(observed_at=moment)
                self.assertEqual(result.comparisons["scheduled"], "unknown")
                self.assertEqual(result.comparisons["active"], "unknown")

    def test_normal_daytime_no_preview_stays_inactive(self):
        b = browser(scheduled=False, active=False)
        out = check(browser_status=b, observed_at=datetime(
            2026, 10, 14, 14, 30, tzinfo=UK,
        ), screen_snapshot=snapshot(3), prior_input_sequence=2)
        self.assertEqual(out.comparisons["scheduled"], "match")
        self.assertEqual(out.comparisons["active"], "match")
        self.assertEqual(out.comparisons["linux_input"], "poll-gated")

    def test_input_deltas_classified_without_extending_real_timer(self):
        out = check(screen_snapshot=snapshot(12), prior_input_sequence=11)
        self.assertEqual(out.comparisons["linux_input"], "activity-observed")
        self.assertEqual(out.verdict, "match")
        self.assertTrue(any("no wake scheduled" in x for x in out.limitations))

    def test_malformed_inputs_refused(self):
        bad = (
            {"browser_status": browser(active=1)},
            {"browser_status": browser(previewing="true")},
            {"browser_status": browser(wakeSeconds="5")},
            {"browser_status": browser(effectiveStyle="unknown")},
            {"browser_status": browser(style="../../etc")},
            {"observed_at": datetime(2026, 10, 14)},
            {"server_settings": settings(night_dim_wake_seconds=4)},
            {"browser_alarm_visible": None},
            {"server_alarm_status": {"screen_required": "ringing"}},
            {"screen_snapshot": {"screen": {"input_activity": {"sequence": -1}}}},
        )
        for item in bad:
            with self.subTest(item=item), self.assertRaises(ValueError):
                check(**item)

    def test_no_runtime_http_keyboard_css_or_settings_mutation(self):
        code = SOURCE.read_text()
        for forbidden in ("systemctl", "subprocess", "write_text(", "write_bytes(",
                          "style.css", "SQUEEKBOARD_KEYBOARDSDIR", "G_RESOURCE_OVERLAYS",
                          "requests.", "urllib", "socket.", "Flask(", "app.route(",
                          "fetch(", "os.environ", "open(", "json.dump("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code)


if __name__ == "__main__":
    unittest.main()
