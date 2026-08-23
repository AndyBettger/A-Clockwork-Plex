from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / 'installer' / 'lib' / 'common.sh'
SERVICES = ROOT / 'installer' / 'lib' / 'services.sh'
AUDIO = ROOT / 'installer' / 'lib' / 'audio.sh'


class EqAudioInstallerLibraryTests(unittest.TestCase):
    def run_bash(self, script: str, *, env: dict[str, str] | None = None):
        merged = os.environ.copy()
        if env:
            merged.update(env)
        return subprocess.run(
            ['/bin/bash', '-c', script],
            cwd=ROOT,
            env=merged,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_library_shell_syntax(self) -> None:
        result = subprocess.run(
            ['/bin/bash', '-n', str(COMMON), str(SERVICES), str(AUDIO)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rooted_install_writes_complete_managed_file_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'rootfs'
            root.mkdir()
            binary = Path(directory) / 'camilladsp'
            binary.write_text('#!/bin/sh\n', encoding='utf-8')
            binary.chmod(0o755)
            script = f'''
source {COMMON!s}
source {AUDIO!s}
ACP_ROOT={root!s}
acp_install_audio_files {binary!s} testuser &&
acp_write_installed_marker
'''
            result = self.run_bash(script)
            self.assertEqual(result.returncode, 0, result.stderr)

            destinations = [
                line
                for line in self.run_bash(
                    f'source {COMMON!s}; source {AUDIO!s}; acp_managed_file_destinations'
                ).stdout.splitlines()
                if line
            ]
            self.assertEqual(len(destinations), 18)
            for destination in destinations:
                installed = root / destination.lstrip('/')
                self.assertTrue(installed.is_file(), destination)

            self.assertEqual(
                (root / 'usr/local/lib/a-clockwork-plex/camilladsp-4.1.3/camilladsp').read_bytes(),
                binary.read_bytes(),
            )
            self.assertEqual(
                stat.S_IMODE((root / 'usr/local/bin/a-clockwork-plex-audio-route').stat().st_mode),
                0o755,
            )
            self.assertEqual(
                stat.S_IMODE((root / 'etc/sudoers.d/a-clockwork-plex-audio-eq').stat().st_mode),
                0o440,
            )
            sudoers = (root / 'etc/sudoers.d/a-clockwork-plex-audio-eq').read_text(
                encoding='utf-8'
            )
            self.assertIn('testuser ALL=(root)', sudoers)
            self.assertNotIn('@PROJECT_USER@', sudoers)

            camilla_unit = (
                root / 'etc/systemd/system/a-clockwork-plex-camilladsp.service'
            ).read_text(encoding='utf-8')
            self.assertIn('User=testuser', camilla_unit)
            self.assertIn('Group=audio', camilla_unit)
            self.assertNotIn('ACP_PROJECT_USER', camilla_unit)
            self.assertNotIn('User=andy', camilla_unit)

            state = json.loads(
                (root / 'var/lib/a-clockwork-plex/split-bus/master-eq.json').read_text(
                    encoding='utf-8'
                )
            )
            self.assertEqual(state['bands'], {'bass': 0.0, 'mid': 0.0, 'treble': 0.0})
            self.assertFalse(state['bypassed'])
            self.assertEqual(
                (root / 'var/lib/a-clockwork-plex/split-bus/installed').read_text(
                    encoding='utf-8'
                ),
                'eq-split-bus\n',
            )

    def test_remove_managed_files_preserves_saved_eq_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'rootfs'
            root.mkdir()
            binary = Path(directory) / 'camilladsp'
            binary.write_text('#!/bin/sh\n', encoding='utf-8')
            binary.chmod(0o755)
            script = f'''
source {COMMON!s}
source {AUDIO!s}
ACP_ROOT={root!s}
acp_install_audio_files {binary!s} testuser &&
acp_write_installed_marker &&
acp_remove_managed_audio_files
'''
            result = self.run_bash(script)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(
                (root / 'var/lib/a-clockwork-plex/split-bus/master-eq.json').is_file()
            )
            self.assertFalse(
                (root / 'var/lib/a-clockwork-plex/split-bus/installed').exists()
            )
            self.assertFalse(
                (root / 'usr/local/bin/a-clockwork-plex-audio-route').exists()
            )

    def test_temporary_root_service_capture_does_not_call_systemd(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / 'services.tsv'
            script = f'''
source {COMMON!s}
source {SERVICES!s}
ACP_ROOT={directory!s}
acp_capture_application_services {snapshot!s}
'''
            result = self.run_bash(script, env={'PATH': '/usr/bin:/bin'})
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = snapshot.read_text(encoding='utf-8').splitlines()
            self.assertEqual(rows[0], 'unit\tactive\tenabled')
            self.assertEqual(len(rows), 4)
            self.assertTrue(all(row.endswith('\tfalse\tfalse') for row in rows[1:]))

    def test_relative_installer_root_is_rejected(self) -> None:
        result = self.run_bash(
            f'source {COMMON!s}; acp_normalise_root relative/path'
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('must be an absolute path', result.stderr)


if __name__ == '__main__':
    unittest.main()
