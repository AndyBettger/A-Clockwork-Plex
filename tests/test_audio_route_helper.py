from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'scripts' / 'a-clockwork-plex-audio-route.py'
PROFILE = ROOT / 'installer' / 'profiles' / 'eq-split-bus'


class FakeResult:
    def __init__(self, returncode: int = 0, stdout: str = '', stderr: str = '') -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class AudioRouteHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location('acp_audio_route', HELPER)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.helper: ModuleType = module

    def make_controller(
        self,
        directory: str,
        *,
        fail_camilla_check: bool = False,
        active_services: dict[str, bool] | None = None,
    ):
        root = Path(directory)
        binary = root / 'camilladsp'
        binary.write_text('#!/bin/sh\n', encoding='utf-8')
        binary.chmod(0o755)
        binary_hash = hashlib.sha256(binary.read_bytes()).hexdigest()

        split = root / 'split-bus.conf'
        direct = root / 'direct-alarm-bypass.conf'
        split.write_text((PROFILE / 'split-bus.conf').read_text(encoding='utf-8'), encoding='utf-8')
        direct.write_text(
            (PROFILE / 'direct-alarm-bypass.conf').read_text(encoding='utf-8'),
            encoding='utf-8',
        )
        base = root / 'alsa.conf'
        base.write_text(
            '@hooks [\n  {\n    func load\n  }\n]\npcm.null { type null }\n',
            encoding='utf-8',
        )
        module_parameters = root / 'parameters'
        module_parameters.mkdir()
        for name, value in {
            'index': '7\n',
            'id': 'ACP_Loopback\n',
            'pcm_substreams': '2\n',
            'pcm_notify': '1\n',
        }.items():
            (module_parameters / name).write_text(value, encoding='utf-8')
        cards = root / 'cards'
        cards.write_text(' 7 [ACPLoopback    ]: Loopback - Loopback\n', encoding='utf-8')
        dac = root / 'hw_params'
        dac.write_text('closed\n', encoding='utf-8')

        values = {
            'CAMILLADSP_BINARY': str(binary),
            'CAMILLADSP_SHA256': binary_hash,
            'ACTIVE_ALSA_CONFIG': str(root / 'active-alsa.conf'),
            'SPLIT_ROUTE': str(split),
            'DIRECT_FAILBACK_ROUTE': str(direct),
            'CAMILLADSP_CONFIG': str(root / 'active-camilla.yml'),
            'STATE_DIR': str(root / 'state'),
            'EQ_STATE_PATH': str(root / 'state' / 'master-eq.json'),
            'ROUTE_STATE_PATH': str(root / 'state' / 'route-state.json'),
            'INSTALLED_MARKER': str(root / 'state' / 'installed'),
            'AUDIO_LOCK_PATH': str(root / 'audio.lock'),
            'DAC_HW_PARAMS': str(dac),
            'ALSA_BASE_CONFIG': str(base),
            'ALSA_CARDS_PATH': str(cards),
            'LOOPBACK_PARAMETERS_PATH': str(module_parameters),
        }
        settings = self.helper.RouteSettings(values)
        active = {
            settings.services['plexamp']: False,
            settings.services['airplay']: False,
            settings.services['dashboard']: False,
            settings.camilladsp_service: False,
            settings.route_service: False,
            settings.failback_service: False,
        }
        active.update(active_services or {})
        enabled = {unit: True for unit in active}
        pids = {settings.camilladsp_service: 4321}
        actions: list[tuple[str, str]] = []

        def runner(command, **kwargs):
            if command[:2] == ['/usr/bin/aplay', '-L']:
                return FakeResult(stdout='\n'.join(self.helper.PUBLIC_PCMS) + '\n')
            if command[:2] == [str(binary), '--version']:
                return FakeResult(stdout='CamillaDSP 4.1.3\n')
            if command[:2] == [str(binary), '--check']:
                if fail_camilla_check:
                    return FakeResult(returncode=1, stderr='candidate rejected')
                return FakeResult()
            if command[:3] == ['/usr/bin/systemctl', 'is-active', '--quiet']:
                return FakeResult(returncode=0 if active.get(command[3], False) else 3)
            if command[:3] == ['/usr/bin/systemctl', 'is-enabled', '--quiet']:
                return FakeResult(returncode=0 if enabled.get(command[3], False) else 1)
            if command[:2] == ['/usr/bin/systemctl', 'show']:
                return FakeResult(stdout=f"{pids.get(command[2], 0)}\n")
            if command[:2] == ['/usr/bin/systemctl', 'stop']:
                unit = command[2]
                actions.append(('stop', unit))
                active[unit] = False
                return FakeResult()
            if command[:2] == ['/usr/bin/systemctl', 'start']:
                unit = command[2]
                actions.append(('start', unit))
                active[unit] = True
                return FakeResult()
            raise AssertionError(f'unexpected command: {command}')

        controller = self.helper.RouteController(
            settings,
            runner=runner,
            sleeper=lambda seconds: None,
        )
        return controller, settings, active, actions

    def test_prepare_split_bus_renders_saved_state_and_selects_split_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller, settings, _active, _actions = self.make_controller(directory)
            settings.eq_state.parent.mkdir(parents=True)
            settings.eq_state.write_text(
                json.dumps({
                    'schema_version': 2,
                    'bypassed': False,
                    'bands': {'bass': 6.0, 'mid': 0.0, 'treble': -2.0},
                }),
                encoding='utf-8',
            )

            result = controller.prepare_split_bus()

            self.assertTrue(result['ok'])
            self.assertEqual(
                settings.active_alsa.read_text(encoding='utf-8'),
                settings.split_route.read_text(encoding='utf-8'),
            )
            rendered = settings.camilladsp_config.read_text(encoding='utf-8')
            self.assertIn('gain: 6.0', rendered)
            self.assertIn('gain: -6.5, scale: dB', rendered)
            state = json.loads(settings.route_state.read_text(encoding='utf-8'))
            self.assertEqual(state['mode'], 'split-bus-selected')

    def test_prepare_failure_selects_validated_direct_failback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller, settings, _active, _actions = self.make_controller(
                directory,
                fail_camilla_check=True,
            )

            with self.assertRaisesRegex(
                RuntimeError,
                'direct failback was selected',
            ):
                controller.prepare_split_bus()

            self.assertEqual(
                settings.active_alsa.read_text(encoding='utf-8'),
                settings.direct_route.read_text(encoding='utf-8'),
            )
            state = json.loads(settings.route_state.read_text(encoding='utf-8'))
            self.assertEqual(state['mode'], 'direct-failback')
            self.assertIn('candidate rejected', state['reason'])

    def test_status_derives_active_mode_from_selected_route_and_running_service(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller, settings, active, _actions = self.make_controller(directory)
            controller.prepare_split_bus()
            active[settings.camilladsp_service] = True

            status = controller.status()

            self.assertEqual(status['selected_mode'], 'split-bus-selected')
            self.assertEqual(status['mode'], 'split-bus-active')
            self.assertTrue(status['ok'])
            self.assertTrue(status['active_matches_split'])

    def test_direct_failback_stops_and_restores_only_previously_active_apps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller, settings, _active, actions = self.make_controller(
                directory,
                active_services={
                    'plexamp.service': True,
                    'shairport-sync.service': True,
                    'a-clockwork-plex.service': True,
                    'a-clockwork-plex-camilladsp.service': True,
                },
            )

            status = controller.activate_direct_failback()

            self.assertEqual(status['mode'], 'direct-failback')
            self.assertEqual(
                actions,
                [
                    ('stop', settings.services['dashboard']),
                    ('stop', settings.services['airplay']),
                    ('stop', settings.services['plexamp']),
                    ('stop', settings.camilladsp_service),
                    ('start', settings.services['plexamp']),
                    ('start', settings.services['airplay']),
                    ('start', settings.services['dashboard']),
                ],
            )

    def test_validate_reports_loopback_and_both_routes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller, _settings, _active, _actions = self.make_controller(directory)
            payload = controller.validate()
            self.assertTrue(payload['ok'])
            self.assertTrue(payload['checks']['loopback']['ok'])
            self.assertEqual(
                payload['checks']['split_route']['public_pcms'],
                list(self.helper.PUBLIC_PCMS),
            )


if __name__ == '__main__':
    unittest.main()
