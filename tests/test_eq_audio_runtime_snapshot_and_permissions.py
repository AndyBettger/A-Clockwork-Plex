from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / 'installer' / 'lib' / 'common.sh'
AUDIO = ROOT / 'installer' / 'lib' / 'audio.sh'
RUNTIME = ROOT / 'installer' / 'lib' / 'runtime.sh'
VERIFICATION = ROOT / 'installer' / 'lib' / 'verification.sh'
INSTALL = ROOT / 'scripts' / 'audio' / 'install-eq.sh'
CAMILLA_HASH = 'e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa'
DIRECT_HASH = '08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9'


class EqAudioRuntimeSnapshotTests(unittest.TestCase):
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

    def test_new_libraries_have_valid_shell_syntax(self) -> None:
        result = subprocess.run(
            ['/bin/bash', '-n', str(RUNTIME), str(VERIFICATION)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_runtime_snapshot_restores_present_and_absent_state_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'rootfs'
            state = root / 'var/lib/a-clockwork-plex/split-bus'
            state.mkdir(parents=True)
            (state / 'master-eq.json').write_text('saved-curve\n', encoding='utf-8')
            (state / 'route-state.json').write_text('old-route\n', encoding='utf-8')
            snapshot = Path(directory) / 'snapshot'

            script = f'''
source {COMMON!s}
source {AUDIO!s}
source {RUNTIME!s}
ACP_ROOT={root!s}
acp_capture_runtime_state {snapshot!s} &&
printf 'changed\\n' > {state / 'master-eq.json'} &&
rm -f {state / 'route-state.json'} &&
printf 'new-manifest\\n' > {state / 'install-manifest.tsv'} &&
acp_restore_runtime_state {snapshot!s}
'''
            result = self.run_bash(script)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                (state / 'master-eq.json').read_text(encoding='utf-8'),
                'saved-curve\n',
            )
            self.assertEqual(
                (state / 'route-state.json').read_text(encoding='utf-8'),
                'old-route\n',
            )
            self.assertFalse((state / 'install-manifest.tsv').exists())

    def test_privileged_verifier_detects_manifest_tampering_in_rooted_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'rootfs'
            target = root / 'etc/test.conf'
            target.parent.mkdir(parents=True)
            target.write_text('original\n', encoding='utf-8')
            state = root / 'var/lib/a-clockwork-plex/split-bus'
            state.mkdir(parents=True)
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            (state / 'install-manifest.tsv').write_text(
                f'destination\tsha256\tmode\n/etc/test.conf\t{digest}\t644\n',
                encoding='utf-8',
            )
            script = f'''
source {COMMON!s}
source {VERIFICATION!s}
ACP_ROOT={root!s}
acp_verify_installed_files
'''
            result = self.run_bash(script)
            self.assertEqual(result.returncode, 0, result.stderr)
            target.write_text('tampered\n', encoding='utf-8')
            result = self.run_bash(script)
            self.assertNotEqual(result.returncode, 0)

    def test_install_retains_readable_indexes_and_private_copies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
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
                f'  {binary}|*camilladsp-4.1.3/camilladsp) printf "{CAMILLA_HASH}  %s\\n" "$1" ;;\n'
                f'  *99-a-clockwork-plex-shared.conf|*pre-eq-active-route.conf) printf "{DIRECT_HASH}  %s\\n" "$1" ;;\n'
                '  *) /usr/bin/sha256sum "$@" ;;\n'
                'esac\n',
                encoding='utf-8',
            )
            wrapper.chmod(0o755)
            env = {'PATH': f'{tools}:/usr/local/bin:/usr/bin:/bin'}
            result = subprocess.run(
                [
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
                ],
                cwd=ROOT,
                env={**os.environ, **env},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            backup = root / 'var/lib/a-clockwork-plex/split-bus/pre-eq-backup'
            self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE((backup / 'files').stat().st_mode), 0o700)
            for name in (
                'managed-before.tsv',
                'pre-eq-active-route.sha256',
                'loopback-before.txt',
                'complete',
                'service-before.tsv',
            ):
                self.assertEqual(
                    stat.S_IMODE((backup / name).stat().st_mode),
                    0o644,
                    name,
                )


if __name__ == '__main__':
    unittest.main()
