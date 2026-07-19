from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.alarm_audio import AlarmAudioManager, normalise_audio_settings
from app.audio_mixer import PlexampVolumeController, SharedAudioMixer


class FakeRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command, **kwargs):
        self.commands.append(list(command))
        if command[-1] == "status":
            values = {
                "master": (80, 96, -1.94),
                "plexamp": (100, 100, 0.0),
                "airplay": (90, 98, -0.92),
                "alarm": (75, 95, -2.5),
            }
            payload = {
                "available": True,
                "configured": True,
                "card": "Pro",
                "hardware_pcm": "hw:CARD=Pro,DEV=0",
                "sample_rate_hz": 44100,
                "channels_count": 2,
                "scale": {
                    "name": "perceptual-amplitude",
                    "examples": {"50_percent_db": -6.02},
                },
                "channels": {
                    name: {
                        "available": True,
                        "pcm_available": True,
                        "percent": percent,
                        "raw_percent": raw_percent,
                        "db": db_value,
                        "scale": "perceptual-amplitude",
                        "error": None,
                    }
                    for name, (percent, raw_percent, db_value) in values.items()
                },
                "error": None,
            }
            return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
        if "set" in command or "live" in command:
            return subprocess.CompletedProcess(command, 0, json.dumps({"ok": True}), "")
        raise AssertionError(f"Unexpected command: {command}")


class FakeUrlResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return self.payload


class FakeUrlOpener:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def __call__(self, request, timeout=0):
        self.urls.append(request.full_url)
        if "/player/timeline/poll?" in request.full_url:
            return FakeUrlResponse(
                b'<MediaContainer><Timeline type="music" state="paused" volume="37" /></MediaContainer>'
            )
        return FakeUrlResponse(b"")


class SharedAudioMixerTests(unittest.TestCase):
    def test_shared_settings_force_alarm_pcm_without_service_handoff(self):
        settings = normalise_audio_settings(
            {
                "shared_mixer_enabled": True,
                "alsa_device": "plughw:CARD=Pro,DEV=0",
                "release_services": True,
                "restore_services": True,
            }
        )
        self.assertTrue(settings["shared_mixer_enabled"])
        self.assertEqual(settings["hardware_device"], "plughw:CARD=Pro,DEV=0")
        self.assertEqual(settings["alsa_device"], "acp_alarm")
        self.assertFalse(settings["release_services"])
        self.assertFalse(settings["restore_services"])

    def test_legacy_settings_remain_available_until_installer_migrates(self):
        settings = normalise_audio_settings(
            {
                "shared_mixer_enabled": False,
                "alsa_device": "hw:1,0",
                "release_services": True,
                "restore_services": True,
            }
        )
        self.assertFalse(settings["shared_mixer_enabled"])
        self.assertEqual(settings["alsa_device"], "hw:1,0")
        self.assertTrue(settings["release_services"])
        self.assertTrue(settings["restore_services"])

    def test_status_maps_all_four_real_mixer_controls_and_scale(self):
        with tempfile.TemporaryDirectory() as directory:
            helper = Path(directory) / "mixer-helper"
            helper.write_text("#!/bin/sh\n", encoding="utf-8")
            helper.chmod(0o755)
            runner = FakeRunner()
            mixer = SharedAudioMixer(helper, runner=runner)
            status = mixer.status()

        self.assertTrue(status["available"])
        self.assertEqual(status["hardware_pcm"], "hw:CARD=Pro,DEV=0")
        self.assertEqual(status["channels"]["master"]["percent"], 80)
        self.assertEqual(status["channels"]["master"]["raw_percent"], 96)
        self.assertEqual(status["channels"]["airplay"]["db"], -0.92)
        self.assertEqual(status["scale"]["name"], "perceptual-amplitude")
        self.assertEqual(status["devices"]["alarm"], "acp_alarm")
        self.assertEqual(runner.commands[0][-1], "status")

    def test_set_volume_is_restricted_to_known_channels_and_percentages(self):
        with tempfile.TemporaryDirectory() as directory:
            helper = Path(directory) / "mixer-helper"
            helper.write_text("#!/bin/sh\n", encoding="utf-8")
            helper.chmod(0o755)
            runner = FakeRunner()
            mixer = SharedAudioMixer(helper, runner=runner)
            status = mixer.set_volume("alarm", 55)

            with self.assertRaisesRegex(ValueError, "Unknown mixer channel"):
                mixer.set_volume("neighbours", 10)
            with self.assertRaisesRegex(ValueError, "0 to 100"):
                mixer.set_volume("master", 101)

        set_command = next(command for command in runner.commands if "set" in command)
        self.assertEqual(set_command[-3:], ["set", "alarm", "55"])
        self.assertTrue(status["available"])

    def test_live_volume_uses_non_persisting_helper_action(self):
        with tempfile.TemporaryDirectory() as directory:
            helper = Path(directory) / "mixer-helper"
            helper.write_text("#!/bin/sh\n", encoding="utf-8")
            helper.chmod(0o755)
            runner = FakeRunner()
            mixer = SharedAudioMixer(helper, runner=runner)
            mixer.set_volume("master", 64, persist=False)

        live_command = next(command for command in runner.commands if "live" in command)
        self.assertEqual(live_command[-3:], ["live", "master", "64"])

    def test_shared_release_never_invokes_legacy_service_helper(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = AlarmAudioManager(
                lambda: {
                    "alarm_audio": {
                        "shared_mixer_enabled": True,
                        "mixer_helper_path": str(Path(directory) / "missing-mixer"),
                    }
                },
                lambda: {"tones": []},
                lambda: {},
                Path(directory) / "runtime.json",
            )
            snapshot = manager._release(manager.settings())

        self.assertTrue(snapshot["services_untouched"])
        self.assertTrue(snapshot["released"])
        self.assertIn("handover_id", snapshot)


class PlexampVolumeControllerTests(unittest.TestCase):
    def test_timeline_parser_reads_music_volume(self):
        payload = b'''<MediaContainer size="2">
            <Timeline type="video" volume="12" />
            <Timeline type="music" state="playing" volume="73.4" />
        </MediaContainer>'''
        self.assertEqual(PlexampVolumeController._timeline_volume(payload), 73)

    def test_set_volume_uses_plexamp_player_parameter_endpoint(self):
        opener = FakeUrlOpener()
        controller = PlexampVolumeController("http://localhost:32500", opener=opener)
        status = controller.set_volume(37)

        self.assertEqual(status["percent"], 37)
        self.assertEqual(status["source"], "plexamp-player")
        self.assertTrue(any("/player/playback/setParameters?" in url for url in opener.urls))
        set_url = next(url for url in opener.urls if "/player/playback/setParameters?" in url)
        self.assertIn("volume=37", set_url)
        self.assertTrue(any("/player/timeline/poll?" in url for url in opener.urls))


if __name__ == "__main__":
    unittest.main()
