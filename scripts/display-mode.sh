#!/bin/bash
set -euo pipefail

MODE="${1:-clock}"
DASHBOARD_BASE="${DASHBOARD_BASE:-http://localhost:8088}"
PLEXAMP_URL="${PLEXAMP_URL:-http://localhost:32500}"
DISPLAY_VALUE="${DISPLAY:-:0}"
XAUTHORITY_VALUE="${XAUTHORITY:-/home/andy/.Xauthority}"

case "$MODE" in
  clock)
    URL="$DASHBOARD_BASE/clock"
    ;;
  weather)
    URL="$DASHBOARD_BASE/weather"
    ;;
  airplay)
    URL="$DASHBOARD_BASE/airplay"
    ;;
  settings)
    URL="$DASHBOARD_BASE/settings"
    ;;
  plexamp)
    URL="$DASHBOARD_BASE/plexamp"
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    exit 1
    ;;
esac

/usr/bin/logger -t a-clockwork-plex "Switching display to $MODE: $URL"
/usr/bin/curl -fsS "$DASHBOARD_BASE/api/mode/$MODE" >/dev/null || true

if command -v xdotool >/dev/null 2>&1; then
  export DISPLAY="$DISPLAY_VALUE"
  export XAUTHORITY="$XAUTHORITY_VALUE"
  xdotool key Ctrl+l
  xdotool type --delay 0 "$URL"
  xdotool key Return
else
  echo "xdotool is not installed; mode state was updated but browser was not navigated." >&2
fi
