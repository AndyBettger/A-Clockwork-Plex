#!/bin/bash
set -euo pipefail

PLEXAMP_SERVICE="plexamp.service"
SHAIRPORT_SERVICE="shairport-sync.service"
PLEXAMP_PAUSE_URL="http://localhost:32500/player/playback/pause"
PLEXAMP_HEALTH_URL="http://localhost:32500/"

service_state() {
    /usr/bin/systemctl show --property=ActiveState --value "$1" 2>/dev/null || printf 'unknown'
}

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

plexamp_http_ready() {
    /usr/bin/curl -fsS --max-time 1 "$PLEXAMP_HEALTH_URL" >/dev/null 2>&1
}

wait_inactive() {
    local service="$1"
    local timeout_seconds="$2"
    local deadline=$((SECONDS + timeout_seconds))
    local state

    while (( SECONDS < deadline )); do
        state="$(service_state "$service")"
        case "$state" in
            inactive|failed|unknown)
                return 0
                ;;
        esac
        /usr/bin/sleep 0.2
    done
    return 1
}

wait_active() {
    local service="$1"
    local timeout_seconds="$2"
    local deadline=$((SECONDS + timeout_seconds))

    while (( SECONDS < deadline )); do
        if is_active "$service"; then
            return 0
        fi
        /usr/bin/sleep 0.2
    done
    return 1
}

wait_plexamp_http() {
    local timeout_seconds="$1"
    local deadline=$((SECONDS + timeout_seconds))

    while (( SECONDS < deadline )); do
        if plexamp_http_ready; then
            return 0
        fi
        /usr/bin/sleep 0.25
    done
    return 1
}

# Print true when SIGKILL was needed, false after a graceful stop.
stop_service_bounded() {
    local service="$1"
    local grace_seconds="${2:-3}"
    local force_wait_seconds="${3:-2}"

    case "$(service_state "$service")" in
        inactive|failed|unknown)
            printf 'false'
            return 0
            ;;
    esac

    /usr/bin/systemctl stop --no-block "$service" >/dev/null 2>&1 || true
    if wait_inactive "$service" "$grace_seconds"; then
        printf 'false'
        return 0
    fi

    # Plexamp Headless can remain in stop-sigterm while still owning the PCM
    # device. Kill only this service cgroup, then wait for systemd to finish the
    # stop job before allowing aplay or a subsequent start.
    /usr/bin/systemctl kill --kill-who=all --signal=SIGKILL "$service" >/dev/null 2>&1 || true
    /usr/bin/systemctl stop --no-block "$service" >/dev/null 2>&1 || true
    if wait_inactive "$service" "$force_wait_seconds"; then
        printf 'true'
        return 0
    fi

    printf 'true'
    return 1
}

status_json() {
    printf '{"plexamp_active":%s,"plexamp_http_ready":%s,"shairport_active":%s,"plexamp_state":"%s","shairport_state":"%s"}\n' \
        "$(json_bool is_active "$PLEXAMP_SERVICE")" \
        "$(json_bool plexamp_http_ready)" \
        "$(json_bool is_active "$SHAIRPORT_SERVICE")" \
        "$(service_state "$PLEXAMP_SERVICE")" \
        "$(service_state "$SHAIRPORT_SERVICE")"
}

case "${1:-status}" in
    status)
        status_json
        ;;

    release)
        shairport_forced=false
        plexamp_forced=false

        # Stop Shairport first. Its normal end hook may restart Plexamp, so
        # Plexamp is paused and stopped afterwards.
        if ! shairport_forced="$(stop_service_bounded "$SHAIRPORT_SERVICE" 1 1)"; then
            printf '{"released":false,"error":"shairport-stop-timeout","shairport_forced":%s}\n' "$shairport_forced"
            exit 70
        fi

        /usr/bin/curl -fsS --max-time 2 "$PLEXAMP_PAUSE_URL" >/dev/null 2>&1 || true
        if ! plexamp_forced="$(stop_service_bounded "$PLEXAMP_SERVICE" 3 2)"; then
            printf '{"released":false,"error":"plexamp-stop-timeout","plexamp_forced":%s}\n' "$plexamp_forced"
            exit 70
        fi

        # Give delayed AirPlay end hooks a brief chance to reveal themselves.
        /usr/bin/sleep 0.5
        case "$(service_state "$PLEXAMP_SERVICE")" in
            inactive|failed|unknown)
                ;;
            *)
                if ! second_forced="$(stop_service_bounded "$PLEXAMP_SERVICE" 1 2)"; then
                    printf '{"released":false,"error":"plexamp-restarted-during-release","plexamp_forced":true}\n'
                    exit 70
                fi
                if [[ "$second_forced" == "true" ]]; then
                    plexamp_forced=true
                fi
                ;;
        esac

        /usr/bin/sleep 0.35
        printf '{"released":true,"plexamp_forced":%s,"shairport_forced":%s,"plexamp_state":"%s","shairport_state":"%s"}\n' \
            "$plexamp_forced" \
            "$shairport_forced" \
            "$(service_state "$PLEXAMP_SERVICE")" \
            "$(service_state "$SHAIRPORT_SERVICE")"
        ;;

    restore)
        plexamp="${2:-0}"
        shairport="${3:-0}"
        [[ "$plexamp" == "0" || "$plexamp" == "1" ]] || exit 64
        [[ "$shairport" == "0" || "$shairport" == "1" ]] || exit 64

        plexamp_ready=false
        shairport_ready=false

        if [[ "$plexamp" == "1" ]]; then
            # A previous timed-out stop must never be allowed to block start.
            case "$(service_state "$PLEXAMP_SERVICE")" in
                inactive|failed|unknown)
                    ;;
                active)
                    ;;
                *)
                    stop_service_bounded "$PLEXAMP_SERVICE" 1 2 >/dev/null || true
                    ;;
            esac
            /usr/bin/systemctl reset-failed "$PLEXAMP_SERVICE" >/dev/null 2>&1 || true
            /usr/bin/systemctl start --no-block "$PLEXAMP_SERVICE" >/dev/null 2>&1 || true
            if wait_active "$PLEXAMP_SERVICE" 3 && wait_plexamp_http 6; then
                plexamp_ready=true
            else
                printf '{"restored":false,"error":"plexamp-health-timeout","plexamp_state":"%s","plexamp_http_ready":%s}\n' \
                    "$(service_state "$PLEXAMP_SERVICE")" \
                    "$(json_bool plexamp_http_ready)"
                exit 71
            fi
        fi

        if [[ "$shairport" == "1" ]]; then
            /usr/bin/systemctl reset-failed "$SHAIRPORT_SERVICE" >/dev/null 2>&1 || true
            /usr/bin/systemctl start --no-block "$SHAIRPORT_SERVICE" >/dev/null 2>&1 || true
            if wait_active "$SHAIRPORT_SERVICE" 2; then
                shairport_ready=true
            else
                printf '{"restored":false,"error":"shairport-health-timeout","shairport_state":"%s","plexamp_ready":%s}\n' \
                    "$(service_state "$SHAIRPORT_SERVICE")" \
                    "$plexamp_ready"
                exit 71
            fi
        fi

        printf '{"restored":true,"plexamp":%s,"plexamp_ready":%s,"shairport":%s,"shairport_ready":%s}\n' \
            "$plexamp" "$plexamp_ready" "$shairport" "$shairport_ready"
        ;;

    *)
        echo "Usage: $0 {status|release|restore <plexamp 0|1> <shairport 0|1>}" >&2
        exit 64
        ;;
esac
