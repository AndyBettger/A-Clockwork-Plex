#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ACP_REPO_ROOT="$REPO_ROOT"

source "$REPO_ROOT/installer/lib/common.sh"
source "$REPO_ROOT/installer/lib/services.sh"
source "$REPO_ROOT/installer/lib/audio.sh"
source "$REPO_ROOT/installer/lib/runtime.sh"
source "$REPO_ROOT/installer/lib/verification.sh"

MODE=prepare
REQUESTED_ROOT=/
CONFIRMATION=
REQUIRED_CONFIRMATION=UNINSTALL-EQ-AUDIO
PROJECT_USER="${SUDO_USER:-${USER:-andy}}"

usage() {
    cat <<'EOF_USAGE'
Usage: scripts/audio/uninstall-eq.sh [options]

Options:
  --prepare-only         Inspect the retained backup and print the plan (default).
  --activate             Restore the exact pre-EQ audio installation.
  --confirm TOKEN        Required for production uninstall: UNINSTALL-EQ-AUDIO
  --root PATH            Alternate filesystem root for non-production tests.
  -h, --help             Show this help.

Uninstall restores the accepted pre-EQ active ALSA route, every managed path's
original present/absent state, original application service enablement/activity
and the original loaded/absent snd_aloop state. Saved EQ values are retained.
EOF_USAGE
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --prepare-only) MODE=prepare; shift ;;
            --activate) MODE=activate; shift ;;
            --confirm)
                [[ $# -ge 2 ]] || { acp_error '--confirm requires a token.'; return 64; }
                CONFIRMATION="$2"; shift 2 ;;
            --root)
                [[ $# -ge 2 ]] || { acp_error '--root requires a path.'; return 64; }
                REQUESTED_ROOT="$2"; shift 2 ;;
            -h|--help) usage; return 2 ;;
            *) acp_error "Unknown option: $1"; usage >&2; return 64 ;;
        esac
    done
}

validate_inputs() {
    ACP_ROOT="$(acp_normalise_root "$REQUESTED_ROOT")" || return 1
    export ACP_ROOT ACP_REPO_ROOT
    [[ -f "$(acp_path '/var/lib/a-clockwork-plex/split-bus/installed')" ]] || {
        acp_error 'The EQ-capable audio profile is not installed.'
        return 1
    }
    [[ -f "$(acp_path "$ACP_BACKUP_DESTINATION/complete")" ]] || {
        acp_error 'The original pre-EQ backup is unavailable or incomplete.'
        return 1
    }
    [[ -f "$(acp_path "$ACP_BACKUP_DESTINATION/service-before.tsv")" ]] || {
        acp_error 'The original application service snapshot is unavailable.'
        return 1
    }
    if acp_is_production_root; then
        [[ "$EUID" -ne 0 ]] || { acp_error "Run as $PROJECT_USER, not as root."; return 1; }
        for command in sudo install cp rm sha256sum stat systemctl modprobe python3; do
            acp_require_command "$command" || return 1
        done
    fi
}

print_plan() {
    local backup expected observed
    backup="$(acp_path "$ACP_BACKUP_DESTINATION")" || return 1
    expected="$(cat "$backup/pre-eq-active-route.sha256")"
    observed="$(sha256sum "$backup/pre-eq-active-route.conf" | awk '{print $1}')" || return 1
    [[ "$expected" == "$observed" ]] || {
        acp_error 'The retained active-route backup checksum does not match.'
        return 1
    }
    cat <<EOF_PLAN
A Clockwork Plex EQ audio uninstall plan

Mode:             prepare-only
Filesystem root:  $ACP_ROOT
Retained backup:  $backup
Direct route SHA: $expected
Saved EQ state:   $(acp_path '/var/lib/a-clockwork-plex/split-bus/master-eq.json')

Activation will stop current audio applications, stop and disable the managed EQ
units, restore the original active ALSA route and managed-file presence, reload
systemd, restore the previous snd_aloop state, then restore the original service
enablement and activity. The saved EQ curve is retained for a future reinstall.

No production file, module, service, route, mixer or PCM was changed.
EOF_PLAN
}

capture_current_install() {
    local snapshot="$1" destination path key table active
    mkdir -p "$snapshot/files" || return 1
    table="$snapshot/managed-current.tsv"
    printf 'destination\tpresent\tmode\tbackup_key\n' >"$table"
    while IFS= read -r destination; do
        path="$(acp_path "$destination")" || return 1
        key="$(acp_backup_key "$destination")" || return 1
        if [[ -f "$path" && ! -L "$path" ]]; then
            acp_run_root cp -p -- "$path" "$snapshot/files/$key" || return 1
            printf '%s\ttrue\t%s\t%s\n' \
                "$destination" "$(stat -c '%a' "$path")" "$key" >>"$table"
        elif [[ ! -e "$path" && ! -L "$path" ]]; then
            printf '%s\tfalse\t-\t%s\n' "$destination" "$key" >>"$table"
        else
            acp_error "Managed path is not a regular file or absent: $path"
            return 1
        fi
    done < <(acp_managed_file_destinations)
    active="$(acp_path "$ACP_ACTIVE_ALSA_DESTINATION")" || return 1
    acp_run_root cp -p -- "$active" "$snapshot/active-alsa.conf" || return 1
    acp_capture_application_services "$snapshot/services.tsv" || return 1
    acp_capture_runtime_state "$snapshot/runtime" || return 1
    acp_capture_managed_service_state "$snapshot/managed-services.tsv" || return 1
    if acp_is_production_root && [[ -d /sys/module/snd_aloop ]]; then
        printf 'loaded\n' >"$snapshot/loopback.txt"
    else
        printf 'absent\n' >"$snapshot/loopback.txt"
    fi
}

restore_current_install() {
    local snapshot="$1" destination present mode key path active failures=0
    while IFS=$'\t' read -r destination present mode key; do
        [[ "$destination" == destination ]] && continue
        path="$(acp_path "$destination")" || { failures=$((failures + 1)); continue; }
        if [[ "$present" == true ]]; then
            acp_run_root install -D -m "$mode" "$snapshot/files/$key" "$path" || \
                failures=$((failures + 1))
        else
            acp_remove_file "$destination" || failures=$((failures + 1))
        fi
    done <"$snapshot/managed-current.tsv"
    active="$(acp_path "$ACP_ACTIVE_ALSA_DESTINATION")" || return 1
    acp_run_root cp -p -- "$snapshot/active-alsa.conf" "$active" || failures=$((failures + 1))
    acp_restore_runtime_state "$snapshot/runtime" || failures=$((failures + 1))
    acp_write_installed_marker || failures=$((failures + 1))
    acp_reload_systemd || failures=$((failures + 1))
    acp_restore_managed_service_state "$snapshot/managed-services.tsv" || \
        failures=$((failures + 1))
    if acp_is_production_root && [[ "$(cat "$snapshot/loopback.txt")" == loaded && ! -d /sys/module/snd_aloop ]]; then
        sudo -- modprobe snd_aloop || failures=$((failures + 1))
    fi
    acp_restore_captured_enablement "$snapshot/services.tsv" || failures=$((failures + 1))
    acp_restore_captured_applications "$snapshot/services.tsv" || failures=$((failures + 1))
    [[ "$failures" -eq 0 ]]
}

stop_current_applications() {
    acp_is_production_root || return 0
    local unit failures=0
    for unit in "${ACP_SERVICE_STOP_ORDER[@]}"; do
        if systemctl is-active --quiet "$unit"; then
            sudo -- systemctl stop "$unit" || failures=$((failures + 1))
        fi
    done
    [[ "$failures" -eq 0 ]]
}

write_direct_rollback_state() {
    local active_hash
    active_hash="$(acp_sha256 "$ACP_ACTIVE_ALSA_DESTINATION")" || return 1
    acp_install_text \
        "{\"schema_version\":1,\"mode\":\"direct-rollback\",\"reason\":\"EQ-capable audio profile uninstalled\",\"active_alsa_sha256\":\"$active_hash\"}\n" \
        '/var/lib/a-clockwork-plex/split-bus/route-state.json' 0644
}

activate_uninstall() {
    local backup original_services snapshot failure= recovery_failures=0
    [[ "$CONFIRMATION" == "$REQUIRED_CONFIRMATION" ]] || {
        acp_error "Uninstall requires: --confirm $REQUIRED_CONFIRMATION"
        return 64
    }
    backup="$(acp_path "$ACP_BACKUP_DESTINATION")" || return 1
    original_services="$backup/service-before.tsv"
    snapshot="$(mktemp -d "${TMPDIR:-/tmp}/a-clockwork-plex-audio-uninstall.XXXXXX")" || return 1
    capture_current_install "$snapshot" || { rm -rf "$snapshot"; return 1; }

    stop_current_applications || failure='could not stop current audio applications'
    [[ -n "$failure" ]] || acp_stop_eq_audio_units || failure='could not stop managed EQ units'
    [[ -n "$failure" ]] || acp_disable_eq_audio_units || failure='could not disable managed EQ units'
    [[ -n "$failure" ]] || acp_remove_file '/var/lib/a-clockwork-plex/split-bus/installed' || \
        failure='could not remove installed marker'
    [[ -n "$failure" ]] || acp_restore_preinstall_files || failure='pre-EQ file restoration failed'
    [[ -n "$failure" ]] || acp_reload_systemd || failure='systemd reload failed'
    [[ -n "$failure" ]] || acp_restore_loopback_state || failure='snd_aloop state restoration failed'
    [[ -n "$failure" ]] || acp_restore_captured_enablement "$original_services" || \
        failure='original service enablement restoration failed'
    [[ -n "$failure" ]] || acp_restore_captured_applications "$original_services" || \
        failure='original application service restoration failed'
    [[ -n "$failure" ]] || write_direct_rollback_state || failure='direct rollback state write failed'
    [[ -n "$failure" ]] || acp_remove_file '/var/lib/a-clockwork-plex/split-bus/install-manifest.tsv' || \
        failure='install manifest removal failed'

    if [[ -n "$failure" ]]; then
        stop_current_applications || recovery_failures=$((recovery_failures + 1))
        acp_stop_eq_audio_units || recovery_failures=$((recovery_failures + 1))
        restore_current_install "$snapshot" || recovery_failures=$((recovery_failures + 1))
        acp_install_text "$(date --iso-8601=seconds) uninstall failed: $failure\n" \
            '/var/lib/a-clockwork-plex/split-bus/last-uninstall-failure.log' 0644 || \
            recovery_failures=$((recovery_failures + 1))
        rm -rf "$snapshot"
        if [[ "$recovery_failures" -eq 0 ]]; then
            acp_error "Uninstall failed; the installed EQ state was restored: $failure"
        else
            acp_error "Uninstall failed and EQ restoration was incomplete: $failure"
        fi
        return 1
    fi

    acp_remove_preinstall_backup || { rm -rf "$snapshot"; return 1; }
    rm -rf "$snapshot"
    acp_write_operation_log 'EQ-capable audio profile uninstalled; direct audio restored' || \
        acp_error 'Warning: uninstall succeeded but the operation log could not be written.'
    acp_log 'EQ-capable audio profile uninstalled; the original direct-audio state was restored.'
}

main() {
    parse_args "$@"
    local parsed=$?
    [[ "$parsed" -eq 2 ]] && return 0
    [[ "$parsed" -eq 0 ]] || return "$parsed"
    validate_inputs || return $?
    if [[ "$MODE" == prepare ]]; then
        print_plan
        return $?
    fi
    activate_uninstall
}

main "$@"
