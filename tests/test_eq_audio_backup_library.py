from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / 'installer' / 'lib' / 'common.sh'
AUDIO = ROOT / 'installer' / 'lib' / 'audio.sh'


class EqAudioBackupLibraryTests(unittest.TestCase):
    def run_bash(self, script: str):
        return subprocess.run(
            ['/bin/bash', '-c', script],
            cwd=ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=False,
        )

    def prepare_root(self, directory: str):
        root = Path(directory) / 'rootfs'
        active = root / 'etc/alsa/conf.d/99-a-clockwork-plex-shared.conf'
        active.parent.mkdir(parents=True)
        active.write_text('accepted-direct-route\n', encoding='utf-8')
        accepted_hash = hashlib.sha256(active.read_bytes()).hexdigest()
        old_defaults = root / 'etc/default/a-clockwork-plex-split-bus'
        old_defaults.parent.mkdir(parents=True)
        old_defaults.write_text('PREEXISTING=true\n', encoding='utf-8')
        binary = Path(directory) / 'camilladsp'
        binary.write_text('#!/bin/sh\n', encoding='utf-8')
        binary.chmod(0o755)
        return root, active, accepted_hash, old_defaults, binary

    def test_capture_install_manifest_and_exact_restore(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, active, accepted_hash, old_defaults, binary = self.prepare_root(directory)
            script = f'''
source {COMMON!s}
source {AUDIO!s}
ACP_ROOT={root!s}
ACP_ACCEPTED_DIRECT_SHA256={accepted_hash}
acp_capture_preinstall_files &&
acp_install_audio_files {binary!s} testuser &&
acp_write_installed_marker &&
acp_write_install_manifest &&
acp_verify_install_manifest &&
acp_restore_preinstall_files
'''
            result = self.run_bash(script)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(active.read_text(encoding='utf-8'), 'accepted-direct-route\n')
            self.assertEqual(old_defaults.read_text(encoding='utf-8'), 'PREEXISTING=true\n')
            self.assertFalse((root / 'usr/local/bin/a-clockwork-plex-audio-route').exists())
            self.assertTrue(
                (root / 'var/lib/a-clockwork-plex/split-bus/pre-eq-backup/complete').is_file()
            )
            self.assertEqual(
                (root / 'var/lib/a-clockwork-plex/split-bus/pre-eq-backup/loopback-before.txt').read_text(
                    encoding='utf-8'
                ),
                'absent\n',
            )

    def test_manifest_detects_changed_installed_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _active, _accepted_hash, _old_defaults, binary = self.prepare_root(directory)
            install = f'''
source {COMMON!s}
source {AUDIO!s}
ACP_ROOT={root!s}
acp_install_audio_files {binary!s} testuser &&
acp_write_installed_marker &&
acp_write_install_manifest
'''
            result = self.run_bash(install)
            self.assertEqual(result.returncode, 0, result.stderr)
            tampered = root / 'etc/a-clockwork-plex/audio-routes/split-bus.conf'
            tampered.write_text('tampered\n', encoding='utf-8')
            verify = f'''
source {COMMON!s}
source {AUDIO!s}
ACP_ROOT={root!s}
acp_verify_install_manifest
'''
            result = self.run_bash(verify)
            self.assertNotEqual(result.returncode, 0)

    def test_backup_cleanup_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'rootfs'
            root.mkdir()
            script = f'''
source {COMMON!s}
source {AUDIO!s}
ACP_ROOT={root!s}
acp_remove_preinstall_backup &&
acp_remove_preinstall_backup
'''
            result = self.run_bash(script)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
