#!/usr/bin/env bash
set -euo pipefail

DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:8088}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
STATE_URL="$DASHBOARD_URL/api/playback/state"
EVENTS_URL="$DASHBOARD_URL/api/playback/events"

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Required command not found: $1" >&2
        exit 1
    fi
}

require_command curl
require_command "$PYTHON_BIN"

state_file="$(mktemp)"
events_file="$(mktemp)"
trap 'rm -f "$state_file" "$events_file"' EXIT

state_status="$(curl -sS -o "$state_file" -w '%{http_code}' "$STATE_URL" || true)"
events_status="$(curl -sS -o "$events_file" -w '%{http_code}' "$EVENTS_URL" || true)"

if [[ "$state_status" != "200" ]]; then
    echo "Playback state endpoint returned HTTP $state_status: $STATE_URL" >&2
    cat "$state_file" >&2
    exit 1
fi
if [[ "$events_status" != "200" ]]; then
    echo "Playback event endpoint returned HTTP $events_status: $EVENTS_URL" >&2
    cat "$events_file" >&2
    exit 1
fi

"$PYTHON_BIN" - "$state_file" "$events_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    state_payload = json.load(handle)
with open(sys.argv[2], encoding="utf-8") as handle:
    event_payload = json.load(handle)

playback = state_payload.get("playback") or {}
sources = playback.get("sources") or {}
airplay = sources.get("airplay") or {}
plexamp = sources.get("plexamp") or {}
alarm = sources.get("alarm") or {}
observed = airplay.get("observed") or {}
hold = airplay.get("hold") or {}
worker = playback.get("worker") or {}
capabilities = playback.get("command_capabilities") or {}
events = event_payload.get("events") or {}
last_event = events.get("last_event") or {}

print("===== PLAYBACK COORDINATOR =====")
print(f"authority:          {playback.get('authority')}")
print(f"commands enabled:   {playback.get('commands_enabled')}")
print(f"source control:     {capabilities.get('source_control')}")
print(f"screen return:      {capabilities.get('screen_return_on_hold_end')}")
print(f"worker running:     {worker.get('running')}")
print(f"active source:      {playback.get('active_source')}")
print(f"decision reason:    {playback.get('decision_reason')}")
print(f"current screen:     {playback.get('current_screen')}")
print(f"recommended screen: {playback.get('recommended_screen')}")
print(f"screen in sync:     {playback.get('screen_in_sync')}")
print()
print("===== SOURCES =====")
print(f"Plexamp:            {plexamp.get('state')} (available={plexamp.get('available')})")
print(f"AirPlay connected:  {airplay.get('connected')}")
print(f"AirPlay state:      {airplay.get('state')}")
print(f"AirPlay source:     {airplay.get('state_source')}")
print(f"AirPlay raw MPRIS:  {observed.get('raw_playback_status')}")
print(f"AirPlay effective:  {observed.get('effective_playback_status')}")
print(f"Alarm active:       {alarm.get('active')}")
print()
print("===== AIRPLAY HOLD =====")
print(f"owner:              {hold.get('owner')}")
print(f"phase:              {hold.get('phase')}")
print(f"active:             {hold.get('active')}")
print(f"started at:         {hold.get('started_at')}")
print(f"until:              {hold.get('until')}")
print(f"remaining seconds:  {hold.get('remaining_seconds')}")
print(f"last reason:        {hold.get('last_reason')}")
print(f"last error:         {hold.get('last_error')}")
print()
print("===== EVENT JOURNAL =====")
print(f"sequence:           {events.get('sequence')}")
if last_event:
    print(
        "last event:         "
        f"#{last_event.get('sequence')} "
        f"{last_event.get('source')}.{last_event.get('event')} "
        f"({last_event.get('kind')})"
    )
else:
    print("last event:         none")

recent = events.get("recent_events") or []
if recent:
    print("recent transitions:")
    for event in recent[-8:]:
        print(
            f"  #{event.get('sequence'):>3} "
            f"{event.get('source')}.{event.get('event')} "
            f"[{event.get('kind')}]"
        )

print()
print("Read-only inspection: no command, mode, mixer, DSP or service was changed.")
PY
