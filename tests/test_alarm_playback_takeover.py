from __future__ import annotations

import unittest
from pathlib import Path

from app.playback_handoff_retention import RetainedBidirectionalHandoffCoordinator


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_CSS = ROOT / "app" / "static" / "css" / "settings-alarm-workspace.css"


class AlarmPlaybackTakeoverTests(unittest.TestCase):
    def coordinator(
        self,
        *,
        plexamp_state: str = "paused",
        airplay_state: str = "Paused",
        alarm_active: bool = True,
        scheduled_enabled: bool = True,
    ):
        plexamp = {
            "available": True,
            "playback_state": plexamp_state,
            "percent": 70,
        }
        airplay = {
            "available": airplay_state.lower() != "disconnected",
            "playback_status": airplay_state,
            "can_control": True,
            "can_play": True,
            "can_pause": True,
        }
        scheduler = {
            "screen_required": alarm_active,
            "active_occurrence": (
                {
                    "occurrence_key": "wake|2026-07-31|18:35",
                    "phase": "ringing",
                    "test_mode": False,
                }
                if alarm_active
                else None
            ),
        }
        audio = {
            "scheduled_playback_enabled": scheduled_enabled,
            "playback_active": alarm_active and scheduled_enabled,
            "playback_kind": "scheduled" if alarm_active and scheduled_enabled else None,
        }
        plexamp_pauses: list[str] = []
        airplay_commands: list[str] = []

        def pause_plexamp():
            plexamp_pauses.append("pause")
            plexamp["playback_state"] = "paused"
            return True, None

        def airplay_command(action: str):
            airplay_commands.append(action)
            if action == "pause":
                airplay["playback_status"] = "Paused"
            return True, None

        coordinator = RetainedBidirectionalHandoffCoordinator(
            load_config=lambda: {"dashboard": {"default_mode": "clock"}},
            load_state=lambda _config: {
                "mode": "alarm" if scheduler["screen_required"] else "clock",
                "airplay": {
                    "active": airplay.get("available") is True,
                    "started_at": "2026-07-31T18:00:00+01:00",
                    "ended_at": None,
                    "metadata": {},
                },
            },
            plexamp_status=lambda: dict(plexamp),
            airplay_status=lambda: dict(airplay),
            alarm_status=lambda: dict(scheduler),
            alarm_audio_status=lambda: dict(audio),
            airplay_command=airplay_command,
            plexamp_pause=pause_plexamp,
            airplay_hold_seconds=600,
            reconcile_seconds=0.05,
            command_verify_seconds=20,
        )
        return coordinator, plexamp, airplay, scheduler, audio, plexamp_pauses, airplay_commands

    def test_real_scheduled_alarm_pauses_plexamp_once(self):
        coordinator, _plexamp, _airplay, _scheduler, _audio, plexamp_pauses, commands = self.coordinator(
            plexamp_state="playing",
            airplay_state="Disconnected",
        )

        coordinator.snapshot()
        self.assertEqual(plexamp_pauses, [])

        first = coordinator.reconcile_once()
        second = coordinator.reconcile_once()

        self.assertEqual(first, "alarm-paused-plexamp")
        self.assertEqual(second, "alarm-active")
        self.assertEqual(plexamp_pauses, ["pause"])
        self.assertEqual(commands, [])
        takeover = coordinator.alarm_takeover_snapshot()
        self.assertTrue(takeover["active"])
        self.assertEqual(takeover["plexamp_pause_count"], 1)
        self.assertEqual(takeover["resume_policy"], "manual")

    def test_real_scheduled_alarm_pauses_airplay_once(self):
        coordinator, _plexamp, _airplay, _scheduler, _audio, plexamp_pauses, commands = self.coordinator(
            plexamp_state="paused",
            airplay_state="Playing",
        )

        first = coordinator.reconcile_once()
        second = coordinator.reconcile_once()

        self.assertEqual(first, "alarm-paused-airplay")
        self.assertEqual(second, "alarm-active")
        self.assertEqual(plexamp_pauses, [])
        self.assertEqual(commands, ["pause"])
        takeover = coordinator.alarm_takeover_snapshot()
        self.assertEqual(takeover["airplay_pause_count"], 1)
        self.assertEqual(takeover["last_error"], None)

    def test_airplay_resume_during_same_alarm_is_paused_again(self):
        coordinator, _plexamp, airplay, _scheduler, _audio, _plexamp_pauses, commands = self.coordinator(
            plexamp_state="paused",
            airplay_state="Playing",
        )

        coordinator.reconcile_once()
        coordinator.reconcile_once()
        airplay["playback_status"] = "Playing"
        coordinator.reconcile_once()

        self.assertEqual(commands, ["pause", "pause"])
        self.assertEqual(coordinator.alarm_takeover_snapshot()["airplay_pause_count"], 2)

    def test_alarm_release_never_auto_resumes_music(self):
        coordinator, plexamp, airplay, scheduler, audio, plexamp_pauses, commands = self.coordinator(
            plexamp_state="playing",
            airplay_state="Playing",
        )

        coordinator.reconcile_once()
        scheduler["screen_required"] = False
        scheduler["active_occurrence"] = None
        audio["scheduled_playback_enabled"] = False
        audio["playback_active"] = False
        audio["playback_kind"] = None
        result = coordinator.reconcile_once()

        self.assertEqual(result, "alarm-released")
        self.assertEqual(plexamp["playback_state"], "paused")
        self.assertEqual(airplay["playback_status"], "Paused")
        self.assertEqual(plexamp_pauses, ["pause"])
        self.assertEqual(commands, ["pause"])
        self.assertFalse(coordinator.alarm_takeover_snapshot()["active"])

    def test_visual_only_alarm_test_does_not_pause_music(self):
        coordinator, _plexamp, _airplay, scheduler, audio, plexamp_pauses, commands = self.coordinator(
            plexamp_state="playing",
            airplay_state="Disconnected",
        )
        scheduler["active_occurrence"]["test_mode"] = True
        audio["playback_active"] = False

        coordinator.reconcile_once()

        self.assertEqual(plexamp_pauses, [])
        self.assertEqual(commands, [])
        self.assertFalse(coordinator.alarm_takeover_snapshot()["active"])

    def test_disabled_scheduled_sound_does_not_claim_audio_priority(self):
        coordinator, _plexamp, _airplay, _scheduler, _audio, plexamp_pauses, commands = self.coordinator(
            plexamp_state="playing",
            airplay_state="Disconnected",
            scheduled_enabled=False,
        )

        coordinator.reconcile_once()

        self.assertEqual(plexamp_pauses, [])
        self.assertEqual(commands, [])
        self.assertFalse(coordinator.alarm_takeover_snapshot()["active"])

    def test_alarm_save_card_returns_to_document_flow_while_keyboard_is_open(self):
        css = WORKSPACE_CSS.read_text(encoding="utf-8")
        self.assertIn("body.keyboard-open .alarm-workspace-save-card", css)
        keyboard_rule = css.split("body.keyboard-open .alarm-workspace-save-card", 1)[1]
        self.assertIn("position: static", keyboard_rule)
        self.assertIn("bottom: auto", keyboard_rule)


if __name__ == "__main__":
    unittest.main()
