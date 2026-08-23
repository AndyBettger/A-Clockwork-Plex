from __future__ import annotations

import shutil
import subprocess
import unittest
from datetime import datetime
from pathlib import Path

from app.time_formatting import format_datetime


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "app" / "static" / "js" / "acp-time.js"
BASE = ROOT / "app" / "templates" / "base.html"
RUNNER = ROOT / "app" / "runner.py"
ADVANCED = ROOT / "app" / "static" / "js" / "settings-advanced.js"


class DashboardTimeFormattingTests(unittest.TestCase):
    def test_server_formatter_supports_24_and_12_hour_output(self):
        parsed = datetime(2026, 8, 2, 15, 7, 9)
        self.assertEqual(format_datetime(parsed, "24h"), "02/08/2026 15:07:09")
        self.assertEqual(format_datetime(parsed, "12h"), "02/08/2026 3:07:09 PM")

    def test_client_has_valid_javascript_syntax(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is not installed.")
        result = subprocess.run(
            [node, "--check", str(CLIENT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_base_loads_one_global_time_authority(self):
        text = BASE.read_text(encoding="utf-8")
        self.assertIn("acp-time.js", text)
        self.assertIn("data-server-clock-format", text)
        self.assertIn("data-acp-datetime", text)

    def test_runner_promotes_server_time_formatter(self):
        text = RUNNER.read_text(encoding="utf-8")
        self.assertIn("promote_server_time_formatting", text)
        self.assertIn("promote_server_time_formatting(dashboard)", text)

    def test_advanced_diagnostics_uses_global_formatter(self):
        text = ADVANCED.read_text(encoding="utf-8")
        self.assertIn("window.ACPTime?.formatDateTime", text)
        self.assertNotIn("hour12: false", text)

    def test_alarm_clock_is_compatibly_projected_through_global_formatter(self):
        text = CLIENT.read_text(encoding="utf-8")
        self.assertIn("alarm-current-time", text)
        self.assertIn("MutationObserver", text)
        self.assertIn("formatTime(new Date())", text)


if __name__ == "__main__":
    unittest.main()
