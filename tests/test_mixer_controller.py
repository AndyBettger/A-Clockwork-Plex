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
        plexamp = {
            "available": True,
            "percent": 55,
            "playback_state": "playing",
            "source": "plexamp-player",
            "error": None,
        }
        mixer = {
            "available": True,
            "configured": True,
            "channels": {
                channel: {
                    "id": channel,
                    "available": True,
                    "pcm_available": True,
                    "percent": value,
                    "error": None,
                }
                for channel, value in {
                    "master": 80,
                    "plexamp": 100,
                    "airplay": 100,
                    "alarm": 75,
                }.items()
            },
            "error": None,
        }
        airplay_commands: list[int] = []
        plexamp_commands: list[int] = []
        mixer_commands: list[tuple[str, int, bool]] = []

        def set_airplay(percent: int):
            airplay_commands.append(percent)
            return True, None

        def set_plexamp(percent: int):
            plexamp_commands.append(percent)
            plexamp["percent"] = percent
            return dict(plexamp)

        def set_mixer(channel: str, percent: int, persist: bool):
            mixer_commands.append((channel, percent, persist))
            mixer["channels"][channel]["percent"] = percent
            return dict(mixer)

        controller = MixerController(
            load_config=lambda: {
                "airplay": {
                    "default_volume_percent": 60,
                    "apply_default_volume_on_start": apply_default,
                }
            },
            airplay_status=lambda: dict(remote),
            set_airplay_volume=set_airplay,
            plexamp_status=lambda: dict(plexamp),
            set_plexamp_volume=set_plexamp,
            mixer_status=lambda: {
                **mixer,
                "channels": {
                    key: dict(value)
                    for key, value in mixer["channels"].items()
                },
            },
            set_mixer_volume=set_mixer,
            sleep_provider=lambda _seconds: None,
            sender_wait_attempts=1,
        )
        return controller, remote, airplay_commands, plexamp_commands, mixer_commands

    def test_starting_volume_is_written_once(self):
        controller, _remote, commands, _plexamp, _mixer = self.controller(observed=20)

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
        controller, remote, commands, _plexamp, _mixer = self.controller(observed=35)
        controller.start_airplay_session(background=False)

        first = controller.airplay_snapshot()
        second = controller.airplay_snapshot()

        self.assertEqual(commands, [60])
        self.assertEqual(remote["volume_percent"], 35)
        self.assertEqual(first["effective_percent"], 60)
        self.assertEqual(second["effective_percent"], 60)
        self.assertTrue(second["request_active"])

    def test_sender_confirmation_releases_pending_request(self):
        controller, remote, commands, _plexamp, _mixer = self.controller(observed=20)
        controller.start_airplay_session(background=False)
        remote["volume_percent"] = 60

        state = controller.airplay_snapshot()

        self.assertEqual(commands, [60])
        self.assertEqual(state["effective_percent"], 60)
        self.assertEqual(state["state_source"], "sender-confirmed")
        self.assertEqual(state["command_status"], "confirmed")
        self.assertFalse(state["request_active"])

    def test_newer_sender_change_supersedes_stale_request(self):
        controller, remote, commands, _plexamp, _mixer = self.controller(observed=20)
        controller.start_airplay_session(background=False)
        remote["volume_percent"] = 73

        state = controller.airplay_snapshot()

        self.assertEqual(commands, [60])
        self.assertEqual(state["effective_percent"], 73)
        self.assertEqual(state["state_source"], "sender-observed-newer")
        self.assertEqual(state["command_status"], "sender-overrode")
        self.assertFalse(state["request_active"])

    def test_resume_does_not_reapply_starting_volume(self):
        controller, _remote, commands, _plexamp, _mixer = self.controller(observed=20)

        first = controller.start_airplay_session(background=False)
        second = controller.start_airplay_session(background=False)

        self.assertEqual(first, "requested")
        self.assertEqual(second, "already-active")
        self.assertEqual(commands, [60])
        self.assertEqual(controller.application_status()["reason"], "session-resume-no-volume-reset")

    def test_live_player_and_sender_controls_use_their_own_adapters(self):
        controller, _remote, airplay, plexamp, mixer = self.controller(observed=20)

        controller.set_live_percent("plexamp", 44)
        controller.set_live_percent("airplay", 66)

        self.assertEqual(plexamp, [44])
        self.assertEqual(airplay, [66])
        self.assertEqual(mixer, [])

    def test_master_and_alarm_live_controls_write_alsa_without_persisting(self):
        controller, _remote, _airplay, _plexamp, mixer = self.controller()

        controller.set_live_percent("master", 64)
        controller.set_live_percent("alarm", 52)

        self.assertEqual(
            mixer,
            [
                ("master", 64, False),
                ("alarm", 52, False),
            ],
        )

    def test_all_trim_controls_write_alsa_with_explicit_persistence(self):
        controller, _remote, _airplay, _plexamp, mixer = self.controller()

        controller.set_trim_percent("plexamp", 81, persist=False)
        controller.set_trim_percent("airplay", 92, persist=True)

        self.assertEqual(
            mixer,
            [
                ("plexamp", 81, False),
                ("airplay", 92, True),
            ],
        )

    def test_snapshot_contains_live_channels_and_direct_alsa_trims(self):
        controller, _remote, _airplay, _plexamp, _mixer = self.controller(observed=30)

        state = controller.snapshot()

        self.assertEqual(state["authority"], "mixer-controller")
        self.assertEqual(state["channels"]["plexamp"]["percent"], 55)
        self.assertEqual(state["channels"]["airplay"]["percent"], 30)
        self.assertEqual(state["channels"]["master"]["percent"], 80)
        self.assertEqual(state["channels"]["plexamp"]["trim"]["percent"], 100)
        self.assertEqual(
            state["command_capabilities"]["alsa_trims"],
            ["airplay", "alarm", "master", "plexamp"],
        )

    def test_disabled_starting_volume_sends_no_command(self):
        controller, _remote, commands, _plexamp, _mixer = self.controller(apply_default=False)

        result = controller.start_airplay_session(background=False)

        self.assertEqual(result, "disabled")
        self.assertEqual(commands, [])
        self.assertEqual(controller.application_status()["status"], "disabled")

    def test_compact_audio_api_controls_live_and_trim_scopes(self):
        controller, remote, airplay, plexamp, mixer = self.controller(observed=25)
        hub = ApplicationStateHub()
        hub.register_service("mixer", controller)
        hub.register_provider("audio", controller.snapshot)
        app = Flask("mixer-controller-api-test")
        register_application_state_api(app, hub)
        client = app.test_client()

        initial = client.get("/api/audio/state")
        airplay_changed = client.post(
            "/api/audio/state",
            json={"scope": "live", "channel": "airplay", "percent": 48},
        )
        plexamp_changed = client.post(
            "/api/audio/state",
            json={"scope": "live", "channel": "plexamp", "percent": 42},
        )
        trim_changed = client.post(
            "/api/audio/state",
            json={"scope": "trim", "channel": "airplay", "percent": 88, "persist": True},
        )

        self.assertEqual(initial.status_code, 200)
        self.assertEqual(initial.get_json()["audio"]["authority"], "mixer-controller")
        self.assertEqual(airplay_changed.status_code, 200)
        self.assertEqual(plexamp_changed.status_code, 200)
        self.assertEqual(trim_changed.status_code, 200)
        self.assertEqual(airplay, [48])
        self.assertEqual(plexamp, [42])
        self.assertEqual(mixer, [("airplay", 88, True)])
        self.assertEqual(airplay_changed.get_json()["audio"]["channels"]["airplay"]["effective_percent"], 48)
        self.assertEqual(remote["volume_percent"], 25)


if __name__ == "__main__":
    unittest.main()
