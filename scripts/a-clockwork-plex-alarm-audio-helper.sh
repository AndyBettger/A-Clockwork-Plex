#!/bin/bash
set -euo pipefail

PLEXAMP_SERVICE="plexamp.service"
SHAIRPORT_SERVICE="shairport-sync.service"
PLEXAMP_PAUSE_URL="http://localhost:32500/player/playback/pause"

is_active() {
    /usr/bin/systemctl is-active --quiet "$1"
}

json_bool() {
    if "$@"; then
        printf 'true'
    else
        printf 'false'
    fi
}

status_json() {
    printf '{"plexamp_active":%s,"shairport_active":%s}\n' \
        "$(json_bool is_active "$PLEXAMP_SERVICE")" \
        "$(json_bool is_active "$SHAIRPORT_SERVICE")"
}

case "${1:-status}" in
    status)
        status_json
        ;;
    release)
        # Stop Shairport first. Its normal end hook may restart Plexamp, so Plexamp
        # is paused and stopped afterwards to leave the DAC genuinely available.
        /usr/bin/systemctl stop "$SHAIRPORT_SERVICE" >/dev/null 2>&1 || true
        /usr/bin/curl -fsS --max-time 2 "$PLEXAMP_PAUSE_URL" >/dev/null 2>&1 || true
        /usr/bin/systemctl stop "$PLEXAMP_SERVICE" >/dev/null 2>&1 || true
        printf '{"released":true}\n'
        ;;
    restore)
        plexamp="${2:-0}"
        shairport="${3:-0}"
        [[ "$plexamp" == "0" || "$plexamp" == "1" ]] || exit 64
        [[ "$shairport" == "0" || "$shairport" == "1" ]] || exit 64
        if [[ "$plexamp" == "1" ]]; then
            /usr/bin/systemctl start "$PLEXAMP_SERVICE"
        fi
        if [[ "$shairport" == "1" ]]; then
            /usr/bin/systemctl start "$SHAIRPORT_SERVICE"
        fi
        printf '{"restored":true,"plexamp":%s,"shairport":%s}\n' "$plexamp" "$shairport"
        ;;
    *)
        echo "Usage: $0 {status|release|restore <plexamp 0|1> <shairport 0|1>}" >&2
        exit 64
        ;;
esac
