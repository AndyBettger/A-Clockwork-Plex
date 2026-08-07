from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTE_HELPER = ROOT / 'scripts' / 'a-clockwork-plex-audio-route.py'
EQ_HELPER = ROOT / 'scripts' / 'a-clockwork-plex-audio-eq.py'
CAMILLA_UNIT = (
    ROOT
    / 'installer'
    / 'profiles'
    / 'eq-split-bus'
    / 'systemd'
    / 'a-clockwork-plex-camilladsp.service'
)


class FakeResult:
    def __init__(self, returncode: int = 0, stdout: str = '', stderr: str = '') -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class EqAudioRuntimeSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        route_spec = importlib.util.spec_from_file_location('acp_route_safety', ROUTE_HELPER)
        assert route_spec and route_spec.loader
        cls.route = importlib.util.module_from_spec(route_spec)
        route_spec.loader.exec_module(cls.route)

        eq_spec = importlib.util.spec_from_file_location('acp_eq_safety', EQ_HELPER)
        assert eq_spec and eq_spec.loader
        cls.eq = importlib.util.module_from_spec(eq_spec)
        eq_spec.loader.exec_module(cls.eq)

    def test_missing_dac_state_does_not_count_as_released(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = self.route.RouteSettings({
                'DAC_HW_PARAMS': str(Path(directory) / 'missing-hw-params'),
            })
            controller = self.route.RouteController(
                settings,
                runner=lambda *args, **kwargs: FakeResult(),
                sleeper=lambda seconds: None,
            )
            with self.assertRaisesRegex(
                RuntimeError,
                'DAC hardware state is unavailable',
            ):
                controller._wait_dac_released()

    def test_selected_split_route_becomes_active_only_with_service_and_pid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / 'camilladsp'
            binary.write_text('#!/bin/sh\n', encoding='utf-8')
            config = root / 'active.yml'
            config.write_text('test\n', encoding='utf-8')
            route_state = root / 'route-state.json'
            route_state.write_text(
                json.dumps({'mode': 'split-bus-selected', 'reason': 'test'}),
                encoding='utf-8',
            )
            settings = self.eq.Settings(
                binary=binary,
                active_config=config,
                state_path=root / 'eq-state.json',
                route_state_path=route_state,
                lock_path=root / 'audio.lock',
            )

            def runner(command, **kwargs):
                if command[:3] == ['/usr/bin/systemctl', 'show', settings.service]:
                    return FakeResult(stdout='4321\n')
                if command[:3] == ['/usr/bin/systemctl', 'is-active', '--quiet']:
                    return FakeResult()
                raise AssertionError(f'unexpected command: {command}')

            status = self.eq.EqController(settings, runner=runner).status()
            self.assertTrue(status['available'])
            self.assertEqual(status['selected_route_mode'], 'split-bus-selected')
            self.assertEqual(status['backend_state'], 'split-bus-active')

    def test_camilladsp_service_uses_unprivileged_audio_identity(self) -> None:
        unit = CAMILLA_UNIT.read_text(encoding='utf-8')
        self.assertIn('User=andy', unit)
        self.assertIn('Group=audio', unit)
        self.assertNotIn('User=root', unit)


if __name__ == '__main__':
    unittest.main()
