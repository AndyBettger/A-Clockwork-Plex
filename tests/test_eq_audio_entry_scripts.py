from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts' / 'audio'
ENTRY_SCRIPTS = (
    SCRIPTS / 'install-eq.sh',
    SCRIPTS / 'repair-audio.sh',
    SCRIPTS / 'verify-audio.sh',
    SCRIPTS / 'uninstall-eq.sh',
)
CAMILLA_HASH = 'e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa'
DIRECT_HASH = '08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9'


class EqAudioEntryScriptTests(unittest.TestCase):
    def run_command(
        self,
        command: list[str],
        *,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        merged = os.environ.copy()
        if env:
            merged.update(env)
        return subprocess.run(
            command,
            cwd=ROOT,
            env=merged,
            capture_output=True,
            text=True,
            check=False,
        )

    def make_fixture(self, directory: str):
        base = Path(directory)
        root = base / 'rootfs'
        active = root / 'etc/alsa/conf.d/99-a-clockwork-plex-shared.conf'
        active.parent.mkdir(parents=True)
        active.write_text('accepted-direct-route\n', encoding='utf-8')

        binary = base / 'camilladsp'
        binary.write_text(
            '#!/bin/bash\n'
            "if [[ \"${1:-}\" == '--version' ]]; then\n"
            "  printf 'CamillaDSP 4.1.3\\n'\n"
            'else\n'
            '  return 0\n'
            'fi\n',
            encoding='utf-8',
        )
        binary.chmod(0o755)

        tools = base / 'tools'
        tools.mkdir()
        wrapper = tools / 'sha256sum'
        wrapper.write_text(
            '#!/bin/bash\n'
            'case "${1:-}" in\n'
            '  *camilladsp-4.1.3/camilladsp|' + str(binary) + ')\n'
            f"    printf '{CAMILLA_HASH}  %s\\n' \"$1\"\n"
            '    ;;\n'
            '  *99-a-clockwork-plex-shared.conf|*pre-eq-active-route.conf)\n'
            f"    printf '{DIRECT_HASH}  %s\\n' \"$1\"\n"
            '    ;;\n'
            '  *)\n'
            '    /usr/bin/sha256sum "$@"\n'
            '    ;;\n'
            'esac\n',
            encoding='utf-8',
        )
        wrapper.chmod(0o755)
        env = {'PATH': f'{tools}:/usr/local/bin:/usr/bin:/bin'}
        return root, active, binary, env

    def test_entry_script_shell_syntax(self) -> None:
        result = self.run_command(['/bin/bash', '-n', *(str(path) for path in ENTRY_SCRIPTS)])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_prepare_is_default_and_does_not_create_rooted_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _active, binary, env = self.make_fixture(directory)
            result = self.run_command(
                [
                    '/bin/bash',
                    str(SCRIPTS / 'install-eq.sh'),
                    '--binary',
                    str(binary),
                    '--project-user',
                    'testuser',
                    '--root',
                    str(root),
                ],
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Mode:             prepare-only', result.stdout)
            self.assertFalse((root / 'var/lib/a-clockwork-plex').exists())

    def test_install_verify_repair_uninstall_and_reinstall_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, active, binary, env = self.make_fixture(directory)
            install = [
                '/bin/bash',
                str(SCRIPTS / 'install-eq.sh'),
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
            result = self.run_command(install, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)

            marker = root / 'var/lib/a-clockwork-plex/split-bus/installed'
            backup = root / 'var/lib/a-clockwork-plex/split-bus/pre-eq-backup'
            state_path = root / 'var/lib/a-clockwork-plex/split-bus/master-eq.json'
            self.assertEqual(marker.read_text(encoding='utf-8'), 'eq-split-bus\n')
            self.assertTrue((backup / 'complete').is_file())
            self.assertTrue((backup / 'service-before.tsv').is_file())
            self.assertTrue((root / 'var/lib/a-clockwork-plex/split-bus/install-manifest.tsv').is_file())
            self.assertEqual(
                stat.S_IMODE((root / 'etc/sudoers.d/a-clockwork-plex-audio-route').stat().st_mode),
                0o440,
            )

            verify = self.run_command(
                [
                    '/bin/bash',
                    str(SCRIPTS / 'verify-audio.sh'),
                    '--root',
                    str(root),
                ],
                env=env,
            )
            self.assertEqual(verify.returncode, 0, verify.stderr)
            self.assertIn('verification passed', verify.stdout)

            stored = json.loads(state_path.read_text(encoding='utf-8'))
            stored['bands']['bass'] = 4.0
            stored['bypassed'] = True
            state_path.write_text(json.dumps(stored) + '\n', encoding='utf-8')
            repair = self.run_command(
                [
                    '/bin/bash',
                    str(SCRIPTS / 'repair-audio.sh'),
                    '--activate',
                    '--confirm',
                    'REPAIR-EQ-AUDIO',
                    '--binary',
                    str(binary),
                    '--project-user',
                    'testuser',
                    '--root',
                    str(root),
                ],
                env=env,
            )
            self.assertEqual(repair.returncode, 0, repair.stderr)
            repaired_state = json.loads(state_path.read_text(encoding='utf-8'))
            self.assertEqual(repaired_state['bands']['bass'], 4.0)
            self.assertTrue(repaired_state['bypassed'])
            self.assertTrue((backup / 'complete').is_file())

            uninstall = self.run_command(
                [
                    '/bin/bash',
                    str(SCRIPTS / 'uninstall-eq.sh'),
                    '--activate',
                    '--confirm',
                    'UNINSTALL-EQ-AUDIO',
                    '--root',
                    str(root),
                ],
                env=env,
            )
            self.assertEqual(uninstall.returncode, 0, uninstall.stderr)
            self.assertFalse(marker.exists())
            self.assertFalse(backup.exists())
            self.assertFalse((root / 'usr/local/bin/a-clockwork-plex-audio-route').exists())
            self.assertEqual(active.read_text(encoding='utf-8'), 'accepted-direct-route\n')
            self.assertTrue(state_path.is_file())
            rollback_state = json.loads(
                (root / 'var/lib/a-clockwork-plex/split-bus/route-state.json').read_text(
                    encoding='utf-8'
                )
            )
            self.assertEqual(rollback_state['mode'], 'direct-rollback')

            reinstall = self.run_command(install, env=env)
            self.assertEqual(reinstall.returncode, 0, reinstall.stderr)
            self.assertTrue(marker.is_file())
            reinstalled_state = json.loads(state_path.read_text(encoding='utf-8'))
            self.assertEqual(reinstalled_state['bands']['bass'], 4.0)
            self.assertTrue(reinstalled_state['bypassed'])

    def test_activation_tokens_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _active, binary, env = self.make_fixture(directory)
            result = self.run_command(
                [
                    '/bin/bash',
                    str(SCRIPTS / 'install-eq.sh'),
                    '--activate',
                    '--binary',
                    str(binary),
                    '--root',
                    str(root),
                ],
                env=env,
            )
            self.assertEqual(result.returncode, 64)
            self.assertIn('Activation requires', result.stderr)


if __name__ == '__main__':
    unittest.main()
