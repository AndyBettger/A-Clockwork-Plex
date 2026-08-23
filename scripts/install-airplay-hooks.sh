#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARD_BASE="${DASHBOARD_BASE:-http://localhost:8088}"
START_WRAPPER="${START_WRAPPER:-/usr/local/bin/a-clockwork-plex-airplay-start}"
END_WRAPPER="${END_WRAPPER:-/usr/local/bin/a-clockwork-plex-airplay-end}"
LEGACY_SESSION_END_WRAPPER="${LEGACY_SESSION_END_WRAPPER:-/usr/local/bin/a-clockwork-plex-airplay-session-end}"
LEGACY_SUDOERS_FILE="${LEGACY_SUDOERS_FILE:-/etc/sudoers.d/a-clockwork-plex-airplay}"
WRAPPER_RENDERER="$SCRIPT_DIR/a-clockwork-plex-airplay-wrappers.py"

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Required command not found: $1" >&2
        exit 1
    fi
}

require_command python3
require_command sudo
require_command install
[[ -f "$WRAPPER_RENDERER" && ! -L "$WRAPPER_RENDERER" ]] || {
    echo "Could not find AirPlay wrapper renderer: $WRAPPER_RENDERER" >&2
    exit 1
}

CANDIDATE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/a-clockwork-plex-airplay-hooks.XXXXXX")"
cleanup() {
    rm -rf "$CANDIDATE_DIR"
}
trap cleanup EXIT

python3 "$WRAPPER_RENDERER" \
    --output-dir "$CANDIDATE_DIR" \
    --dashboard-base "$DASHBOARD_BASE"

sudo install -D -m 0755 \
    "$CANDIDATE_DIR/a-clockwork-plex-airplay-start" \
    "$START_WRAPPER"
sudo install -D -m 0755 \
    "$CANDIDATE_DIR/a-clockwork-plex-airplay-end" \
    "$END_WRAPPER"

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
