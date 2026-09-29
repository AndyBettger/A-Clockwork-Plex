from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audio" / "rehearse-direct-failback-airplay.py"


class DirectFailbackAirplayRehearsalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location(
            "acp_direct_airplay_rehearsal", SCRIPT
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.rehearsal = module

    def test_candidate_is_exact_receiver_owned_airplay_delta(self) -> None:
        baseline = self.rehearsal.PROFILE_DIRECT.read_text(encoding="utf-8")
        candidate = self.rehearsal.render_candidate()

        self.assertNotIn("pcm.acp_airplay_live_volume", baseline)
        self.assertEqual(candidate.count("pcm.acp_airplay_live_volume"), 1)
        self.assertIn('name "A Clockwork AirPlay Live"', candidate)
        self.assertIn('slave.pcm "acp_airplay_live_volume"', candidate)

        reverted = candidate.replace(
            self.rehearsal.AIRPLAY_LIVE_PREFIX,
            self.rehearsal.AIRPLAY_PREFIX,
            1,
        )
        self.assertEqual(reverted, baseline)

    def test_candidate_preserves_direct_rate_and_alarm_lane_exactly(self) -> None:
        baseline = self.rehearsal.PROFILE_DIRECT.read_text(encoding="utf-8")
        candidate = self.rehearsal.render_candidate()

        self.assertIn("format S16_LE", candidate)
        self.assertIn("rate 44100", candidate)

        baseline_alarm = baseline[baseline.index("pcm.acp_alarm_volume") :]
        candidate_alarm = candidate[candidate.index("pcm.acp_alarm_volume") :]
        self.assertEqual(candidate_alarm, baseline_alarm)

    def test_rehearsal_does_not_modify_pinned_profile_source(self) -> None:
        before = self.rehearsal.PROFILE_DIRECT.read_bytes()
        self.rehearsal.render_candidate()
        after = self.rehearsal.PROFILE_DIRECT.read_bytes()
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
