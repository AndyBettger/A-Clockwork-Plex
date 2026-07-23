from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / 'scripts' / 'test-camilladsp-loopback-lab.sh'


class CamillaDspLoopbackLaboratorySafetyTests(unittest.TestCase):
    def test_script_has_valid_shell_syntax(self):
        result = subprocess.run(
            ['bash', '-n', str(LAB)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_help_is_read_only(self):
        result = subprocess.run(
            ['bash', str(LAB), '--help'],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--prepare-only', result.stdout)
        self.assertIn('--fetch', result.stdout)
        self.assertIn('--run', result.stdout)
        self.assertIn('never loads a kernel module', result.stdout)
        self.assertIn('opens hw:Pro,0', result.stdout)

    def test_default_mode_precedes_download_and_audio(self):
        text = LAB.read_text(encoding='utf-8')
        gate = text.index('if [[ "$MODE" == prepare ]]')
        self.assertLess(gate, text.index('curl -fsSL'))
        self.assertLess(gate, text.index('arecord -q -D "$OUTPUT_CAPTURE"'))
        self.assertLess(gate, text.index('aplay -q -D "$INPUT_PLAYBACK"'))

    def test_binary_is_pinned_and_digest_verified(self):
        text = LAB.read_text(encoding='utf-8')
        self.assertIn('CAMILLADSP_VERSION="4.1.3"', text)
        self.assertIn('camilladsp-linux-aarch64.tar.gz', text)
        self.assertIn('api.github.com/repos/HEnquist/camilladsp/releases/tags', text)
        self.assertIn('asset_digest#sha256:', text)
        self.assertIn('actual_sha', text)
        self.assertIn('--check "$CONFIG_FILE"', text)

    def test_run_is_loopback_only_and_measures_gain(self):
        text = LAB.read_text(encoding='utf-8')
        self.assertIn('DSP_CAPTURE="hw:${LOOPBACK_INDEX},1,0"', text)
        self.assertIn('DSP_PLAYBACK="hw:${LOOPBACK_INDEX},0,1"', text)
        self.assertIn('GAIN_DB=-6.0', text)
        self.assertIn('dsp-gain', text)
        self.assertIn('physical-dac-unchanged', text)
        self.assertNotIn('sudo ', text)
        self.assertNotIn('modprobe ', text)
        self.assertNotIn('systemctl ', text)
        self.assertNotIn('/etc/alsa/conf.d', text)


if __name__ == '__main__':
    unittest.main()
