from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audio" / "snapshot-airplay-hi-res.py"
REHEARSAL = ROOT / "scripts" / "audio" / "rehearse-hi-res-bus.py"


def load_module():
    spec = importlib.util.spec_from_file_location("snapshot_airplay_hi_res", SCRIPT)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError("Could not load AirPlay hi-res snapshot helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_rehearsal_module():
    spec = importlib.util.spec_from_file_location("rehearse_hi_res_bus", REHEARSAL)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError("Could not load hi-res rehearsal helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AirplayHiResSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()
        cls.rehearsal = load_rehearsal_module()

    def test_duration_geometry_exposes_fixed_frame_time_collapse(self) -> None:
        self.assertAlmostEqual(self.module.milliseconds(1024, 44100), 23.21995, places=4)
        self.assertAlmostEqual(self.module.milliseconds(1024, 192000), 5.33333, places=4)
        self.assertAlmostEqual(self.module.milliseconds(8192, 44100), 185.75964, places=4)
        self.assertAlmostEqual(self.module.milliseconds(8192, 192000), 42.66667, places=4)
        self.assertAlmostEqual(self.module.milliseconds(2048, 192000), 10.66667, places=4)

    def test_duration_rejects_missing_or_invalid_rate(self) -> None:
        self.assertIsNone(self.module.milliseconds(None, 192000))
        self.assertIsNone(self.module.milliseconds(1024, None))
        self.assertIsNone(self.module.milliseconds(1024, 0))

    def test_yaml_scalar_reads_device_values(self) -> None:
        text = """devices:\n  samplerate: 192000\n  chunksize: 1024\n  enable_rate_adjust: true\n  resampler: null\n"""
        self.assertEqual(self.module.yaml_scalar(text, "samplerate"), "192000")
        self.assertEqual(self.module.yaml_scalar(text, "chunksize"), "1024")
        self.assertEqual(self.module.yaml_scalar(text, "enable_rate_adjust"), "true")
        self.assertEqual(self.module.yaml_scalar(text, "resampler"), "null")
        self.assertIsNone(self.module.yaml_scalar(text, "capture_samplerate"))

    def test_time_scaled_192_geometry_preserves_time_headroom(self) -> None:
        geometry = self.rehearsal.candidate_geometry(192000, "time-scaled")
        self.assertEqual(
            geometry,
            {
                "period_size": 4096,
                "buffer_size": 32768,
                "chunksize": 4096,
                "target_level": 8192,
            },
        )
        self.assertAlmostEqual(
            self.module.milliseconds(geometry["chunksize"], 192000),
            21.33333,
            places=4,
        )
        self.assertAlmostEqual(
            self.module.milliseconds(geometry["buffer_size"], 192000),
            170.66667,
            places=4,
        )
        route, defaults = self.rehearsal.render_candidate(192000, "time-scaled")
        self.assertIn("        period_size 4096\n", route)
        self.assertIn("        buffer_size 32768\n", route)
        self.assertIn("PERIOD_SIZE=4096\n", defaults)
        self.assertIn("BUFFER_SIZE=32768\n", defaults)
        self.assertIn("CHUNKSIZE=4096\n", defaults)
        self.assertIn("TARGET_LEVEL=8192\n", defaults)

    def test_time_scaled_high_target_changes_only_192_target_level(self) -> None:
        baseline = self.rehearsal.candidate_geometry(192000, "time-scaled")
        candidate = self.rehearsal.candidate_geometry(192000, "time-scaled-high-target")

        self.assertEqual(candidate["period_size"], baseline["period_size"])
        self.assertEqual(candidate["buffer_size"], baseline["buffer_size"])
        self.assertEqual(candidate["chunksize"], baseline["chunksize"])
        self.assertEqual(baseline["target_level"], 8192)
        self.assertEqual(candidate["target_level"], 12288)

        route, defaults = self.rehearsal.render_candidate(
            192000, "time-scaled-high-target"
        )
        self.assertIn("        period_size 4096\n", route)
        self.assertIn("        buffer_size 32768\n", route)
        self.assertIn("PERIOD_SIZE=4096\n", defaults)
        self.assertIn("BUFFER_SIZE=32768\n", defaults)
        self.assertIn("CHUNKSIZE=4096\n", defaults)
        self.assertIn("TARGET_LEVEL=12288\n", defaults)

    def test_time_scaled_high_target_is_deliberately_192_only(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError, "No time-scaled-high-target geometry exists for rate 96000"
        ):
            self.rehearsal.candidate_geometry(96000, "time-scaled-high-target")

    def test_unchanged_timing_profile_preserves_original_frame_counts(self) -> None:
        route, defaults = self.rehearsal.render_candidate(192000, "unchanged")
        self.assertIn("        period_size 1024\n", route)
        self.assertIn("        buffer_size 8192\n", route)
        self.assertIn("PERIOD_SIZE=1024\n", defaults)
        self.assertIn("BUFFER_SIZE=8192\n", defaults)
        self.assertIn("CHUNKSIZE=1024\n", defaults)
        self.assertIn("TARGET_LEVEL=2048\n", defaults)

    def test_journal_redaction_removes_ipv4_and_mac_addresses(self) -> None:
        line = "peer 192.168.1.45 hardware aa:bb:cc:dd:ee:ff underrun"
        redacted = self.module.redact(line)
        self.assertNotIn("192.168.1.45", redacted)
        self.assertNotIn("aa:bb:cc:dd:ee:ff", redacted)
        self.assertIn("<ip>", redacted)
        self.assertIn("<mac>", redacted)
        self.assertIn("underrun", redacted)


if __name__ == "__main__":
    unittest.main()
