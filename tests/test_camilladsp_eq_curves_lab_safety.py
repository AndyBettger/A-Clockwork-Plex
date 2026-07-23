from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / 'scripts' / 'test-camilladsp-eq-curves-lab.sh'


class CamillaDspEqCurveLaboratorySafetyTests(unittest.TestCase):
    def test_script_has_valid_shell_syntax(self):
        result = subprocess.run(
            ['bash', '-n', str(LAB)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_default_mode_precedes_audio_execution(self):
        text = LAB.read_text(encoding='utf-8')
        self.assertIn('MODE=prepare', text)
        self.assertIn('if [[ "$MODE" == prepare ]]', text)
        self.assertGreater(text.index('run_profile neutral-start'), text.index('if [[ "$MODE" == prepare ]]'))

    def test_run_is_loopback_only(self):
        text = LAB.read_text(encoding='utf-8')
        self.assertIn('INPUT_PLAYBACK="hw:${LOOPBACK_INDEX},0,0"', text)
        self.assertIn('DSP_CAPTURE="hw:${LOOPBACK_INDEX},1,0"', text)
        self.assertIn('DSP_PLAYBACK="hw:${LOOPBACK_INDEX},0,1"', text)
        self.assertIn('OUTPUT_CAPTURE="hw:${LOOPBACK_INDEX},1,1"', text)
        self.assertIn('physical-dac-unchanged', text)
        self.assertNotIn('sudo ', text)
        self.assertNotIn('modprobe', text)
        self.assertNotIn('systemctl', text)
        self.assertNotIn('/etc/alsa/conf.d', text)
        self.assertNotIn('device: "hw:Pro,0"', text)

    def test_three_band_shapes_and_limits_are_explicit(self):
        text = LAB.read_text(encoding='utf-8')
        self.assertIn('type: Lowshelf', text)
        self.assertIn('type: Peaking', text)
        self.assertIn('type: Highshelf', text)
        self.assertIn('run_profile bass-boost 6.0', text)
        self.assertIn('run_profile mid-cut 0.0 -6.0', text)
        self.assertIn('run_profile treble-cut 0.0 0.0 -6.0', text)
        self.assertIn('run_profile neutral-return', text)

    def test_requires_verified_pinned_binary(self):
        text = LAB.read_text(encoding='utf-8')
        self.assertIn('CAMILLADSP_VERSION="4.1.3"', text)
        self.assertIn('--binary is required for --run', text)
        self.assertIn('grep -Fq "$CAMILLADSP_VERSION"', text)
        self.assertNotIn('curl ', text)
        self.assertNotIn('wget ', text)


if __name__ == '__main__':
    unittest.main()
