#!/usr/bin/env bash
set -euo pipefail

DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:8088}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
STATE_URL="$DASHBOARD_URL/api/audio/state"

if ! command -v curl >/dev/null 2>&1; then
    echo "Required command not found: curl" >&2
    exit 1
fi
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Required command not found: $PYTHON_BIN" >&2
    exit 1
fi

state_file="$(mktemp)"
trap 'rm -f "$state_file"' EXIT
status="$(curl -sS -o "$state_file" -w '%{http_code}' "$STATE_URL" || true)"
if [[ "$status" != "200" ]]; then
    echo "Audio state endpoint returned HTTP $status: $STATE_URL" >&2
    cat "$state_file" >&2
    exit 1
fi

"$PYTHON_BIN" - "$state_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

audio = payload.get("audio") or {}
defaults = audio.get("defaults") or {}
capabilities = audio.get("command_capabilities") or {}
airplay = (audio.get("channels") or {}).get("airplay") or {}
remote = airplay.get("remote") or {}

print("===== MIXER CONTROLLER =====")
print(f"authority:          {audio.get('authority')}")
print(f"commands enabled:   {audio.get('commands_enabled')}")
print(f"AirPlay promoted:   {capabilities.get('airplay_sender_volume')}")
print(f"start write limit:  {capabilities.get('airplay_starting_volume_write_limit')}")
print(f"service restarts:   {capabilities.get('service_restarts')}")
print()
print("===== AIRPLAY SENDER VOLUME =====")
print(f"available:          {airplay.get('available')}")
print(f"effective percent:  {airplay.get('effective_percent')}")
print(f"observed percent:   {airplay.get('observed_percent')}")
print(f"requested percent:  {airplay.get('requested_percent')}")
print(f"state source:       {airplay.get('state_source')}")
print(f"command status:     {airplay.get('command_status')}")
print(f"request active:     {airplay.get('request_active')}")
print(f"command count:      {airplay.get('command_count')}")
print(f"target percent:     {airplay.get('target_percent')}")
print(f"baseline percent:   {airplay.get('baseline_percent')}")
print(f"last attempted:     {airplay.get('last_attempt_at')}")
print(f"last applied:       {airplay.get('last_applied_at')}")
print(f"last confirmed:     {airplay.get('last_confirmed_at')}")
print(f"last error:         {airplay.get('last_error')}")
print()
print("===== RAW SHAIRPORT OBSERVATION =====")
print(f"sender available:   {remote.get('sender_available')}")
print(f"availability via:   {remote.get('availability_source')}")
print(f"MPRIS service live: {remote.get('mpris_service_available')}")
print(f"playback status:    {remote.get('playback_status')}")
print(f"volume percent:     {remote.get('volume_percent')}")
print(f"sender error:       {remote.get('sender_error')}")
print()
print("Read-only inspection: no volume, playback, mixer, DSP or service was changed.")
PY
