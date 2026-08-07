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
REQUIRED_CONFIRMATION=INSTALL-EQ-AUDIO

usage() {
    cat <<'EOF_USAGE'
Usage: scripts/audio/install-eq.sh [options]

Options:
  --prepare-only         Validate inputs and print the installation plan (default).
  --activate             Install or repair the EQ-capable audio profile.
  --confirm TOKEN        Required for production activation: INSTALL-EQ-AUDIO
  --binary PATH          Verified CamillaDSP 4.1.3 aarch64 executable.
  --project-user USER    Dashboard/audio user (default: invoking user).
  --root PATH            Alternate filesystem root for non-production tests.
  -h, --help             Show this help.

Production activation must be run as the normal project user. The script uses
sudo only for fixed filesystem, module and systemd operations. A repeated
activation on an installed EQ profile delegates to repair-audio.sh.
EOF_USAGE
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --prepare-only)
                MODE=prepare
                shift
                ;;
            --activate)
                MODE=activate
                shift
                ;;
            --confirm)
                [[ $# -ge 2 ]] || { acp_error '--confirm requires a token.'; return 64; }
                CONFIRMATION="$2"
                shift 2
                ;;
            --binary)
                [[ $# -ge 2 ]] || { acp_error '--binary requires a path.'; return 64; }
                CAMILLADSP_BINARY="$2"
                shift 2
                ;;
            --project-user)
                [[ $# -ge 2 ]] || { acp_error '--project-user requires a user.'; return 64; }
                PROJECT_USER="$2"
                shift 2
                ;;
            --root)
                [[ $# -ge 2 ]] || { acp_error '--root requires a path.'; return 64; }
                REQUESTED_ROOT="$2"
                shift 2
                ;;
            -h|--help)
                usage
                return 2
                ;;
            *)
                acp_error "Unknown option: $1"
                usage >&2
                return 64
                ;;
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
    [[ -n "$CAMILLADSP_BINARY" ]] || {
        acp_error '--binary is required.'
        return 64
    }
    acp_verify_audio_sources || return 1
    acp_verify_camilladsp_binary "$CAMILLADSP_BINARY" || return 1

    if acp_is_production_root; then
        [[ "$EUID" -ne 0 ]] || {
            acp_error "Run as $PROJECT_USER, not as root."
            return 1
        }
        for command in sudo install cp rm sha256sum stat systemctl modprobe aplay python3 visudo; do
            acp_require_command "$command" || return 1
        done
        acp_validate_sudoers_templates "$PROJECT_USER" || return 1
    fi
}

print_plan() {
    local marker backup
    marker="$(acp_path '/var/lib/a-clockwork-plex/split-bus/installed')" || return 1
    backup="$(acp_path "$ACP_BACKUP_DESTINATION")" || return 1
    cat <<EOF_PLAN
A Clockwork Plex EQ audio installation plan

Mode:             prepare-only
Filesystem root:  $ACP_ROOT
Project user:     $PROJECT_USER
CamillaDSP:       $CAMILLADSP_BINARY
Profile:          eq-split-bus
Managed files:    $(acp_managed_file_destinations | wc -l)
Installed marker: $marker
Uninstall backup: $backup

Activation will:
  1. verify the accepted direct ALSA baseline on first install;
  2. capture one exact pre-EQ backup and application-service snapshot;
  3. install the reviewed routes, helpers, binary, units and loopback settings;
  4. load or verify snd_aloop;
  5. reload systemd and enable the route and CamillaDSP units;
  6. activate split-bus audio through the fixed route helper;
  7. verify the installed manifest and retain the pre-EQ backup for uninstall.

No production file, module, service, route, mixer or PCM was changed.
EOF_PLAN
}

write_failure_report() {
    local detail="$1"
    acp_install_text "$(date --iso-8601=seconds) install failed: $detail\n" \
        '/var/lib/a-clockwork-plex/split-bus/last-install-failure.log' 0644
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

rollback_first_install() {
    local service_snapshot="$1" reason="$2" failures=0
    acp_log 'Installation failed; restoring the accepted direct-audio baseline.'

    stop_current_applications || failures=$((failures + 1))
    acp_stop_eq_audio_units || failures=$((failures + 1))
    acp_disable_eq_audio_units || true
    acp_remove_file '/var/lib/a-clockwork-plex/split-bus/installed' || failures=$((failures + 1))
    acp_restore_preinstall_files || failures=$((failures + 1))
    acp_reload_systemd || failures=$((failures + 1))
    acp_restore_loopback_state || failures=$((failures + 1))
    acp_restore_captured_enablement "$service_snapshot" || failures=$((failures + 1))
    acp_restore_captured_applications "$service_snapshot" || failures=$((failures + 1))
    write_failure_report "$reason" || failures=$((failures + 1))

    if [[ "$failures" -eq 0 ]]; then
        acp_remove_preinstall_backup || return 1
        acp_error "Installation failed, but the original direct-audio state was restored: $reason"
        return 1
    fi
    acp_error "Installation failed and rollback was incomplete. The pre-EQ backup was retained: $reason"
    return 1
}

first_install() {
    local marker backup service_snapshot failure=
    marker="$(acp_path '/var/lib/a-clockwork-plex/split-bus/installed')" || return 1
    backup="$(acp_path "$ACP_BACKUP_DESTINATION")" || return 1
    service_snapshot="$backup/service-before.tsv"

    [[ ! -e "$backup" ]] || {
        acp_error "A pre-EQ backup path already exists and must be reviewed: $backup"
        return 1
    }

    acp_capture_preinstall_files || return 1
    if ! acp_capture_application_services "$service_snapshot"; then
        write_failure_report 'could not capture application service state'
        acp_remove_preinstall_backup || true
        return 1
    fi

    acp_install_audio_files "$CAMILLADSP_BINARY" "$PROJECT_USER" || failure='file installation failed'
    [[ -n "$failure" ]] || acp_ensure_loopback || failure='snd_aloop setup failed'
    [[ -n "$failure" ]] || acp_reload_systemd || failure='systemd reload failed'
    [[ -n "$failure" ]] || acp_enable_eq_audio_units || failure='managed unit enablement failed'
    [[ -n "$failure" ]] || acp_write_installed_marker || failure='installed marker write failed'

    if [[ -z "$failure" ]] && acp_is_production_root; then
        sudo -- /usr/local/bin/a-clockwork-plex-audio-route activate-split-bus || \
            failure='split-bus activation failed'
    fi
    [[ -n "$failure" ]] || acp_write_install_manifest || failure='install manifest write failed'
    [[ -n "$failure" ]] || acp_verify_install_manifest || failure='installed file verification failed'

    if [[ -n "$failure" ]]; then
        rollback_first_install "$service_snapshot" "$failure"
        return 1
    fi

    acp_write_operation_log 'EQ-capable audio profile installed successfully' || return 1
    acp_log 'EQ-capable audio profile installed successfully.'
    if acp_is_production_root; then
        sudo -- /usr/local/bin/a-clockwork-plex-audio-route status || return 1
        sudo -- /usr/local/bin/a-clockwork-plex-audio-eq status || return 1
    fi
}

activate() {
    local marker
    [[ "$CONFIRMATION" == "$REQUIRED_CONFIRMATION" ]] || {
        acp_error "Activation requires: --confirm $REQUIRED_CONFIRMATION"
        return 64
    }
    marker="$(acp_path '/var/lib/a-clockwork-plex/split-bus/installed')" || return 1
    if [[ -f "$marker" ]]; then
        acp_log 'The EQ audio profile is already installed; delegating to repair.'
        "$SCRIPT_DIR/repair-audio.sh" \
            --activate \
            --confirm REPAIR-EQ-AUDIO \
            --binary "$CAMILLADSP_BINARY" \
            --project-user "$PROJECT_USER" \
            --root "$ACP_ROOT"
        return $?
    fi
    first_install
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
    activate
}

main "$@"
