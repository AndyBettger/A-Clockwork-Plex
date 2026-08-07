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
            'backend': 'camilladsp',
            'backend_state': 'split-bus-active',
            'bypassed': False,
            'bands': {
                'bass': {'db': 1.0},
                'mid': {'db': 0.0},
                'treble': {'db': -1.0},
            },
        }

        def runner(*args, **kwargs):
            return FakeResult(stdout=json.dumps(payload))

        eq = MasterEqualizer(self.helper, runner=runner)
        status = eq.status()
        self.assertTrue(status['available'])
        self.assertEqual(status['backend'], 'camilladsp')
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
        eq = MasterEqualizer(
            self.helper,
            runner=lambda *args, **kwargs: FakeResult(),
        )
        with self.assertRaisesRegex(ValueError, r'-6 dB to \+6 dB'):
            eq.set_band('treble', 7)

    def test_bypass_uses_restricted_helper_action(self):
        commands = []

        def runner(command, **kwargs):
            commands.append(command)
            return FakeResult(
                stdout=json.dumps({'available': True, 'bypassed': True})
            )

        eq = MasterEqualizer(self.helper, runner=runner)
        status = eq.set_bypass(True)
        self.assertTrue(status['bypassed'])
        self.assertEqual(commands[0][-2:], ['bypass', 'on'])


class CamillaDspEqHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        helper_path = (
            Path(__file__).resolve().parents[1]
            / 'scripts'
            / 'a-clockwork-plex-audio-eq.py'
        )
        spec = importlib.util.spec_from_file_location('acp_eq_helper', helper_path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.helper_module: ModuleType = module

    def make_controller(
        self,
        directory: str,
        *,
        pid_sequence: list[int] | None = None,
    ):
        root = Path(directory)
        binary = root / 'camilladsp'
        binary.write_text('#!/bin/sh\n', encoding='utf-8')
        binary.chmod(0o755)
        active = root / 'active.yml'
        active.write_text('original-config\n', encoding='utf-8')
        route_state = root / 'route-state.json'
        route_state.write_text(
            json.dumps({'mode': 'split-bus-active', 'reason': 'test'}),
            encoding='utf-8',
        )
        settings = self.helper_module.Settings(
            binary=binary,
            active_config=active,
            state_path=root / 'eq-state.json',
            route_state_path=route_state,
            lock_path=root / 'audio.lock',
        )
        pids = list(pid_sequence or [321])

        def runner(command, **kwargs):
            if command[:3] == ['/usr/bin/systemctl', 'show', settings.service]:
                pid = pids.pop(0) if len(pids) > 1 else pids[0]
                return FakeResult(stdout=f'{pid}\n')
            if command[:3] == ['/usr/bin/systemctl', 'is-active', '--quiet']:
                return FakeResult()
            if command[:2] == [str(binary), '--check']:
                return FakeResult()
            raise AssertionError(f'unexpected command: {command}')

        signals: list[tuple[int, int]] = []
        controller = self.helper_module.EqController(
            settings,
            runner=runner,
            signal_sender=lambda pid, sig: signals.append((pid, sig)),
            sleeper=lambda seconds: None,
        )
        return controller, settings, signals

    def test_clamp_uses_half_db_steps(self):
        self.assertEqual(self.helper_module.clamp_db(1.24), 1.0)
        self.assertEqual(self.helper_module.clamp_db(1.26), 1.5)
        self.assertEqual(self.helper_module.clamp_db(99), 6.0)

    def test_headroom_uses_largest_positive_boost_plus_margin(self):
        headroom = self.helper_module.calculate_headroom_db(
            {'bass': 6.0, 'mid': 2.0, 'treble': -3.0}
        )
        self.assertEqual(headroom, -6.5)
        self.assertEqual(
            self.helper_module.calculate_headroom_db(
                {'bass': -2.0, 'mid': 0.0, 'treble': -1.0}
            ),
            0.0,
        )

    def test_render_preserves_alarm_bypass_and_final_limiter_order(self):
        config = self.helper_module.render_config(
            self.helper_module.Settings(),
            {
                'schema_version': 2,
                'bypassed': False,
                'bands': {'bass': 6, 'mid': 0, 'treble': -2},
            },
        )
        self.assertIn('gain: 6.0', config)
        self.assertIn('gain: -6.5, scale: dB', config)
        self.assertIn('{channel: 2, gain: 0', config)
        music = config.index('names: [bass, mid, treble, headroom]')
        combine = config.index('name: combine_music_and_alarm')
        limiter = config.index('names: [final_safety_limiter]')
        self.assertLess(music, combine)
        self.assertLess(combine, limiter)

    def test_bypass_renders_neutral_filters_but_preserves_stored_curve(self):
        state = {
            'schema_version': 2,
            'bypassed': True,
            'bands': {'bass': 6, 'mid': -2, 'treble': 3},
        }
        config = self.helper_module.render_config(
            self.helper_module.Settings(),
            state,
        )
        self.assertIn(
            'parameters: {type: Lowshelf, freq: 125, gain: 0.0, slope: 6}',
            config,
        )
        self.assertIn(
            'parameters: {type: Peaking, freq: 1000, gain: 0.0, q: 0.7}',
            config,
        )
        self.assertIn(
            'parameters: {type: Highshelf, freq: 4000, gain: 0.0, slope: 6}',
            config,
        )
        self.assertIn('parameters: {gain: 0.0, scale: dB', config)
        self.assertEqual(
            self.helper_module.normalise_state(state)['bands']['bass'],
            6.0,
        )

    def test_persistent_change_validates_reloads_same_pid_and_saves_state(self):
        with tempfile.TemporaryDirectory() as directory:
            controller, settings, signals = self.make_controller(directory)
            status = controller.set_band('bass', 6, persist=True)

            saved = json.loads(settings.state_path.read_text(encoding='utf-8'))
            active = settings.active_config.read_text(encoding='utf-8')
            self.assertEqual(saved['bands']['bass'], 6.0)
            self.assertIn('gain: 6.0', active)
            self.assertIn('gain: -6.5, scale: dB', active)
            self.assertEqual(len(signals), 1)
            self.assertEqual(signals[0][0], 321)
            self.assertTrue(status['available'])
            self.assertEqual(status['backend_state'], 'split-bus-active')
            self.assertEqual(status['headroom_db'], -6.5)

    def test_live_change_does_not_replace_authoritative_state(self):
        with tempfile.TemporaryDirectory() as directory:
            controller, settings, _signals = self.make_controller(directory)
            settings.state_path.write_text(
                json.dumps({
                    'schema_version': 2,
                    'bypassed': False,
                    'bands': {'bass': 0, 'mid': 0, 'treble': 0},
                }),
                encoding='utf-8',
            )
            controller.set_band('treble', 4, persist=False)
            saved = json.loads(settings.state_path.read_text(encoding='utf-8'))
            self.assertEqual(saved['bands']['treble'], 0)
            self.assertIn(
                'gain: 4.0',
                settings.active_config.read_text(encoding='utf-8'),
            )

    def test_neutral_clears_curve_and_bypass(self):
        with tempfile.TemporaryDirectory() as directory:
            controller, settings, _signals = self.make_controller(directory)
            settings.state_path.write_text(
                json.dumps({
                    'schema_version': 2,
                    'bypassed': True,
                    'bands': {'bass': 6, 'mid': -2, 'treble': 3},
                }),
                encoding='utf-8',
            )
            status = controller.neutral()
            saved = json.loads(settings.state_path.read_text(encoding='utf-8'))
            self.assertFalse(saved['bypassed'])
            self.assertEqual(
                saved['bands'],
                {'bass': 0.0, 'mid': 0.0, 'treble': 0.0},
            )
            self.assertFalse(status['bypassed'])
            self.assertEqual(status['headroom_db'], 0.0)

    def test_changed_pid_causes_exact_config_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            controller, settings, _signals = self.make_controller(
                directory,
                pid_sequence=[321, 999],
            )
            original = settings.active_config.read_text(encoding='utf-8')
            with self.assertRaisesRegex(
                RuntimeError,
                'previous configuration was restored',
            ):
                controller.set_band('mid', 3, persist=True)
            self.assertEqual(
                settings.active_config.read_text(encoding='utf-8'),
                original,
            )
            self.assertFalse(settings.state_path.exists())

    def test_direct_failback_reports_saved_curve_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            controller, settings, _signals = self.make_controller(directory)
            settings.route_state_path.write_text(
                json.dumps({'mode': 'direct-failback', 'reason': 'forced test'}),
                encoding='utf-8',
            )
            status = controller.status()
            self.assertFalse(status['available'])
            self.assertEqual(status['backend_state'], 'direct-failback')
            self.assertIn('saved EQ curve is unavailable', status['error'])


if __name__ == '__main__':
    unittest.main()
