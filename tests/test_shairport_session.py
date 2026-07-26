from __future__ import annotations

import subprocess
import unittest

from app.shairport_session import parse_busctl_bool, shairport_remote_status


class ShairportSessionStatusTests(unittest.TestCase):
    def completed(self, stdout: str, *, returncode: int = 0, stderr: str = ""):
        return subprocess.CompletedProcess(
            args=["busctl"],
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )

    def test_busctl_boolean_parser(self):
        self.assertIs(parse_busctl_bool("b true"), True)
        self.assertIs(parse_busctl_bool("b false"), False)
        self.assertIsNone(parse_busctl_bool('s "Playing"'))

    def test_connected_pause_keeps_sender_available(self):
        def runner(*_args, **_kwargs):
            return self.completed("b true\n")

        status = shairport_remote_status(
            lambda: {"available": True, "playback_status": "Paused"},
            runner=runner,
        )

        self.assertTrue(status["mpris_service_available"])
        self.assertTrue(status["sender_available"])
        self.assertTrue(status["available"])
        self.assertEqual(status["availability_source"], "shairport-remote-control")

    def test_disconnected_sender_overrides_live_mpris_service(self):
        def runner(*_args, **_kwargs):
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
            lambda: {"available": True, "playback_status": "Paused"},
            runner=runner,
        )

        self.assertTrue(status["available"])
        self.assertIsNone(status["sender_available"])
        self.assertEqual(status["availability_source"], "mpris-service-fallback")
        self.assertIn("property unavailable", status["sender_error"])


if __name__ == "__main__":
    unittest.main()
