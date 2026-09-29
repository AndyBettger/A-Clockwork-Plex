from __future__ import annotations

import subprocess
import unittest

from app.shairport_session import (
    AIRPLAY_VOLUME_MUTE_DB,
    airplay_db_to_percent,
    airplay_percent_to_db,
    parse_busctl_bool,
    parse_busctl_double,
    set_sender_airplay_volume,
    shairport_remote_status,
)


class ShairportSessionStatusTests(unittest.TestCase):
    def completed(self, stdout: str, *, returncode: int = 0, stderr: str = ""):
        return subprocess.CompletedProcess(
            args=["busctl"],
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )

    def test_busctl_scalar_parsers(self):
        self.assertIs(parse_busctl_bool("b true"), True)
        self.assertIs(parse_busctl_bool("b false"), False)
        self.assertIsNone(parse_busctl_bool('s "Playing"'))
        self.assertEqual(parse_busctl_double("d -12.5"), -12.5)
        self.assertIsNone(parse_busctl_double("b true"))

    def test_airplay_volume_scale_maps_slider_linearly_and_zero_to_mute(self):
        self.assertEqual(airplay_db_to_percent(-30.0), 0)
        self.assertEqual(airplay_db_to_percent(-15.0), 50)
        self.assertEqual(airplay_db_to_percent(0.0), 100)
        self.assertEqual(airplay_db_to_percent(-144.0), 0)
        self.assertEqual(airplay_percent_to_db(0), AIRPLAY_VOLUME_MUTE_DB)
        self.assertAlmostEqual(airplay_percent_to_db(50), -15.0, places=6)
        self.assertAlmostEqual(airplay_percent_to_db(100), 0.0, places=6)

    def test_connected_pause_keeps_sender_available_and_uses_native_volume(self):
        def runner(command, **_kwargs):
            if command[-1] == "Available":
                return self.completed("b true\n")
            if command[-1] == "AirplayVolume":
                return self.completed("d -15.0\n")
            raise AssertionError(command)

        status = shairport_remote_status(
            lambda: {
                "available": True,
                "playback_status": "Paused",
                "volume": 0.2,
                "volume_percent": 20,
            },
            runner=runner,
        )

        self.assertTrue(status["mpris_service_available"])
        self.assertTrue(status["sender_available"])
        self.assertTrue(status["available"])
        self.assertEqual(status["availability_source"], "shairport-remote-control")
        self.assertEqual(status["volume_percent"], 50)
        self.assertEqual(status["volume"], 0.5)
        self.assertEqual(status["airplay_volume_db"], -15.0)
        self.assertEqual(status["volume_source"], "shairport-remote-control-airplay")

    def test_disconnected_sender_overrides_live_mpris_service(self):
        def runner(command, **_kwargs):
            self.assertEqual(command[-1], "Available")
            return self.completed("b false\n")

        status = shairport_remote_status(
            lambda: {"available": True, "playback_status": "Paused"},
            runner=runner,
        )

        self.assertTrue(status["mpris_service_available"])
        self.assertFalse(status["sender_available"])
        self.assertFalse(status["available"])
        self.assertEqual(status["availability_source"], "shairport-remote-control")

    def test_dbus_failure_falls_back_to_mpris_without_false_disconnect(self):
        def runner(*_args, **_kwargs):
            return self.completed("", returncode=1, stderr="property unavailable")

        status = shairport_remote_status(
            lambda: {
                "available": True,
                "playback_status": "Paused",
                "volume": 0.42,
                "volume_percent": 42,
            },
            runner=runner,
        )

        self.assertTrue(status["available"])
        self.assertIsNone(status["sender_available"])
        self.assertEqual(status["availability_source"], "mpris-service-fallback")
        self.assertEqual(status["volume_percent"], 42)
        self.assertIn("property unavailable", status["sender_error"])

    def test_native_sender_volume_command_protects_negative_db_from_option_parsing(self):
        commands = []

        def runner(command, **_kwargs):
            commands.append(command)
            return self.completed("")

        ok, error = set_sender_airplay_volume(58, runner=runner)

        self.assertTrue(ok)
        self.assertIsNone(error)
        self.assertEqual(commands[0][3], "--")
        self.assertEqual(commands[0][-2], "d")
        self.assertTrue(commands[0][-1].startswith("-"))


    def test_native_sender_volume_command_uses_airplay_db_scale(self):
        commands = []

        def runner(command, **_kwargs):
            commands.append(command)
            return self.completed("")

        ok, error = set_sender_airplay_volume(75, runner=runner)

        self.assertTrue(ok)
        self.assertIsNone(error)
        self.assertEqual(
            commands,
            [[
                "/usr/bin/busctl",
                "--system",
                "call",
                "--",
                "org.gnome.ShairportSync",
                "/org/gnome/ShairportSync",
                "org.gnome.ShairportSync.RemoteControl",
                "SetAirplayVolume",
                "d",
                "-7.500000",
            ]],
        )


if __name__ == "__main__":
    unittest.main()
