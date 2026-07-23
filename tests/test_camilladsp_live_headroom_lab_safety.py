from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / 'scripts' / 'test-camilladsp-live-headroom-lab.sh'


class CamillaDspLiveHeadroomLaboratorySafetyTests(unittest.TestCase):
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
        self.assertIn('--run', result.stdout)
        self.assertIn('physical DAC', result.stdout)

    def test_default_mode_precedes_audio_execution(self):
        text = LAB.read_text(encoding='utf-8')
        gate = text.index('if [[ "$MODE" == prepare ]]')
        self.assertLess(gate, text.index('"$CAMILLADSP_BINARY" --gain=0'))
        self.assertLess(gate, text.index('arecord -q -D "$OUTPUT_CAPTURE"'))
        self.assertLess(gate, text.index('timeout 6 aplay'))

    def test_run_is_loopback_only(self):
        text = LAB.read_text(encoding='utf-8')
        self.assertIn('LOOPBACK_INDEX="${LOOPBACK_INDEX:-7}"', text)
        self.assertIn('INPUT_PLAYBACK="hw:${LOOPBACK_INDEX},0,0"', text)
        self.assertIn('OUTPUT_CAPTURE="hw:${LOOPBACK_INDEX},1,1"', text)
        for forbidden in ('sudo', 'modprobe', 'systemctl', '/etc/alsa', 'hw:Pro,0'):
            self.assertNotIn(forbidden, text)

    def test_live_reload_headroom_and_limiter_are_explicit(self):
        text = LAB.read_text(encoding='utf-8')
        self.assertIn('CAMILLADSP_VERSION="4.1.3"', text)
        self.assertIn('kill -HUP "$DSP_PID"', text)
        self.assertIn('mv "$ACTIVE_CONFIG.tmp" "$ACTIVE_CONFIG"', text)
        self.assertIn('all-protected 6.0 6.0 6.0 -6.5', text)
        self.assertIn('LIMIT_DB=-1.0', text)
        self.assertIn('type: Limiter', text)
        self.assertIn('physical-dac-unchanged', text)
        self.assertIn('single-process-survival', text)


if __name__ == '__main__':
    unittest.main()
