"""Fast functional checks for the opt-in, long-running native C3 keyboard session."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'scripts/try-squeekboard-c3-dev.py'
spec = importlib.util.spec_from_file_location('acp_c3_dev_test', PATH)
assert spec and spec.loader
dev = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = dev
spec.loader.exec_module(dev)

BRIDGE_PATH = ROOT / 'app/squeekboard_theme_sync.py'
bridge_spec = importlib.util.spec_from_file_location('acp_c3_dev_bridge_test', BRIDGE_PATH)
assert bridge_spec and bridge_spec.loader
bridge = importlib.util.module_from_spec(bridge_spec)
sys.modules[bridge_spec.name] = bridge
bridge_spec.loader.exec_module(bridge)


class C3DevSessionTests(unittest.TestCase):
    def test_pointer_is_private_and_no_untrusted_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'private'
            root.mkdir(mode=0o700)
            state = root / 'trial-test/state.json'
            with mock.patch.object(dev, 'STATE_FILE', root / 'dev-active.json'), \
                 mock.patch.object(dev.os, 'getuid', return_value=root.stat().st_uid):
                trial = types.SimpleNamespace(ROOT=root)
                dev.save_pointer(state, trial)
                self.assertEqual(dev.pointer_state(), state)
                self.assertEqual(stat.S_IMODE(dev.STATE_FILE.stat().st_mode), 0o600)
                dev.remove_pointer(state)
                self.assertIsNone(dev.pointer_state())
                (root / 'elsewhere').write_text('safe')
                (root / 'dev-active.json').symlink_to(root / 'elsewhere')
                with self.assertRaises(dev.DevError):
                    dev.pointer_state()

    def test_live_candidate_is_eligible_without_180_second_timer(self):
        path = Path('/demo/trial-test/state.json')
        trial = types.SimpleNamespace(
            TRIAL_UNIT='acp-squeekboard-c3-trial',
            ROLLBACK_UNIT='acp-squeekboard-c3-restore',
            C2_TRIAL_UNIT='acp-squeekboard-overlay-trial',
            C2_ROLLBACK_UNIT='acp-squeekboard-overlay-restore',
            read_state=lambda _: {'theme_sync': True, 'candidate': str(path.parent / 'candidate')},
            candidate_pids=lambda _: [301],
            vendor_pids=lambda: [],
        )
        active = lambda unit: unit == 'acp-squeekboard-c3-dev.service'
        with mock.patch.object(dev, 'pointer_state', return_value=path):
            self.assertEqual(dev.active_state(trial, unit_check=active), path)
            self.assertIsNone(dev.active_state(trial, unit_check=lambda _: False))
            self.assertIsNone(dev.active_state(
                trial, unit_check=lambda x: x in (dev.UNIT + '.service', trial.TRIAL_UNIT + '.service')))

    def test_dev_launch_has_no_keyboard_timer_or_autostart_install(self):
        state = Path('/dummy/trial-abcd/state.json')
        archive = Path('/dummy/c3.zip')
        trial = types.SimpleNamespace(
            unit_active=lambda _: False,
            prepare=mock.Mock(return_value=(111, {'WAYLAND_DISPLAY': 'wayland-0'}, state)), 
            unit_environment=lambda env: ['--setenv=WAYLAND_DISPLAY=wayland-0'],
            run=mock.Mock(return_value=types.SimpleNamespace(returncode=0)),
        )
        with mock.patch.object(dev, 'load_trial', return_value=trial), \
             mock.patch.object(dev, 'pointer_state', return_value=None), \
             mock.patch.object(dev, 'save_pointer') as save, \
             mock.patch.object(dev, 'remove_pointer') as remove:
            dev.start(archive)
        save.assert_called_once_with(state, trial)
        remove.assert_not_called()
        prepare_args = trial.prepare.call_args
        self.assertEqual(prepare_args.kwargs, {
            'modify': True, 'theme_sync': True, 'allow_selected_palette': True,
        })
        args = trial.run.call_args.args
        self.assertIn('--unit=acp-squeekboard-c3-dev', args)
        self.assertIn('--property=KillMode=mixed', args)
        self.assertIn('--property=TimeoutStopSec=25s', args)
        self.assertNotIn('--on-active=240s', args)
        self.assertNotIn('--on-active=180s', args)
        self.assertEqual(args[-2:], ('--worker', str(state)))

    def test_dev_launch_failure_does_not_remove_stock_keyboard(self):
        state = Path('/dummy/trial-abcd/state.json')
        trial = types.SimpleNamespace(
            unit_active=lambda _: False,
            prepare=lambda *a, **k: (111, {}, state),
            unit_environment=lambda _: [],
            run=lambda *a, **k: types.SimpleNamespace(returncode=1, stderr='failed'),
        )
        with mock.patch.object(dev, 'load_trial', return_value=trial), \
             mock.patch.object(dev, 'pointer_state', return_value=None), \
             mock.patch.object(dev, 'save_pointer'), \
             mock.patch.object(dev, 'remove_pointer') as remove:
            with self.assertRaises(dev.DevError):
                dev.start(Path('/dummy/c3.zip'))
        remove.assert_called_once_with(state)

    def test_stop_waits_for_service_then_restores_stock(self):
        state = Path('/dummy/trial-abcd/state.json')
        calls = []
        def is_active(_unit):
            calls.append('active')
            return calls.count('active') == 1
        trial = types.SimpleNamespace(
            unit_active=is_active,
            run=lambda *a, **k: (calls.append('stop') or types.SimpleNamespace(returncode=0)),
            restore_stock=lambda *a, **k: calls.append('restore'),
        )
        with mock.patch.object(dev, 'load_trial', return_value=trial), \
             mock.patch.object(dev, 'pointer_state', return_value=state), \
             mock.patch.object(dev, 'remove_pointer') as remove:
            dev.stop()
        self.assertLess(calls.index('stop'), calls.index('restore'))
        remove.assert_called_once_with(state)

    def test_bridge_accepts_one_exact_dev_candidate_but_preserves_old_gates(self):
        path = Path('/dummy/trial-abcd/state.json')
        actual_trial = types.SimpleNamespace(TRIAL_UNIT='trial', ROLLBACK_UNIT='restore',
            C2_TRIAL_UNIT='c2-trial', C2_ROLLBACK_UNIT='c2-restore')
        actual_dev = types.SimpleNamespace(active_state=mock.Mock(return_value=path))
        def load(name):
            return actual_dev if name == 'try-squeekboard-c3-dev.py' else actual_trial
        with mock.patch.object(bridge, 'load_script', side_effect=load), \
             mock.patch.object(bridge.os, 'geteuid', return_value=1000), \
             mock.patch.object(bridge, 'user_unit_active',
                               side_effect=lambda x: x == dev.UNIT + '.service') as check:
            self.assertEqual(bridge.opted_in_trial(), path)
            args = actual_dev.active_state.call_args
            self.assertIs(args.kwargs['trial'], actual_trial)
            self.assertIs(args.kwargs['unit_check'], check)
        self.assertIn('acp-squeekboard-c3-dev.service',
                      (ROOT / 'app/squeekboard_theme_sync.py').read_text())

    def test_session_never_installs_or_enables_service_and_keeps_pinned_c3_artifact(self):
        source = PATH.read_text()
        self.assertIn('allow_selected_palette=True', source)
        self.assertIn('trial.restore_stock(path, stop_trial=False)', source)
        self.assertIn('trial.read_state(path)', source)
        for unsupported in ('systemctl enable', 'systemctl --system', 'apt-get install',
                            'chmod 777', 'os.chmod("/usr/bin/', 'dpkg -i'):
            self.assertNotIn(unsupported, source)
        self.assertIn('--collect', source)
        self.assertIn("'--stop'", source)
        self.assertNotIn('TRIAL_SECONDS', source)


if __name__ == '__main__':
    unittest.main()
