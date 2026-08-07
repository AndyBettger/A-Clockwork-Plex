from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class EqAudioEntryHardeningContractTests(unittest.TestCase):
    def text(self, path: str) -> str:
        return (ROOT / path).read_text(encoding='utf-8')

    def test_install_snapshots_runtime_and_requires_full_verification(self) -> None:
        script = self.text('scripts/audio/install-eq.sh')
        self.assertIn('source "$REPO_ROOT/installer/lib/runtime.sh"', script)
        self.assertIn('source "$REPO_ROOT/installer/lib/verification.sh"', script)
        self.assertIn('acp_capture_runtime_state "$runtime_snapshot"', script)
        self.assertIn('acp_capture_managed_service_state', script)
        self.assertIn('acp_restore_runtime_state "$backup/runtime-before"', script)
        self.assertIn('acp_restore_managed_service_state', script)
        self.assertIn('"$SCRIPT_DIR/verify-audio.sh" --root "$ACP_ROOT"', script)
        self.assertNotIn('acp_verify_install_manifest || failure=', script)

    def test_repair_restores_previous_runtime_and_managed_service_state(self) -> None:
        script = self.text('scripts/audio/repair-audio.sh')
        self.assertIn('acp_capture_runtime_state "$snapshot/runtime"', script)
        self.assertIn(
            'acp_capture_managed_service_state "$snapshot/managed-services.tsv"',
            script,
        )
        self.assertIn('acp_restore_runtime_state "$snapshot/runtime"', script)
        self.assertIn(
            'acp_restore_managed_service_state "$snapshot/managed-services.tsv"',
            script,
        )
        self.assertIn('"$SCRIPT_DIR/verify-audio.sh" --root "$ACP_ROOT"', script)

    def test_uninstall_failure_can_restore_the_installed_runtime_mode(self) -> None:
        script = self.text('scripts/audio/uninstall-eq.sh')
        self.assertIn('acp_capture_runtime_state "$snapshot/runtime"', script)
        self.assertIn(
            'acp_capture_managed_service_state "$snapshot/managed-services.tsv"',
            script,
        )
        self.assertIn('acp_restore_runtime_state "$snapshot/runtime"', script)
        self.assertIn(
            'acp_restore_managed_service_state "$snapshot/managed-services.tsv"',
            script,
        )

    def test_live_verifier_reads_root_owned_files_and_parses_json(self) -> None:
        verifier = self.text('scripts/audio/verify-audio.sh')
        library = self.text('installer/lib/verification.sh')
        self.assertIn('acp_verify_installed_files', verifier)
        self.assertIn('acp_validate_eq_state_file', verifier)
        self.assertIn('validate_route_payload', verifier)
        self.assertIn('validate_eq_payload', verifier)
        self.assertIn('acp_run_root cat -- "$source"', library)
        self.assertIn('acp_run_root sha256sum "$path"', library)
        self.assertIn('acp_run_root stat -c', library)

    def test_installed_launchers_do_not_leave_python_cache_files(self) -> None:
        for path in (
            'scripts/a-clockwork-plex-audio-eq.py',
            'scripts/a-clockwork-plex-audio-route.py',
        ):
            self.assertIn('sys.dont_write_bytecode = True', self.text(path), path)

    def test_one_time_patch_assets_are_not_retained(self) -> None:
        self.assertFalse(
            (ROOT / '.github/workflows/apply-eq-entry-hardening.yml').exists()
        )
        self.assertFalse(
            (ROOT / '.github/workflows/apply-eq-entry-hardening-v2.yml').exists()
        )
        self.assertFalse(
            (ROOT / 'scripts/dev/apply_eq_entry_hardening_v2.py').exists()
        )


if __name__ == '__main__':
    unittest.main()
