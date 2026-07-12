#!/bin/bash
set -euo pipefail

DASHBOARD_BASE="${DASHBOARD_BASE:-http://localhost:8088}"
PLEXAMP_URL="${PLEXAMP_URL:-http://localhost:32500}"
PLEXAMP_SERVICE="${PLEXAMP_SERVICE:-plexamp.service}"
SHAIRPORT_USER="${SHAIRPORT_USER:-shairport-sync}"
START_WRAPPER="${START_WRAPPER:-/usr/local/bin/a-clockwork-plex-airplay-start}"
END_WRAPPER="${END_WRAPPER:-/usr/local/bin/a-clockwork-plex-airplay-end}"
SUDOERS_FILE="${SUDOERS_FILE:-/etc/sudoers.d/a-clockwork-plex-airplay}"

validate_simple_name() {
  local name="$1"
  local value="$2"

  if [[ ! "$value" =~ ^[A-Za-z0-9_.@-]+$ ]]; then
    echo "Invalid $name: $value" >&2
    echo "$name may only contain letters, numbers, '.', '_', '@' and '-'." >&2
    exit 1
  fi
}

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

validate_simple_name "PLEXAMP_SERVICE" "$PLEXAMP_SERVICE"
validate_simple_name "SHAIRPORT_USER" "$SHAIRPORT_USER"
validate_url_value "DASHBOARD_BASE" "$DASHBOARD_BASE"
validate_url_value "PLEXAMP_URL" "$PLEXAMP_URL"

require_command sudo
require_command tee
require_command install
require_command visudo

# Install self-contained wrappers outside /home so Shairport can execute them
# even when the shairport-sync user cannot traverse /home/andy.
cat <<START_WRAPPER_EOF | sudo tee "$START_WRAPPER" >/dev/null
#!/bin/bash
set -euo pipefail

DASHBOARD_BASE="$DASHBOARD_BASE"
PLEXAMP_URL="$PLEXAMP_URL"
PLEXAMP_SERVICE="$PLEXAMP_SERVICE"

/usr/bin/logger -t shairport-plexamp "AirPlay starting - switching display to AirPlay"
/usr/bin/curl -fsS "\$DASHBOARD_BASE/api/airplay/start" >/dev/null || true

/usr/bin/logger -t shairport-plexamp "AirPlay starting - pausing Plexamp playback"
/usr/bin/curl -s "\$PLEXAMP_URL/player/playback/pause" >/dev/null 2>&1 || true

sleep 1

/usr/bin/logger -t shairport-plexamp "AirPlay starting - stopping Plexamp service"
/usr/bin/sudo /usr/bin/systemctl stop "\$PLEXAMP_SERVICE"

sleep 2

/usr/bin/logger -t shairport-plexamp "Plexamp service stopped - DAC should be free"
START_WRAPPER_EOF

cat <<END_WRAPPER_EOF | sudo tee "$END_WRAPPER" >/dev/null
#!/bin/bash
set -euo pipefail

DASHBOARD_BASE="$DASHBOARD_BASE"
PLEXAMP_SERVICE="$PLEXAMP_SERVICE"

STATUS_JSON="\$(/usr/bin/curl -fsS "\$DASHBOARD_BASE/api/status" 2>/dev/null || true)"
HOLD_STATUS="\$(printf '%s' "\$STATUS_JSON" | /usr/bin/python3 -c '
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
sys.exit(0 if 0 <= age <= 20 else 1)
' 2>/dev/null || true)"

if printf '%s' "\$HOLD_STATUS" | /usr/bin/grep -q '^mode=airplay .* age='; then
    AGE="\$(printf '%s' "\$HOLD_STATUS" | /usr/bin/sed -n 's/.* age=\([0-9.]*\).*/\1/p')"
    if /usr/bin/python3 - "\$AGE" <<'PY'
import sys
try:
    age = float(sys.argv[1])
except Exception:
    sys.exit(1)
sys.exit(0 if 0 <= age <= 20 else 1)
PY
    then
        /usr/bin/logger -t shairport-plexamp "AirPlay ended after dashboard pause - staying on AirPlay screen (\$HOLD_STATUS)"
        exit 0
    fi
fi

/usr/bin/logger -t shairport-plexamp "AirPlay end hook did not see dashboard pause hold (\$HOLD_STATUS)"
/usr/bin/logger -t shairport-plexamp "AirPlay ended - starting Plexamp service"
/usr/bin/sudo /usr/bin/systemctl start "\$PLEXAMP_SERVICE"
/usr/bin/logger -t shairport-plexamp "Plexamp service start requested"

sleep 5

/usr/bin/logger -t shairport-plexamp "AirPlay ended - switching display to clock"
/usr/bin/curl -fsS "\$DASHBOARD_BASE/api/airplay/end" >/dev/null || true
END_WRAPPER_EOF

sudo chmod 755 "$START_WRAPPER" "$END_WRAPPER"

cat <<SUDOERS_EOF | sudo tee "$SUDOERS_FILE" >/dev/null
# Allow Shairport Sync to release and restore the DAC for A Clockwork Plex AirPlay handoff.
$SHAIRPORT_USER ALL=(root) NOPASSWD: /usr/bin/systemctl stop $PLEXAMP_SERVICE, /usr/bin/systemctl start $PLEXAMP_SERVICE
SUDOERS_EOF

sudo chmod 440 "$SUDOERS_FILE"
sudo visudo -cf "$SUDOERS_FILE" >/dev/null

echo "Installed self-contained AirPlay hook wrappers:"
echo "  $START_WRAPPER"
echo "  $END_WRAPPER"
echo
echo "Installed sudoers rule:"
echo "  $SUDOERS_FILE"
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
