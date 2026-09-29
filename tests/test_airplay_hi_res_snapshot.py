from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audio" / "snapshot-airplay-hi-res.py"
PROFILE = ROOT / "installer" / "profiles" / "eq-split-bus"


def load_module():
    spec = importlib.util.spec_from_file_location("snapshot_airplay_hi_res", SCRIPT)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError("Could not load AirPlay hi-res snapshot helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AirplayHiResSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

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
        text = """devices:
  samplerate: 192000
  chunksize: 4096
  target_level: 12288
  enable_rate_adjust: true
  resampler: null
"""
        self.assertEqual(self.module.yaml_scalar(text, "samplerate"), "192000")
        self.assertEqual(self.module.yaml_scalar(text, "chunksize"), "4096")
        self.assertEqual(self.module.yaml_scalar(text, "target_level"), "12288")
        self.assertEqual(self.module.yaml_scalar(text, "enable_rate_adjust"), "true")
        self.assertEqual(self.module.yaml_scalar(text, "resampler"), "null")
        self.assertIsNone(self.module.yaml_scalar(text, "capture_samplerate"))

    def test_production_profile_uses_physically_accepted_high_target_geometry(self) -> None:
        route = (PROFILE / "split-bus.conf").read_text(encoding="utf-8")
        defaults = (PROFILE / "a-clockwork-plex-split-bus.defaults").read_text(
            encoding="utf-8"
        )
        camilla = (PROFILE / "camilladsp-split-bus.yml").read_text(encoding="utf-8")

        for value in (
            "format S32_LE",
            "rate 192000",
            "period_size 4096",
            "buffer_size 32768",
        ):
            self.assertIn(value, route)
        for value in (
            "SAMPLE_RATE=192000",
            "FORMAT=S32_LE",
            "PERIOD_SIZE=4096",
            "BUFFER_SIZE=32768",
            "CHUNKSIZE=4096",
            "TARGET_LEVEL=12288",
        ):
            self.assertIn(value, defaults)
        for value in (
            "samplerate: 192000",
            "chunksize: 4096",
            "target_level: 12288",
            "format: S32_LE",
        ):
            self.assertIn(value, camilla)

        self.assertAlmostEqual(self.module.milliseconds(4096, 192000), 21.33333, places=4)
        self.assertAlmostEqual(self.module.milliseconds(32768, 192000), 170.66667, places=4)
        self.assertAlmostEqual(self.module.milliseconds(12288, 192000), 64.0, places=4)

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
