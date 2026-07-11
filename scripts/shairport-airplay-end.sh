#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

/usr/bin/logger -t shairport-plexamp "AirPlay ended - starting Plexamp service"
/usr/bin/sudo /usr/bin/systemctl start plexamp.service
/usr/bin/logger -t shairport-plexamp "Plexamp service start requested"

sleep 5

/usr/bin/logger -t shairport-plexamp "AirPlay ended - switching display to clock"
/usr/bin/curl -fsS "${DASHBOARD_BASE:-http://localhost:8088}/api/airplay/end" >/dev/null || /bin/bash "$SCRIPT_DIR/display-mode.sh" clock || true
