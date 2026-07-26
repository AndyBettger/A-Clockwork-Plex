#!/bin/bash
set -euo pipefail

DASHBOARD_BASE="${DASHBOARD_BASE:-http://localhost:8088}"
PLEXAMP_URL="${PLEXAMP_URL:-http://localhost:32500}"
START_WRAPPER="${START_WRAPPER:-/usr/local/bin/a-clockwork-plex-airplay-start}"
END_WRAPPER="${END_WRAPPER:-/usr/local/bin/a-clockwork-plex-airplay-end}"
SESSION_END_WRAPPER="${SESSION_END_WRAPPER:-/usr/local/bin/a-clockwork-plex-airplay-session-end}"
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

# START remains a thin adapter: pause Plexamp first, publish the established
# AirPlay session, and let the route wrapper journal airplay.playing.
cat <<START_WRAPPER_EOF | sudo tee "$START_WRAPPER" >/dev/null
#!/bin/bash
set -euo pipefail

DASHBOARD_BASE="$DASHBOARD_BASE"
PLEXAMP_URL="$PLEXAMP_URL"

/usr/bin/logger -t shairport-plexamp "AirPlay starting - pausing Plexamp before publishing the new session"
/usr/bin/curl -sS --max-time 2 "\$PLEXAMP_URL/player/playback/pause" >/dev/null 2>&1 || true

/usr/bin/logger -t shairport-plexamp "AirPlay starting - switching display to AirPlay and cancelling any coordinator hold"
/usr/bin/curl -fsS "\$DASHBOARD_BASE/api/airplay/start" >/dev/null || true

/usr/bin/logger -t shairport-plexamp "Shared ALSA mixer active - Plexamp remains available"
START_WRAPPER_EOF

# END classifies the active-to-inactive transition and publishes a pause event.
# A separate session-end adapter below handles disconnects that happen later.
cat <<END_WRAPPER_EOF | sudo tee "$END_WRAPPER" >/dev/null
#!/bin/bash
set -euo pipefail

DASHBOARD_BASE="$DASHBOARD_BASE"

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

post_pause_event() {
    /usr/bin/curl -fsS -X POST \
        -H 'Content-Type: application/json' \
        --data '{"source":"airplay","event":"paused","details":{"origin":"shairport-end-wrapper"}}' \
        "\$DASHBOARD_BASE/api/playback/events" >/dev/null
}

PLAYER_STATE="\$(remote_player_state)"
REMOTE_AVAILABLE="\$(remote_available_status)"

# A stale END may arrive just after START on resume. The newer START route has
# already journalled airplay.playing, so this older END must not overwrite it.
if [ "\$PLAYER_STATE" = 's "Playing"' ]; then
    /usr/bin/logger -t shairport-plexamp "AirPlay END observed after playback resumed - retaining the newer playing session"
    exit 0
fi

if [ "\$REMOTE_AVAILABLE" = "b false" ]; then
    /usr/bin/logger -t shairport-plexamp "AirPlay sender disconnected during active-state exit - ending the dashboard session"
    /usr/bin/curl -fsS "\$DASHBOARD_BASE/api/airplay/end" >/dev/null || true
    exit 0
fi

/usr/bin/curl -fsS -X POST "\$DASHBOARD_BASE/api/mode/airplay" >/dev/null || true
if post_pause_event; then
    /usr/bin/logger -t shairport-plexamp "AirPlay paused with sender available - PlaybackCoordinator owns the configured hold"
else
    /usr/bin/logger -t shairport-plexamp "AirPlay pause event could not reach PlaybackCoordinator; AirPlay screen retained for inspection"
fi
END_WRAPPER_EOF

# Shairport calls run_this_after_play_ends when the sender session itself ends.
# This is distinct from leaving the active state, so it catches a sender that is
# disconnected after it has already been paused. A currently playing coordinator
# state is treated as a stale callback from an older session and ignored.
cat <<SESSION_END_WRAPPER_EOF | sudo tee "$SESSION_END_WRAPPER" >/dev/null
#!/bin/bash
set -euo pipefail

DASHBOARD_BASE="$DASHBOARD_BASE"

coordinator_airplay_state() {
    /usr/bin/curl -fsS --max-time 3 "\$DASHBOARD_BASE/api/playback/state" 2>/dev/null | \
        /usr/bin/python3 -c '
import json
import sys
try:
    payload = json.load(sys.stdin)
except Exception:
    print("unknown")
    raise SystemExit(1)
source = (((payload.get("playback") or {}).get("sources") or {}).get("airplay") or {})
print(str(source.get("state") or "unknown").lower())
' 2>/dev/null || printf 'unknown'
}

AIRPLAY_STATE="\$(coordinator_airplay_state)"
if [ "\$AIRPLAY_STATE" = "playing" ]; then
    /usr/bin/logger -t shairport-plexamp "AirPlay session-end callback is stale because a newer session is playing - ignored"
    exit 0
fi

if [ "\$AIRPLAY_STATE" = "unknown" ]; then
    /usr/bin/logger -t shairport-plexamp "AirPlay session ended but coordinator state was unavailable - leaving state unchanged for inspection"
    exit 0
fi

/usr/bin/logger -t shairport-plexamp "AirPlay sender session ended - publishing disconnect to PlaybackCoordinator"
/usr/bin/curl -fsS "\$DASHBOARD_BASE/api/airplay/end" >/dev/null || true
SESSION_END_WRAPPER_EOF

sudo chmod 755 "$START_WRAPPER" "$END_WRAPPER" "$SESSION_END_WRAPPER"

# Shared mixing means the hooks never need permission to stop/start Plexamp.
if [[ -e "$LEGACY_SUDOERS_FILE" ]]; then
    sudo rm -f "$LEGACY_SUDOERS_FILE"
fi

echo "Installed coordinator-event AirPlay hook wrappers:"
echo "  $START_WRAPPER"
echo "  $END_WRAPPER"
echo "  $SESSION_END_WRAPPER"
echo
echo "Plexamp is paused for AirPlay but its service remains running."
echo "PlaybackCoordinator owns paused-session timing and idle return."
echo "The session-end adapter detects disconnects that occur after AirPlay is already paused."
echo "The wrappers contain no detached watchdog, token file or browser heartbeat."
echo
echo "Use this in /etc/shairport-sync.conf:"
echo "sessioncontrol ="
echo "{"
echo "    run_this_before_entering_active_state = \"$START_WRAPPER\";"
echo "    run_this_after_exiting_active_state = \"$END_WRAPPER\";"
echo "    run_this_after_play_ends = \"$SESSION_END_WRAPPER\";"
echo "    active_state_timeout = 10;"
echo "    session_timeout = 15;"
echo "    wait_for_completion = \"yes\";"
echo "};"
echo
echo "Then run:"
echo "  sudo systemctl restart shairport-sync.service"
echo "  sudo systemctl status shairport-sync.service --no-pager"
