from __future__ import annotations

import unittest
from copy import deepcopy

from app.screen_projection_activity import ActivityAwareScreenProjectionController


class FakePlayback:
    def __init__(self) -> None:
        self.payload = {
            "current_screen": "settings",
            "active_source": "none",
            "sources": {
                "alarm": {
                    "active": False,
                    "screen_required": False,
                    "playback_active": False,
                }
            },
        }

    def snapshot(self):
        return deepcopy(self.payload)


class AlarmAudioScreenOwnershipTests(unittest.TestCase):
    def build_controller(self):
        playback = FakePlayback()
        controller = ActivityAwareScreenProjectionController(
            load_config=lambda: {
                "dashboard": {
                    "default_mode": "clock",
                    "idle_timeout_seconds": 180,
                }
            },
            load_state=lambda _config: {"mode": "settings"},
            playback=playback,
            set_mode=lambda _mode: None,
            input_activity=lambda: {
                "available": False,
                "running": False,
                "sequence": 0,
                "last_activity_at": None,
                "last_event": None,
                "last_error": None,
            },
        )
        controller.interaction(
            "settings",
            source="test-settings-open",
            manual=True,
            visible_surface="settings",
        )
        return controller, playback

    def test_audio_only_alarm_test_keeps_settings_lease(self):
        controller, playback = self.build_controller()
        playback.payload.update(
            {
                "active_source": "alarm",
                "sources": {
                    "alarm": {
                        "active": True,
                        "screen_required": False,
                        "playback_active": True,
                    }
                },
            }
        )

        state = controller.snapshot("settings")

        self.assertEqual(state["recommended_screen"], "settings")
        self.assertEqual(state["decision_reason"], "manual-settings-lease")
        self.assertTrue(state["lease"]["active"])
        self.assertFalse(state["should_apply"])
        self.assertFalse(state["should_present"])

    def test_screen_required_alarm_still_overrides_settings_lease(self):
        controller, playback = self.build_controller()
        playback.payload.update(
            {
                "active_source": "alarm",
                "sources": {
                    "alarm": {
                        "active": True,
                        "screen_required": True,
                        "playback_active": True,
                    }
                },
            }
        )

        state = controller.snapshot("settings")

        self.assertEqual(state["recommended_screen"], "alarm")
        self.assertEqual(state["decision_reason"], "alarm-screen-required")
        self.assertTrue(state["should_apply"])
        self.assertTrue(state["should_present"])


if __name__ == "__main__":
    unittest.main()
