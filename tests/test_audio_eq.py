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

    def test_neutral_uses_closest_available_control_value(self):
        self.assertEqual(self.helper_module.db_to_control_value(0), 67)
        self.assertAlmostEqual(self.helper_module.control_value_to_db(67), 0.24, places=2)

    def test_restrained_range_maps_inside_plugin_range(self):
        self.assertEqual(self.helper_module.db_to_control_value(-6), 58)
        self.assertEqual(self.helper_module.db_to_control_value(6), 75)

    def test_band_groups_cover_all_ten_controls(self):
        indexes = [index for group in self.helper_module.BAND_INDEXES.values() for index in group]
        self.assertEqual(sorted(indexes), list(range(10)))

    def test_set_controls_uses_exact_integer_not_percent_syntax(self):
        commands = []
        original_run = self.helper_module.run

        def fake_run(command, **kwargs):
            commands.append(command)
            return FakeResult()

        self.helper_module.run = fake_run
        try:
            names = [f'{index:02d}. Band' for index in range(10)]
            error = self.helper_module.set_controls('acp_equal', names, 'bass', 0.0)
        finally:
            self.helper_module.run = original_run

        self.assertIsNone(error)
        self.assertEqual(len(commands), 3)
        self.assertTrue(all(command[-1] == '67' for command in commands))
        self.assertTrue(all(not command[-1].endswith('%') for command in commands))

    def test_truncated_percent_readback_is_diagnostic_not_db(self):
        output = """
Simple mixer control '00. 31 Hz',0
  Front Left: 66 [66%]
  Front Right: 66 [66%]
"""
        parsed = self.helper_module.parse_control_contents(output)
        control = parsed['00. 31 Hz']
        self.assertEqual(control['reported_percent'], 66)
        self.assertIsNone(control['reported_db'])

    def test_read_controls_accepts_one_step_truncated_neutral(self):
        names = [f'{index:02d}. Band' for index in range(10)]
        blocks = []
        for name in names:
            blocks.append(
                f"Simple mixer control '{name}',0\n"
                "  Front Left: 66 [66%]\n"
                "  Front Right: 66 [66%]\n"
            )
        original_run = self.helper_module.run
        self.helper_module.run = lambda *args, **kwargs: FakeResult(stdout=''.join(blocks))
        try:
            diagnostics, controls, error = self.helper_module.read_controls(
                'acp_equal', names, {'bass': 0.0, 'mid': 0.0, 'treble': 0.0}
            )
        finally:
            self.helper_module.run = original_run

        self.assertIsNone(error)
        self.assertTrue(diagnostics['bass']['in_sync'])
        self.assertEqual(diagnostics['bass']['control_value'], 67)
        self.assertAlmostEqual(diagnostics['bass']['quantised_db'], 0.24, places=2)
        self.assertTrue(all(control['requested_db'] == 0.0 for control in controls))


if __name__ == '__main__':
    unittest.main()
