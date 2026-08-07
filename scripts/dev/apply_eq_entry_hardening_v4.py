#!/usr/bin/python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_lines(path: str) -> list[str]:
    return (ROOT / path).read_text(encoding="utf-8").splitlines()


def write_lines(path: str, lines: list[str]) -> None:
    (ROOT / path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def has(lines: list[str], marker: str) -> bool:
    return any(marker in line for line in lines)


def one_index(lines: list[str], exact: str, path: str) -> int:
    indexes = [index for index, line in enumerate(lines) if line == exact]
    if len(indexes) != 1:
        raise SystemExit(f"{path}: expected one {exact!r}; found {len(indexes)}")
    return indexes[0]


def insert_after(path: str, exact: str, additions: list[str], marker: str) -> None:
    lines = read_lines(path)
    if has(lines, marker):
        return
    index = one_index(lines, exact, path) + 1
    lines[index:index] = additions
    write_lines(path, lines)


def replace_line(path: str, exact: str, replacements: list[str], marker: str) -> None:
    lines = read_lines(path)
    if has(lines, marker):
        return
    index = one_index(lines, exact, path)
    lines[index:index + 1] = replacements
    write_lines(path, lines)


def replace_sequence(path: str, old: list[str], new: list[str], marker: str) -> None:
    lines = read_lines(path)
    if has(lines, marker):
        return
    starts = [
        index
        for index in range(len(lines) - len(old) + 1)
        if lines[index:index + len(old)] == old
    ]
    if len(starts) != 1:
        raise SystemExit(f"{path}: expected one sequence {old[0]!r}; found {len(starts)}")
    index = starts[0]
    lines[index:index + len(old)] = new
    write_lines(path, lines)


def guard_launcher(path: str) -> None:
    lines = read_lines(path)
    if has(lines, "sys.dont_write_bytecode = True"):
        return
    index = one_index(lines, "import sys", path) + 1
    lines[index:index] = ["", "sys.dont_write_bytecode = True"]
    write_lines(path, lines)


for path in (
    "scripts/audio/install-eq.sh",
    "scripts/audio/repair-audio.sh",
    "scripts/audio/uninstall-eq.sh",
):
    insert_after(
        path,
        'source "$REPO_ROOT/installer/lib/audio.sh"',
        [
            'source "$REPO_ROOT/installer/lib/runtime.sh"',
            'source "$REPO_ROOT/installer/lib/verification.sh"',
        ],
        "installer/lib/runtime.sh",
    )

insert_after(
    "scripts/audio/install-eq.sh",
    '    acp_run_root chmod 0755 "$backup" || return 1',
    [
        '    acp_run_root chmod 0755 "$backup/runtime-before" || return 1',
        '    acp_run_root chmod 0644 "$backup/runtime-before/state-files.tsv" "$backup/runtime-before/managed-services.tsv" || return 1',
    ],
    "runtime-before/state-files.tsv",
)
insert_after(
    "scripts/audio/install-eq.sh",
    "    acp_restore_preinstall_files || failures=$((failures + 1))",
    ['    acp_restore_runtime_state "$backup/runtime-before" || failures=$((failures + 1))'],
    'acp_restore_runtime_state "$backup/runtime-before"',
)
insert_after(
    "scripts/audio/install-eq.sh",
    "    acp_reload_systemd || failures=$((failures + 1))",
    ['    acp_restore_managed_service_state "$backup/runtime-before/managed-services.tsv" || failures=$((failures + 1))'],
    "backup/runtime-before/managed-services.tsv",
)
replace_line(
    "scripts/audio/install-eq.sh",
    "    local marker backup service_snapshot failure=",
    ["    local marker backup service_snapshot runtime_snapshot failure="],
    "runtime_snapshot failure=",
)
replace_sequence(
    "scripts/audio/install-eq.sh",
    [
        "    acp_capture_preinstall_files || return 1",
        '    if ! prepare_backup_indexes "$backup" "$service_snapshot"; then',
    ],
    [
        '    runtime_snapshot="$(mktemp -d "${TMPDIR:-/tmp}/a-clockwork-plex-preinstall-state.XXXXXX")" || return 1',
        '    if ! acp_capture_runtime_state "$runtime_snapshot" || ! acp_capture_managed_service_state "$runtime_snapshot/managed-services.tsv"; then',
        '        rm -rf "$runtime_snapshot"',
        "        return 1",
        "    fi",
        "    if ! acp_capture_preinstall_files; then",
        '        rm -rf "$runtime_snapshot"',
        "        acp_remove_preinstall_backup || true",
        "        return 1",
        "    fi",
        '    if ! acp_run_root cp -a "$runtime_snapshot" "$backup/runtime-before"; then',
        '        rm -rf "$runtime_snapshot"',
        "        acp_remove_preinstall_backup || true",
        "        return 1",
        "    fi",
        '    rm -rf "$runtime_snapshot"',
        '    if ! prepare_backup_indexes "$backup" "$service_snapshot"; then',
    ],
    "a-clockwork-plex-preinstall-state.XXXXXX",
)
replace_line(
    "scripts/audio/install-eq.sh",
    "    [[ -n \"$failure\" ]] || acp_verify_install_manifest || failure='installed file verification failed'",
    ["    [[ -n \"$failure\" ]] || \"$SCRIPT_DIR/verify-audio.sh\" --root \"$ACP_ROOT\" || failure='installed audio verification failed'"],
    "installed audio verification failed",
)
replace_sequence(
    "scripts/audio/install-eq.sh",
    [
        "    acp_write_operation_log 'EQ-capable audio profile installed successfully' || return 1",
        "    acp_log 'EQ-capable audio profile installed successfully.'",
        "    if acp_is_production_root; then",
        "        sudo -- /usr/local/bin/a-clockwork-plex-audio-route status || return 1",
        "        sudo -- /usr/local/bin/a-clockwork-plex-audio-eq status || return 1",
        "    fi",
    ],
    [
        "    acp_write_operation_log 'EQ-capable audio profile installed successfully' || acp_error 'Warning: installation succeeded but the operation log could not be written.'",
        "    acp_log 'EQ-capable audio profile installed successfully.'",
    ],
    "Warning: installation succeeded but the operation log could not be written.",
)

insert_after(
    "scripts/audio/repair-audio.sh",
    '    acp_run_root cp -p -- "$active" "$snapshot/active-alsa.conf" || return 1',
    [
        '    acp_capture_runtime_state "$snapshot/runtime" || return 1',
        '    acp_capture_managed_service_state "$snapshot/managed-services.tsv" || return 1',
    ],
    'acp_capture_runtime_state "$snapshot/runtime"',
)
insert_after(
    "scripts/audio/repair-audio.sh",
    '    acp_run_root cp -p -- "$snapshot/active-alsa.conf" "$active" || failures=$((failures + 1))',
    ['    acp_restore_runtime_state "$snapshot/runtime" || failures=$((failures + 1))'],
    'acp_restore_runtime_state "$snapshot/runtime"',
)
replace_line(
    "scripts/audio/repair-audio.sh",
    "    [[ -n \"$failure\" ]] || acp_verify_install_manifest || failure='repaired file verification failed'",
    ["    [[ -n \"$failure\" ]] || \"$SCRIPT_DIR/verify-audio.sh\" --root \"$ACP_ROOT\" || failure='repaired audio verification failed'"],
    "repaired audio verification failed",
)
insert_after(
    "scripts/audio/repair-audio.sh",
    "        acp_reload_systemd || rollback_failures=$((rollback_failures + 1))",
    ['        acp_restore_managed_service_state "$snapshot/managed-services.tsv" || rollback_failures=$((rollback_failures + 1))'],
    'acp_restore_managed_service_state "$snapshot/managed-services.tsv"',
)
replace_sequence(
    "scripts/audio/repair-audio.sh",
    [
        "    acp_write_operation_log 'EQ-capable audio profile repaired successfully' || return 1",
        "    acp_log 'EQ-capable audio profile repaired successfully.'",
        "    if acp_is_production_root; then",
        "        sudo -- /usr/local/bin/a-clockwork-plex-audio-route status || return 1",
        "        sudo -- /usr/local/bin/a-clockwork-plex-audio-eq status || return 1",
        "    fi",
    ],
    [
        "    acp_write_operation_log 'EQ-capable audio profile repaired successfully' || acp_error 'Warning: repair succeeded but the operation log could not be written.'",
        "    acp_log 'EQ-capable audio profile repaired successfully.'",
    ],
    "Warning: repair succeeded but the operation log could not be written.",
)

insert_after(
    "scripts/audio/uninstall-eq.sh",
    '    acp_capture_application_services "$snapshot/services.tsv" || return 1',
    [
        '    acp_capture_runtime_state "$snapshot/runtime" || return 1',
        '    acp_capture_managed_service_state "$snapshot/managed-services.tsv" || return 1',
    ],
    'acp_capture_managed_service_state "$snapshot/managed-services.tsv"',
)
insert_after(
    "scripts/audio/uninstall-eq.sh",
    '    acp_run_root cp -p -- "$snapshot/active-alsa.conf" "$active" || failures=$((failures + 1))',
    ['    acp_restore_runtime_state "$snapshot/runtime" || failures=$((failures + 1))'],
    'acp_restore_runtime_state "$snapshot/runtime"',
)
insert_after(
    "scripts/audio/uninstall-eq.sh",
    "    acp_reload_systemd || failures=$((failures + 1))",
    ['    acp_restore_managed_service_state "$snapshot/managed-services.tsv" || failures=$((failures + 1))'],
    'acp_restore_managed_service_state "$snapshot/managed-services.tsv"',
)
replace_sequence(
    "scripts/audio/uninstall-eq.sh",
    [
        "    acp_write_operation_log 'EQ-capable audio profile uninstalled; direct audio restored' || return 1",
        "    acp_log 'EQ-capable audio profile uninstalled; the original direct-audio state was restored.'",
    ],
    [
        "    acp_write_operation_log 'EQ-capable audio profile uninstalled; direct audio restored' || acp_error 'Warning: uninstall succeeded but the operation log could not be written.'",
        "    acp_log 'EQ-capable audio profile uninstalled; the original direct-audio state was restored.'",
    ],
    "Warning: uninstall succeeded but the operation log could not be written.",
)

for launcher in (
    "scripts/a-clockwork-plex-audio-eq.py",
    "scripts/a-clockwork-plex-audio-route.py",
):
    guard_launcher(launcher)
