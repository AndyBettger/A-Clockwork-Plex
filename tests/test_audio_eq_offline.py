from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.audio_eq import MasterEqualizer


class OfflineEqualizerTests(unittest.TestCase):
    def test_missing_backend_is_reported_as_laboratory_only(self):
        with tempfile.TemporaryDirectory() as directory:
            helper = Path(directory) / 'missing-eq-helper'
            status = MasterEqualizer(helper).status()

        self.assertFalse(status['available'])
        self.assertFalse(status['installed'])
        self.assertEqual(status['backend_state'], 'offline')
        self.assertEqual(status['activation'], 'laboratory-only')
        self.assertIn('controls are preserved', status['error'])
        self.assertIn('isolated laboratory procedure', status['error'])
        self.assertNotIn('Run sudo bash scripts/install-master-eq.sh', status['error'])


if __name__ == '__main__':
    unittest.main()
