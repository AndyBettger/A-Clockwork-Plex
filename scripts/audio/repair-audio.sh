#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ACP_REPO_ROOT="$REPO_ROOT"

source "$REPO_ROOT/installer/lib/common.sh"
source "$REPO_ROOT/installer/lib/services.sh"
source "$REPO_ROOT/installer/lib/audio.sh"

MODE=prepare
REQUESTED_ROOT=/
CAMILLADSP_BINARY=
PROJECT_USER="${SUDO_USER:-${USER:-andy}}"
CONFIRMATION=
REQUIRED_CONFIRMATION=REPAIR-EQ-AUDIO

usage() {
    cat <<'EOF_USAGE'
Usage: scripts/audio/repair-audio.sh [options]

Options:
  --prepare-only         Inspect the installed profile and print the repair plan.
  --activate             Reinstall and reactivate the EQ-capable audio files.
  --confirm TOKEN        Required for production repair: REPAIR-EQ-AUDIO
  --binary PATH          Verified CamillaDSP 4.1.3 aarch64 executable.
  --project-user USER    Dashboard/audio user (default: invoking user).
  --root PATH            Alternate filesystem root for non-production tests.
  -h, --help             Show this help.

Repair preserves the original pre-EQ uninstall backup and saved EQ state. It
uses a disposable snapshot of the currently installed files and active route;
a failed repair restores that snapshot before returning an error.
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
            --binary)
                [[ $# -ge 2 ]] || { acp_error '--binary requires a path.'; return 64; }
                CAMILLADSP_BINARY="$2"; shift 2 ;;
            --project-user)
                [[ $# -ge 2 ]] || { acp_error '--project-user requires a user.'; return 64; }
                PROJECT_USER="$2"; shift 2 ;;
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
    [[ "$PROJECT_USER" =~ ^[A-Za-z0-9_.@-]+$ ]] || {
        acp_error "Invalid project user: $PROJECT_USER"
        return 1
    }
    [[ -n "$CAMILLADSP_BINARY" ]] || { acp_error '--binary is required.'; return 64; }
    acp_verify_audio_sources || return 1
    acp_verify_camilladsp_binary "$CAMILLADSP_BINARY" || return 1
    [[ -f "$(acp_path '/var/lib/a-clockwork-plex/split-bus/installed')" ]] || {
        acp_error 'The EQ-capable audio profile is not installed.'
        return 1
    }
    [[ -f "$(acp_path "$ACP_BACKUP_DESTINATION/complete")" ]] || {
        acp_error 'The original pre-EQ uninstall backup is unavailable.'
        return 1
    }
    if acp_is_production_root; then
        [[ "$EUID" -ne 0 ]] || { acp_error "Run as $PROJECT_USER, not as root."; return 1; }
        for command in sudo install cp rm sha256sum stat systemctl modprobe aplay python3 visudo; do
            acp_require_command "$command" || return 1
        done
        acp_validate_sudoers_templates "$PROJECT_USER" || return 1
    fi
}

print_plan() {
    cat <<EOF_PLAN
A Clockwork Plex EQ audio repair plan

Mode:             prepare-only
Filesystem root:  $ACP_ROOT
Project user:     $PROJECT_USER
CamillaDSP:       $CAMILLADSP_BINARY
Saved EQ state:   $(acp_path '/var/lib/a-clockwork-plex/split-bus/master-eq.json')
Uninstall backup: $(acp_path "$ACP_BACKUP_DESTINATION")

Repair will snapshot the current managed files and active ALSA route, reinstall
the reviewed assets, verify/load snd_aloop, reload systemd, activate split-bus
audio and rewrite the installed manifest. Saved EQ state and the original
pre-EQ uninstall backup remain untouched.

No production file, module, service, route, mixer or PCM was changed.
EOF_PLAN
}

capture_repair_snapshot() {
    local snapshot="$1" destination path key table active
    mkdir -p "$snapshot/files" || return 1
    table="$snapshot/managed-current.tsv"
    printf 'destination\tpresent\tmode\tbackup_key\n' >"$table"
    while IFS= read -r destination; do
        path="$(acp_path "$destination")" || return 1
        key="$(acp_backup_key "$destination")" || return 1
        if [[ -f "$path" && ! -L "$path" ]]; then
            cp -p -- "$path" "$snapshot/files/$key" || return 1
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
    [[ -f "$active" && ! -L "$active" ]] || return 1
    cp -p -- "$active" "$snapshot/active-alsa.conf" || return 1
    if acp_is_production_root && [[ -d /sys/module/snd_aloop ]]; then
        printf 'loaded\n' >"$snapshot/loopback.txt"
    else
        printf 'absent\n' >"$snapshot/loopback.txt"
    fi
}

restore_repair_snapshot() {
    local snapshot="$1" destination present mode key path failures=0 active
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
    if acp_is_production_root && [[ "$(cat "$snapshot/loopback.txt")" == absent && -d /sys/module/snd_aloop ]]; then
        sudo -- modprobe -r snd_aloop || failures=$((failures + 1))
    fi
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

activate_repair() {
    local snapshot service_snapshot failure= rollback_failures=0
    [[ "$CONFIRMATION" == "$REQUIRED_CONFIRMATION" ]] || {
        acp_error "Repair requires: --confirm $REQUIRED_CONFIRMATION"
        return 64
    }
    snapshot="$(mktemp -d "${TMPDIR:-/tmp}/a-clockwork-plex-audio-repair.XXXXXX")" || return 1
    service_snapshot="$snapshot/services.tsv"
    capture_repair_snapshot "$snapshot" || { rm -rf "$snapshot"; return 1; }
    acp_capture_application_services "$service_snapshot" || { rm -rf "$snapshot"; return 1; }

    acp_install_audio_files "$CAMILLADSP_BINARY" "$PROJECT_USER" || failure='file repair failed'
    [[ -n "$failure" ]] || acp_ensure_loopback || failure='snd_aloop repair failed'
    [[ -n "$failure" ]] || acp_reload_systemd || failure='systemd reload failed'
    [[ -n "$failure" ]] || acp_enable_eq_audio_units || failure='managed unit enablement failed'
    [[ -n "$failure" ]] || acp_write_installed_marker || failure='installed marker repair failed'
    if [[ -z "$failure" ]] && acp_is_production_root; then
        sudo -- /usr/local/bin/a-clockwork-plex-audio-route activate-split-bus || \
            failure='split-bus reactivation failed'
    fi
    [[ -n "$failure" ]] || acp_write_install_manifest || failure='manifest rewrite failed'
    [[ -n "$failure" ]] || acp_verify_install_manifest || failure='repaired file verification failed'

    if [[ -n "$failure" ]]; then
        stop_current_applications || rollback_failures=$((rollback_failures + 1))
        acp_stop_eq_audio_units || rollback_failures=$((rollback_failures + 1))
        restore_repair_snapshot "$snapshot" || rollback_failures=$((rollback_failures + 1))
        acp_reload_systemd || rollback_failures=$((rollback_failures + 1))
        acp_restore_captured_enablement "$service_snapshot" || rollback_failures=$((rollback_failures + 1))
        acp_restore_captured_applications "$service_snapshot" || rollback_failures=$((rollback_failures + 1))
        acp_install_text "$(date --iso-8601=seconds) repair failed: $failure\n" \
            '/var/lib/a-clockwork-plex/split-bus/last-repair-failure.log' 0644 || \
            rollback_failures=$((rollback_failures + 1))
        rm -rf "$snapshot"
        if [[ "$rollback_failures" -eq 0 ]]; then
            acp_error "Repair failed; the previous installed state was restored: $failure"
        else
            acp_error "Repair failed and restoration was incomplete: $failure"
        fi
        return 1
    fi

    rm -rf "$snapshot"
    acp_write_operation_log 'EQ-capable audio profile repaired successfully' || return 1
    acp_log 'EQ-capable audio profile repaired successfully.'
    if acp_is_production_root; then
        sudo -- /usr/local/bin/a-clockwork-plex-audio-route status || return 1
        sudo -- /usr/local/bin/a-clockwork-plex-audio-eq status || return 1
    fi
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
    activate_repair
}

main "$@"
