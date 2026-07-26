#!/bin/bash
set -euo pipefail

MODE=prepare
CONFIRM_TOKEN=""
LAB_ROOT="${LAB_ROOT:-}"
ALSA_CARD="${ALSA_CARD:-Pro}"
ALIAS_CONFIG="${ALIAS_CONFIG:-/etc/alsa/conf.d/98-a-clockwork-plex-control-aliases.conf}"
LIVE_CONFIG="${LIVE_CONFIG:-/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf}"
MIXER_HELPER="${MIXER_HELPER:-/usr/local/bin/a-clockwork-plex-audio-mixer}"
REQUIRED_CONFIRMATION="ACP-CONTROL-ALIASES"
SERVICES=(plexamp.service a-clockwork-plex.service)
APPLY_ACTIVE=false
APPLY_COMMITTED=false
ROLLBACK_FAILURES=0

usage() {
    cat <<'EOF_USAGE'
Usage: bash scripts/test-alsa-control-alias-migration.sh [options]

Options:
  --prepare-only       Generate and validate the alias fragment only (default).
  --apply              Install the separate alias fragment and restart Plexamp/dashboard.
  --verify             Verify an applied alias migration; requires --lab-root PATH.
  --rollback           Restore the pre-apply alias state; requires --lab-root PATH.
  --confirm TOKEN      Required with --apply: ACP-CONTROL-ALIASES
  --lab-root PATH      Reuse or create PATH for evidence and rollback data.
  --card CARD          Physical ALSA control card ID (default: Pro).
  -h, --help           Show this help.

Prepare-only writes only inside the laboratory directory. Apply changes only the
separate named-control alias fragment, snapshots its prior state, restarts only
Plexamp and the dashboard, and automatically rolls back if validation fails.
EOF_USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prepare-only) MODE=prepare; shift ;;
        --apply) MODE=apply; shift ;;
        --verify) MODE=verify; shift ;;
        --rollback) MODE=rollback; shift ;;
        --confirm)
            [[ $# -ge 2 ]] || { echo "--confirm requires a token." >&2; exit 64; }
            CONFIRM_TOKEN="$2"; shift 2 ;;
        --lab-root)
            [[ $# -ge 2 ]] || { echo "--lab-root requires a path." >&2; exit 64; }
            LAB_ROOT="$2"; shift 2 ;;
        --card)
            [[ $# -ge 2 ]] || { echo "--card requires an ALSA card ID." >&2; exit 64; }
            ALSA_CARD="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 64 ;;
    esac
done

[[ "$ALSA_CARD" =~ ^[A-Za-z0-9_.@-]+$ ]] || { echo "Invalid ALSA card ID: $ALSA_CARD" >&2; exit 64; }
[[ "$EUID" -ne 0 ]] || { echo "Run this script as the project user, not with sudo." >&2; exit 1; }
if [[ "$MODE" == apply && "$CONFIRM_TOKEN" != "$REQUIRED_CONFIRMATION" ]]; then
    echo "Alias activation is blocked without: --confirm $REQUIRED_CONFIRMATION" >&2
    exit 64
fi
if [[ "$MODE" =~ ^(verify|rollback)$ && -z "$LAB_ROOT" ]]; then
    echo "--lab-root PATH is required with --$MODE." >&2
    exit 64
fi

if [[ -z "$LAB_ROOT" ]]; then
    LAB_ROOT="$(mktemp -d /var/tmp/a-clockwork-plex-ctl-migration.XXXXXX)"
else
    mkdir -p "$LAB_ROOT"
    LAB_ROOT="$(cd "$LAB_ROOT" && pwd)"
fi
chmod 0700 "$LAB_ROOT"

ALIAS_CANDIDATE="$LAB_ROOT/98-a-clockwork-plex-control-aliases.conf"
VALIDATION_ROOT="$LAB_ROOT/alsa-isolated.conf"
RESULTS_FILE="$LAB_ROOT/results.tsv"
REPORT_FILE="$LAB_ROOT/report.txt"
BACKUP_DIR="$LAB_ROOT/rollback-snapshot"
SERVICE_STATE_FILE="$LAB_ROOT/service-state.tsv"
ALIAS_STATE_FILE="$LAB_ROOT/original-alias-state.txt"
CONTROLS_BEFORE="$LAB_ROOT/controls-before.txt"
CONTROLS_AFTER="$LAB_ROOT/controls-after.txt"
CONTROLS_VERIFY="$LAB_ROOT/controls-verify.txt"
PLEXAMP_JOURNAL="$LAB_ROOT/plexamp-restart.log"
TIMELINE_FILE="$LAB_ROOT/plexamp-timeline.xml"

require_command() {
    command -v "$1" >/dev/null 2>&1 || { echo "Required command not found: $1" >&2; exit 1; }
}

for command in python3 amixer sha256sum cmp awk grep curl; do require_command "$command"; done

write_alias_fragment() {
    cat >"$ALIAS_CANDIDATE" <<EOF_ALIAS
# Managed by A Clockwork Plex.
# Named ALSA control aliases for applications that pair ctl.<name> with pcm.<name>.

ctl.acp_dmix { type hw card "$ALSA_CARD" }
ctl.acp_master { type hw card "$ALSA_CARD" }
ctl.acp_master_volume { type hw card "$ALSA_CARD" }
ctl.acp_plexamp { type hw card "$ALSA_CARD" }
ctl.acp_plexamp_volume { type hw card "$ALSA_CARD" }
ctl.acp_airplay { type hw card "$ALSA_CARD" }
ctl.acp_airplay_volume { type hw card "$ALSA_CARD" }
ctl.acp_alarm { type hw card "$ALSA_CARD" }
ctl.acp_alarm_volume { type hw card "$ALSA_CARD" }
EOF_ALIAS
}

build_validation_root() {
    [[ -f "$LIVE_CONFIG" ]] || { echo "Live shared-audio fragment is missing: $LIVE_CONFIG" >&2; exit 1; }
    python3 - /usr/share/alsa/alsa.conf "$LIVE_CONFIG" "$ALIAS_CANDIDATE" "$VALIDATION_ROOT" <<'PY'
from __future__ import annotations
import sys
from pathlib import Path

base_path, live_path, alias_path, output_path = map(Path, sys.argv[1:])
lines = base_path.read_text(encoding="utf-8").splitlines()
result: list[str] = []
skipping = False
depth = 0
removed = False
for line in lines:
    stripped = line.strip()
    if not removed and not skipping and stripped.startswith("@hooks") and "[" in stripped:
        skipping = True
        depth = line.count("[") - line.count("]")
        if depth == 0:
            skipping = False
            removed = True
        continue
    if skipping:
        depth += line.count("[") - line.count("]")
        if depth == 0:
            skipping = False
            removed = True
        continue
    result.append(line)
if not removed:
    raise SystemExit("could not remove the global ALSA preload hook")
result.extend(("", live_path.read_text(encoding="utf-8"), "", alias_path.read_text(encoding="utf-8")))
output_path.write_text("\n".join(result).rstrip() + "\n", encoding="utf-8")
PY
}

snapshot_controls() {
    local destination="$1"
    {
        echo "# A Clockwork Plex restricted mixer"
        if [[ -x "$MIXER_HELPER" ]]; then
            sudo -n "$MIXER_HELPER" status 2>/dev/null || true
        fi
        for control in \
            "A Clockwork Master" \
            "A Clockwork Plexamp" \
            "A Clockwork AirPlay" \
            "A Clockwork Alarm" \
            "Digital" \
            "Analogue" \
            "Analogue Playback Boost"; do
            echo
            echo "## $control"
            amixer -c "$ALSA_CARD" sget "$control" 2>/dev/null || true
        done
    } >"$destination"
}

record_service_state() {
    : >"$SERVICE_STATE_FILE"
    local service
    for service in "${SERVICES[@]}"; do
        printf '%s\t%s\t%s\n' \
            "$service" \
            "$(systemctl is-active "$service" 2>/dev/null || true)" \
            "$(systemctl is-enabled "$service" 2>/dev/null || true)" \
            >>"$SERVICE_STATE_FILE"
    done
}

service_was_active() {
    awk -F '\t' -v wanted="$1" '$1 == wanted && $2 == "active" {found=1} END {exit(found ? 0 : 1)}' "$SERVICE_STATE_FILE"
}

restore_services() {
    local service
    for service in "${SERVICES[@]}"; do
        if service_was_active "$service"; then
            sudo systemctl restart "$service" || ROLLBACK_FAILURES=$((ROLLBACK_FAILURES + 1))
        else
            sudo systemctl stop "$service" || ROLLBACK_FAILURES=$((ROLLBACK_FAILURES + 1))
        fi
    done
}

rollback_apply() {
    [[ "$APPLY_ACTIVE" == true ]] || return 0
    set +e
    echo "Rolling back the named-control alias migration..."
    if [[ -f "$ALIAS_STATE_FILE" ]] && grep -qx 'present' "$ALIAS_STATE_FILE"; then
        sudo cp -a "$BACKUP_DIR/original-alias.conf" "$ALIAS_CONFIG" || ROLLBACK_FAILURES=$((ROLLBACK_FAILURES + 1))
    else
        sudo rm -f "$ALIAS_CONFIG" || ROLLBACK_FAILURES=$((ROLLBACK_FAILURES + 1))
    fi
    restore_services
    APPLY_ACTIVE=false
    set -e
}

on_exit() {
    local status=$?
    trap - EXIT
    if [[ "$APPLY_ACTIVE" == true && "$APPLY_COMMITTED" == false ]]; then rollback_apply; fi
    if (( ROLLBACK_FAILURES > 0 )) && (( status == 0 )); then status=1; fi
    exit "$status"
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

write_alias_fragment
build_validation_root
printf 'check\tresult\tdetail\n' >"$RESULTS_FILE"
if ALSA_CONFIG_PATH="$VALIDATION_ROOT" amixer -D acp_plexamp scontrols >"$LAB_ROOT/isolated-acp-plexamp.txt" 2>"$LAB_ROOT/isolated-acp-plexamp.err"; then
    printf 'isolated-ctl-acp_plexamp\tPASS\talias opens against hw:%s\n' "$ALSA_CARD" | tee -a "$RESULTS_FILE"
else
    printf 'isolated-ctl-acp_plexamp\tFAIL\tsee isolated-acp-plexamp.err\n' | tee -a "$RESULTS_FILE"
    exit 1
fi

cat >"$REPORT_FILE" <<EOF_REPORT
A Clockwork Plex guarded control-alias migration
Generated: $(date --iso-8601=seconds)
Directory: $LAB_ROOT
Mode: $MODE
Live shared graph: $LIVE_CONFIG
Alias target: $ALIAS_CONFIG
Physical control card: hw:$ALSA_CARD
Audio route changed: no
EOF_REPORT

if [[ "$MODE" == prepare ]]; then
    cat <<EOF_STATUS

Control-alias migration prepared.

  Directory:       $LAB_ROOT
  Alias candidate: $ALIAS_CANDIDATE
  Live target:     $ALIAS_CONFIG

No production file, service, mixer value or audio route has been changed.
EOF_STATUS
    exit 0
fi

for command in sudo systemctl journalctl install rm; do require_command "$command"; done

if [[ "$MODE" == rollback ]]; then
    [[ -f "$ALIAS_STATE_FILE" && -f "$SERVICE_STATE_FILE" ]] || { echo "Rollback snapshot is incomplete in $LAB_ROOT." >&2; exit 1; }
    APPLY_ACTIVE=true
    rollback_apply
    printf 'rollback\tPASS\tprevious alias state and service states restored\n' | tee -a "$RESULTS_FILE"
    exit "$ROLLBACK_FAILURES"
fi

if [[ "$MODE" == verify ]]; then
    amixer -D acp_plexamp scontrols >"$LAB_ROOT/live-acp-plexamp-verify.txt" 2>"$LAB_ROOT/live-acp-plexamp-verify.err"
    snapshot_controls "$CONTROLS_VERIFY"
    if cmp -s "$CONTROLS_BEFORE" "$CONTROLS_VERIFY"; then
        printf 'mixer-state-verify\tPASS\tmonitored controls unchanged\n' | tee -a "$RESULTS_FILE"
    else
        printf 'mixer-state-verify\tWARN\tinspect controls-before.txt and controls-verify.txt\n' | tee -a "$RESULTS_FILE"
    fi
    printf 'live-ctl-acp_plexamp\tPASS\tnamed control opens\n' | tee -a "$RESULTS_FILE"
    exit 0
fi

sudo -v
sudo install -d -m 0700 "$BACKUP_DIR"
record_service_state
snapshot_controls "$CONTROLS_BEFORE"
if [[ -e "$ALIAS_CONFIG" ]]; then
    printf 'present\n' >"$ALIAS_STATE_FILE"
    sudo cp -a "$ALIAS_CONFIG" "$BACKUP_DIR/original-alias.conf"
else
    printf 'absent\n' >"$ALIAS_STATE_FILE"
fi
APPLY_ACTIVE=true

sudo install -o root -g root -m 0644 "$ALIAS_CANDIDATE" "$ALIAS_CONFIG"
if amixer -D acp_plexamp scontrols >"$LAB_ROOT/live-acp-plexamp.txt" 2>"$LAB_ROOT/live-acp-plexamp.err"; then
    printf 'live-ctl-acp_plexamp\tPASS\tnamed control opens after install\n' | tee -a "$RESULTS_FILE"
else
    printf 'live-ctl-acp_plexamp\tFAIL\tsee live-acp-plexamp.err\n' | tee -a "$RESULTS_FILE"
    exit 1
fi

restart_since="$(date --iso-8601=seconds)"
sudo systemctl stop a-clockwork-plex.service
sudo systemctl restart plexamp.service

ready=false
for _ in {1..60}; do
    if curl -fsS --max-time 2 \
        'http://localhost:32500/player/timeline/poll?commandID=765432&type=music&wait=0' \
        >"$TIMELINE_FILE" 2>/dev/null \
        && grep -q 'Timeline[^>]*type="music"' "$TIMELINE_FILE"; then
        ready=true
        break
    fi
    sleep 1
done
[[ "$ready" == true ]] || { echo "Plexamp timeline did not become available after restart." >&2; exit 1; }

sudo systemctl start a-clockwork-plex.service
sleep 3
sudo journalctl -u plexamp.service --since "$restart_since" --no-pager >"$PLEXAMP_JOURNAL" 2>&1 || true
if grep -Fq 'Invalid CTL acp_plexamp' "$PLEXAMP_JOURNAL"; then
    printf 'plexamp-control-log\tFAIL\tInvalid CTL remained after alias install\n' | tee -a "$RESULTS_FILE"
    exit 1
else
    printf 'plexamp-control-log\tPASS\tno Invalid CTL acp_plexamp after restart\n' | tee -a "$RESULTS_FILE"
fi

snapshot_controls "$CONTROLS_AFTER"
if cmp -s "$CONTROLS_BEFORE" "$CONTROLS_AFTER"; then
    printf 'mixer-state-after-restart\tPASS\tmonitored controls unchanged\n' | tee -a "$RESULTS_FILE"
else
    printf 'mixer-state-after-restart\tFAIL\tmonitored controls changed; rolling back\n' | tee -a "$RESULTS_FILE"
    exit 1
fi

APPLY_COMMITTED=true
APPLY_ACTIVE=false
cat <<EOF_DONE

Named-control aliases are ACTIVE for the direct-mixer playback test.

  Evidence: $LAB_ROOT
  Alias file: $ALIAS_CONFIG

Open Plexamp and press Play without reconnecting the local player. Then run:

  bash scripts/test-alsa-control-alias-migration.sh --verify --lab-root "$LAB_ROOT"

To restore the exact pre-test alias state:

  bash scripts/test-alsa-control-alias-migration.sh --rollback --lab-root "$LAB_ROOT"
EOF_DONE
