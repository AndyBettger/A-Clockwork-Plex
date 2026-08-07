#!/usr/bin/python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def update(path: str, old: str, new: str, *, completed_marker: str) -> None:
    file = ROOT / path
    text = file.read_text(encoding='utf-8')
    if completed_marker in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected one match, found {count}: {old[:100]!r}')
    file.write_text(text.replace(old, new, 1), encoding='utf-8')


def insert_sources(path: str) -> None:
    update(
        path,
        'source "$REPO_ROOT/installer/lib/audio.sh"\n',
        'source "$REPO_ROOT/installer/lib/audio.sh"\n'
        'source "$REPO_ROOT/installer/lib/runtime.sh"\n'
        'source "$REPO_ROOT/installer/lib/verification.sh"\n',
        completed_marker='source "$REPO_ROOT/installer/lib/runtime.sh"',
    )


for script in (
    'scripts/audio/install-eq.sh',
    'scripts/audio/repair-audio.sh',
    'scripts/audio/uninstall-eq.sh',
):
    insert_sources(script)

update(
    'scripts/audio/install-eq.sh',
    '    acp_run_root chmod 0755 "$backup" || return 1\n',
    '    acp_run_root chmod 0755 "$backup" || return 1\n'
    '    acp_run_root chmod 0755 "$backup/runtime-before" || return 1\n'
    '    acp_run_root chmod 0644 \\\n'
    '        "$backup/runtime-before/state-files.tsv" \\\n'
    '        "$backup/runtime-before/managed-services.tsv" || return 1\n',
    completed_marker='"$backup/runtime-before/state-files.tsv"',
)
update(
    'scripts/audio/install-eq.sh',
    '    acp_restore_preinstall_files || failures=$((failures + 1))\n'
    '    acp_reload_systemd || failures=$((failures + 1))\n'
    '    acp_restore_loopback_state || failures=$((failures + 1))\n',
    '    acp_restore_preinstall_files || failures=$((failures + 1))\n'
    '    acp_restore_runtime_state "$backup/runtime-before" || failures=$((failures + 1))\n'
    '    acp_reload_systemd || failures=$((failures + 1))\n'
    '    acp_restore_managed_service_state \\\n'
    '        "$backup/runtime-before/managed-services.tsv" || failures=$((failures + 1))\n'
    '    acp_restore_loopback_state || failures=$((failures + 1))\n',
    completed_marker='acp_restore_runtime_state "$backup/runtime-before"',
)
update(
    'scripts/audio/install-eq.sh',
    '    local marker backup service_snapshot failure=\n',
    '    local marker backup service_snapshot runtime_snapshot failure=\n',
    completed_marker='local marker backup service_snapshot runtime_snapshot failure=',
)
update(
    'scripts/audio/install-eq.sh',
    '    acp_capture_preinstall_files || return 1\n'
    '    if ! prepare_backup_indexes "$backup" "$service_snapshot"; then\n',
    '    runtime_snapshot="$(mktemp -d "${TMPDIR:-/tmp}/a-clockwork-plex-preinstall-state.XXXXXX")" || return 1\n'
    '    if ! acp_capture_runtime_state "$runtime_snapshot" || \\\n'
    '       ! acp_capture_managed_service_state "$runtime_snapshot/managed-services.tsv"; then\n'
    '        rm -rf "$runtime_snapshot"\n'
    '        return 1\n'
    '    fi\n'
    '    if ! acp_capture_preinstall_files; then\n'
    '        rm -rf "$runtime_snapshot"\n'
    '        acp_remove_preinstall_backup || true\n'
    '        return 1\n'
    '    fi\n'
    '    if ! acp_run_root cp -a "$runtime_snapshot" "$backup/runtime-before"; then\n'
    '        rm -rf "$runtime_snapshot"\n'
    '        acp_remove_preinstall_backup || true\n'
    '        return 1\n'
    '    fi\n'
    '    rm -rf "$runtime_snapshot"\n'
    '    if ! prepare_backup_indexes "$backup" "$service_snapshot"; then\n',
    completed_marker='a-clockwork-plex-preinstall-state.XXXXXX',
)
update(
    'scripts/audio/install-eq.sh',
    '    [[ -n "$failure" ]] || acp_write_install_manifest || failure=\'install manifest write failed\'\n'
    '    [[ -n "$failure" ]] || acp_verify_install_manifest || failure=\'installed file verification failed\'\n',
    '    [[ -n "$failure" ]] || acp_write_install_manifest || failure=\'install manifest write failed\'\n'
    '    [[ -n "$failure" ]] || "$SCRIPT_DIR/verify-audio.sh" --root "$ACP_ROOT" || \\\n'
    '        failure=\'installed audio verification failed\'\n',
    completed_marker='failure=\'installed audio verification failed\'',
)
update(
    'scripts/audio/install-eq.sh',
    '    acp_write_operation_log \'EQ-capable audio profile installed successfully\' || return 1\n'
    '    acp_log \'EQ-capable audio profile installed successfully.\'\n'
    '    if acp_is_production_root; then\n'
    '        sudo -- /usr/local/bin/a-clockwork-plex-audio-route status || return 1\n'
    '        sudo -- /usr/local/bin/a-clockwork-plex-audio-eq status || return 1\n'
    '    fi\n',
    '    acp_write_operation_log \'EQ-capable audio profile installed successfully\' || \\\n'
    '        acp_error \'Warning: installation succeeded but the operation log could not be written.\'\n'
    '    acp_log \'EQ-capable audio profile installed successfully.\'\n',
    completed_marker='Warning: installation succeeded but the operation log could not be written.',
)

update(
    'scripts/audio/repair-audio.sh',
    '    if acp_is_production_root && [[ -d /sys/module/snd_aloop ]]; then\n'
    '        printf \'loaded\\n\' >"$snapshot/loopback.txt"\n',
    '    acp_capture_runtime_state "$snapshot/runtime" || return 1\n'
    '    acp_capture_managed_service_state "$snapshot/managed-services.tsv" || return 1\n'
    '    if acp_is_production_root && [[ -d /sys/module/snd_aloop ]]; then\n'
    '        printf \'loaded\\n\' >"$snapshot/loopback.txt"\n',
    completed_marker='acp_capture_runtime_state "$snapshot/runtime"',
)
update(
    'scripts/audio/repair-audio.sh',
    '    acp_run_root cp -p -- "$snapshot/active-alsa.conf" "$active" || failures=$((failures + 1))\n'
    '    if acp_is_production_root && [[ "$(cat "$snapshot/loopback.txt")" == absent && -d /sys/module/snd_aloop ]]; then\n',
    '    acp_run_root cp -p -- "$snapshot/active-alsa.conf" "$active" || failures=$((failures + 1))\n'
    '    acp_restore_runtime_state "$snapshot/runtime" || failures=$((failures + 1))\n'
    '    if acp_is_production_root && [[ "$(cat "$snapshot/loopback.txt")" == absent && -d /sys/module/snd_aloop ]]; then\n',
    completed_marker='acp_restore_runtime_state "$snapshot/runtime"',
)
update(
    'scripts/audio/repair-audio.sh',
    '    [[ -n "$failure" ]] || acp_write_install_manifest || failure=\'manifest rewrite failed\'\n'
    '    [[ -n "$failure" ]] || acp_verify_install_manifest || failure=\'repaired file verification failed\'\n',
    '    [[ -n "$failure" ]] || acp_write_install_manifest || failure=\'manifest rewrite failed\'\n'
    '    [[ -n "$failure" ]] || "$SCRIPT_DIR/verify-audio.sh" --root "$ACP_ROOT" || \\\n'
    '        failure=\'repaired audio verification failed\'\n',
    completed_marker='failure=\'repaired audio verification failed\'',
)
update(
    'scripts/audio/repair-audio.sh',
    '        acp_reload_systemd || rollback_failures=$((rollback_failures + 1))\n'
    '        acp_restore_captured_enablement "$service_snapshot" || rollback_failures=$((rollback_failures + 1))\n',
    '        acp_reload_systemd || rollback_failures=$((rollback_failures + 1))\n'
    '        acp_restore_managed_service_state "$snapshot/managed-services.tsv" || \\\n'
    '            rollback_failures=$((rollback_failures + 1))\n'
    '        acp_restore_captured_enablement "$service_snapshot" || rollback_failures=$((rollback_failures + 1))\n',
    completed_marker='acp_restore_managed_service_state "$snapshot/managed-services.tsv"',
)
update(
    'scripts/audio/repair-audio.sh',
    '    acp_write_operation_log \'EQ-capable audio profile repaired successfully\' || return 1\n'
    '    acp_log \'EQ-capable audio profile repaired successfully.\'\n'
    '    if acp_is_production_root; then\n'
    '        sudo -- /usr/local/bin/a-clockwork-plex-audio-route status || return 1\n'
    '        sudo -- /usr/local/bin/a-clockwork-plex-audio-eq status || return 1\n'
    '    fi\n',
    '    acp_write_operation_log \'EQ-capable audio profile repaired successfully\' || \\\n'
    '        acp_error \'Warning: repair succeeded but the operation log could not be written.\'\n'
    '    acp_log \'EQ-capable audio profile repaired successfully.\'\n',
    completed_marker='Warning: repair succeeded but the operation log could not be written.',
)

update(
    'scripts/audio/uninstall-eq.sh',
    '    acp_capture_application_services "$snapshot/services.tsv" || return 1\n'
    '    if acp_is_production_root && [[ -d /sys/module/snd_aloop ]]; then\n',
    '    acp_capture_application_services "$snapshot/services.tsv" || return 1\n'
    '    acp_capture_runtime_state "$snapshot/runtime" || return 1\n'
    '    acp_capture_managed_service_state "$snapshot/managed-services.tsv" || return 1\n'
    '    if acp_is_production_root && [[ -d /sys/module/snd_aloop ]]; then\n',
    completed_marker='acp_capture_managed_service_state "$snapshot/managed-services.tsv"',
)
update(
    'scripts/audio/uninstall-eq.sh',
    '    acp_run_root cp -p -- "$snapshot/active-alsa.conf" "$active" || failures=$((failures + 1))\n'
    '    acp_write_installed_marker || failures=$((failures + 1))\n'
    '    acp_reload_systemd || failures=$((failures + 1))\n',
    '    acp_run_root cp -p -- "$snapshot/active-alsa.conf" "$active" || failures=$((failures + 1))\n'
    '    acp_restore_runtime_state "$snapshot/runtime" || failures=$((failures + 1))\n'
    '    acp_write_installed_marker || failures=$((failures + 1))\n'
    '    acp_reload_systemd || failures=$((failures + 1))\n'
    '    acp_restore_managed_service_state "$snapshot/managed-services.tsv" || \\\n'
    '        failures=$((failures + 1))\n',
    completed_marker='acp_restore_runtime_state "$snapshot/runtime"',
)
update(
    'scripts/audio/uninstall-eq.sh',
    '    acp_write_operation_log \'EQ-capable audio profile uninstalled; direct audio restored\' || return 1\n'
    '    acp_log \'EQ-capable audio profile uninstalled; the original direct-audio state was restored.\'\n',
    '    acp_write_operation_log \'EQ-capable audio profile uninstalled; direct audio restored\' || \\\n'
    '        acp_error \'Warning: uninstall succeeded but the operation log could not be written.\'\n'
    '    acp_log \'EQ-capable audio profile uninstalled; the original direct-audio state was restored.\'\n',
    completed_marker='Warning: uninstall succeeded but the operation log could not be written.',
)

for launcher in (
    'scripts/a-clockwork-plex-audio-eq.py',
    'scripts/a-clockwork-plex-audio-route.py',
):
    update(
        launcher,
        'import sys\n',
        'import sys\n\nsys.dont_write_bytecode = True\n',
        completed_marker='sys.dont_write_bytecode = True',
    )
