#!/usr/bin/env bash
set -euo pipefail

DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:8088}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
STATE_URL="$DASHBOARD_URL/api/playback/state"
EVENTS_URL="$DASHBOARD_URL/api/playback/events"
SCREEN_URL="$DASHBOARD_URL/api/screen/state"

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
screen_file="$(mktemp)"
trap 'rm -f "$state_file" "$events_file" "$screen_file"' EXIT

state_status="$(curl -sS -o "$state_file" -w '%{http_code}' "$STATE_URL" || true)"
events_status="$(curl -sS -o "$events_file" -w '%{http_code}' "$EVENTS_URL" || true)"
screen_status="$(curl -sS -o "$screen_file" -w '%{http_code}' "$SCREEN_URL" || true)"

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
if [[ "$screen_status" != "200" ]]; then
    echo "Screen projection endpoint returned HTTP $screen_status: $SCREEN_URL" >&2
    cat "$screen_file" >&2
    exit 1
fi

"$PYTHON_BIN" - "$state_file" "$events_file" "$screen_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    state_payload = json.load(handle)
with open(sys.argv[2], encoding="utf-8") as handle:
    event_payload = json.load(handle)
with open(sys.argv[3], encoding="utf-8") as handle:
    screen_payload = json.load(handle)

playback = state_payload.get("playback") or {}
sources = playback.get("sources") or {}
airplay = sources.get("airplay") or {}
plexamp = sources.get("plexamp") or {}
alarm = sources.get("alarm") or {}
observed = airplay.get("observed") or {}
hold = airplay.get("hold") or {}
worker = playback.get("worker") or {}
capabilities = playback.get("command_capabilities") or {}
commands = playback.get("commands") or {}
command = commands.get("airplay") or {}
navigation = commands.get("airplay_navigation") or {}
handoffs = playback.get("handoffs") or {}
takeover = handoffs.get("airplay_to_plexamp") or {}
reverse = handoffs.get("plexamp_to_airplay") or {}
events = event_payload.get("events") or {}
last_event = events.get("last_event") or {}
screen = screen_payload.get("screen") or {}
lease = screen.get("lease") or {}

print("===== PLAYBACK COORDINATOR =====")
print(f"authority:          {playback.get('authority')}")
print(f"commands enabled:   {playback.get('commands_enabled')}")
print(f"source control:     {capabilities.get('source_control')}")
print(f"AirPlay transport:  {capabilities.get('airplay_transport')}")
print(f"AirPlay navigation: {capabilities.get('airplay_navigation')}")
print(f"AirPlay actions:    {capabilities.get('airplay_actions')}")
print(f"AirPlay→Plexamp:    {capabilities.get('airplay_to_plexamp_handoff')}")
print(f"Plexamp→AirPlay:    {capabilities.get('plexamp_to_airplay_handoff')}")
print(f"AirPlay ceded:      {capabilities.get('airplay_ceded_to_plexamp')}")
print(f"screen projection:  {screen.get('screen_projection')}")
print(f"preserve Plexamp:   {capabilities.get('preserve_open_plexamp_surface')}")
print(f"Plexamp transport:  {capabilities.get('plexamp_transport')}")
print(f"auto arbitration:   {capabilities.get('automatic_arbitration')}")
print(f"screen return:      {capabilities.get('screen_return_on_hold_end')}")
print(f"worker running:     {worker.get('running')}")
print(f"active source:      {playback.get('active_source')}")
print(f"decision reason:    {playback.get('decision_reason')}")
print(f"current screen:     {playback.get('current_screen')}")
print(f"recommended screen: {playback.get('recommended_screen')}")
print(f"screen in sync:     {playback.get('screen_in_sync')}")
print()
print("===== SCREEN PROJECTION =====")
print(f"authority:          {screen.get('authority')}")
print(f"current screen:     {screen.get('current_screen')}")
print(f"recommended screen: {screen.get('recommended_screen')}")
print(f"decision reason:    {screen.get('decision_reason')}")
print(f"screen in sync:     {screen.get('screen_in_sync')}")
print(f"apply required:     {screen.get('should_apply')}")
print(f"idle timeout:       {screen.get('idle_timeout_seconds')}")
print(f"idle return:        {screen.get('idle_return_mode')}")
print(f"manual surface:     {lease.get('manual_surface')}")
print(f"lease active:       {lease.get('active')}")
print(f"lease remaining:    {lease.get('remaining_seconds')}")
print(f"idle remaining:     {lease.get('idle_remaining_seconds')}")
print(f"interaction via:    {lease.get('last_interaction_source')}")
print(f"last applied screen:{screen.get('last_applied_screen')}")
print(f"last error:         {screen.get('last_error')}")
print()
print("===== SOURCES =====")
print(f"Plexamp:            {plexamp.get('state')} (available={plexamp.get('available')})")
print(f"AirPlay connected:  {airplay.get('connected')}")
print(f"AirPlay state:      {airplay.get('state')}")
print(f"AirPlay source:     {airplay.get('state_source')}")
print(f"AirPlay ownership:  {airplay.get('ownership')}")
print(f"Sender available:   {observed.get('sender_available')}")
print(f"Availability via:   {observed.get('availability_source')}")
print(f"MPRIS service live: {observed.get('mpris_service_available')}")
print(f"Sender query error: {observed.get('sender_error')}")
print(f"AirPlay raw MPRIS:  {observed.get('raw_playback_status')}")
print(f"AirPlay effective:  {observed.get('effective_playback_status')}")
print(f"Alarm active:       {alarm.get('active')}")
print()
print("===== AIRPLAY COMMAND =====")
print(f"sequence:           {command.get('sequence')}")
print(f"action:             {command.get('action')}")
print(f"target state:       {command.get('target_state')}")
print(f"status:             {command.get('status')}")
print(f"noop:               {command.get('noop')}")
print(f"requested at:       {command.get('requested_at')}")
print(f"accepted at:        {command.get('accepted_at')}")
print(f"completed at:       {command.get('completed_at')}")
print(f"observed state:     {command.get('observed_state')}")
print(f"observed via:       {command.get('observed_source')}")
print(f"last error:         {command.get('last_error')}")
print()
print("===== AIRPLAY NAVIGATION =====")
print(f"sequence:           {navigation.get('sequence')}")
print(f"action:             {navigation.get('action')}")
print(f"status:             {navigation.get('status')}")
print(f"completion policy:  {navigation.get('completion_policy')}")
print(f"requested at:       {navigation.get('requested_at')}")
print(f"accepted at:        {navigation.get('accepted_at')}")
print(f"completed at:       {navigation.get('completed_at')}")
print(f"accepted via:       {navigation.get('observed_source')}")
print(f"last error:         {navigation.get('last_error')}")
print()
print("===== AIRPLAY → PLEXAMP HANDOFF =====")
print(f"sequence:           {takeover.get('sequence')}")
print(f"direction:          {takeover.get('direction')}")
print(f"status:             {takeover.get('status')}")
print(f"trigger:            {takeover.get('trigger')}")
print(f"Plexamp before:     {takeover.get('plexamp_before')}")
print(f"Plexamp after:      {takeover.get('plexamp_after')}")
print(f"pause command count:{takeover.get('command_count')}")
print(f"completion policy:  {takeover.get('completion_policy')}")
print(f"screen policy:      {takeover.get('screen_policy')}")
print(f"requested at:       {takeover.get('requested_at')}")
print(f"accepted at:        {takeover.get('accepted_at')}")
print(f"completed at:       {takeover.get('completed_at')}")
print(f"last error:         {takeover.get('last_error')}")
print()
print("===== PLEXAMP → AIRPLAY HANDOFF =====")
print(f"sequence:           {reverse.get('sequence')}")
print(f"direction:          {reverse.get('direction')}")
print(f"status:             {reverse.get('status')}")
print(f"trigger:            {reverse.get('trigger')}")
print(f"AirPlay before:     {reverse.get('airplay_before')}")
print(f"AirPlay after:      {reverse.get('airplay_after')}")
print(f"pause command count:{reverse.get('command_count')}")
print(f"completion policy:  {reverse.get('completion_policy')}")
print(f"ownership policy:   {reverse.get('ownership_policy')}")
print(f"screen policy:      {reverse.get('screen_policy')}")
print(f"requested at:       {reverse.get('requested_at')}")
print(f"accepted at:        {reverse.get('accepted_at')}")
print(f"completed at:       {reverse.get('completed_at')}")
print(f"last error:         {reverse.get('last_error')}")
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
