#!/bin/bash
set -euo pipefail

DASHBOARD_BASE="${DASHBOARD_BASE:-http://localhost:8088}"
START_WRAPPER="${START_WRAPPER:-/usr/local/bin/a-clockwork-plex-airplay-start}"
END_WRAPPER="${END_WRAPPER:-/usr/local/bin/a-clockwork-plex-airplay-end}"
LEGACY_SESSION_END_WRAPPER="${LEGACY_SESSION_END_WRAPPER:-/usr/local/bin/a-clockwork-plex-airplay-session-end}"
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
require_command sudo
require_command tee

# START is now a pure lifecycle adapter. The dashboard route journals the real
# AirPlay playing transition; PlaybackCoordinator owns any required Plexamp pause.
# The route also preserves an explicitly open Plexamp surface instead of stealing
# the screen at connection time.
cat <<START_WRAPPER_EOF | sudo tee "$START_WRAPPER" >/dev/null
#!/bin/bash
set -euo pipefail

DASHBOARD_BASE="$DASHBOARD_BASE"

/usr/bin/logger -t shairport-plexamp "AirPlay starting - publishing playing intent to PlaybackCoordinator"
/usr/bin/curl -fsS "\$DASHBOARD_BASE/api/airplay/start" >/dev/null || true

/usr/bin/logger -t shairport-plexamp "PlaybackCoordinator owns Plexamp pause; shared ALSA services remain running"
START_WRAPPER_EOF

# END classifies the active-to-inactive transition. A connected sender means
# pause; an already unavailable sender means the session ended at the same time.
# It publishes lifecycle only and never chooses a dashboard screen.
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

if post_pause_event; then
    /usr/bin/logger -t shairport-plexamp "AirPlay paused with sender available - PlaybackCoordinator owns the configured hold"
else
    /usr/bin/logger -t shairport-plexamp "AirPlay pause event could not reach PlaybackCoordinator; the current screen was left untouched"
fi
END_WRAPPER_EOF

sudo chmod 755 "$START_WRAPPER" "$END_WRAPPER"

# Remove the experimental play-end callback. On the bedroom Shairport build it
# fires for an ordinary pause and therefore must never publish a disconnect.
if [[ -e "$LEGACY_SESSION_END_WRAPPER" ]]; then
    sudo rm -f "$LEGACY_SESSION_END_WRAPPER"
fi

# Shared mixing means the hooks never need permission to stop/start Plexamp.
if [[ -e "$LEGACY_SUDOERS_FILE" ]]; then
    sudo rm -f "$LEGACY_SUDOERS_FILE"
fi

echo "Installed coordinator-event AirPlay hook wrappers:"
echo "  $START_WRAPPER"
echo "  $END_WRAPPER"
echo
echo "The wrappers publish lifecycle intent only; they do not call Plexamp or choose a screen."
echo "PlaybackCoordinator owns AirPlay-to-Plexamp pause, paused-session timing, sender polling and idle return."
echo "An explicitly open Plexamp surface is preserved when AirPlay starts or pauses."
echo "The retired play-end wrapper was removed because Shairport fires it for ordinary pauses."
echo "The wrappers contain no detached watchdog, token file or browser heartbeat."
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
echo "Remove any run_this_after_play_ends or session_timeout lines added during the previous rehearsal."
echo
echo "Then run:"
echo "  sudo systemctl restart shairport-sync.service"
echo "  sudo systemctl status shairport-sync.service --no-pager"
