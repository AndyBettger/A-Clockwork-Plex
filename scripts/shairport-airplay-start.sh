#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

/usr/bin/logger -t shairport-plexamp "AirPlay starting - switching display to AirPlay"
/bin/bash "$SCRIPT_DIR/display-mode.sh" airplay || true

/usr/bin/logger -t shairport-plexamp "AirPlay starting - pausing Plexamp playback"
/usr/bin/curl -s "http://localhost:32500/player/playback/pause" >/dev/null 2>&1 || true

sleep 1

/usr/bin/logger -t shairport-plexamp "AirPlay starting - stopping Plexamp service"
/usr/bin/sudo /usr/bin/systemctl stop plexamp.service

sleep 2

/usr/bin/logger -t shairport-plexamp "Plexamp service stopped - DAC should be free"
