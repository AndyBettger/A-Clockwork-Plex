from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / 'scripts' / 'test-camilladsp-split-bus-lab.sh'


class CamillaDspSplitBusLaboratorySafetyTests(unittest.TestCase):
    def test_script_has_valid_shell_syntax(self):
        result = subprocess.run(
            ['bash', '-n', str(LAB)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_help_describes_read_only_split_bus(self):
        result = subprocess.run(
            ['bash', str(LAB), '--help'],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--prepare-only', result.stdout)
        self.assertIn('--run', result.stdout)
        self.assertIn('Music occupies loopback', result.stdout)
        self.assertIn('alarm occupies channels 2/3', result.stdout)
        self.assertIn('physical DAC', result.stdout)

    def test_default_mode_precedes_audio_execution(self):
        text = LAB.read_text(encoding='utf-8')
        gate = text.index('if [[ "$MODE" == prepare ]]')
        self.assertLess(gate, text.index('"$CAMILLADSP_BINARY" --gain=0'))
        self.assertLess(gate, text.index('arecord -q -D "$OUTPUT_CAPTURE"'))
        self.assertLess(gate, text.index('timeout 6 aplay'))

    def test_prepare_only_generates_split_bus_configs_without_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                ['bash', str(LAB), '--prepare-only', '--lab-root', directory],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            config = (Path(directory) / 'neutral.yml').read_text(encoding='utf-8')
        self.assertIn('channels: 4', config)
        self.assertIn('channels: 2', config)
        self.assertIn('channels: [0, 1]', config)
        self.assertIn('- {channel: 2, gain: 0, scale: dB, inverted: false}', config)
        self.assertIn('- {channel: 3, gain: 0, scale: dB, inverted: false}', config)
        self.assertLess(config.index('names: [music_eq, music_master, music_test_gain]'), config.index('type: Mixer'))
        self.assertLess(config.index('type: Mixer'), config.index('names: [final_safety_limiter]'))

    def test_run_contains_no_production_mutation_commands(self):
        text = LAB.read_text(encoding='utf-8')
        forbidden_commands = (
            'sudo ',
            'modprobe ',
            'systemctl ',
            'install ',
            'cp /etc/',
            'mv /etc/',
            'rm /etc/',
        )
        for forbidden in forbidden_commands:
            self.assertNotIn(forbidden, text)
        self.assertIn('INPUT_PLAYBACK="hw:${LOOPBACK_INDEX},0,0"', text)
        self.assertIn('OUTPUT_CAPTURE="hw:${LOOPBACK_INDEX},1,1"', text)

    def test_acceptance_profiles_prove_alarm_isolation(self):
        text = LAB.read_text(encoding='utf-8')
        self.assertIn('music-master-isolation', text)
        self.assertIn('-20.6 -19.4 -0.35 0.35', text)
        self.assertIn('music-eq-isolation', text)
        self.assertIn('5.2 6.6 -0.35 0.35', text)
        self.assertIn('final-limiter', text)
        self.assertIn('LIMIT_DB=-1.0', text)
        self.assertIn('Alarm level remained independent of Music Master and music EQ.', text)


if __name__ == '__main__':
    unittest.main()
