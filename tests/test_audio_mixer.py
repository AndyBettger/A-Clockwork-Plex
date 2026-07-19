from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.alarm_audio import AlarmAudioManager, normalise_audio_settings
from app.audio_mixer import SharedAudioMixer


class FakeRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command, **kwargs):
        self.commands.append(list(command))
        if command[-1] == "status":
            payload = {
                "available": True,
                "configured": True,
                "card": "Pro",
                "hardware_pcm": "hw:CARD=Pro,DEV=0",
                "sample_rate_hz": 44100,
                "channels_count": 2,
                "channels": {
                    name: {
                        "available": True,
                        "pcm_available": True,
                        "percent": percent,
                        "error": None,
                    }
                    for name, percent in {
                        "master": 80,
                        "plexamp": 100,
                        "airplay": 90,
                        "alarm": 75,
                    }.items()
                },
                "error": None,
            }
            return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
        if "set" in command:
            return subprocess.CompletedProcess(command, 0, json.dumps({"ok": True}), "")
        raise AssertionError(f"Unexpected command: {command}")


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

    def test_status_maps_all_four_real_mixer_controls(self):
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
        self.assertEqual(status["channels"]["airplay"]["percent"], 90)
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


if __name__ == "__main__":
    unittest.main()
