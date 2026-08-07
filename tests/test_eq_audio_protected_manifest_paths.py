from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / 'installer' / 'lib' / 'common.sh'
AUDIO = ROOT / 'installer' / 'lib' / 'audio.sh'
VERIFICATION = ROOT / 'installer' / 'lib' / 'verification.sh'


class EqAudioProtectedManifestPathTests(unittest.TestCase):
    def run_bash(self, script: str):
        return subprocess.run(
            ['/bin/bash', '-c', script],
            cwd=ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=False,
        )

    def test_manifest_creation_uses_privileged_boundary_for_protected_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / 'install-manifest.tsv'
            script = f'''
source {COMMON!s}
source {AUDIO!s}
source {VERIFICATION!s}
ACP_ROOT=/
protected=/opaque/protected-sudoers-file
manifest={manifest!s}
acp_managed_file_destinations() {{ printf '/etc/sudoers.d/protected\\n'; }}
acp_path() {{
    if [[ "$1" == '/var/lib/a-clockwork-plex/split-bus/install-manifest.tsv' ]]; then
        printf '%s\\n' "$manifest"
    else
        printf '%s\\n' "$protected"
    fi
}}
acp_run_root() {{
    case "$1" in
        test) return 0 ;;
        sha256sum) printf '0123456789abcdef  %s\\n' "$2" ; return 0 ;;
        stat) printf '440\\n' ; return 0 ;;
        install)
            command cp -- "$5" "$6" || return 1
            command chmod "$4" "$6"
            ;;
        cat) command cat -- "$3" ;;
        *) return 99 ;;
    esac
}}
acp_write_install_manifest
cat "$manifest"
'''
            result = self.run_bash(script)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('/etc/sudoers.d/protected\t0123456789abcdef\t440', result.stdout)

    def test_installed_file_verification_uses_privileged_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / 'install-manifest.tsv'
            manifest.write_text(
                'destination\tsha256\tmode\n'
                '/etc/sudoers.d/protected\t0123456789abcdef\t440\n',
                encoding='utf-8',
            )
            script = f'''
source {COMMON!s}
source {AUDIO!s}
source {VERIFICATION!s}
ACP_ROOT=/
protected=/opaque/protected-sudoers-file
manifest={manifest!s}
acp_path() {{
    if [[ "$1" == '/var/lib/a-clockwork-plex/split-bus/install-manifest.tsv' ]]; then
        printf '%s\\n' "$manifest"
    else
        printf '%s\\n' "$protected"
    fi
}}
acp_run_root() {{
    case "$1" in
        test) return 0 ;;
        sha256sum) printf '0123456789abcdef  %s\\n' "$2" ; return 0 ;;
        stat) printf '440\\n' ; return 0 ;;
        cat) command cat -- "$3" ;;
        *) return 99 ;;
    esac
}}
acp_verify_installed_files
'''
            result = self.run_bash(script)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
