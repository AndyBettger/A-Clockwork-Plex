from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
AUDIO_EQ_JS = ROOT / 'app' / 'static' / 'js' / 'audio-eq.js'


class AudioEqUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = AUDIO_EQ_JS.read_text(encoding='utf-8')

    def test_bypass_locks_band_adjustment_controls(self):
        self.assertIn(
            'const controlsEnabled = available && !bypassed;',
            self.source,
        )
        self.assertIn(
            "knob.setAttribute('aria-disabled', controlsEnabled ? 'false' : 'true');",
            self.source,
        )
        self.assertIn(
            'knob.tabIndex = controlsEnabled ? 0 : -1;',
            self.source,
        )
        self.assertIn(
            'if (range) range.disabled = !controlsEnabled;',
            self.source,
        )

    def test_eq_copy_truthfully_excludes_alarm_lane(self):
        self.assertNotIn('All sources · before Master', self.source)
        self.assertNotIn(
            'shared by Plexamp, AirPlay and alarms',
            self.source,
        )
        self.assertIn('Plexamp + AirPlay · music only', self.source)
        self.assertIn('Scheduled alarms bypass the music EQ.', self.source)


if __name__ == '__main__':
    unittest.main()
