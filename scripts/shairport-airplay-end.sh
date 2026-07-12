#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARD_BASE="${DASHBOARD_BASE:-http://localhost:8088}"

STATUS_JSON="$(/usr/bin/curl -fsS "$DASHBOARD_BASE/api/status" 2>/dev/null || true)"

if printf '%s' "$STATUS_JSON" | /usr/bin/python3 -c '
import json
import sys
from datetime import datetime

try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(1)

state = payload.get("state") or {}
last_change = str(state.get("last_mode_change") or "").strip()

if state.get("mode") != "airplay" or not last_change:
    sys.exit(1)

try:
    parsed = datetime.fromisoformat(last_change.replace("Z", "+00:00"))
except ValueError:
    sys.exit(1)

now = datetime.now(parsed.tzinfo) if parsed.tzinfo else datetime.now()
age = (now - parsed).total_seconds()

# The AirPlay page sends a short heartbeat only after the dashboard pause button is pressed.
# A fresh heartbeat means the user probably wants a loo-break pause, not a full handoff back to Plexamp.
# Keep the window wider than the browser heartbeat interval so a busy Pi does not miss it.
sys.exit(0 if 0 <= age <= 12 else 1)
'; then
    /usr/bin/logger -t shairport-plexamp "AirPlay ended after dashboard pause - staying on AirPlay screen"
    exit 0
fi

/usr/bin/logger -t shairport-plexamp "AirPlay ended - starting Plexamp service"
/usr/bin/sudo /usr/bin/systemctl start plexamp.service
/usr/bin/logger -t shairport-plexamp "Plexamp service start requested"

sleep 5

/usr/bin/logger -t shairport-plexamp "AirPlay ended - switching display to clock"
/usr/bin/curl -fsS "$DASHBOARD_BASE/api/airplay/end" >/dev/null || /bin/bash "$SCRIPT_DIR/display-mode.sh" clock || true
