from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / 'scripts' / 'audio' / 'install-eq.sh'
CAMILLA_HASH = 'e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa'
DIRECT_HASH = '08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9'


class EqAudioInstallIdempotenceAndFailureTests(unittest.TestCase):
    def fixture(self, directory: str, *, fail_destination: str | None = None):
        base = Path(directory)
        root = base / 'rootfs'
        active = root / 'etc/alsa/conf.d/99-a-clockwork-plex-shared.conf'
        active.parent.mkdir(parents=True)
        active.write_text('accepted-direct-route\n', encoding='utf-8')
        existing = root / 'etc/default/a-clockwork-plex-split-bus'
        existing.parent.mkdir(parents=True)
        existing.write_text('PREEXISTING=true\n', encoding='utf-8')

        binary = base / 'camilladsp'
        binary.write_text(
            '#!/bin/bash\n'
            "if [[ \"${1:-}\" == '--version' ]]; then\n"
            "  printf 'CamillaDSP 4.1.3\\n'\n"
            'fi\n',
            encoding='utf-8',
        )
        binary.chmod(0o755)

        tools = base / 'tools'
        tools.mkdir()
        sha = tools / 'sha256sum'
        sha.write_text(
            '#!/bin/bash\n'
            'case "${1:-}" in\n'
            f'  {binary}|*camilladsp-4.1.3/camilladsp) printf "{CAMILLA_HASH}  %s\\n" "$1" ;;\n'
            f'  *99-a-clockwork-plex-shared.conf|*pre-eq-active-route.conf) printf "{DIRECT_HASH}  %s\\n" "$1" ;;\n'
            '  *) /usr/bin/sha256sum "$@" ;;\n'
            'esac\n',
            encoding='utf-8',
        )
        sha.chmod(0o755)

        if fail_destination:
            install = tools / 'install'
            install.write_text(
                '#!/bin/bash\n'
                f'if [[ "$*" == *"{fail_destination}"* ]]; then\n'
                '  printf "forced install failure\\n" >&2\n'
                '  false\n'
                'else\n'
                '  /usr/bin/install "$@"\n'
                'fi\n',
                encoding='utf-8',
            )
            install.chmod(0o755)

        env = {**os.environ, 'PATH': f'{tools}:/usr/local/bin:/usr/bin:/bin'}
        command = [
            '/bin/bash',
            str(INSTALL),
            '--activate',
            '--confirm',
            'INSTALL-EQ-AUDIO',
            '--binary',
            str(binary),
            '--project-user',
            'testuser',
            '--root',
            str(root),
        ]
        return root, active, existing, command, env

    def run_install(self, command: list[str], env: dict[str, str]):
        return subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_second_install_delegates_to_repair_and_keeps_original_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _active, _existing, command, env = self.fixture(directory)
            first = self.run_install(command, env)
            self.assertEqual(first.returncode, 0, first.stderr)
            backup = root / 'var/lib/a-clockwork-plex/split-bus/pre-eq-backup'
            original_backup_hash = hashlib.sha256(
                (backup / 'pre-eq-active-route.conf').read_bytes()
            ).hexdigest()

            second = self.run_install(command, env)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn('delegating to repair', second.stdout)
            self.assertEqual(
                hashlib.sha256(
                    (backup / 'pre-eq-active-route.conf').read_bytes()
                ).hexdigest(),
                original_backup_hash,
            )
            self.assertTrue((backup / 'complete').is_file())

    def test_mid_install_failure_restores_direct_baseline_and_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, active, existing, command, env = self.fixture(
                directory,
                fail_destination='a-clockwork-plex-audio-route.service',
            )
            result = self.run_install(command, env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('original direct-audio state was restored', result.stderr)
            self.assertEqual(active.read_text(encoding='utf-8'), 'accepted-direct-route\n')
            self.assertEqual(existing.read_text(encoding='utf-8'), 'PREEXISTING=true\n')
            self.assertFalse(
                (root / 'var/lib/a-clockwork-plex/split-bus/installed').exists()
            )
            self.assertFalse(
                (root / 'var/lib/a-clockwork-plex/split-bus/pre-eq-backup').exists()
            )
            self.assertFalse(
                (root / 'usr/local/bin/a-clockwork-plex-audio-route').exists()
            )
            self.assertTrue(
                (root / 'var/lib/a-clockwork-plex/split-bus/last-install-failure.log').is_file()
            )


if __name__ == '__main__':
    unittest.main()
