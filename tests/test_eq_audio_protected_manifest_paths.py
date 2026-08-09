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
expected_manifest={manifest!s}
acp_managed_file_destinations() {{ printf '/etc/sudoers.d/protected\\n'; }}
acp_path() {{
    if [[ "$1" == '/var/lib/a-clockwork-plex/split-bus/install-manifest.tsv' ]]; then
        printf '%s\\n' "$expected_manifest"
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
cat "$expected_manifest"
'''
            result = self.run_bash(script)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('/etc/sudoers.d/protected\t0123456789abcdef\t440', result.stdout)

    def test_manifest_marks_live_camilladsp_config_as_runtime_generated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / 'install-manifest.tsv'
            script = f'''
source {COMMON!s}
source {AUDIO!s}
source {VERIFICATION!s}
ACP_ROOT=/
live=/opaque/camilladsp-split-bus.yml
expected_manifest={manifest!s}
acp_managed_file_destinations() {{ printf '/etc/a-clockwork-plex/camilladsp-split-bus.yml\\n'; }}
acp_path() {{
    if [[ "$1" == '/var/lib/a-clockwork-plex/split-bus/install-manifest.tsv' ]]; then
        printf '%s\\n' "$expected_manifest"
    else
        printf '%s\\n' "$live"
    fi
}}
acp_run_root() {{
    case "$1" in
        test) return 0 ;;
        sha256sum) printf 'SHOULD-NOT-BE-HASHED  %s\\n' "$2" ; return 0 ;;
        stat) printf '644\\n' ; return 0 ;;
        install)
            command cp -- "$5" "$6" || return 1
            command chmod "$4" "$6"
            ;;
        cat) command cat -- "$3" ;;
        *) return 99 ;;
    esac
}}
acp_write_install_manifest
cat "$expected_manifest"
'''
            result = self.run_bash(script)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                '/etc/a-clockwork-plex/camilladsp-split-bus.yml\truntime-generated\t644',
                result.stdout,
            )
            self.assertNotIn('SHOULD-NOT-BE-HASHED', result.stdout)

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
expected_manifest={manifest!s}
acp_path() {{
    if [[ "$1" == '/var/lib/a-clockwork-plex/split-bus/install-manifest.tsv' ]]; then
        printf '%s\\n' "$expected_manifest"
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

    def test_runtime_generated_camilladsp_config_ignores_hash_but_checks_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'rootfs'
            config = root / 'etc/a-clockwork-plex/camilladsp-split-bus.yml'
            manifest = root / 'var/lib/a-clockwork-plex/split-bus/install-manifest.tsv'
            config.parent.mkdir(parents=True)
            manifest.parent.mkdir(parents=True)
            config.write_text('live runtime curve\n', encoding='utf-8')
            config.chmod(0o644)
            manifest.write_text(
                'destination\tsha256\tmode\n'
                '/etc/a-clockwork-plex/camilladsp-split-bus.yml\truntime-generated\t644\n',
                encoding='utf-8',
            )
            script = f'''
source {COMMON!s}
source {AUDIO!s}
source {VERIFICATION!s}
ACP_ROOT={root!s}
acp_verify_installed_files
'''
            result = self.run_bash(script)
            self.assertEqual(result.returncode, 0, result.stderr)

            config.chmod(0o600)
            result = self.run_bash(script)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('mode mismatch', result.stderr)

    def test_production_accepts_legacy_concrete_hash_for_mutable_camilladsp_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / 'install-manifest.tsv'
            manifest.write_text(
                'destination\tsha256\tmode\n'
                '/etc/a-clockwork-plex/camilladsp-split-bus.yml\told-install-hash\t644\n',
                encoding='utf-8',
            )
            script = f'''
source {COMMON!s}
source {AUDIO!s}
source {VERIFICATION!s}
ACP_ROOT=/
live=/opaque/camilladsp-split-bus.yml
expected_manifest={manifest!s}
acp_path() {{
    if [[ "$1" == '/var/lib/a-clockwork-plex/split-bus/install-manifest.tsv' ]]; then
        printf '%s\\n' "$expected_manifest"
    else
        printf '%s\\n' "$live"
    fi
}}
acp_run_root() {{
    case "$1" in
        test) return 0 ;;
        sha256sum) printf 'new-runtime-hash  %s\\n' "$2" ; return 0 ;;
        stat) printf '644\\n' ; return 0 ;;
        cat) command cat -- "$3" ;;
        *) return 99 ;;
    esac
}}
acp_verify_installed_files
'''
            result = self.run_bash(script)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_hash_mismatch_names_the_immutable_managed_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'rootfs'
            managed = root / 'etc/example.conf'
            manifest = root / 'var/lib/a-clockwork-plex/split-bus/install-manifest.tsv'
            managed.parent.mkdir(parents=True)
            manifest.parent.mkdir(parents=True)
            managed.write_text('changed\n', encoding='utf-8')
            managed.chmod(0o644)
            manifest.write_text(
                'destination\tsha256\tmode\n'
                '/etc/example.conf\tdefinitely-not-the-live-hash\t644\n',
                encoding='utf-8',
            )
            script = f'''
source {COMMON!s}
source {AUDIO!s}
source {VERIFICATION!s}
ACP_ROOT={root!s}
acp_verify_installed_files
'''
            result = self.run_bash(script)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('/etc/example.conf', result.stderr)
            self.assertIn('hash mismatch', result.stderr)

    def test_protected_file_cleanup_uses_privileged_boundary(self) -> None:
        script = f'''
source {COMMON!s}
ACP_ROOT=/
protected=/opaque/protected-sudoers-file
acp_path() {{ printf '%s\\n' "$protected"; }}
acp_run_root() {{
    printf '%s\\n' "$*"
    case "$1" in
        test) return 0 ;;
        rm) return 0 ;;
        *) return 99 ;;
    esac
}}
acp_remove_file '/etc/sudoers.d/protected'
'''
        result = self.run_bash(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('test -e /opaque/protected-sudoers-file', result.stdout)
        self.assertIn('rm -f -- /opaque/protected-sudoers-file', result.stdout)


if __name__ == '__main__':
    unittest.main()
