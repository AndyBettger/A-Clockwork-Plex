from __future__ import annotations

import unittest

from app.alarm_audio_status_scheduled import project_scheduler_status


class AlarmStatusProjectionTests(unittest.TestCase):
    def test_enabled_audio_replaces_internal_scheduler_lockout(self):
        internal = {
            "running": True,
            "playback_enabled": False,
            "playback_lockout_reason": "stale foundation wording",
        }
        audio = {
            "scheduled_playback_enabled": True,
            "settings": {
                "master_enabled": True,
                "scheduled_enabled": True,
            },
        }

        projected = project_scheduler_status(internal, audio)

        self.assertTrue(projected["playback_enabled"])
        self.assertIsNone(projected["playback_lockout_reason"])
        self.assertEqual(projected["playback_owner"], "scheduled-alarm-audio-manager")
        self.assertEqual(projected["playback_policy"], "two-key-safety-gate")
        self.assertFalse(internal["playback_enabled"])
        self.assertEqual(internal["playback_lockout_reason"], "stale foundation wording")

    def test_master_switch_has_specific_public_lockout_reason(self):
        projected = project_scheduler_status(
            {"running": True, "playback_enabled": False},
            {
                "scheduled_playback_enabled": False,
                "settings": {
                    "master_enabled": False,
                    "scheduled_enabled": False,
                },
            },
        )

        self.assertFalse(projected["playback_enabled"])
        self.assertIn("master safety switch", projected["playback_lockout_reason"])

    def test_second_switch_has_specific_public_lockout_reason(self):
        projected = project_scheduler_status(
            {"running": True, "playback_enabled": False},
            {
                "scheduled_playback_enabled": False,
                "settings": {
                    "master_enabled": True,
                    "scheduled_enabled": False,
                },
            },
        )

        self.assertFalse(projected["playback_enabled"])
        self.assertIn("second safety switch", projected["playback_lockout_reason"])


if __name__ == "__main__":
    unittest.main()
