from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "scripts" / "test-split-bus-alsa-routing-lab.sh"


class SplitBusAlsaRoutingLaboratorySafetyTests(unittest.TestCase):
    def test_script_has_valid_shell_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(LAB)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_help_describes_loopback_only_scope(self):
        result = subprocess.run(
            ["bash", str(LAB), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--prepare-only", result.stdout)
        self.assertIn("--run", result.stdout)
        self.assertIn("ALSA_CONFIG_PATH", result.stdout)
        self.assertIn("physical DAC", result.stdout)

    def test_default_mode_gates_all_audio_io(self):
        text = LAB.read_text(encoding="utf-8")
        gate = text.index('if [[ "$MODE" == prepare ]]')
        self.assertLess(gate, text.index('arecord -q'))
        self.assertLess(gate, text.index('timeout 5 aplay -q'))

    def test_no_production_write_or_service_path_exists(self):
        text = LAB.read_text(encoding="utf-8")
        for forbidden in (
            "sudo ",
            "systemctl",
            "alsactl",
            "amixer",
            "/etc/alsa",
            "hw:Pro,0",
            "install -",
        ):
            self.assertNotIn(forbidden, text)
        self.assertIn('ALSA_CONFIG_PATH="$ALSA_ROOT"', text)

    def test_music_and_alarm_channel_mappings_are_explicit(self):
        text = LAB.read_text(encoding="utf-8")
        self.assertIn("channels $BUS_CHANNELS", text)
        self.assertIn("0.0 1", text)
        self.assertIn("1.1 1", text)
        self.assertIn("0.2 1", text)
        self.assertIn("1.3 1", text)
        self.assertIn("Music mapping: source L/R -> bus 0/1", text)
        self.assertIn("Alarm mapping: source L/R -> bus 2/3", text)

    def test_lane_isolation_concurrency_and_dac_checks_are_required(self):
        text = LAB.read_text(encoding="utf-8")
        self.assertIn('classify("music-lane"', text)
        self.assertIn('classify("alarm-lane"', text)
        self.assertIn('classify("concurrent-lanes"', text)
        self.assertIn("inactive_maximum = 5.0", text)
        self.assertIn("physical-dac-unchanged", text)
        self.assertIn("both source PCMs opened concurrently", text)


if __name__ == "__main__":
    unittest.main()
