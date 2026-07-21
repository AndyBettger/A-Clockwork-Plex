from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

from app.audio_eq import MasterEqualizer


class FakeResult:
    def __init__(self, returncode: int = 0, stdout: str = '', stderr: str = '') -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class MasterEqualizerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.helper = Path(self.temp_dir.name) / 'eq-helper'
        self.helper.write_text('#!/bin/sh\n', encoding='utf-8')
        self.helper.chmod(0o755)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_status_returns_helper_payload(self):
        payload = {
            'available': True,
            'configured': True,
            'bypassed': False,
            'bands': {'bass': {'db': 1.0}, 'mid': {'db': 0.0}, 'treble': {'db': -1.0}},
        }

        def runner(*args, **kwargs):
            return FakeResult(stdout=json.dumps(payload))

        eq = MasterEqualizer(self.helper, runner=runner)
        status = eq.status()
        self.assertTrue(status['available'])
        self.assertEqual(status['bands']['bass']['db'], 1.0)
        self.assertEqual(status['helper_path'], str(self.helper))

    def test_set_band_uses_half_db_steps(self):
        commands = []

        def runner(command, **kwargs):
            commands.append(command)
            return FakeResult(stdout=json.dumps({'available': True, 'bands': {}}))

        eq = MasterEqualizer(self.helper, runner=runner)
        eq.set_band('bass', 1.24, persist=False)
        self.assertEqual(commands[0][-3:], ['live', 'bass', '1'])

    def test_set_band_rejects_out_of_range(self):
        eq = MasterEqualizer(self.helper, runner=lambda *args, **kwargs: FakeResult())
        with self.assertRaisesRegex(ValueError, r'-6 dB to \+6 dB'):
            eq.set_band('treble', 7)

    def test_bypass_uses_restricted_helper_action(self):
        commands = []

        def runner(command, **kwargs):
            commands.append(command)
            return FakeResult(stdout=json.dumps({'available': True, 'bypassed': True}))

        eq = MasterEqualizer(self.helper, runner=runner)
        status = eq.set_bypass(True)
        self.assertTrue(status['bypassed'])
        self.assertEqual(commands[0][-2:], ['bypass', 'on'])


class EqHelperMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        helper_path = Path(__file__).resolve().parents[1] / 'scripts' / 'a-clockwork-plex-audio-eq.py'
        spec = importlib.util.spec_from_file_location('acp_eq_helper', helper_path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.helper_module: ModuleType = module

    def test_neutral_maps_to_eq10_centre(self):
        self.assertEqual(self.helper_module.db_to_raw_percent(0), 67)

    def test_restrained_range_maps_inside_plugin_range(self):
        self.assertEqual(self.helper_module.db_to_raw_percent(-6), 58)
        self.assertEqual(self.helper_module.db_to_raw_percent(6), 75)

    def test_band_groups_cover_all_ten_controls(self):
        indexes = [index for group in self.helper_module.BAND_INDEXES.values() for index in group]
        self.assertEqual(sorted(indexes), list(range(10)))


if __name__ == '__main__':
    unittest.main()
