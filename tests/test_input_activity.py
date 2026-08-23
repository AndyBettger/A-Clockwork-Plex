from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.input_activity import EV_ABS, EV_KEY, EV_REL, EV_SYN, LinuxInputActivityMonitor


class LinuxInputActivityMonitorTests(unittest.TestCase):
    def test_activity_classifier_ignores_releases_and_sync_frames(self):
        self.assertEqual(LinuxInputActivityMonitor.activity_kind(EV_KEY, 1), "key")
        self.assertEqual(LinuxInputActivityMonitor.activity_kind(EV_KEY, 2), "key")
        self.assertIsNone(LinuxInputActivityMonitor.activity_kind(EV_KEY, 0))
        self.assertEqual(LinuxInputActivityMonitor.activity_kind(EV_REL, 4), "relative")
        self.assertIsNone(LinuxInputActivityMonitor.activity_kind(EV_REL, 0))
        self.assertEqual(LinuxInputActivityMonitor.activity_kind(EV_ABS, 0), "absolute")
        self.assertIsNone(LinuxInputActivityMonitor.activity_kind(EV_SYN, 0))

    def test_recorded_activity_snapshot_is_serializable(self):
        now = datetime(2026, 7, 28, 21, 0, tzinfo=timezone.utc)
        monitor = LinuxInputActivityMonitor(
            device_glob="/definitely/not/present/event*",
            now_provider=lambda: now,
            debounce_seconds=0,
        )

        monitor._record_activity(  # Deliberately exercises the event-to-snapshot boundary.
            {"path": "/dev/input/event7", "name": "Touchscreen"},
            kind="absolute",
            code=53,
            value=412,
        )
        snapshot = monitor.snapshot()

        self.assertEqual(snapshot["sequence"], 1)
        self.assertEqual(snapshot["last_activity_at"], now.isoformat(timespec="milliseconds"))
        self.assertEqual(snapshot["last_event"]["device"], "Touchscreen")
        self.assertEqual(snapshot["last_event"]["kind"], "absolute")
        self.assertFalse(snapshot["available"])


if __name__ == "__main__":
    unittest.main()
