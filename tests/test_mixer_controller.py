from __future__ import annotations

import unittest

from flask import Flask

from app.application_state import ApplicationStateHub, register_application_state_api
from app.mixer_controller import MixerController


class MixerControllerTests(unittest.TestCase):
    def controller(self, *, observed=20, available=True, apply_default=True):
        remote = {
            "available": available,
            "sender_available": available,
            "volume_percent": observed,
            "playback_status": "Playing",
            "can_control": True,
            "error": None,
        }
        commands: list[int] = []

        def set_volume(percent: int):
            commands.append(percent)
            return True, None

        controller = MixerController(
            load_config=lambda: {
                "airplay": {
                    "default_volume_percent": 60,
                    "apply_default_volume_on_start": apply_default,
                }
            },
            airplay_status=lambda: dict(remote),
            set_airplay_volume=set_volume,
            sleep_provider=lambda _seconds: None,
            sender_wait_attempts=1,
        )
        return controller, remote, commands

    def test_starting_volume_is_written_once(self):
        controller, _remote, commands = self.controller(observed=20)

        result = controller.start_airplay_session(background=False)
        state = controller.airplay_snapshot()

        self.assertEqual(result, "requested")
        self.assertEqual(commands, [60])
        self.assertEqual(state["command_count"], 1)
        self.assertEqual(state["observed_percent"], 20)
        self.assertEqual(state["requested_percent"], 60)
        self.assertEqual(state["effective_percent"], 60)
        self.assertEqual(state["state_source"], "controller-request")

    def test_stale_baseline_does_not_overwrite_requested_value(self):
        controller, remote, commands = self.controller(observed=35)
        controller.start_airplay_session(background=False)

        first = controller.airplay_snapshot()
        second = controller.airplay_snapshot()

        self.assertEqual(commands, [60])
        self.assertEqual(remote["volume_percent"], 35)
        self.assertEqual(first["effective_percent"], 60)
        self.assertEqual(second["effective_percent"], 60)
        self.assertTrue(second["request_active"])

    def test_sender_confirmation_releases_pending_request(self):
        controller, remote, commands = self.controller(observed=20)
        controller.start_airplay_session(background=False)
        remote["volume_percent"] = 60

        state = controller.airplay_snapshot()

        self.assertEqual(commands, [60])
        self.assertEqual(state["effective_percent"], 60)
        self.assertEqual(state["state_source"], "sender-confirmed")
        self.assertEqual(state["command_status"], "confirmed")
        self.assertFalse(state["request_active"])

    def test_newer_sender_change_supersedes_stale_request(self):
        controller, remote, commands = self.controller(observed=20)
        controller.start_airplay_session(background=False)
        remote["volume_percent"] = 73

        state = controller.airplay_snapshot()

        self.assertEqual(commands, [60])
        self.assertEqual(state["effective_percent"], 73)
        self.assertEqual(state["state_source"], "sender-observed-newer")
        self.assertEqual(state["command_status"], "sender-overrode")
        self.assertFalse(state["request_active"])

    def test_resume_does_not_reapply_starting_volume(self):
        controller, _remote, commands = self.controller(observed=20)

        first = controller.start_airplay_session(background=False)
        second = controller.start_airplay_session(background=False)

        self.assertEqual(first, "requested")
        self.assertEqual(second, "already-active")
        self.assertEqual(commands, [60])
        self.assertEqual(controller.application_status()["reason"], "session-resume-no-volume-reset")

    def test_pi_slider_command_is_one_explicit_write(self):
        controller, _remote, commands = self.controller(observed=20)

        state = controller.set_airplay_percent(44)

        self.assertEqual(commands, [44])
        self.assertEqual(state["requested_percent"], 44)
        self.assertEqual(state["effective_percent"], 44)
        self.assertEqual(state["command_count"], 1)

    def test_disabled_starting_volume_sends_no_command(self):
        controller, _remote, commands = self.controller(apply_default=False)

        result = controller.start_airplay_session(background=False)

        self.assertEqual(result, "disabled")
        self.assertEqual(commands, [])
        self.assertEqual(controller.application_status()["status"], "disabled")

    def test_compact_audio_api_reads_and_writes_mixer_authority(self):
        controller, remote, commands = self.controller(observed=25)
        hub = ApplicationStateHub()
        hub.register_service("mixer", controller)
        hub.register_provider("audio", controller.snapshot)
        app = Flask("mixer-controller-api-test")
        register_application_state_api(app, hub)
        client = app.test_client()

        initial = client.get("/api/audio/state")
        changed = client.post("/api/audio/state", json={"channel": "airplay", "percent": 48})

        self.assertEqual(initial.status_code, 200)
        self.assertEqual(initial.get_json()["audio"]["authority"], "mixer-controller")
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(commands, [48])
        self.assertEqual(changed.get_json()["audio"]["channels"]["airplay"]["effective_percent"], 48)
        self.assertEqual(remote["volume_percent"], 25)


if __name__ == "__main__":
    unittest.main()
