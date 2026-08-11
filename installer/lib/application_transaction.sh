#!/bin/bash

# Whole-appliance application transaction boundary.
#
# Package/venv bootstrap intentionally happens before this transaction and forms
# its prerequisite baseline. This layer captures only application-managed state
# that later specialist owners may mutate. EQ teardown remains owned by the
# standalone EQ lifecycle and must run before generic restoration.

if [[ -z "${ACP_REPO_ROOT:-}" ]]; then
    ACP_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi

# shellcheck source=installer/lib/common.sh
source "$ACP_REPO_ROOT/installer/lib/common.sh"
# shellcheck source=installer/lib/transaction.sh
source "$ACP_REPO_ROOT/installer/lib/transaction.sh"
# shellcheck source=installer/lib/audio.sh
source "$ACP_REPO_ROOT/installer/lib/audio.sh"

ACP_APPLICATION_SERVICES=(
    plexamp.service
    shairport-sync.service
    a-clockwork-plex.service
    a-clockwork-plex-airplay-metadata.service
    a-clockwork-plex-audio-route.service
    a-clockwork-plex-camilladsp.service
    a-clockwork-plex-audio-failback.service
)

acp_application_validate_identity() {
    local project_user="$1" project_dir="$2"
    [[ "$project_user" =~ ^[A-Za-z_][A-Za-z0-9_.-]*$ ]] || {
        acp_error "Invalid project user: $project_user"
        return 1
    }
    [[ "$project_dir" == /* ]] || {
        acp_error "Project directory must be absolute: $project_dir"
        return 1
    }
}

acp_application_managed_paths() {
    local project_user="$1" project_dir="$2"
    acp_application_validate_identity "$project_user" "$project_dir" || return 1

    cat <<EOF
$project_dir/config.json
/etc/default/a-clockwork-plex-weather
/etc/systemd/system/a-clockwork-plex.service
/home/$project_user/.config/autostart/a-clockwork-plex-dashboard.desktop
/usr/local/bin/a-clockwork-plex-alarm-audio
/etc/sudoers.d/a-clockwork-plex-alarm-audio
/usr/local/bin/a-clockwork-plex-shairport-name
/etc/sudoers.d/a-clockwork-plex-shairport-name
/etc/shairport-sync.conf
/usr/local/bin/a-clockwork-plex-airplay-start
/usr/local/bin/a-clockwork-plex-airplay-end
/usr/local/bin/a-clockwork-plex-airplay-session-end
/etc/sudoers.d/a-clockwork-plex-airplay
/etc/systemd/system/a-clockwork-plex-airplay-metadata.service
/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf
/var/lib/a-clockwork-plex/split-bus/master-eq.json
/var/lib/a-clockwork-plex/split-bus/installed
/var/lib/a-clockwork-plex/split-bus/install-manifest.tsv
/var/lib/a-clockwork-plex/split-bus/route-state.json
/var/lib/a-clockwork-plex/split-bus/last-operation.log
/var/lib/a-clockwork-plex/split-bus/last-install-failure.log
/var/lib/a-clockwork-plex/split-bus/last-uninstall-failure.log
EOF
    acp_managed_file_destinations
}

acp_application_capture_fifo() {
    local directory="$1" logical="$2" path state mode uid gid
    acp_transaction_validate_directory "$directory" || return 1
    [[ "$logical" == /* ]] || {
        acp_error "FIFO path must be absolute: $logical"
        return 1
    }
    path="$(acp_path "$logical")" || return 1
    if [[ -L "$path" || ( -e "$path" && ! -p "$path" ) ]]; then
        acp_error "Managed FIFO path is neither absent nor a FIFO: $logical"
        return 1
    fi
    if [[ -p "$path" ]]; then
        state=fifo
        mode="$(stat -c '%a' "$path")" || return 1
        uid="$(stat -c '%u' "$path")" || return 1
        gid="$(stat -c '%g' "$path")" || return 1
    else
        state=absent
        mode=-
        uid=-
        gid=-
    fi
    printf 'path\tstate\tmode\tuid\tgid\n%s\t%s\t%s\t%s\t%s\n' \
        "$logical" "$state" "$mode" "$uid" "$gid" >"$directory/fifo.tsv"
}

acp_application_restore_fifo() {
    local directory="$1" logical state mode uid gid path
    [[ -f "$directory/fifo.tsv" ]] || return 1
    IFS=$'\t' read -r logical state mode uid gid < <(tail -n 1 "$directory/fifo.tsv")
    path="$(acp_path "$logical")" || return 1
    if [[ -L "$path" || ( -e "$path" && ! -p "$path" ) ]]; then
        acp_error "Cannot restore FIFO state over unexpected object: $logical"
        return 1
    fi
    case "$state" in
        absent)
            if [[ -p "$path" ]]; then
                acp_run_root rm -f -- "$path" || return 1
            fi
            ;;
        fifo)
            if [[ ! -p "$path" ]]; then
                acp_run_root mkfifo "$path" || return 1
            fi
            acp_run_root chmod "$mode" "$path" || return 1
            if acp_is_production_root; then
                acp_run_root chown "$uid:$gid" "$path" || return 1
            fi
            ;;
        *)
            acp_error "Unknown captured FIFO state: $state"
            return 1
            ;;
    esac
    return 0
}

acp_application_capture_loaded_services() {
    local directory="$1" unit load_state
    acp_is_production_root || return 0
    printf 'unit\n' >"$directory/application-services.tsv"
    for unit in "${ACP_APPLICATION_SERVICES[@]}"; do
        load_state="$(systemctl show "$unit" -p LoadState --value 2>/dev/null || true)"
        if [[ -n "$load_state" && "$load_state" != not-found ]]; then
            acp_transaction_capture_service "$directory" "$unit" || return 1
            printf '%s\n' "$unit" >>"$directory/application-services.tsv"
        fi
    done
}

acp_application_stop_owned_services() {
    local unit
    acp_is_production_root || return 0
    for unit in "${ACP_APPLICATION_SERVICES[@]}"; do
        sudo -- systemctl stop "$unit" >/dev/null 2>&1 || true
    done
}

acp_application_transaction_begin() {
    local directory="$1" project_user="$2" project_dir="$3" logical
    acp_application_validate_identity "$project_user" "$project_dir" || return 1
    acp_transaction_begin "$directory" || return 1
    while IFS= read -r logical; do
        [[ -n "$logical" ]] || continue
        acp_transaction_capture_path "$directory" "$logical" || return 1
    done < <(acp_application_managed_paths "$project_user" "$project_dir")
    acp_application_capture_fifo "$directory" '/tmp/shairport-sync-metadata' || return 1
    acp_application_capture_loaded_services "$directory" || return 1
}

acp_application_transaction_restore() {
    local directory="$1" failures=0
    acp_application_stop_owned_services || failures=$((failures + 1))
    acp_transaction_restore_paths "$directory" || failures=$((failures + 1))
    acp_application_restore_fifo "$directory" || failures=$((failures + 1))
    if acp_is_production_root; then
        sudo -- systemctl daemon-reload || failures=$((failures + 1))
        acp_transaction_restore_services "$directory" || failures=$((failures + 1))
    fi
    [[ "$failures" -eq 0 ]]
}
