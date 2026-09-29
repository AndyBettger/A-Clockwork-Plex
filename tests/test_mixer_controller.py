from __future__ import annotations

import unittest

from flask import Flask

from app.application_state import ApplicationStateHub, register_application_state_api
from app.mixer_controller import MixerController


class MixerControllerTests(unittest.TestCase):
    def controller(self, *, observed=33, available=True, live_percent=100):
        remote = {
            "available": available,
            "sender_available": available,
            "volume_percent": observed,
            "airplay_volume_db": -20.0,
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
                    "airplay": 90,
                    "airplay_live": live_percent,
                    "alarm": 75,
                }.items()
            },
            "error": None,
        }
        plexamp_commands: list[int] = []
        mixer_commands: list[tuple[str, int, bool]] = []

        def set_plexamp(percent: int):
            plexamp_commands.append(percent)
            plexamp["percent"] = percent
            return dict(plexamp)

        def set_mixer(channel: str, percent: int, persist: bool):
            mixer_commands.append((channel, percent, persist))
            mixer["channels"][channel]["percent"] = percent
            return dict(mixer)

        controller = MixerController(
            airplay_status=lambda: dict(remote),
            plexamp_status=lambda: dict(plexamp),
            set_plexamp_volume=set_plexamp,
            mixer_status=lambda: {
                **mixer,
                "channels": {key: dict(value) for key, value in mixer["channels"].items()},
            },
            set_mixer_volume=set_mixer,
        )
        return controller, remote, plexamp_commands, mixer_commands

    def test_airplay_snapshot_uses_local_live_control_not_sender_volume(self):
        controller, remote, _plexamp, _mixer = self.controller(observed=12, live_percent=67)

        state = controller.airplay_snapshot()

        self.assertEqual(state["effective_percent"], 67)
        self.assertEqual(state["percent"], 67)
        self.assertEqual(state["state_source"], "receiver-local-alsa")
        self.assertTrue(state["sender_volume_ignored"])
        self.assertEqual(state["sender_volume_percent"], 12)
        self.assertEqual(state["sender_volume_db"], -20.0)
        self.assertEqual(state["trim"]["percent"], 90)
        self.assertEqual(remote["volume_percent"], 12)

    def test_live_airplay_fader_writes_runtime_alsa_without_persisting(self):
        controller, remote, _plexamp, mixer = self.controller(observed=20)

        state = controller.set_live_percent("airplay", 66)

        self.assertEqual(mixer, [("airplay_live", 66, False)])
        self.assertEqual(state["channels"]["airplay"]["effective_percent"], 66)
        self.assertEqual(remote["volume_percent"], 20)

    def test_live_plexamp_uses_player_adapter(self):
        controller, _remote, plexamp, mixer = self.controller()

        controller.set_live_percent("plexamp", 44)

        self.assertEqual(plexamp, [44])
        self.assertEqual(mixer, [])

    def test_master_and_alarm_live_controls_write_alsa_without_persisting(self):
        controller, _remote, _plexamp, mixer = self.controller()

        controller.set_live_percent("master", 64)
        controller.set_live_percent("alarm", 52)

        self.assertEqual(mixer, [("master", 64, False), ("alarm", 52, False)])

    def test_persistent_airplay_trim_remains_separate_from_live_control(self):
        controller, _remote, _plexamp, mixer = self.controller()

        controller.set_trim_percent("airplay", 92, persist=True)

        self.assertEqual(mixer, [("airplay", 92, True)])

    def test_session_start_never_resets_or_writes_volume(self):
        controller, _remote, _plexamp, mixer = self.controller(live_percent=73)

        first = controller.start_airplay_session(background=False)
        second = controller.start_airplay_session(background=False)
        state = controller.airplay_snapshot()

        self.assertEqual(first, "receiver-owned")
        self.assertEqual(second, "already-active")
        self.assertEqual(mixer, [])
        self.assertEqual(state["effective_percent"], 73)

    def test_snapshot_declares_receiver_owned_capabilities(self):
        controller, _remote, _plexamp, _mixer = self.controller(live_percent=81)

        state = controller.snapshot()
        caps = state["command_capabilities"]

        self.assertEqual(state["mode"], "receiver-owned-airplay")
        self.assertEqual(state["channels"]["airplay"]["percent"], 81)
        self.assertEqual(caps["live_player_volume"], ["plexamp"])
        self.assertEqual(caps["live_alsa_volume"], ["master", "airplay", "alarm"])
        self.assertTrue(caps["airplay_receiver_volume"])
        self.assertFalse(caps["airplay_sender_volume"])
        self.assertFalse(caps["airplay_starting_volume"])
        self.assertEqual(caps["alsa_trims"], ["airplay", "alarm", "master", "plexamp"])

    def test_compact_audio_api_routes_live_airplay_to_runtime_alsa(self):
        controller, remote, plexamp, mixer = self.controller(observed=25)
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
        self.assertEqual(airplay_changed.status_code, 200)
        self.assertEqual(plexamp_changed.status_code, 200)
        self.assertEqual(trim_changed.status_code, 200)
        self.assertEqual(plexamp, [42])
        self.assertEqual(
            mixer,
            [
                ("airplay_live", 48, False),
                ("airplay", 88, True),
            ],
        )
        self.assertEqual(
            airplay_changed.get_json()["audio"]["channels"]["airplay"]["effective_percent"],
            48,
        )
        self.assertEqual(remote["volume_percent"], 25)


if __name__ == "__main__":
    unittest.main()
