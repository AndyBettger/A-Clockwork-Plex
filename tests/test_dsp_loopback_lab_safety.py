from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / 'scripts' / 'test-dsp-loopback-lab.sh'


class DspLoopbackLaboratorySafetyTests(unittest.TestCase):
    def test_script_has_valid_shell_syntax(self):
        result = subprocess.run(
            ['bash', '-n', str(LAB)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_help_requires_no_root_or_audio_access(self):
        result = subprocess.run(
            ['bash', str(LAB), '--help'],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--prepare-only', result.stdout)
        self.assertIn('--run', result.stdout)
        self.assertIn('does not edit /etc', result.stdout)
        self.assertIn('never opens hw:Pro,0', LAB.read_text(encoding='utf-8'))

    def test_default_mode_does_not_load_kernel_module(self):
        text = LAB.read_text(encoding='utf-8')
        self.assertIn('RUN_TESTS=false', text)
        self.assertIn('if [[ "$RUN_TESTS" != true ]]', text)
        self.assertIn('sudo modprobe snd_aloop', text)
        self.assertGreater(text.index('if [[ "$RUN_TESTS" != true ]]'), 0)
        self.assertGreater(text.index('sudo modprobe snd_aloop'), text.index('if [[ "$RUN_TESTS" != true ]]'))

    def test_run_uses_fixed_named_loopback_and_checks_dac_unchanged(self):
        text = LAB.read_text(encoding='utf-8')
        self.assertIn('LOOPBACK_ID="${LOOPBACK_ID:-ACP_Loopback}"', text)
        self.assertIn('LOOPBACK_INDEX="${LOOPBACK_INDEX:-7}"', text)
        self.assertIn('physical-dac-unchanged', text)
        self.assertIn('cmp -s "$DAC_BEFORE" "$DAC_AFTER"', text)
        self.assertNotIn('systemctl restart', text)
        self.assertNotIn('/etc/alsa/conf.d', text)

    def test_loaded_card_is_discovered_and_used_by_numeric_index(self):
        text = LAB.read_text(encoding='utf-8')
        self.assertIn('discover_loopback_card()', text)
        self.assertIn(': Loopback - Loopback', text)
        self.assertIn('snd_aloop was already loaded; discovering and reusing its ALSA card.', text)
        self.assertIn("printf 'hw:%s,0,%s'", text)
        self.assertIn("printf 'hw:%s,1,%s'", text)
        self.assertNotIn('refusing to replace it', text)


if __name__ == '__main__':
    unittest.main()
