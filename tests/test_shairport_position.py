from __future__ import annotations

import subprocess
import unittest

from app.shairport_session import parse_busctl_int64, shairport_remote_status


class ShairportPositionTests(unittest.TestCase):
    def completed(self, stdout: str, *, returncode: int = 0, stderr: str = ""):
        return subprocess.CompletedProcess(
            args=["busctl"],
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )

    def test_busctl_position_parser_accepts_signed_and_unsigned_int64(self):
        self.assertEqual(parse_busctl_int64("x 1234567"), 1234567)
        self.assertEqual(parse_busctl_int64("t 7654321"), 7654321)
        self.assertIsNone(parse_busctl_int64('s "Playing"'))

    def test_remote_status_includes_mpris_position_without_changing_availability(self):
        def runner(command, **_kwargs):
            property_name = command[-1]
            if property_name == "Available":
                return self.completed("b true\n")
            if property_name == "Position":
                return self.completed("x 3456789\n")
            return self.completed("", returncode=1, stderr="unexpected property")

        status = shairport_remote_status(
            lambda: {"available": True, "playback_status": "Playing"},
            runner=runner,
        )

        self.assertTrue(status["available"])
        self.assertEqual(status["position_us"], 3456789)
        self.assertIsNone(status["position_error"])


if __name__ == "__main__":
    unittest.main()
