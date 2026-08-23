from __future__ import annotations

import json
import unittest
from pathlib import Path

from app.application_state import DEFAULT_AIRPLAY_HOLD_SECONDS, configured_airplay_hold_seconds


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CONFIG = ROOT / "config.example.json"


class AirPlayHoldPolicyTests(unittest.TestCase):
    def test_default_is_seven_minutes(self):
        self.assertEqual(DEFAULT_AIRPLAY_HOLD_SECONDS, 420)
        self.assertEqual(configured_airplay_hold_seconds({}), 420)
        self.assertEqual(configured_airplay_hold_seconds({"airplay": {}}), 420)

    def test_example_config_uses_the_same_default(self):
        config = json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config["airplay"]["pause_hold_seconds"], 420)

    def test_configured_value_remains_bounded(self):
        self.assertEqual(configured_airplay_hold_seconds({"airplay": {"pause_hold_seconds": 7}}), 15)
        self.assertEqual(
            configured_airplay_hold_seconds({"airplay": {"pause_hold_seconds": 100000}}),
            420,
        )
        self.assertEqual(
            configured_airplay_hold_seconds({"airplay": {"pause_hold_seconds": 421}}),
            420,
        )


if __name__ == "__main__":
    unittest.main()
