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


class ScreenProjectionTakeoverTests(unittest.TestCase):
    def controller(self):
        now = [datetime(2026, 7, 29, 5, 0, tzinfo=timezone.utc)]
        state = {
            "mode": "clock",
            "active_source": "none",
            "alarm_active": False,
        }
        playback = FakePlayback(state)
        applied: list[str] = []

        def set_mode(mode: str) -> None:
            applied.append(mode)
            state["mode"] = mode

        controller = ScreenProjectionController(
            load_config=lambda: {
                "dashboard": {
                    "idle_timeout_seconds": 30,
                    "default_mode": "clock",
                }
            },
            load_state=lambda _config: {"mode": state["mode"]},
            playback=playback,
            set_mode=set_mode,
            input_activity=lambda: {
                "sequence": 0,
                "last_activity_at": None,
                "last_event": None,
            },
            now_provider=lambda: now[0],
        )
        return controller, now, state, applied

    def test_new_plexamp_playback_interrupts_a_quiet_clock_lease(self):
        controller, _now, state, _applied = self.controller()
        opened = controller.interaction("clock", source="navigation-link", manual=True)

        self.assertTrue(opened["lease"]["active"])
        self.assertEqual(opened["lease"]["audio_source_at_start"], "none")

        state["active_source"] = "plexamp"
        takeover = controller.snapshot("clock")

        self.assertFalse(takeover["lease"]["active"])
        self.assertIsNone(takeover["lease"]["manual_surface"])
        self.assertEqual(
            takeover["lease"]["last_end_reason"],
            "audio-source-changed:none->plexamp",
        )
        self.assertEqual(takeover["recommended_screen"], "plexamp")
        self.assertEqual(takeover["decision_reason"], "plexamp-owns-audio")
        self.assertTrue(takeover["should_apply"])
        self.assertTrue(takeover["should_present"])

    def test_airplay_takeover_interrupts_a_plexamp_background_lease(self):
        controller, _now, state, _applied = self.controller()
        state["active_source"] = "plexamp"
        controller.interaction("settings", source="navigation-link", manual=True)

        state["active_source"] = "airplay"
        takeover = controller.snapshot("settings")

        self.assertFalse(takeover["lease"]["active"])
        self.assertEqual(
            takeover["lease"]["last_end_reason"],
            "audio-source-changed:plexamp->airplay",
        )
        self.assertEqual(takeover["recommended_screen"], "airplay")
        self.assertEqual(takeover["decision_reason"], "airplay-owns-audio")

    def test_same_audio_owner_does_not_interrupt_manual_settings(self):
        controller, _now, state, _applied = self.controller()
        state["mode"] = "settings"
        state["active_source"] = "plexamp"
        controller.interaction("settings", source="navigation-link", manual=True)

        unchanged = controller.snapshot("settings")

        self.assertTrue(unchanged["lease"]["active"])
        self.assertEqual(unchanged["lease"]["audio_source_at_start"], "plexamp")
        self.assertEqual(unchanged["recommended_screen"], "settings")
        self.assertEqual(unchanged["decision_reason"], "manual-settings-lease")

    def test_disconnect_to_clock_repairs_visible_airplay_without_mode_write(self):
        controller, now, state, applied = self.controller()
        now[0] += timedelta(seconds=31)
        state["mode"] = "clock"
        state["active_source"] = "none"

        snapshot = controller.snapshot("airplay")

        self.assertEqual(snapshot["current_screen"], "clock")
        self.assertEqual(snapshot["visible_surface"], "airplay")
        self.assertEqual(snapshot["recommended_screen"], "clock")
        self.assertEqual(snapshot["decision_reason"], "configured-idle-return")
        self.assertFalse(snapshot["should_apply"])
        self.assertTrue(snapshot["should_present"])
        self.assertFalse(snapshot["presentation_in_sync"])

        applied_state = controller.apply("airplay")
        self.assertEqual(applied, [])
        self.assertTrue(applied_state["should_present"])


if __name__ == "__main__":
    unittest.main()
