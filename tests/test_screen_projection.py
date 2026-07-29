from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from app.screen_projection import ScreenProjectionController


class FakePlayback:
    def __init__(self, state: dict) -> None:
        self.state = state

    def snapshot(self) -> dict:
        return {
            "current_screen": self.state["mode"],
            "active_source": self.state.get("active_source", "none"),
            "sources": {
                "alarm": {"active": self.state.get("alarm_active", False)},
            },
        }


class ScreenProjectionControllerTests(unittest.TestCase):
    def controller(self, *, idle_timeout: int = 30):
        now = [datetime(2026, 7, 28, 21, 0, tzinfo=timezone.utc)]
        state = {
            "mode": "plexamp",
            "active_source": "none",
            "alarm_active": False,
        }
        input_state = {
            "authority": "linux-input-activity-monitor",
            "running": True,
            "available": True,
            "sequence": 0,
            "last_activity_at": None,
            "last_event": None,
            "last_error": None,
        }
        playback = FakePlayback(state)
        applied: list[str] = []

        def set_mode(mode: str) -> None:
            applied.append(mode)
            state["mode"] = mode

        controller = ScreenProjectionController(
            load_config=lambda: {
                "dashboard": {
                    "idle_timeout_seconds": idle_timeout,
                    "default_mode": "clock",
                }
            },
            load_state=lambda _config: {"mode": state["mode"]},
            playback=playback,
            set_mode=set_mode,
            input_activity=lambda: dict(input_state),
            now_provider=lambda: now[0],
        )
        return controller, now, state, applied, input_state

    def test_quiet_manual_plexamp_returns_to_configured_idle_page_after_lease(self):
        controller, now, state, applied, _input = self.controller()
        controller.set_idle_return_mode("weather")
        opened = controller.interaction("plexamp", source="manual-open", manual=True)

        self.assertTrue(opened["lease"]["active"])
        self.assertEqual(opened["recommended_screen"], "plexamp")
        self.assertFalse(opened["should_apply"])

        now[0] += timedelta(seconds=31)
        expired = controller.snapshot()
        self.assertFalse(expired["lease"]["active"])
        self.assertEqual(expired["recommended_screen"], "weather")
        self.assertTrue(expired["should_apply"])

        applied_state = controller.apply()
        self.assertEqual(applied, ["weather"])
        self.assertEqual(state["mode"], "weather")
        self.assertEqual(applied_state["applied_screen"], "weather")

    def test_airplay_under_manual_plexamp_waits_for_lease_expiry(self):
        controller, now, state, _applied, _input = self.controller()
        state["active_source"] = "airplay"
        controller.interaction("plexamp", source="manual-open", manual=True)

        leased = controller.snapshot()
        self.assertEqual(leased["recommended_screen"], "plexamp")
        self.assertEqual(leased["decision_reason"], "manual-plexamp-lease")

        now[0] += timedelta(seconds=31)
        expired = controller.snapshot()
        self.assertEqual(expired["recommended_screen"], "airplay")
        self.assertEqual(expired["decision_reason"], "airplay-owns-audio")

    def test_settings_lease_overrides_active_audio_until_inactivity_timeout(self):
        controller, now, state, _applied, _input = self.controller()
        state["mode"] = "settings"
        state["active_source"] = "plexamp"

        opened = controller.interaction("settings", source="initial-settings-surface", manual=True)

        self.assertTrue(opened["lease"]["active"])
        self.assertEqual(opened["lease"]["manual_surface"], "settings")
        self.assertEqual(opened["recommended_screen"], "settings")
        self.assertEqual(opened["decision_reason"], "manual-settings-lease")
        self.assertFalse(opened["should_apply"])

        now[0] += timedelta(seconds=31)
        expired = controller.snapshot()
        self.assertFalse(expired["lease"]["active"])
        self.assertEqual(expired["recommended_screen"], "plexamp")
        self.assertEqual(expired["decision_reason"], "plexamp-playing")
        self.assertTrue(expired["should_apply"])

    def test_settings_touch_renews_lease_while_airplay_continues(self):
        controller, now, state, _applied, input_state = self.controller()
        state["mode"] = "settings"
        state["active_source"] = "airplay"
        controller.interaction("settings", source="initial-settings-surface", manual=True)
        now[0] += timedelta(seconds=25)
        input_state.update(
            {
                "sequence": 1,
                "last_activity_at": now[0].isoformat(timespec="milliseconds"),
                "last_event": {
                    "sequence": 1,
                    "kind": "absolute",
                    "device": "Touchscreen",
                },
            }
        )

        renewed = controller.snapshot()

        self.assertTrue(renewed["lease"]["active"])
        self.assertGreaterEqual(renewed["lease"]["remaining_seconds"], 29)
        self.assertEqual(renewed["recommended_screen"], "settings")
        self.assertEqual(
            renewed["lease"]["last_interaction_source"],
            "linux-input:absolute:Touchscreen",
        )

    def test_plexamp_playback_keeps_plexamp_after_manual_lease_expires(self):
        controller, now, state, _applied, _input = self.controller()
        controller.interaction("plexamp", source="manual-open", manual=True)
        state["active_source"] = "plexamp"
        now[0] += timedelta(seconds=90)

        snapshot = controller.snapshot()
        self.assertFalse(snapshot["lease"]["active"])
        self.assertEqual(snapshot["recommended_screen"], "plexamp")
        self.assertEqual(snapshot["decision_reason"], "plexamp-playing")
        self.assertFalse(snapshot["should_apply"])

    def test_alarm_immediately_overrides_manual_plexamp_lease(self):
        controller, _now, state, _applied, _input = self.controller()
        controller.interaction("plexamp", source="manual-open", manual=True)
        state["alarm_active"] = True

        snapshot = controller.snapshot()
        self.assertTrue(snapshot["lease"]["active"])
        self.assertEqual(snapshot["recommended_screen"], "alarm")
        self.assertEqual(snapshot["decision_reason"], "alarm-active")
        self.assertTrue(snapshot["should_apply"])

    def test_alarm_immediately_overrides_settings_lease(self):
        controller, _now, state, _applied, _input = self.controller()
        state["mode"] = "settings"
        state["active_source"] = "airplay"
        controller.interaction("settings", source="initial-settings-surface", manual=True)
        state["alarm_active"] = True

        snapshot = controller.snapshot()

        self.assertTrue(snapshot["lease"]["active"])
        self.assertEqual(snapshot["recommended_screen"], "alarm")
        self.assertEqual(snapshot["decision_reason"], "alarm-active")
        self.assertTrue(snapshot["should_apply"])

    def test_iframe_interaction_renews_manual_lease(self):
        controller, now, _state, _applied, _input = self.controller()
        controller.interaction("plexamp", source="manual-open", manual=True)
        now[0] += timedelta(seconds=25)
        renewed = controller.interaction("plexamp", source="plexamp-frame-focus")

        self.assertTrue(renewed["lease"]["active"])
        self.assertGreaterEqual(renewed["lease"]["remaining_seconds"], 29)
        self.assertEqual(renewed["lease"]["last_interaction_source"], "plexamp-frame-focus")

    def test_linux_touch_event_renews_manual_plexamp_lease(self):
        controller, now, _state, _applied, input_state = self.controller()
        controller.interaction("plexamp", source="manual-open", manual=True)
        now[0] += timedelta(seconds=25)
        input_state.update(
            {
                "sequence": 1,
                "last_activity_at": now[0].isoformat(timespec="milliseconds"),
                "last_event": {
                    "sequence": 1,
                    "kind": "absolute",
                    "device": "Touchscreen",
                },
            }
        )

        renewed = controller.snapshot()

        self.assertTrue(renewed["lease"]["active"])
        self.assertGreaterEqual(renewed["lease"]["remaining_seconds"], 29)
        self.assertEqual(
            renewed["lease"]["last_interaction_source"],
            "linux-input:absolute:Touchscreen",
        )

    def test_same_input_sequence_cannot_keep_resetting_lease(self):
        controller, now, _state, _applied, input_state = self.controller()
        controller.interaction("plexamp", source="manual-open", manual=True)
        now[0] += timedelta(seconds=25)
        input_state.update(
            {
                "sequence": 1,
                "last_activity_at": now[0].isoformat(timespec="milliseconds"),
                "last_event": {
                    "sequence": 1,
                    "kind": "relative",
                    "device": "Test mouse",
                },
            }
        )
        renewed = controller.snapshot()
        self.assertGreaterEqual(renewed["lease"]["remaining_seconds"], 29)

        now[0] += timedelta(seconds=10)
        stationary = controller.snapshot()

        self.assertGreaterEqual(stationary["lease"]["remaining_seconds"], 19)
        self.assertLessEqual(stationary["lease"]["remaining_seconds"], 20)
        self.assertEqual(stationary["input_activity"]["sequence"], 1)

    def test_recent_activity_delays_idle_return_on_non_media_surface(self):
        controller, now, state, _applied, _input = self.controller()
        state["mode"] = "settings"
        controller.interaction("settings", source="outer-pointerdown")
        now[0] += timedelta(seconds=20)

        active = controller.snapshot()
        self.assertEqual(active["recommended_screen"], "settings")
        self.assertEqual(active["decision_reason"], "recent-browser-activity")

        now[0] += timedelta(seconds=11)
        idle = controller.snapshot()
        self.assertEqual(idle["recommended_screen"], "clock")
        self.assertEqual(idle["decision_reason"], "configured-idle-return")


if __name__ == "__main__":
    unittest.main()
