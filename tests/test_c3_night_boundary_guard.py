"""Guarded two-boundary night schedule rehearsal (no live settings writes in tests)."""
from __future__ import annotations

from datetime import datetime
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/try-c3-night-boundary.py'
spec = importlib.util.spec_from_file_location('c3_boundary_guard_test', SOURCE)
assert spec is not None and spec.loader is not None
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def settings(start='22:00', end='07:00', *, enabled=True, theme='classic_dark', other='retained'):
    return {'ok': True, 'revision': 'revision-A', 'settings': {
        'display': {'night_dim_enabled': enabled, 'night_dim_start': start,
                    'night_dim_end': end, 'daytime_theme': theme,
                    'night_dim_style': 'classic', 'night_dim_active_style': 'same',
                    'other_display': other},
        'weather': {'preserved': True},
    }}


class NightBoundaryGuardTests(unittest.TestCase):
    def test_start_and_end_are_one_minute_apart_with_preparation_lead(self):
        start, end = guard.window(datetime(2026, 10, 19, 20, 3, 42, tzinfo=ZoneInfo('Europe/London')))
        self.assertEqual(start.strftime('%H:%M'), '20:07')
        self.assertEqual(end.strftime('%H:%M'), '20:08')
        self.assertEqual((end - start).total_seconds(), 60)

    def test_never_arm_overnight_or_close_to_existing_night_boundaries(self):
        for h, m in ((22, 15), (2, 30), (7, 5), (20, 41), (21, 15)):
            with self.subTest(clock=(h, m)), self.assertRaises(guard.BoundaryError):
                guard.window(datetime(2026, 10, 19, h, m, tzinfo=ZoneInfo('Europe/London')))

    def test_refuse_drift_from_user_accepted_baseline(self):
        guard.validate_baseline(settings())
        for payload in (settings('22:30', '07:00'), settings(enabled=False), settings(theme='midnight_blue')):
            with self.subTest(payload=payload), self.assertRaises(guard.BoundaryError):
                guard.validate_baseline(payload)

    def test_remote_safety_requires_no_active_alarm_and_sync_off(self):
        def available(path):
            if path == '/api/alarms/active':
                return {'ok': True, 'active': None, 'screen_required': False, 'snoozed_until': None}
            if path == '/api/osk/c3/theme-sync/status':
                return {'ok': True, 'enabled': False}
            return settings()
        with mock.patch.object(guard, 'read_api', side_effect=available):
            self.assertEqual(guard.check_remote_safety(), settings())
        def alarm_active(path):
            return {'ok': True, 'active': {'id': 1}, 'screen_required': True} if 'alarms' in path else available(path)
        with mock.patch.object(guard, 'read_api', side_effect=alarm_active), self.assertRaises(guard.BoundaryError):
            guard.check_remote_safety()

    def test_post_uses_revisioned_public_settings_without_editing_other_fields(self):
        calls = []
        def fake_open(request, timeout):
            calls.append(request)
            return io.BytesIO(b'{"ok": true}')
        with mock.patch.object(guard, 'urlopen', side_effect=fake_open):
            guard.submit_times(settings(), ('20:07', '20:08'))
        self.assertEqual(len(calls), 1)
        data = json.loads(calls[0].data)
        self.assertEqual(data['revision'], 'revision-A')
        self.assertEqual(data['settings']['display']['night_dim_start'], '20:07')
        self.assertEqual(data['settings']['display']['night_dim_end'], '20:08')
        self.assertEqual(data['settings']['display']['other_display'], 'retained')
        self.assertEqual(data['settings']['weather'], {'preserved': True})
        self.assertEqual(calls[0].get_method(), 'POST')

    def test_restore_only_expected_temporary_schedule_uses_current_revision(self):
        state = {'schema': 1, 'baseline': ['22:00', '07:00'],
                 'temporary': ['20:07', '20:08'], 'created_at': 1.0}
        old = settings('20:07', '20:08', other='newly-edited-unrelated')
        restored = settings('22:00', '07:00', other='newly-edited-unrelated')
        with mock.patch.object(guard, 'load_state', return_value=state), \
             mock.patch.object(guard, 'read_api', side_effect=[old, restored]), \
             mock.patch.object(guard, 'submit_times') as update, \
             mock.patch.object(Path, 'unlink') as unlink:
            guard.restore()
        update.assert_called_once_with(old, ('22:00', '07:00'))
        unlink.assert_called_once()

    def test_restore_fails_closed_on_unrecognised_schedule_change(self):
        state = {'schema': 1, 'baseline': ['22:00', '07:00'],
                 'temporary': ['20:07', '20:08'], 'created_at': 1.0}
        with mock.patch.object(guard, 'load_state', return_value=state), \
             mock.patch.object(guard, 'read_api', return_value=settings('20:25','20:26')), \
             mock.patch.object(guard, 'submit_times') as update, \
             mock.patch.object(guard.time, 'sleep') as sleep, \
             self.assertRaises(guard.BoundaryError):
            guard.restore()
        update.assert_not_called()
        self.assertEqual(sleep.call_count, 5)

    def test_arm_timer_before_any_change_and_validate_afterwards(self):
        events=[]
        def timer_active():
            events.append('checktimer')
            return len([x for x in events if x == 'armed']) > 0
        def call_systemd(command, **kwargs):
            events.append('armed')
            self.assertIn('--on-active=420s', command)
            return types.SimpleNamespace(returncode=0)
        def update(_snapshot, pair):
            events.append('submit')
            self.assertEqual(pair, ('20:07', '20:08'))
        with mock.patch.object(guard, 'timer_active', side_effect=timer_active), \
             mock.patch.object(guard, 'check_remote_safety', return_value=settings()), \
             mock.patch.object(guard, 'save_state') as save, \
             mock.patch.object(guard.subprocess, 'run', side_effect=call_systemd), \
             mock.patch.object(guard, 'submit_times', side_effect=update), \
             mock.patch.object(guard, 'read_api', return_value=settings('20:07', '20:08')), \
             mock.patch.object(guard.os, 'geteuid', return_value=1000):
            guard.arm(datetime(2026,10,19,20,3,42, tzinfo=ZoneInfo('Europe/London')))
        self.assertLess(events.index('armed'), events.index('submit'))
        save.assert_called_once_with('20:07', '20:08')

    def test_timer_failure_refuses_all_settings_changes(self):
        with mock.patch.object(guard, 'timer_active', return_value=False), \
             mock.patch.object(guard, 'check_remote_safety', return_value=settings()), \
             mock.patch.object(guard, 'save_state'), \
             mock.patch.object(guard.subprocess, 'run', return_value=types.SimpleNamespace(returncode=1)), \
             mock.patch.object(guard, 'submit_times') as update, \
             mock.patch.object(guard.os, 'geteuid', return_value=1000), \
             self.assertRaises(guard.BoundaryError):
            guard.arm(datetime(2026,10,19,20,3,42, tzinfo=ZoneInfo('Europe/London')))
        update.assert_not_called()

    def test_state_file_private_and_no_keyboard_or_css_mutation_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(guard, 'STATE_DIR', Path(temp) / 'guard'), \
                 mock.patch.object(guard, 'STATE', Path(temp) / 'guard/state.json'):
                guard.save_state('20:07', '20:08')
                self.assertEqual(guard.load_state()['temporary'], ['20:07', '20:08'])
                self.assertEqual((Path(temp) / 'guard/state.json').stat().st_mode & 0o777, 0o600)
        source = SOURCE.read_text()
        for mutation in ('os.kill(', 'SQUEEKBOARD_KEYBOARDSDIR', 'G_RESOURCE_OVERLAYS', 'style.css', 'apt install'):
            self.assertNotIn(mutation, source)

if __name__ == '__main__':
    unittest.main()
