#!/bin/bash

ACP_SERVICE_STOP_ORDER=(
    a-clockwork-plex.service
    shairport-sync.service
    plexamp.service
)

ACP_SERVICE_START_ORDER=(
    plexamp.service
    shairport-sync.service
    a-clockwork-plex.service
)

acp_service_is_active() {
    systemctl is-active --quiet "$1"
}

acp_service_is_enabled() {
    systemctl is-enabled --quiet "$1"
}

acp_capture_application_services() {
    local destination="$1" unit active enabled
    : >"$destination" || return 1
    printf 'unit\tactive\tenabled\n' >"$destination"
    if ! acp_is_production_root; then
        for unit in "${ACP_SERVICE_START_ORDER[@]}"; do
            printf '%s\tfalse\tfalse\n' "$unit" >>"$destination"
        done
        return 0
    fi
    for unit in "${ACP_SERVICE_START_ORDER[@]}"; do
        active=false
        enabled=false
        acp_service_is_active "$unit" && active=true
        acp_service_is_enabled "$unit" && enabled=true
        printf '%s\t%s\t%s\n' "$unit" "$active" "$enabled" >>"$destination"
    done
}

acp_captured_service_value() {
    local snapshot="$1" unit="$2" column="$3"
    awk -F '\t' -v wanted="$unit" -v field="$column" \
        '$1 == wanted { print $field; found=1 } END { if (!found) exit 1 }' "$snapshot"
}

acp_stop_captured_applications() {
    local snapshot="$1" unit was_active stopped=()
    acp_is_production_root || return 0
    for unit in "${ACP_SERVICE_STOP_ORDER[@]}"; do
        was_active="$(acp_captured_service_value "$snapshot" "$unit" 2)" || return 1
        [[ "$was_active" == true ]] || continue
        if sudo -- systemctl stop "$unit"; then
            stopped+=("$unit")
            continue
        fi
        acp_error "Could not stop $unit; restoring services already stopped."
        local restore_unit
        for restore_unit in "${ACP_SERVICE_START_ORDER[@]}"; do
            local candidate
            for candidate in "${stopped[@]}"; do
                [[ "$candidate" == "$restore_unit" ]] || continue
                sudo -- systemctl start "$restore_unit" || \
                    acp_error "Could not restore $restore_unit after partial stop failure."
            done
        done
        return 1
    done
}

acp_restore_captured_applications() {
    local snapshot="$1" unit was_active failures=0
    acp_is_production_root || return 0
    for unit in "${ACP_SERVICE_START_ORDER[@]}"; do
        was_active="$(acp_captured_service_value "$snapshot" "$unit" 2)" || return 1
        [[ "$was_active" == true ]] || continue
        if ! sudo -- systemctl start "$unit"; then
            acp_error "Could not restore $unit."
            failures=$((failures + 1))
        fi
    done
    [[ "$failures" -eq 0 ]]
}

acp_restore_captured_enablement() {
    local snapshot="$1" unit was_enabled failures=0
    acp_is_production_root || return 0
    for unit in "${ACP_SERVICE_START_ORDER[@]}"; do
        was_enabled="$(acp_captured_service_value "$snapshot" "$unit" 3)" || return 1
        if [[ "$was_enabled" == true ]]; then
            sudo -- systemctl enable "$unit" >/dev/null || failures=$((failures + 1))
        else
            sudo -- systemctl disable "$unit" >/dev/null || failures=$((failures + 1))
        fi
    done
    [[ "$failures" -eq 0 ]]
}

acp_reload_systemd() {
    acp_is_production_root || return 0
    sudo -- systemctl daemon-reload
}

acp_enable_eq_audio_units() {
    acp_is_production_root || return 0
    sudo -- systemctl enable \
        a-clockwork-plex-audio-route.service \
        a-clockwork-plex-camilladsp.service >/dev/null
}

acp_disable_eq_audio_units() {
    acp_is_production_root || return 0
    sudo -- systemctl disable \
        a-clockwork-plex-camilladsp.service \
        a-clockwork-plex-audio-route.service >/dev/null
}

acp_stop_eq_audio_units() {
    acp_is_production_root || return 0
    sudo -- systemctl stop a-clockwork-plex-camilladsp.service >/dev/null 2>&1 || true
    sudo -- systemctl stop a-clockwork-plex-audio-route.service >/dev/null 2>&1 || true
}
