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
STATUS_API = ROOT / "app" / "alarm_audio_status_scheduled.py"
SETTINGS_CLIENT = ROOT / "app" / "static" / "js" / "settings-alarm-scheduled.js"
SCHEDULER_CLIENT = ROOT / "app" / "static" / "js" / "settings-alarm-scheduler.js"
UNIFIED_CLIENT = ROOT / "app" / "static" / "js" / "settings-ipad.js"
SETTINGS_TEMPLATE = ROOT / "app" / "templates" / "settings.html"
ALARM_CLIENT = ROOT / "app" / "static" / "js" / "alarm-active.js"
BASE = ROOT / "app" / "templates" / "base.html"
ALARM_TEMPLATE = ROOT / "app" / "templates" / "alarm.html"


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

    def test_runner_promotes_audio_and_status_before_state_providers(self):
        text = RUNNER.read_text(encoding="utf-8")
        audio_promotion = text.index("promote_scheduled_alarm_audio(dashboard)")
        status_promotion = text.index("register_scheduled_alarm_status_api(dashboard)")
        state_hub = text.index("build_default_application_state_hub(dashboard)")
        self.assertLess(audio_promotion, status_promotion)
        self.assertLess(status_promotion, state_hub)

    def test_status_api_uses_promoted_audio_enablement(self):
        text = STATUS_API.read_text(encoding="utf-8")
        self.assertIn('audio.get("scheduled_playback_enabled")', text)
        self.assertIn('dashboard.app.view_functions["api_alarm_active"]', text)
        self.assertIn('dashboard.app.view_functions["api_alarm_scheduler"]', text)
        self.assertNotIn('"playback_enabled": False', text)

    def test_alarm_clients_have_valid_javascript_syntax(self):
        for path in (SETTINGS_CLIENT, SCHEDULER_CLIENT, UNIFIED_CLIENT, ALARM_CLIENT):
            with self.subTest(path=path.name):
                result = subprocess.run(
                    ["node", "--check", str(path)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_retired_settings_client_still_documents_second_switch_contract(self):
        text = SETTINGS_CLIENT.read_text(encoding="utf-8")
        guard = text.index("dataset?.activePage")
        installer = text.index("function install()")
        self.assertLess(guard, installer)
        self.assertIn("alarm-audio-scheduled-enabled", text)
        self.assertIn("scheduled_enabled", text)
        self.assertIn("Second safety key", text)

    def test_unified_settings_exposes_both_scheduled_audio_keys(self):
        template = SETTINGS_TEMPLATE.read_text(encoding="utf-8")
        client = UNIFIED_CLIENT.read_text(encoding="utf-8")
        self.assertIn('data-setting-path="alarm_audio.master_enabled"', template)
        self.assertIn('data-setting-path="alarm_audio.scheduled_enabled"', template)
        self.assertIn("Two-key scheduled-audio safety", template)
        self.assertIn("/api/settings", client)
        self.assertIn("alarm_audio", client)
        self.assertNotIn("js/settings-alarm-scheduled.js", BASE.read_text(encoding="utf-8"))

    def test_scheduler_and_alarm_screen_render_promoted_audio_truth(self):
        scheduler = SCHEDULER_CLIENT.read_text(encoding="utf-8")
        active = ALARM_CLIENT.read_text(encoding="utf-8")
        self.assertIn("audio.scheduled_playback_enabled", scheduler)
        self.assertIn("Scheduled alarm audio enabled", scheduler)
        self.assertIn("Scheduled alarm · sounding", active)
        self.assertIn("playbackKind === 'scheduled'", active)
        self.assertIn("Scheduled alarm · audio locked", active)

    def test_alarm_screen_remains_cache_busted_and_settings_uses_unified_client(self):
        base = BASE.read_text(encoding="utf-8")
        settings = SETTINGS_TEMPLATE.read_text(encoding="utf-8")
        alarm = ALARM_TEMPLATE.read_text(encoding="utf-8")
        self.assertNotIn("js/settings-alarm-scheduled.js", base)
        self.assertNotIn("js/settings-alarm-scheduler.js", base)
        self.assertIn("js/settings-ipad.js", settings)
        self.assertIn("20260802-unified-settings", settings)
        self.assertIn("20260731-scheduled-alarm-audio-truth", alarm)


if __name__ == "__main__":
    unittest.main()
