from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'scripts' / 'a-clockwork-plex-audio-route.py'


class AudioRouteQuiescenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location('acp_audio_route_quiescence', HELPER)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.helper = module

    def test_partial_stop_failure_restores_already_stopped_services(self) -> None:
        settings = self.helper.RouteSettings()
        controller = self.helper.RouteController(settings)
        actions: list[tuple[str, str]] = []

        def fake_systemctl(action: str, unit: str) -> None:
            actions.append((action, unit))
            if action == 'stop' and unit == settings.services['airplay']:
                raise RuntimeError('forced AirPlay stop failure')

        controller._systemctl = fake_systemctl
        snapshot = {'plexamp': True, 'airplay': True, 'dashboard': True}

        with self.assertRaisesRegex(
            RuntimeError,
            'already stopped services were restored',
        ):
            controller._stop_applications(snapshot)

        self.assertEqual(
            actions,
            [
                ('stop', settings.services['dashboard']),
                ('stop', settings.services['airplay']),
                ('start', settings.services['dashboard']),
            ],
        )

    def test_partial_restoration_failure_is_reported_distinctly(self) -> None:
        settings = self.helper.RouteSettings()
        controller = self.helper.RouteController(settings)

        def fake_systemctl(action: str, unit: str) -> None:
            if action == 'stop' and unit == settings.services['airplay']:
                raise RuntimeError('forced AirPlay stop failure')
            if action == 'start' and unit == settings.services['dashboard']:
                raise RuntimeError('forced dashboard restore failure')

        controller._systemctl = fake_systemctl
        snapshot = {'plexamp': True, 'airplay': True, 'dashboard': True}

        with self.assertRaisesRegex(
            RuntimeError,
            'partial restoration failed',
        ):
            controller._stop_applications(snapshot)


if __name__ == '__main__':
    unittest.main()
