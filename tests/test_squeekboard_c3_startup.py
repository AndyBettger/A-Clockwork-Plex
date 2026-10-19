"""Opt-in desktop-login startup and vendor-first C3 handover, no Pi changes."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


startup = load(ROOT / "scripts/configure-squeekboard-c3-startup.py", 'c3_startup_test')
dev = load(ROOT / "scripts/try-squeekboard-c3-dev.py", 'c3_dev_startup_test')


class C3LoginStartupTests(unittest.TestCase):
    def test_provision_enable_check_disable_no_existing_keyboard_change(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            script = root / 'try-squeekboard-c3-dev.py'
            script.write_text('print("C3")\n')
            archive = root / 'test-only.zip'
            archive.write_bytes(b'development-artifact')
            dest = root / '.config/autostart' / startup.DESKTOP_NAME
            with mock.patch.object(startup.os, 'geteuid', return_value=1000):
                startup.enable(script, archive, dest)
                self.assertTrue(startup.managed(dest))
                value = dest.read_text()
                self.assertIn('Type=Application', value)
                self.assertIn('--startup ' + str(archive), value)
                self.assertIn('X-GNOME-Autostart-enabled=true', value)
                self.assertNotIn('systemctl enable', value)
                self.assertNotIn('sbtest', value.split('Exec=')[1].splitlines()[0])
                self.assertEqual(dest.stat().st_mode & 0o777, 0o600)
                startup.enable(script, archive, dest)  # idempotent
                startup.disable(dest)
                self.assertFalse(dest.exists())

    def test_never_overwrite_or_delete_foreign_desktop_entry(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dest = root / 'existing.desktop'
            dest.write_text('[Desktop Entry]\nExec=/usr/bin/true\n')
            script = root / 'try-squeekboard-c3-dev.py'
            script.write_text('')
            archive = root / 'candidate.zip'
            archive.write_text('test')
            with mock.patch.object(startup.os, 'geteuid', return_value=1000):
                with self.assertRaises(startup.StartupError):
                    startup.enable(script, archive, dest)
                with self.assertRaises(startup.StartupError):
                    startup.disable(dest)
            self.assertIn('Exec=/usr/bin/true', dest.read_text())

    def test_refuse_missing_archive_and_unsafe_desktop_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            script = root / 'try-squeekboard-c3-dev.py'
            script.write_text('')
            with mock.patch.object(startup.os, 'geteuid', return_value=1000):
                with self.assertRaises(startup.StartupError):
                    startup.enable(script, root / 'no.zip', root / 'auto.desktop')
            with self.assertRaises(startup.StartupError):
                startup.desktop_text(Path('/home/a b/script.py'), Path('/home/pi/c3.zip'))
            with self.assertRaises(startup.StartupError):
                startup.desktop_text(Path('/home/pi/script.py'), Path('/home/pi/c3%zip'))

    def test_session_starts_only_after_stock_keyboard_appears(self):
        archive = Path('/tmp/pinned-candidate.zip')
        trace = []
        stock = iter([[], [], [321]])
        trial = types.SimpleNamespace(
            unit_active=lambda unit: False,
            vendor_pids=lambda: (trace.append('check-stock') or next(stock)),
            orphan_trial_keyboard_pids=lambda: [],
        )
        with mock.patch.object(dev, 'load_trial', return_value=trial), \
             mock.patch.object(dev, 'pointer_state', return_value=None), \
             mock.patch.object(dev, 'start', side_effect=lambda z: trace.append(('start', z))), \
             mock.patch.object(dev.time, 'sleep', return_value=None):
            dev.start_at_login(archive, wait_seconds=20)
        self.assertEqual(trace.count('check-stock'), 3)
        self.assertEqual(trace[-1], ('start', archive))

    def test_clean_stale_pointer_only_after_live_stock_without_candidate(self):
        path = Path('/cache/old-trial/state.json')
        trace = []
        trial = types.SimpleNamespace(
            unit_active=lambda _: False,
            vendor_pids=lambda: [333],
            orphan_trial_keyboard_pids=lambda: [],
            read_state=lambda p, **opts: (trace.append(('validated', p, opts)) or {'stock_pid':1})
        )
        with mock.patch.object(dev, 'load_trial', return_value=trial), \
             mock.patch.object(dev, 'pointer_state', return_value=path), \
             mock.patch.object(dev, 'remove_pointer', side_effect=lambda p: trace.append(('remove', p))), \
             mock.patch.object(dev, 'start', side_effect=lambda p: trace.append(('start', p))):
            dev.start_at_login(Path('/pinned.zip'), wait_seconds=0)
        self.assertEqual(trace[-2:], [('remove', path), ('start', Path('/pinned.zip'))])
        self.assertEqual(trace[0][0], 'validated')

    def test_existing_candidate_or_active_dev_service_blocks_second_start(self):
        with mock.patch.object(dev, 'load_trial', return_value=types.SimpleNamespace(
            unit_active=lambda _: True,
        )), mock.patch.object(dev, 'start') as start:
            dev.start_at_login(Path('/candidate.zip'))
            start.assert_not_called()
        trial = types.SimpleNamespace(
            unit_active=lambda _: False,
            vendor_pids=lambda: [222],
            orphan_trial_keyboard_pids=lambda: [321],
        )
        with mock.patch.object(dev, 'load_trial', return_value=trial), \
             mock.patch.object(dev, 'start') as start, \
             self.assertRaises(dev.DevError):
            dev.start_at_login(Path('/candidate.zip'), wait_seconds=0)
        start.assert_not_called()

    def test_no_stock_keyboard_means_no_launch(self):
        trial = types.SimpleNamespace(
            unit_active=lambda _: False, vendor_pids=lambda: [],
        )
        with mock.patch.object(dev, 'load_trial', return_value=trial), \
             mock.patch.object(dev, 'start') as start, \
             self.assertRaises(dev.DevError):
            dev.start_at_login(Path('/candidate.zip'), wait_seconds=0)
        start.assert_not_called()


if __name__ == '__main__':
    unittest.main()
