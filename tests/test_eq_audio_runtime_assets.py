from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'installer' / 'profiles' / 'eq-split-bus'
SYSTEMD = PROFILE / 'systemd'
TEMPLATES = ROOT / 'installer' / 'templates'


class EqAudioRuntimeAssetTests(unittest.TestCase):
    def test_defaults_use_selected_paths_and_no_stage_c_authority_fields(self) -> None:
        defaults = (PROFILE / 'a-clockwork-plex-split-bus.defaults').read_text(
            encoding='utf-8'
        )
        self.assertIn('AUDIO_PROFILE=eq-split-bus', defaults)
        self.assertIn('EQ_STATE_PATH=/var/lib/a-clockwork-plex/split-bus/master-eq.json', defaults)
        self.assertIn('ROUTE_STATE_PATH=/var/lib/a-clockwork-plex/split-bus/route-state.json', defaults)
        self.assertIn('AUDIO_LOCK_PATH=/run/lock/a-clockwork-plex-audio-route.lock', defaults)
        self.assertNotIn('APPROVAL', defaults)
        self.assertNotIn('TRANSACTION', defaults)
        self.assertNotIn('PACKAGE_PHASE', defaults)

    def test_route_unit_prepares_before_all_audio_applications(self) -> None:
        unit = (SYSTEMD / 'a-clockwork-plex-audio-route.service').read_text(
            encoding='utf-8'
        )
        self.assertIn(
            'Before=a-clockwork-plex-camilladsp.service plexamp.service '
            'shairport-sync.service a-clockwork-plex.service',
            unit,
        )
        self.assertIn(
            'ExecStart=/usr/local/bin/a-clockwork-plex-audio-route prepare-split-bus',
            unit,
        )
        self.assertIn('OnFailure=a-clockwork-plex-audio-failback.service', unit)
        self.assertIn(
            'ConditionPathExists=/var/lib/a-clockwork-plex/split-bus/installed',
            unit,
        )
        self.assertNotIn('activation-approved', unit)

    def test_camilladsp_unit_fails_directly_into_failback_without_restart_race(self) -> None:
        unit = (SYSTEMD / 'a-clockwork-plex-camilladsp.service').read_text(
            encoding='utf-8'
        )
        self.assertIn('Requires=a-clockwork-plex-audio-route.service sound.target', unit)
        self.assertIn('Before=plexamp.service shairport-sync.service a-clockwork-plex.service', unit)
        self.assertIn('OnFailure=a-clockwork-plex-audio-failback.service', unit)
        self.assertIn('Restart=no', unit)
        self.assertNotIn('Restart=on-failure', unit)
        self.assertNotIn('RestartSec=', unit)
        self.assertNotIn('StartLimitIntervalSec=', unit)
        self.assertNotIn('StartLimitBurst=', unit)
        self.assertIn(
            'ExecStart=/usr/local/lib/a-clockwork-plex/camilladsp-4.1.3/camilladsp '
            '/etc/a-clockwork-plex/camilladsp-split-bus.yml',
            unit,
        )
        self.assertNotIn('supervise', unit)
        self.assertNotIn('runtime-authority', unit)

    def test_failback_unit_exposes_only_the_fixed_direct_transition(self) -> None:
        unit = (SYSTEMD / 'a-clockwork-plex-audio-failback.service').read_text(
            encoding='utf-8'
        )
        self.assertIn(
            'ExecStart=/usr/local/bin/a-clockwork-plex-audio-route '
            'activate-direct-failback',
            unit,
        )
        self.assertNotIn('Before=', unit)
        for app_unit in (
            'plexamp.service',
            'shairport-sync.service',
            'a-clockwork-plex.service',
        ):
            self.assertNotIn(app_unit, unit)
        self.assertNotIn('%', unit)
        self.assertNotIn('Environment=', unit)

    def test_route_sudoers_has_only_fixed_actions(self) -> None:
        sudoers = (
            TEMPLATES / 'a-clockwork-plex-audio-route.sudoers.in'
        ).read_text(encoding='utf-8')
        self.assertEqual(sudoers.count('@PROJECT_USER@ ALL='), 4)
        for action in (
            'status',
            'validate',
            'activate-split-bus',
            'activate-direct-failback',
        ):
            self.assertIn(f'a-clockwork-plex-audio-route {action}', sudoers)
        self.assertNotIn('prepare-split-bus', sudoers)
        self.assertNotIn('/bin/sh', sudoers)
        self.assertNotIn('/bin/bash', sudoers)

    def test_eq_sudoers_delegates_only_the_existing_helper_contract(self) -> None:
        sudoers = (
            TEMPLATES / 'a-clockwork-plex-audio-eq.sudoers.in'
        ).read_text(encoding='utf-8')
        self.assertEqual(sudoers.count('@PROJECT_USER@ ALL='), 5)
        for action in ('status', 'set *', 'live *', 'bypass *', 'neutral'):
            self.assertIn(f'a-clockwork-plex-audio-eq {action}', sudoers)
        self.assertNotIn('/usr/bin/amixer', sudoers)
        self.assertNotIn('alsaequal', sudoers.lower())
        self.assertNotIn('/bin/sh', sudoers)
        self.assertNotIn('/bin/bash', sudoers)


if __name__ == '__main__':
    unittest.main()
