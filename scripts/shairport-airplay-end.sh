#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARD_BASE="${DASHBOARD_BASE:-http://localhost:8088}"

STATUS_JSON="$(/usr/bin/curl -fsS "$DASHBOARD_BASE/api/status" 2>/dev/null || true)"
HOLD_STATUS="$(printf '%s' "$STATUS_JSON" | /usr/bin/python3 -c '
import json
import sys
from datetime import datetime

try:
    payload = json.load(sys.stdin)
except Exception as exc:
    print(f"invalid-status-json:{exc}")
    sys.exit(1)

state = payload.get("state") or {}
airplay = state.get("airplay") or {}
metadata = airplay.get("metadata") or {}
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

# The AirPlay page sends rapid heartbeats only after the dashboard pause button is pressed.
# A fresh heartbeat means the user probably wants a loo-break pause, not a full handoff back to Plexamp.
# Keep the window wider than the browser heartbeat interval so a busy Pi does not miss it.
sys.exit(0 if 0 <= age <= 20 else 1)
' 2>/dev/null || true)"

if printf '%s' "$HOLD_STATUS" | /usr/bin/grep -q '^mode=airplay .* age='; then
    AGE="$(printf '%s' "$HOLD_STATUS" | /usr/bin/sed -n 's/.* age=\([0-9.]*\).*/\1/p')"
    if /usr/bin/python3 - "$AGE" <<'PY'
import sys
try:
    age = float(sys.argv[1])
except Exception:
    sys.exit(1)
sys.exit(0 if 0 <= age <= 20 else 1)
PY
    then
        /usr/bin/logger -t shairport-plexamp "AirPlay ended after dashboard pause - staying on AirPlay screen ($HOLD_STATUS)"
        exit 0
    fi
fi

/usr/bin/logger -t shairport-plexamp "AirPlay end hook did not see dashboard pause hold ($HOLD_STATUS)"
/usr/bin/logger -t shairport-plexamp "AirPlay ended - starting Plexamp service"
/usr/bin/sudo /usr/bin/systemctl start plexamp.service
/usr/bin/logger -t shairport-plexamp "Plexamp service start requested"

sleep 5

/usr/bin/logger -t shairport-plexamp "AirPlay ended - switching display to clock"
/usr/bin/curl -fsS "$DASHBOARD_BASE/api/airplay/end" >/dev/null || /bin/bash "$SCRIPT_DIR/display-mode.sh" clock || true
