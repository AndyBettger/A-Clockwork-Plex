#!/bin/bash

# Read-only component inventory for the Phase 7 appliance installer.
# This library describes specialist ownership; it does not activate anything.

if [[ -z "${ACP_REPO_ROOT:-}" ]]; then
    ACP_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi

ACP_COMPONENT_IDS=(
    dashboard-service
    dashboard-kiosk
    airplay-hooks
    airplay-metadata
    alarm-audio-helper
    shairport-name-helper
)

acp_component_record() {
    case "$1" in
        dashboard-service)
            printf '%s\t%s\t%s\t%s\t%s\n' \
                dashboard-service native-check \
                scripts/install-dashboard-service.sh \
                'bash scripts/install-dashboard-service.sh --check' \
                'bash scripts/install-dashboard-service.sh --apply --confirm INSTALL-DASHBOARD-RUNNER'
            ;;
        dashboard-kiosk)
            printf '%s\t%s\t%s\t%s\t%s\n' \
                dashboard-kiosk native-check \
                scripts/install-dashboard-kiosk.sh \
                'bash scripts/install-dashboard-kiosk.sh --check' \
                'bash scripts/install-dashboard-kiosk.sh --apply --confirm INSTALL-DASHBOARD-KIOSK'
            ;;
        airplay-hooks)
            printf '%s\t%s\t%s\t%s\t%s\n' \
                airplay-hooks adapter-check \
                scripts/install-airplay-hooks.sh \
                'bash scripts/check-appliance-components.sh --component airplay-hooks' \
                'bash scripts/install-airplay-hooks.sh'
            ;;
        airplay-metadata)
            printf '%s\t%s\t%s\t%s\t%s\n' \
                airplay-metadata adapter-check \
                scripts/install-airplay-metadata-listener.sh \
                'bash scripts/check-appliance-components.sh --component airplay-metadata' \
                'bash scripts/install-airplay-metadata-listener.sh'
            ;;
        alarm-audio-helper)
            printf '%s\t%s\t%s\t%s\t%s\n' \
                alarm-audio-helper adapter-check \
                scripts/install-appliance-helpers.sh \
                'bash scripts/check-appliance-components.sh --component alarm-audio-helper' \
                'bash scripts/install-appliance-helpers.sh --activate --confirm INSTALL-APPLIANCE-HELPERS'
            ;;
        shairport-name-helper)
            printf '%s\t%s\t%s\t%s\t%s\n' \
                shairport-name-helper adapter-check \
                scripts/install-appliance-helpers.sh \
                'bash scripts/check-appliance-components.sh --component shairport-name-helper' \
                'bash scripts/install-appliance-helpers.sh --activate --confirm INSTALL-APPLIANCE-HELPERS'
            ;;
        *)
            printf '[A Clockwork Plex] ERROR: Unknown component: %s\n' "$1" >&2
            return 64
            ;;
    esac
}

acp_component_source_files() {
    local id kind source check apply
    for id in "${ACP_COMPONENT_IDS[@]}"; do
        IFS=$'\t' read -r id kind source check apply < <(acp_component_record "$id") || return 1
        printf '%s\n' "$ACP_REPO_ROOT/$source"
    done

    cat <<EOF
$ACP_REPO_ROOT/scripts/airplay-metadata-listener.py
$ACP_REPO_ROOT/scripts/a-clockwork-plex-alarm-audio-helper.sh
$ACP_REPO_ROOT/scripts/a-clockwork-plex-shairport-name.py
$ACP_REPO_ROOT/scripts/launch-dashboard-kiosk.sh
EOF
}

acp_verify_component_sources() {
    local source failures=0
    while IFS= read -r source; do
        [[ -f "$source" && ! -L "$source" ]] || {
            printf '[A Clockwork Plex] ERROR: Required appliance component source is unavailable: %s\n' "$source" >&2
            failures=$((failures + 1))
            continue
        }
        case "$source" in
            *.sh)
                if ! bash -n "$source"; then
                    printf '[A Clockwork Plex] ERROR: Shell syntax check failed: %s\n' "$source" >&2
                    failures=$((failures + 1))
                fi
                ;;
        esac
    done < <(acp_component_source_files)
    [[ "$failures" -eq 0 ]]
}

acp_component_plan() {
    local project_user="${1:-${ACP_PROJECT_USER:-${SUDO_USER:-${USER:-andy}}}}"
    local id kind source check apply
    echo 'Specialist component ownership:'
    for id in "${ACP_COMPONENT_IDS[@]}"; do
        IFS=$'\t' read -r id kind source check apply < <(acp_component_record "$id") || return 1
        if [[ "$id" == dashboard-service ]]; then
            check="$check --project-user $project_user"
        fi
        printf '  %-22s %-13s %s\n' "$id" "$kind" "$check"
    done
    cat <<'EOF'

  native-check  = the specialist installer already owns a safe read-only check mode.
  adapter-check = installed state is inspected through the shared read-only adapter.

Apply commands remain specialist-owned. Alarm-audio and Shairport-name helper
runtime implementations remain specialist sources, while their fresh-appliance
packaging/sudo policy is jointly owned by the guarded
scripts/install-appliance-helpers.sh entrypoint. AirPlay hooks and metadata
remain legacy apply-only and are not executed by the root installer yet.
EOF
}
