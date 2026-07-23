from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / 'scripts' / 'test-master-eq-lab-stage2.sh'


class EqLaboratoryStageTwoSafetyTests(unittest.TestCase):
    def test_stage_two_script_has_valid_shell_syntax(self):
        result = subprocess.run(
            ['bash', '-n', str(LAB)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_stage_two_defaults_to_prepare_only(self):
        text = LAB.read_text(encoding='utf-8')
        self.assertIn('RUN_TESTS=false', text)
        self.assertIn('if [[ "$RUN_TESTS" != true ]]', text)
        self.assertNotIn('systemctl restart', text)
        self.assertNotIn('/etc/alsa/conf.d', text)
        self.assertNotIn('shairport-sync.conf', text)

    def test_stage_two_contains_exact_production_order_and_valid_concurrency(self):
        text = LAB.read_text(encoding='utf-8')
        self.assertIn('pcm.acp_lab2_e_volume', text)
        self.assertIn('slave.pcm "acp_lab2_e_equal"', text)
        self.assertIn('slave.pcm "$MASTER_PCM"', text)
        self.assertIn('acp_lab2_a1+acp_lab2_a2', text)
        self.assertNotIn('acp_lab_b@44.1k + acp_lab_c@48k', text)

    def test_stage_two_help_describes_temporary_softvol(self):
        result = subprocess.run(
            ['bash', str(LAB), '--help'],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('temporary ALSA softvol control', result.stdout)
        self.assertIn('does not alter any A Clockwork Plex', result.stdout)


if __name__ == '__main__':
    unittest.main()
