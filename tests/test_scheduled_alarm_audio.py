from __future__ import annotations

import subprocess
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from app.alarm_audio_scheduled import (
    MAX_CONTROLLED_TEST_SECONDS,
    ScheduledAlarmAudioManager,
    normalise_audio_settings,
)


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "app" / "runner.py"
SETTINGS_CLIENT = ROOT / "app" / "static" / "js" / "settings-alarm-scheduled.js"
BASE = ROOT / "app" / "templates" / "base.html"


class ProbeManager(ScheduledAlarmAudioManager):
    def __init__(self, config, scheduler, runtime_path):
        self.probe_config = config
        self.probe_scheduler = scheduler
        self.starts = []
        self.stops = []
        super().__init__(
            lambda: deepcopy(self.probe_config),
            lambda: {"tones": []},
            lambda: deepcopy(self.probe_scheduler),
            runtime_path,
        )

    def _start(self, occurrence, cycle):
        self.starts.append((deepcopy(occurrence), cycle))

    def stop_playback(self, *, reason="stopped", restore=True):
        self.stops.append(reason)
        with self.lock:
            self.state["playback_active"] = False
            self.state["playback_kind"] = None
        return self.status()


class ScheduledAlarmAudioTests(unittest.TestCase):
    def test_scheduled_playback_requires_both_safety_keys(self):
        disabled_master = normalise_audio_settings(
            {"master_enabled": False, "scheduled_enabled": True}
        )
        enabled = normalise_audio_settings(
            {"master_enabled": True, "scheduled_enabled": True}
        )

        self.assertFalse(disabled_master["scheduled_enabled"])
        self.assertTrue(enabled["scheduled_enabled"])

    def test_promoted_normaliser_keeps_explicit_tests_at_thirty_seconds(self):
        settings = normalise_audio_settings(
            {
                "master_enabled": True,
                "scheduled_enabled": True,
                "test_duration_seconds": 999,
            }
        )
        self.assertEqual(settings["test_duration_seconds"], MAX_CONTROLLED_TEST_SECONDS)
        self.assertEqual(settings["test_volume_cap_percent"], 25)

    def test_real_scheduled_occurrence_starts_without_test_arming(self):
        active = {
            "occurrence_key": "wake|2026-07-31|11:00",
            "phase": "ringing",
            "ring_cycle_started_at": "2026-07-31T11:00:00+01:00",
            "ring_minutes": 3,
            "test_mode": False,
        }
        with tempfile.TemporaryDirectory() as directory:
            manager = ProbeManager(
                {
                    "alarm_audio": {
                        "master_enabled": True,
                        "scheduled_enabled": True,
                    }
                },
                {"active_occurrence": active, "completed_occurrence_keys": []},
                Path(directory) / "runtime.json",
            )
            manager.reconcile_scheduler_audio()

        self.assertEqual(len(manager.starts), 1)
        occurrence, cycle = manager.starts[0]
        self.assertTrue(occurrence["scheduled_alarm"])
        self.assertFalse(occurrence.get("audio_test", False))
        self.assertIn(active["occurrence_key"], cycle)

    def test_visual_test_still_requires_explicit_occurrence_arm(self):
        active = {
            "occurrence_key": "test|123",
            "phase": "ringing",
            "ring_cycle_started_at": "2026-07-31T11:00:00+01:00",
            "test_mode": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            manager = ProbeManager(
                {
                    "alarm_audio": {
                        "master_enabled": True,
                        "scheduled_enabled": True,
                    }
                },
                {"active_occurrence": active, "completed_occurrence_keys": []},
                Path(directory) / "runtime.json",
            )
            manager.reconcile_scheduler_audio()
            self.assertEqual(manager.starts, [])

            manager.arm_occurrence(active["occurrence_key"])
            manager.reconcile_scheduler_audio()

        self.assertEqual(len(manager.starts), 1)
        self.assertTrue(manager.starts[0][0]["audio_test"])
        self.assertFalse(manager.starts[0][0].get("scheduled_alarm", False))

    def test_disabled_scheduled_switch_keeps_real_alarm_silent(self):
        active = {
            "occurrence_key": "wake|2026-07-31|11:00",
            "phase": "ringing",
            "ring_cycle_started_at": "2026-07-31T11:00:00+01:00",
            "test_mode": False,
        }
        with tempfile.TemporaryDirectory() as directory:
            manager = ProbeManager(
                {
                    "alarm_audio": {
                        "master_enabled": True,
                        "scheduled_enabled": False,
                    }
                },
                {"active_occurrence": active, "completed_occurrence_keys": []},
                Path(directory) / "runtime.json",
            )
            manager.reconcile_scheduler_audio()

        self.assertEqual(manager.starts, [])

    def test_disabling_scheduled_switch_stops_current_scheduled_audio(self):
        active = {
            "occurrence_key": "wake|2026-07-31|11:00",
            "phase": "ringing",
            "ring_cycle_started_at": "2026-07-31T11:00:00+01:00",
            "test_mode": False,
        }
        with tempfile.TemporaryDirectory() as directory:
            manager = ProbeManager(
                {
                    "alarm_audio": {
                        "master_enabled": True,
                        "scheduled_enabled": False,
                    }
                },
                {"active_occurrence": active, "completed_occurrence_keys": []},
                Path(directory) / "runtime.json",
            )
            with manager.lock:
                manager.state.update(
                    {
                        "playback_active": True,
                        "playback_kind": "scheduled",
                        "current_occurrence_key": active["occurrence_key"],
                    }
                )
            manager.reconcile_scheduler_audio()

        self.assertIn("scheduled-audio-disabled", manager.stops)

    def test_runner_promotes_scheduled_audio_before_state_providers(self):
        text = RUNNER.read_text(encoding="utf-8")
        promotion = text.index("promote_scheduled_alarm_audio(dashboard)")
        state_hub = text.index("build_default_application_state_hub(dashboard)")
        self.assertLess(promotion, state_hub)

    def test_settings_client_is_valid_and_exposes_second_switch(self):
        result = subprocess.run(
            ["node", "--check", str(SETTINGS_CLIENT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        text = SETTINGS_CLIENT.read_text(encoding="utf-8")
        self.assertIn("alarm-audio-scheduled-enabled", text)
        self.assertIn("scheduled_enabled", text)
        self.assertIn("Second safety key", text)

    def test_base_loads_scheduled_settings_client_with_cache_token(self):
        text = BASE.read_text(encoding="utf-8")
        self.assertIn("js/settings-alarm-scheduled.js", text)
        self.assertIn("20260731-guarded-scheduled-alarm-audio", text)


if __name__ == "__main__":
    unittest.main()
