#!/bin/bash

ACP_RUNTIME_STATE_PATHS=(
    /var/lib/a-clockwork-plex/split-bus/master-eq.json
    /var/lib/a-clockwork-plex/split-bus/route-state.json
    /var/lib/a-clockwork-plex/split-bus/install-manifest.tsv
)

acp_runtime_key() {
    printf '%s' "$1" | sha256sum | awk '{print $1}'
}

acp_capture_runtime_state() {
    local snapshot table
    local destination path key mode uid gid
    snapshot="$1"
    table="$snapshot/state-files.tsv"
    mkdir -p "$snapshot/files" || return 1
    printf 'destination\tpresent\tmode\tuid\tgid\tbackup_key\n' >"$table"

    for destination in "${ACP_RUNTIME_STATE_PATHS[@]}"; do
        path="$(acp_path "$destination")" || return 1
        key="$(acp_runtime_key "$destination")" || return 1
        if [[ -f "$path" && ! -L "$path" ]]; then
            mode="$(acp_run_root stat -c '%a' "$path")" || return 1
            uid="$(acp_run_root stat -c '%u' "$path")" || return 1
            gid="$(acp_run_root stat -c '%g' "$path")" || return 1
            acp_run_root cp -p -- "$path" "$snapshot/files/$key" || return 1
            printf '%s\ttrue\t%s\t%s\t%s\t%s\n' \
                "$destination" "$mode" "$uid" "$gid" "$key" >>"$table"
        elif [[ ! -e "$path" && ! -L "$path" ]]; then
            printf '%s\tfalse\t-\t-\t-\t%s\n' "$destination" "$key" >>"$table"
        else
            acp_error "Runtime state path is not a regular file or absent: $path"
            return 1
        fi
    done
}

acp_restore_runtime_state() {
    local snapshot table
    local destination present mode uid gid key path failures=0
    snapshot="$1"
    table="$snapshot/state-files.tsv"
    [[ -f "$table" ]] || {
        acp_error "Runtime-state snapshot is incomplete: $snapshot"
        return 1
    }

    while IFS=$'\t' read -r destination present mode uid gid key; do
        [[ "$destination" == destination ]] && continue
        path="$(acp_path "$destination")" || { failures=$((failures + 1)); continue; }
        if [[ "$present" == true ]]; then
            if ! acp_run_root install -D -m "$mode" "$snapshot/files/$key" "$path"; then
                failures=$((failures + 1))
                continue
            fi
            if acp_is_production_root; then
                acp_run_root chown "$uid:$gid" "$path" || failures=$((failures + 1))
            fi
        else
            acp_remove_file "$destination" || failures=$((failures + 1))
        fi
    done <"$table"
    [[ "$failures" -eq 0 ]]
}

acp_capture_managed_service_state() {
    local destination="$1" unit active enabled
    : >"$destination" || return 1
    printf 'unit\tactive\tenabled\n' >"$destination"
    for unit in \
        a-clockwork-plex-audio-route.service \
        a-clockwork-plex-camilladsp.service; do
        active=false
        enabled=false
        if acp_is_production_root; then
            systemctl is-active --quiet "$unit" && active=true
            systemctl is-enabled --quiet "$unit" && enabled=true
        fi
        printf '%s\t%s\t%s\n' "$unit" "$active" "$enabled" >>"$destination"
    done
}

acp_managed_service_value() {
    local snapshot="$1" unit="$2" column="$3"
    awk -F '\t' -v wanted="$unit" -v field="$column" \
        '$1 == wanted { print $field; found=1 } END { if (!found) exit 1 }' "$snapshot"
}

acp_restore_managed_service_state() {
    local snapshot="$1" route_enabled camilla_enabled camilla_active failures=0
    acp_is_production_root || return 0

    route_enabled="$(acp_managed_service_value \
        "$snapshot" a-clockwork-plex-audio-route.service 3)" || return 1
    camilla_enabled="$(acp_managed_service_value \
        "$snapshot" a-clockwork-plex-camilladsp.service 3)" || return 1
    camilla_active="$(acp_managed_service_value \
        "$snapshot" a-clockwork-plex-camilladsp.service 2)" || return 1

    if [[ "$route_enabled" == true ]]; then
        sudo -- systemctl enable a-clockwork-plex-audio-route.service >/dev/null || \
            failures=$((failures + 1))
    else
        sudo -- systemctl disable a-clockwork-plex-audio-route.service >/dev/null 2>&1 || true
    fi
    if [[ "$camilla_enabled" == true ]]; then
        sudo -- systemctl enable a-clockwork-plex-camilladsp.service >/dev/null || \
            failures=$((failures + 1))
    else
        sudo -- systemctl disable a-clockwork-plex-camilladsp.service >/dev/null 2>&1 || true
    fi

    if [[ "$camilla_active" == true ]]; then
        sudo -- systemctl start a-clockwork-plex-camilladsp.service || \
            failures=$((failures + 1))
    else
        sudo -- systemctl stop a-clockwork-plex-camilladsp.service >/dev/null 2>&1 || true
    fi
    [[ "$failures" -eq 0 ]]
}
