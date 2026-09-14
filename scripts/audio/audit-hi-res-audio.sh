#!/bin/bash

# Read-only baseline audit for the already-installed A Clockwork Plex managed
# audio stack. Unlike preflight-eq.sh, this script expects the EQ/split-bus
# profile to be installed and active. It does not open a PCM, change a route,
# write a mixer control, restart a service, load a module or alter configuration.

set -o pipefail
shopt -s nullglob

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DEFAULTS=/etc/default/a-clockwork-plex-split-bus
ACTIVE_ROUTE=/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf
CAMILLADSP_CONFIG=/etc/a-clockwork-plex/camilladsp-split-bus.yml
ROUTE_HELPER=/usr/local/bin/a-clockwork-plex-audio-route
EQ_HELPER=/usr/local/bin/a-clockwork-plex-audio-eq

usage() {
    cat <<'EOF_USAGE'
Usage: bash scripts/audio/audit-hi-res-audio.sh

Prints a read-only baseline of the currently installed managed audio path for
high-resolution/EQ development. It reads repository state, ALSA descriptors,
current hw_params, installed profile/configuration and existing helper status.

It deliberately does NOT:
  - open or play to a PCM;
  - stop/start/restart/enable/disable a service;
  - select or rewrite an ALSA route;
  - change mixer/EQ state;
  - load/unload a kernel module;
  - write appliance configuration.
EOF_USAGE
}

section() {
    printf '\n===== %s =====\n' "$1"
}

show_file() {
    local path="$1"
    if [[ -r "$path" ]]; then
        printf -- '--- %s ---\n' "$path"
        cat "$path"
    else
        printf '%s\n' "unavailable: $path"
    fi
}

show_hw_params_tree() {
    local root="$1" path
    if [[ ! -d "$root" ]]; then
        printf '%s\n' "unavailable: $root"
        return 0
    fi
    local paths=("$root"/pcm*/sub*/hw_params)
    if [[ ${#paths[@]} -eq 0 ]]; then
        printf '%s\n' "no hw_params entries beneath $root"
        return 0
    fi
    for path in "${paths[@]}"; do
        show_file "$path"
    done
}

show_service() {
    local unit="$1" active enabled
    active="$(systemctl is-active "$unit" 2>/dev/null || true)"
    enabled="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
    printf '%-42s active=%-12s enabled=%s\n' "$unit" "${active:-unknown}" "${enabled:-unknown}"
}

read_default() {
    local key="$1"
    [[ -r "$DEFAULTS" ]] || return 0
    awk -F= -v key="$key" '$1 == key { print substr($0, index($0, "=") + 1); exit }' "$DEFAULTS"
}

main() {
    if [[ $# -gt 0 ]]; then
        case "$1" in
            -h|--help)
                usage
                return 0
                ;;
            *)
                printf 'Unknown option: %s\n' "$1" >&2
                usage >&2
                return 64
                ;;
        esac
    fi

    local dac_card loopback_index dac_proc loopback_proc
    dac_card="$(read_default DAC_CARD)"
    loopback_index="$(read_default LOOPBACK_INDEX)"
    dac_card="${dac_card:-Pro}"
    loopback_index="${loopback_index:-7}"
    dac_proc="/proc/asound/$dac_card"
    loopback_proc="/proc/asound/card$loopback_index"

    section 'audit identity'
    printf 'timestamp=%s\n' "$(date --iso-8601=seconds 2>/dev/null || date)"
    printf 'user=%s\n' "$(id -un)"
    printf 'architecture=%s\n' "$(uname -m)"
    printf 'kernel=%s\n' "$(uname -r)"
    if [[ -r /proc/device-tree/model ]]; then
        printf 'hardware=' && tr -d '\0' </proc/device-tree/model && printf '\n'
    fi
    printf 'repo_branch=%s\n' "$(git -C "$REPO_ROOT" branch --show-current 2>/dev/null || true)"
    printf 'repo_head=%s\n' "$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || true)"

    section 'managed audio verification'
    if [[ -f "$REPO_ROOT/scripts/audio/verify-audio.sh" ]]; then
        if bash "$REPO_ROOT/scripts/audio/verify-audio.sh"; then
            printf 'verify_audio=PASS\n'
        else
            printf 'verify_audio=FAIL\n'
        fi
    else
        printf 'verify_audio=unavailable\n'
    fi

    section 'ALSA cards and hardware PCMs'
    show_file /proc/asound/cards
    if command -v aplay >/dev/null 2>&1; then
        printf -- '--- aplay -l ---\n'
        aplay -l 2>&1 || true
        printf -- '--- ACP-related aplay -L names ---\n'
        aplay -L 2>/dev/null | grep -E '^(acp_|hw:|plughw:)' || true
    else
        printf 'aplay unavailable\n'
    fi

    section 'DAC descriptor availability'
    show_file "$dac_proc/id"
    show_file "$dac_proc/pcm0p/info"
    if [[ -r "$dac_proc/stream0" ]]; then
        show_file "$dac_proc/stream0"
    else
        printf 'stream0 capability descriptor not exposed at %s/stream0 (normal for an I2S/non-USB DAC).\n' "$dac_proc"
        printf 'Exact hardware format/rate support therefore requires a separate guarded idle-DAC capability probe.\n'
    fi

    section 'live DAC hw_params'
    show_hw_params_tree "$dac_proc"

    section 'live ACP loopback hw_params'
    printf 'loopback_proc=%s\n' "$loopback_proc"
    show_hw_params_tree "$loopback_proc"

    section 'installed split-bus profile'
    if [[ -r "$DEFAULTS" ]]; then
        grep -E '^(AUDIO_PROFILE|DAC_CARD|DAC_DEVICE|LOOPBACK_INDEX|LOOPBACK_ID|SAMPLE_RATE|FORMAT|PERIOD_SIZE|BUFFER_SIZE|CHUNKSIZE|TARGET_LEVEL|CAMILLADSP_VERSION)=' "$DEFAULTS" || true
    else
        printf 'unavailable: %s\n' "$DEFAULTS"
    fi

    section 'active ALSA route format/rate clues'
    if [[ -e "$ACTIVE_ROUTE" || -L "$ACTIVE_ROUTE" ]]; then
        printf 'path=%s\n' "$ACTIVE_ROUTE"
        printf 'resolved=%s\n' "$(readlink -f "$ACTIVE_ROUTE" 2>/dev/null || true)"
        if command -v sha256sum >/dev/null 2>&1; then
            sha256sum "$ACTIVE_ROUTE" 2>/dev/null || true
        fi
        grep -nEi '(^|[[:space:]])(type|pcm|slave|card|device|rate|format|channels)[[:space:]]' "$ACTIVE_ROUTE" 2>/dev/null || true
    else
        printf 'unavailable: %s\n' "$ACTIVE_ROUTE"
    fi

    section 'CamillaDSP format/rate clues'
    if [[ -r "$CAMILLADSP_CONFIG" ]]; then
        grep -nEi '^[[:space:]]*(samplerate|chunksize|queuelimit|target_level|enable_rate_adjust|resampler|channels|device|format):' "$CAMILLADSP_CONFIG" || true
    else
        printf 'unavailable: %s\n' "$CAMILLADSP_CONFIG"
    fi

    section 'managed route status'
    if [[ -x "$ROUTE_HELPER" ]]; then
        "$ROUTE_HELPER" status 2>&1 || true
    else
        printf 'unavailable: %s\n' "$ROUTE_HELPER"
    fi

    section 'managed EQ status'
    if [[ -x "$EQ_HELPER" ]]; then
        "$EQ_HELPER" status 2>&1 || true
    else
        printf 'unavailable: %s\n' "$EQ_HELPER"
    fi

    section 'service state'
    if command -v systemctl >/dev/null 2>&1; then
        show_service plexamp.service
        show_service shairport-sync.service
        show_service a-clockwork-plex.service
        show_service a-clockwork-plex-audio-route.service
        show_service a-clockwork-plex-camilladsp.service
        show_service a-clockwork-plex-audio-failback.service
    else
        printf 'systemctl unavailable\n'
    fi

    section 'CamillaDSP process snapshot'
    if command -v ps >/dev/null 2>&1; then
        ps -C camilladsp -o pid=,pcpu=,pmem=,etimes=,args= 2>/dev/null || true
    fi

    section 'audit result'
    printf '%s\n' 'READ_ONLY_AUDIT_COMPLETE'
}

main "$@"
