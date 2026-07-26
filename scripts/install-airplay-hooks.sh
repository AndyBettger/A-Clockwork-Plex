#!/bin/bash
set -euo pipefail

DASHBOARD_BASE="${DASHBOARD_BASE:-http://localhost:8088}"
PLEXAMP_URL="${PLEXAMP_URL:-http://localhost:32500}"
START_WRAPPER="${START_WRAPPER:-/usr/local/bin/a-clockwork-plex-airplay-start}"
END_WRAPPER="${END_WRAPPER:-/usr/local/bin/a-clockwork-plex-airplay-end}"
LEGACY_SUDOERS_FILE="${LEGACY_SUDOERS_FILE:-/etc/sudoers.d/a-clockwork-plex-airplay}"
HOLD_TOKEN_FILE="${AIRPLAY_HOLD_TOKEN_FILE:-/tmp/a-clockwork-plex-airplay-hold.token}"

validate_url_value() {
    local name="$1"
    local value="$2"
    if [[ "$value" =~ [[:space:]\"\'\`\\] ]]; then
        echo "Invalid $name: $value" >&2
        echo "$name must not contain spaces, quotes, backticks or backslashes." >&2
        exit 1
    fi
}

validate_path_value() {
    local name="$1"
    local value="$2"
    if [[ ! "$value" =~ ^/[A-Za-z0-9_./@-]+$ ]]; then
        echo "Invalid $name: $value" >&2
        exit 1
    fi
}

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Required command not found: $1" >&2
        exit 1
    fi
}

validate_url_value "DASHBOARD_BASE" "$DASHBOARD_BASE"
validate_url_value "PLEXAMP_URL" "$PLEXAMP_URL"
validate_path_value "HOLD_TOKEN_FILE" "$HOLD_TOKEN_FILE"
require_command sudo
require_command tee

# Shared ALSA mixing means AirPlay never stops or starts Plexamp. START cancels
# any older pause-hold generation, selects the AirPlay surface and pauses Plexamp.
cat <<START_WRAPPER_EOF | sudo tee "$START_WRAPPER" >/dev/null
#!/bin/bash
set -euo pipefail

DASHBOARD_BASE="$DASHBOARD_BASE"
PLEXAMP_URL="$PLEXAMP_URL"
HOLD_TOKEN_FILE="$HOLD_TOKEN_FILE"

/usr/bin/rm -f "\$HOLD_TOKEN_FILE" 2>/dev/null || true
/usr/bin/logger -t shairport-plexamp "AirPlay starting - switching display to AirPlay"
/usr/bin/curl -fsS "\$DASHBOARD_BASE/api/airplay/start" >/dev/null || true

/usr/bin/logger -t shairport-plexamp "AirPlay starting - pausing Plexamp without stopping its service"
/usr/bin/curl -sS --max-time 2 "\$PLEXAMP_URL/player/playback/pause" >/dev/null 2>&1 || true

/usr/bin/logger -t shairport-plexamp "Shared ALSA mixer active - Plexamp remains available"
START_WRAPPER_EOF

# END distinguishes a disconnected sender from a paused sender. Paused sessions
# retain the AirPlay surface for ten minutes without any browser heartbeat. A
# generation token prevents an old watchdog from ending a newer resumed session.
cat <<END_WRAPPER_EOF | sudo tee "$END_WRAPPER" >/dev/null
#!/bin/bash
set -euo pipefail

DASHBOARD_BASE="$DASHBOARD_BASE"
HOLD_TOKEN_FILE="$HOLD_TOKEN_FILE"
WATCHDOG_SECONDS="\${AIRPLAY_DASHBOARD_PAUSE_WATCHDOG_SECONDS:-600}"
WATCHDOG_INTERVAL_SECONDS="\${AIRPLAY_DASHBOARD_PAUSE_WATCHDOG_INTERVAL_SECONDS:-5}"

remote_available_status() {
    if command -v /usr/bin/busctl >/dev/null 2>&1; then
        /usr/bin/busctl --system get-property \
            org.gnome.ShairportSync \
            /org/gnome/ShairportSync \
            org.gnome.ShairportSync.RemoteControl \
            Available 2>/dev/null || printf 'unknown'
    else
        printf 'unknown'
    fi
}

remote_player_state() {
    if command -v /usr/bin/busctl >/dev/null 2>&1; then
        /usr/bin/busctl --system get-property \
            org.gnome.ShairportSync \
            /org/gnome/ShairportSync \
            org.gnome.ShairportSync.RemoteControl \
            PlayerState 2>/dev/null || printf 'unknown'
    else
        printf 'unknown'
    fi
}

dashboard_mode() {
    /usr/bin/curl -fsS -m 4 "\$DASHBOARD_BASE/api/status" 2>/dev/null | /usr/bin/python3 -c '
import json
import sys
try:
    payload = json.load(sys.stdin)
except Exception:
    print("unknown")
    raise SystemExit(1)
print(str((payload.get("state") or {}).get("mode") or "unknown"))
' 2>/dev/null || printf 'unknown'
}

return_to_clock() {
    local reason="\$1"
    /usr/bin/logger -t shairport-plexamp "\$reason - returning dashboard to Clock; Plexamp service was never stopped"
    /usr/bin/curl -fsS "\$DASHBOARD_BASE/api/airplay/end" >/dev/null || true
}

new_hold_token() {
    local temporary token
    temporary="\$(/usr/bin/mktemp /tmp/a-clockwork-plex-airplay-hold.XXXXXX)"
    token="\$(/usr/bin/date +%s%N)-\$\$"
    /usr/bin/printf '%s\n' "\$token" >"\$temporary"
    /usr/bin/chmod 0600 "\$temporary"
    /usr/bin/mv -f "\$temporary" "\$HOLD_TOKEN_FILE"
    /usr/bin/printf '%s' "\$token"
}

hold_token_is_current() {
    local expected="\$1"
    [ -r "\$HOLD_TOKEN_FILE" ] && [ "\$(/usr/bin/cat "\$HOLD_TOKEN_FILE" 2>/dev/null || true)" = "\$expected" ]
}

clear_hold_token() {
    local expected="\$1"
    if hold_token_is_current "\$expected"; then
        /usr/bin/rm -f "\$HOLD_TOKEN_FILE" 2>/dev/null || true
    fi
}

arm_dashboard_pause_watchdog() {
    local token="\$1"
    (
        /usr/bin/logger -t shairport-plexamp "AirPlay dashboard pause hold armed for \${WATCHDOG_SECONDS}s"
        local elapsed=0
        while [ "\$elapsed" -lt "\$WATCHDOG_SECONDS" ]; do
            sleep "\$WATCHDOG_INTERVAL_SECONDS"
            elapsed=\$((elapsed + WATCHDOG_INTERVAL_SECONDS))

            if ! hold_token_is_current "\$token"; then
                /usr/bin/logger -t shairport-plexamp "AirPlay pause hold superseded by a newer session"
                exit 0
            fi

            local mode
            mode="\$(dashboard_mode)"
            if [ "\$mode" != "airplay" ]; then
                clear_hold_token "\$token"
                /usr/bin/logger -t shairport-plexamp "AirPlay pause hold exiting because dashboard mode is \$mode"
                exit 0
            fi

            local player_state
            player_state="\$(remote_player_state)"
            if [ "\$player_state" = 's "Playing"' ]; then
                clear_hold_token "\$token"
                /usr/bin/logger -t shairport-plexamp "AirPlay pause hold exiting because playback resumed"
                exit 0
            fi

            local available
            available="\$(remote_available_status)"
            if [ "\$available" = "b false" ]; then
                clear_hold_token "\$token"
                return_to_clock "AirPlay sender disconnected during pause hold"
                exit 0
            fi
        done

        if hold_token_is_current "\$token"; then
            clear_hold_token "\$token"
            return_to_clock "AirPlay dashboard pause hold timed out after \${WATCHDOG_SECONDS}s"
        fi
    ) >/dev/null 2>&1 &
}

PLAYER_STATE="\$(remote_player_state)"
REMOTE_AVAILABLE="\$(remote_available_status)"

# A stale END can arrive just after a resume. Never let it overwrite the newer
# START state or turn a visibly playing session back into Clock.
if [ "\$PLAYER_STATE" = 's "Playing"' ]; then
    /usr/bin/logger -t shairport-plexamp "AirPlay END observed after playback had already resumed - retaining AirPlay mode"
    exit 0
fi

if [ "\$REMOTE_AVAILABLE" = "b false" ]; then
    /usr/bin/rm -f "\$HOLD_TOKEN_FILE" 2>/dev/null || true
    return_to_clock "AirPlay sender disconnected"
    exit 0
fi

/usr/bin/curl -fsS -X POST "\$DASHBOARD_BASE/api/mode/airplay" >/dev/null || true
TOKEN="\$(new_hold_token)"
/usr/bin/logger -t shairport-plexamp "AirPlay paused/stopped with sender available - retaining AirPlay screen"
arm_dashboard_pause_watchdog "\$TOKEN"
END_WRAPPER_EOF

sudo chmod 755 "$START_WRAPPER" "$END_WRAPPER"

# Remove the obsolete permission to stop/start Plexamp. Shared mixing makes it
# unnecessary and leaving it behind would widen the service hook's privileges.
if [[ -e "$LEGACY_SUDOERS_FILE" ]]; then
    sudo rm -f "$LEGACY_SUDOERS_FILE"
fi

echo "Installed shared-mixer AirPlay hook wrappers:"
echo "  $START_WRAPPER"
echo "  $END_WRAPPER"
echo
echo "Plexamp will now be paused for AirPlay but its service remains running."
echo "Paused AirPlay sessions retain the AirPlay page for ten minutes without browser heartbeats."
echo
echo "Use this in /etc/shairport-sync.conf:"
echo "sessioncontrol ="
echo "{"
echo "    run_this_before_entering_active_state = \"$START_WRAPPER\";"
echo "    run_this_after_exiting_active_state = \"$END_WRAPPER\";"
echo "    active_state_timeout = 10;"
echo "    wait_for_completion = \"yes\";"
echo "};"
echo
echo "Then run:"
echo "  sudo systemctl restart shairport-sync.service"
echo "  sudo systemctl status shairport-sync.service --no-pager"
