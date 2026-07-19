#!/bin/bash
set -euo pipefail

DASHBOARD_BASE="${DASHBOARD_BASE:-http://localhost:8088}"
PLEXAMP_URL="${PLEXAMP_URL:-http://localhost:32500}"
START_WRAPPER="${START_WRAPPER:-/usr/local/bin/a-clockwork-plex-airplay-start}"
END_WRAPPER="${END_WRAPPER:-/usr/local/bin/a-clockwork-plex-airplay-end}"
LEGACY_SUDOERS_FILE="${LEGACY_SUDOERS_FILE:-/etc/sudoers.d/a-clockwork-plex-airplay}"

validate_url_value() {
    local name="$1"
    local value="$2"
    if [[ "$value" =~ [[:space:]\"\'\`\\] ]]; then
        echo "Invalid $name: $value" >&2
        echo "$name must not contain spaces, quotes, backticks or backslashes." >&2
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
require_command sudo
require_command tee

# Shared ALSA mixing means AirPlay no longer stops or starts Plexamp. The start
# hook pauses playback and changes the dashboard mode; both audio services stay
# alive so handoff is immediate and neither has to rediscover the DAC.
cat <<START_WRAPPER_EOF | sudo tee "$START_WRAPPER" >/dev/null
#!/bin/bash
set -euo pipefail

DASHBOARD_BASE="$DASHBOARD_BASE"
PLEXAMP_URL="$PLEXAMP_URL"

/usr/bin/logger -t shairport-plexamp "AirPlay starting - switching display to AirPlay"
/usr/bin/curl -fsS "\$DASHBOARD_BASE/api/airplay/start" >/dev/null || true

/usr/bin/logger -t shairport-plexamp "AirPlay starting - pausing Plexamp without stopping its service"
/usr/bin/curl -sS --max-time 2 "\$PLEXAMP_URL/player/playback/pause" >/dev/null 2>&1 || true

/usr/bin/logger -t shairport-plexamp "Shared ALSA mixer active - Plexamp remains available"
START_WRAPPER_EOF

cat <<END_WRAPPER_EOF | sudo tee "$END_WRAPPER" >/dev/null
#!/bin/bash
set -euo pipefail

DASHBOARD_BASE="$DASHBOARD_BASE"
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

arm_dashboard_pause_watchdog() {
    (
        /usr/bin/logger -t shairport-plexamp "AirPlay dashboard pause watchdog armed for \${WATCHDOG_SECONDS}s"
        local elapsed=0
        local unavailable_logged=0
        while [ "\$elapsed" -lt "\$WATCHDOG_SECONDS" ]; do
            sleep "\$WATCHDOG_INTERVAL_SECONDS"
            elapsed=\$((elapsed + WATCHDOG_INTERVAL_SECONDS))

            local mode
            mode="\$(dashboard_mode)"
            if [ "\$mode" != "airplay" ]; then
                /usr/bin/logger -t shairport-plexamp "AirPlay pause watchdog exiting because dashboard mode is \$mode"
                exit 0
            fi

            local player_state
            player_state="\$(remote_player_state)"
            if [ "\$player_state" = 's "Playing"' ]; then
                /usr/bin/logger -t shairport-plexamp "AirPlay pause watchdog exiting because playback resumed"
                exit 0
            fi

            local available
            available="\$(remote_available_status)"
            if [ "\$available" = "b false" ] && [ "\$unavailable_logged" -eq 0 ]; then
                /usr/bin/logger -t shairport-plexamp "AirPlay remote unavailable after \${elapsed}s; retaining pause screen until timeout"
                unavailable_logged=1
            fi
        done

        /usr/bin/logger -t shairport-plexamp "AirPlay pause watchdog timed out after \${WATCHDOG_SECONDS}s"
        return_to_clock "AirPlay dashboard pause watchdog timeout"
    ) >/dev/null 2>&1 &
}

STATUS_FILE="\$(/usr/bin/mktemp /tmp/a-clockwork-airplay-status.XXXXXX)"
trap '/usr/bin/rm -f "\$STATUS_FILE"' EXIT

CURL_OUTPUT="\$(/usr/bin/curl -sS -m 4 -o "\$STATUS_FILE" -w '%{http_code}' "\$DASHBOARD_BASE/api/status" 2>&1 || true)"
HTTP_CODE="\$(printf '%s' "\$CURL_OUTPUT" | /usr/bin/tail -c 3)"

if [ "\$HTTP_CODE" != "200" ]; then
    HOLD_STATUS="curl=\$CURL_OUTPUT"
    HOLD_EXIT=1
else
    set +e
    HOLD_STATUS="\$(/usr/bin/python3 - "\$STATUS_FILE" <<'PY'
import json
import sys
from datetime import datetime

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
except Exception as exc:
    print(f"invalid-status-json:{exc}")
    sys.exit(1)

state = payload.get("state") or {}
metadata = ((state.get("airplay") or {}).get("metadata") or {})
last_change = str(state.get("last_mode_change") or "").strip()
mode = str(state.get("mode") or "").strip()
last_event = str(metadata.get("last_event") or "").strip()

if mode != "airplay" or not last_change:
    print(f"mode={mode or '-'} last_change={last_change or '-'} last_event={last_event or '-'} age=-")
    sys.exit(1)

try:
    parsed = datetime.fromisoformat(last_change.replace("Z", "+00:00"))
except ValueError:
    print(f"mode={mode} last_change=invalid last_event={last_event or '-'} age=-")
    sys.exit(1)

now = datetime.now(parsed.tzinfo) if parsed.tzinfo else datetime.now()
age = (now - parsed).total_seconds()
print(f"mode={mode} last_change={last_change} last_event={last_event or '-'} age={age:.1f}")
sys.exit(0 if 0 <= age <= 20 else 1)
PY
)"
    HOLD_EXIT=\$?
    set -e
fi

REMOTE_AVAILABLE="\$(remote_available_status)"
if [ "\$HOLD_EXIT" -eq 0 ] && [ "\$REMOTE_AVAILABLE" != "b false" ]; then
    /usr/bin/logger -t shairport-plexamp "AirPlay ended after dashboard pause - retaining AirPlay screen (\$HOLD_STATUS remote_available=\$REMOTE_AVAILABLE)"
    arm_dashboard_pause_watchdog
    exit 0
fi

/usr/bin/logger -t shairport-plexamp "AirPlay ended - shared mixer requires no Plexamp service restart (\$HOLD_STATUS remote_available=\$REMOTE_AVAILABLE)"
return_to_clock "AirPlay ended"
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
