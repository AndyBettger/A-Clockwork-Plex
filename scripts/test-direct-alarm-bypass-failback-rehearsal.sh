#!/bin/bash
set -euo pipefail

# A Clockwork Plex Stage C0 direct alarm-bypass failback rehearsal.
#
# This proves the no-DSP route that a future CamillaDSP watchdog can select:
#
#   Plexamp/AirPlay -> source trims -> Music Master --\
#                                                     +-> stereo dmix -> DAC
#   Alarm -> independent Alarm ceiling -------------/
#
# Prepare-only is the default. Activation is temporary, time-limited and always
# restores the exact original ALSA file, mixer values and service states.

MODE=prepare
CONFIRM_TOKEN=""
LAB_ROOT="${LAB_ROOT:-}"
PROJECT_USER="${PROJECT_USER:-${SUDO_USER:-$(id -un)}}"
DAC_CARD="${DAC_CARD:-Pro}"
DAC_DEVICE="${DAC_DEVICE:-0}"
DURATION_SECONDS="${DURATION_SECONDS:-900}"
ALSA_CONFIG="${ALSA_CONFIG:-/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf}"
MIXER_HELPER="${MIXER_HELPER:-/usr/local/bin/a-clockwork-plex-audio-mixer}"
DAC_HW_PARAMS="${DAC_HW_PARAMS:-/proc/asound/Pro/pcm0p/sub0/hw_params}"
SAMPLE_RATE=44100
FORMAT=S16_LE
CHANNELS=2
PERIOD_SIZE=1024
BUFFER_SIZE=8192
TEST_TONE_DB=-42.0
REQUIRED_CONFIRMATION="STAGE-C0-DIRECT-FAILBACK-REAL-DAC"
SERVICES=(plexamp.service shairport-sync.service a-clockwork-plex.service)

SUDO_KEEPALIVE_PID=""
DAC_INDEX=""
ROLLBACK_NEEDED=false
ROLLBACK_DONE=false
ROLLBACK_FAILURES=0
ORIGINAL_MASTER_PERCENT=""

usage() {
    cat <<'EOF_USAGE'
Usage: bash scripts/test-direct-alarm-bypass-failback-rehearsal.sh [options]

Options:
  --prepare-only       Generate and validate files only (default).
  --activate           Run the time-limited real-service/DAC rehearsal.
  --confirm TOKEN      Required with --activate: STAGE-C0-DIRECT-FAILBACK-REAL-DAC
  --duration SECONDS   Rehearsal window, 120 to 1200 seconds (default: 900).
  --lab-root PATH      Reuse or create PATH instead of a new /var/tmp directory.
  -h, --help           Show this help.

Prepare-only writes only inside its private laboratory directory, invokes no
sudo command, opens no audio device and changes no service or production file.

Activation temporarily installs a direct no-DSP route where Music Master affects
Plexamp and AirPlay but not alarm. Enter, timeout, Ctrl-C, ordinary failure and
shell exit all restore the exact original direct route.
EOF_USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prepare-only) MODE=prepare; shift ;;
        --activate) MODE=activate; shift ;;
        --confirm)
            [[ $# -ge 2 ]] || { echo "--confirm requires a token." >&2; exit 64; }
            CONFIRM_TOKEN="$2"; shift 2 ;;
        --duration)
            [[ $# -ge 2 ]] || { echo "--duration requires seconds." >&2; exit 64; }
            DURATION_SECONDS="$2"; shift 2 ;;
        --lab-root)
            [[ $# -ge 2 ]] || { echo "--lab-root requires a path." >&2; exit 64; }
            LAB_ROOT="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 64 ;;
    esac
done

[[ "$DURATION_SECONDS" =~ ^[0-9]+$ ]] || { echo "Duration must be numeric." >&2; exit 64; }
(( DURATION_SECONDS >= 120 && DURATION_SECONDS <= 1200 )) || {
    echo "Duration must be from 120 to 1200 seconds." >&2
    exit 64
}
[[ "$PROJECT_USER" =~ ^[A-Za-z0-9_.@-]+$ ]] || { echo "Invalid project user: $PROJECT_USER" >&2; exit 64; }
[[ "$DAC_CARD" =~ ^[A-Za-z0-9_.@-]+$ ]] || { echo "Invalid DAC card: $DAC_CARD" >&2; exit 64; }
[[ "$DAC_DEVICE" =~ ^[0-9]+$ ]] || { echo "Invalid DAC device: $DAC_DEVICE" >&2; exit 64; }
[[ "$EUID" -ne 0 ]] || {
    echo "Run this script as $PROJECT_USER, not with sudo; guarded activation invokes sudo itself." >&2
    exit 1
}

if [[ "$MODE" == activate ]]; then
    [[ "$(uname -m)" == "aarch64" ]] || { echo "Activation expects aarch64; found $(uname -m)." >&2; exit 1; }
    [[ "$CONFIRM_TOKEN" == "$REQUIRED_CONFIRMATION" ]] || {
        echo "Physical activation is blocked without: --confirm $REQUIRED_CONFIRMATION" >&2
        exit 64
    }
fi

if [[ -z "$LAB_ROOT" ]]; then
    LAB_ROOT="$(mktemp -d /var/tmp/a-clockwork-plex-direct-failback.XXXXXX)"
else
    mkdir -p "$LAB_ROOT"
    LAB_ROOT="$(cd "$LAB_ROOT" && pwd)"
fi
chmod 0700 "$LAB_ROOT"

CANDIDATE_ALSA="$LAB_ROOT/99-a-clockwork-plex-direct-alarm-bypass.conf"
ALSA_VALIDATION_ROOT="$LAB_ROOT/alsa-validation.conf"
RESULTS_FILE="$LAB_ROOT/results.tsv"
REPORT_FILE="$LAB_ROOT/report.txt"
SNAPSHOT_DIR="$LAB_ROOT/rollback-snapshot"
SERVICE_STATE_FILE="$LAB_ROOT/service-state.tsv"
ORIGINAL_SHA_FILE="$LAB_ROOT/original-alsa.sha256"
RESTORED_SHA_FILE="$LAB_ROOT/restored-alsa.sha256"
MIXER_BEFORE="$LAB_ROOT/mixer-before.json"
MIXER_AFTER="$LAB_ROOT/mixer-after.json"
MIXER_RESTORE="$LAB_ROOT/mixer-restore.tsv"
CONTROL_HELPER="$LAB_ROOT/rehearsal-control.sh"
MUSIC_SIGNAL="$LAB_ROOT/low-level-music-997.raw"
ALARM_SIGNAL="$LAB_ROOT/low-level-alarm-2711.raw"
DAC_BEFORE="$LAB_ROOT/dac-before.txt"
DAC_ACTIVE="$LAB_ROOT/dac-active.txt"
DAC_AFTER="$LAB_ROOT/dac-after.txt"

require_command() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Required command not found: $1" >&2
        exit 1
    }
}

for command in python3 aplay systemctl timeout cmp sha256sum grep awk sudo install fuser pgrep curl; do
    require_command "$command"
done

cat >"$CANDIDATE_ALSA" <<EOF_ALSA
# A Clockwork Plex Stage C0 direct alarm-bypass failback rehearsal.
# Temporary only. Music remains beneath Master; alarm feeds dmix independently.

pcm.acp_dmix {
    type dmix
    ipc_key 1094931536
    ipc_key_add_uid false
    ipc_perm 0666
    slave {
        pcm "hw:CARD=$DAC_CARD,DEV=$DAC_DEVICE"
        format $FORMAT
        rate $SAMPLE_RATE
        channels $CHANNELS
        period_size $PERIOD_SIZE
        buffer_size $BUFFER_SIZE
    }
    bindings {
        0 0
        1 1
    }
}

pcm.acp_master_volume {
    type softvol
    slave.pcm "acp_dmix"
    control {
        name "A Clockwork Master"
        card "$DAC_CARD"
    }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}

pcm.acp_master {
    type plug
    slave.pcm "acp_master_volume"
    hint {
        show on
        description "A Clockwork Plex - Music master (direct failback rehearsal)"
    }
}

pcm.acp_plexamp_volume {
    type softvol
    slave.pcm "acp_master"
    control {
        name "A Clockwork Plexamp"
        card "$DAC_CARD"
    }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}

pcm.acp_plexamp {
    type plug
    slave.pcm "acp_plexamp_volume"
    hint {
        show on
        description "A Clockwork Plex - Plexamp"
    }
}

pcm.acp_airplay_volume {
    type softvol
    slave.pcm "acp_master"
    control {
        name "A Clockwork AirPlay"
        card "$DAC_CARD"
    }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}

pcm.acp_airplay {
    type plug
    slave.pcm "acp_airplay_volume"
    hint {
        show on
        description "A Clockwork Plex - AirPlay"
    }
}

pcm.acp_alarm_volume {
    type softvol
    slave.pcm "acp_dmix"
    control {
        name "A Clockwork Alarm"
        card "$DAC_CARD"
    }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}

pcm.acp_alarm {
    type plug
    slave.pcm "acp_alarm_volume"
    hint {
        show on
        description "A Clockwork Plex - Independent alarm direct failback"
    }
}
EOF_ALSA

python3 - /usr/share/alsa/alsa.conf "$CANDIDATE_ALSA" "$ALSA_VALIDATION_ROOT" <<'PY_ALSA_ROOT'
from __future__ import annotations

import sys
from pathlib import Path

base_path = Path(sys.argv[1])
fragment_path = Path(sys.argv[2])
output_path = Path(sys.argv[3])
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

result.extend(("", fragment_path.read_text(encoding="utf-8")))
output_path.write_text("\n".join(result).rstrip() + "\n", encoding="utf-8")
PY_ALSA_ROOT

if ALSA_CONFIG_PATH="$ALSA_VALIDATION_ROOT" aplay -L >"$LAB_ROOT/aplay-list.txt" 2>"$LAB_ROOT/aplay-list.err"; then
    printf 'alsa-config-parse\tPASS\ttemporary direct failback fragment parsed\n' | tee "$RESULTS_FILE"
else
    printf 'alsa-config-parse\tFAIL\tsee aplay-list.err\n' | tee "$RESULTS_FILE"
    exit 1
fi

for pcm in acp_dmix acp_master acp_plexamp acp_airplay acp_alarm; do
    grep -q "^${pcm}$" "$LAB_ROOT/aplay-list.txt" || {
        echo "Prepared ALSA graph is missing PCM: $pcm" >&2
        exit 1
    }
done

python3 - "$MUSIC_SIGNAL" "$ALARM_SIGNAL" "$SAMPLE_RATE" "$TEST_TONE_DB" <<'PY_SIGNALS'
from __future__ import annotations

import math
import struct
import sys
from pathlib import Path

music_path = Path(sys.argv[1])
alarm_path = Path(sys.argv[2])
rate = int(sys.argv[3])
db = float(sys.argv[4])
amplitude = int(32767 * (10 ** (db / 20)))

for path, frequency, seconds in (
    (music_path, 997.0, 4),
    (alarm_path, 2711.0, 1),
):
    frames = bytearray()
    for index in range(rate * seconds):
        sample = int(amplitude * math.sin(2 * math.pi * frequency * index / rate))
        frames.extend(struct.pack('<hh', sample, sample))
    path.write_bytes(frames)
PY_SIGNALS

cat >"$REPORT_FILE" <<EOF_REPORT
A Clockwork Plex Stage C0 direct alarm-bypass failback rehearsal
Prepared: $(date --iso-8601=seconds)
Mode: $MODE
Laboratory: $LAB_ROOT
Candidate ALSA: $CANDIDATE_ALSA
Physical DAC: hw:CARD=$DAC_CARD,DEV=$DAC_DEVICE
Duration: $DURATION_SECONDS seconds maximum
EOF_REPORT

cat <<EOF_PREPARED

A Clockwork Plex Stage C0 direct failback rehearsal prepared.

  Directory:      $LAB_ROOT
  ALSA fragment:  $CANDIDATE_ALSA
  Format:         $SAMPLE_RATE Hz / $FORMAT
  Duration:       $DURATION_SECONDS seconds maximum

No production file, service, mixer level or audio route has been changed.
The physical DAC has not been opened.
EOF_PREPARED

if [[ "$MODE" == prepare ]]; then
    cat <<EOF_COMMAND

After review, activation requires this exact token:

  bash scripts/test-direct-alarm-bypass-failback-rehearsal.sh --activate \
    --confirm $REQUIRED_CONFIRMATION \
    --duration $DURATION_SECONDS \
    --lab-root "$LAB_ROOT"

Activation is temporary and always restores the original direct mixer.
EOF_COMMAND
    exit 0
fi

[[ -f "$ALSA_CONFIG" ]] || { echo "Expected stable ALSA config is missing: $ALSA_CONFIG" >&2; exit 1; }
[[ -x "$MIXER_HELPER" ]] || { echo "Mixer helper is unavailable: $MIXER_HELPER" >&2; exit 1; }
pgrep -x camilladsp >/dev/null 2>&1 && {
    echo "An existing CamillaDSP process is running; Stage C0 expects the stable direct route." >&2
    exit 1
}

python3 - "$ALSA_CONFIG" <<'PY_STABLE_GRAPH'
from pathlib import Path
import sys

text = Path(sys.argv[1]).read_text(encoding="utf-8")
required = (
    "pcm.acp_dmix",
    "pcm.acp_master_volume",
    "pcm.acp_plexamp_volume",
    "pcm.acp_airplay_volume",
    "pcm.acp_alarm_volume",
)
missing = [item for item in required if item not in text]
if missing:
    raise SystemExit(f"unexpected stable graph; missing {', '.join(missing)}")
start = text.index("pcm.acp_alarm_volume")
end = text.index("pcm.acp_alarm {", start)
alarm_block = text[start:end]
if 'slave.pcm "acp_master"' not in alarm_block:
    raise SystemExit("stable graph is not the expected pre-Stage-C direct route")
PY_STABLE_GRAPH

DAC_INDEX="$(awk -v wanted="$DAC_CARD" '$0 ~ "\[" wanted "[[:space:]]*\]" {print $1; exit}' /proc/asound/cards 2>/dev/null || true)"
[[ "$DAC_INDEX" =~ ^[0-9]+$ ]] || { echo "Could not resolve ALSA card index for $DAC_CARD." >&2; exit 1; }

record_service_state() {
    : >"$SERVICE_STATE_FILE"
    local service
    for service in "${SERVICES[@]}"; do
        if systemctl is-active --quiet "$service"; then
            printf '%s\tactive\n' "$service" >>"$SERVICE_STATE_FILE"
        else
            printf '%s\tinactive\n' "$service" >>"$SERVICE_STATE_FILE"
        fi
    done
}

service_was_active() {
    grep -Fqx "$1"$'\tactive' "$SERVICE_STATE_FILE"
}

stop_services() {
    local service
    for service in "${SERVICES[@]}"; do
        sudo systemctl stop "$service" || true
    done
}

restore_services() {
    local service
    for service in "${SERVICES[@]}"; do
        if service_was_active "$service"; then
            sudo systemctl start "$service"
        else
            sudo systemctl stop "$service" || true
        fi
    done
}

restore_mixer_levels() {
    [[ -s "$MIXER_RESTORE" ]] || return 0
    while IFS=$'\t' read -r channel percent; do
        [[ -n "$channel" && "$percent" =~ ^[0-9]+$ ]] || continue
        sudo "$MIXER_HELPER" live "$channel" "$percent" >/dev/null || return 1
    done <"$MIXER_RESTORE"
}

stop_sudo_keepalive() {
    if [[ -n "$SUDO_KEEPALIVE_PID" ]]; then
        kill "$SUDO_KEEPALIVE_PID" >/dev/null 2>&1 || true
        wait "$SUDO_KEEPALIVE_PID" >/dev/null 2>&1 || true
        SUDO_KEEPALIVE_PID=""
    fi
}

rollback() {
    [[ "$ROLLBACK_DONE" == false ]] || return 0
    ROLLBACK_DONE=true
    set +e
    echo
    echo "Restoring the original direct audio graph..."

    stop_services
    sudo cp -a "$SNAPSHOT_DIR/original-alsa.conf" "$ALSA_CONFIG" || ROLLBACK_FAILURES=$((ROLLBACK_FAILURES + 1))

    restore_mixer_levels || ROLLBACK_FAILURES=$((ROLLBACK_FAILURES + 1))
    restore_services || ROLLBACK_FAILURES=$((ROLLBACK_FAILURES + 1))
    sleep 2

    sudo sha256sum "$ALSA_CONFIG" | awk '{print $1}' >"$RESTORED_SHA_FILE" 2>/dev/null || true
    if cmp -s "$ORIGINAL_SHA_FILE" "$RESTORED_SHA_FILE"; then
        printf 'rollback-alsa-config\tPASS\toriginal checksum restored\n' | tee -a "$RESULTS_FILE"
    else
        printf 'rollback-alsa-config\tFAIL\tchecksum mismatch\n' | tee -a "$RESULTS_FILE"
        ROLLBACK_FAILURES=$((ROLLBACK_FAILURES + 1))
    fi

    local service
    for service in "${SERVICES[@]}"; do
        if service_was_active "$service"; then
            if systemctl is-active --quiet "$service"; then
                printf 'rollback-service-%s\tPASS\trestored active\n' "$service" | tee -a "$RESULTS_FILE"
            else
                printf 'rollback-service-%s\tFAIL\tnot active\n' "$service" | tee -a "$RESULTS_FILE"
                ROLLBACK_FAILURES=$((ROLLBACK_FAILURES + 1))
            fi
        fi
    done

    sudo "$MIXER_HELPER" status >"$MIXER_AFTER" 2>/dev/null || true
    if [[ -s "$MIXER_BEFORE" && -s "$MIXER_AFTER" ]] && cmp -s "$MIXER_BEFORE" "$MIXER_AFTER"; then
        printf 'rollback-mixer-state\tPASS\toriginal displayed levels restored\n' | tee -a "$RESULTS_FILE"
    elif [[ -s "$MIXER_BEFORE" && -s "$MIXER_AFTER" ]]; then
        printf 'rollback-mixer-state\tWARN\tstatus differs; inspect JSON snapshots\n' | tee -a "$RESULTS_FILE"
    fi

    if [[ -r "$DAC_HW_PARAMS" ]]; then cat "$DAC_HW_PARAMS" >"$DAC_AFTER"; else printf 'unavailable\n' >"$DAC_AFTER"; fi
    stop_sudo_keepalive
    ROLLBACK_NEEDED=false
    set -e
}

on_exit() {
    local status=$?
    trap - EXIT
    if [[ "$ROLLBACK_NEEDED" == true ]]; then
        rollback
    else
        stop_sudo_keepalive
    fi
    if (( ROLLBACK_FAILURES > 0 )) && (( status == 0 )); then status=1; fi
    exit "$status"
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

sudo -v
(
    trap '' INT
    while sleep 30; do
        sudo -n true >/dev/null 2>&1 || exit 0
    done
) &
SUDO_KEEPALIVE_PID=$!

sudo install -d -m 0700 "$SNAPSHOT_DIR"
record_service_state
sudo cp -a "$ALSA_CONFIG" "$SNAPSHOT_DIR/original-alsa.conf"
sudo sha256sum "$ALSA_CONFIG" | awk '{print $1}' >"$ORIGINAL_SHA_FILE"
sudo "$MIXER_HELPER" status >"$MIXER_BEFORE"
python3 - "$MIXER_BEFORE" "$MIXER_RESTORE" <<'PY_MIXER'
from __future__ import annotations

import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
channels = payload.get("channels") or {}
lines: list[str] = []
for name in ("master", "plexamp", "airplay", "alarm"):
    value = (channels.get(name) or {}).get("percent")
    if not isinstance(value, int) or not 0 <= value <= 100:
        raise SystemExit(f"could not snapshot mixer channel {name}")
    lines.append(f"{name}\t{value}")
Path(sys.argv[2]).write_text("\n".join(lines) + "\n", encoding="utf-8")
PY_MIXER
ORIGINAL_MASTER_PERCENT="$(awk -F '\t' '$1 == "master" {print $2; exit}' "$MIXER_RESTORE")"
[[ "$ORIGINAL_MASTER_PERCENT" =~ ^[0-9]+$ ]] || { echo "Could not snapshot Music Master." >&2; exit 1; }

cat >"$CONTROL_HELPER" <<EOF_CONTROL
#!/bin/bash
set -euo pipefail
case "\${1:-}" in
  master-zero) sudo "$MIXER_HELPER" live master 0 ;;
  master-restore) sudo "$MIXER_HELPER" live master "$ORIGINAL_MASTER_PERCENT" ;;
  status) sudo "$MIXER_HELPER" status ;;
  *) echo "Usage: \$0 {master-zero|master-restore|status}" >&2; exit 64 ;;
esac
EOF_CONTROL
chmod 0700 "$CONTROL_HELPER"

if [[ -r "$DAC_HW_PARAMS" ]]; then cat "$DAC_HW_PARAMS" >"$DAC_BEFORE"; else printf 'unavailable\n' >"$DAC_BEFORE"; fi
ROLLBACK_NEEDED=true
printf 'rollback-snapshot\tPASS\t%s\n' "$SNAPSHOT_DIR" | tee -a "$RESULTS_FILE"

curl -fsS --max-time 2 http://localhost:32500/player/playback/pause >/dev/null 2>&1 || true
stop_services
sleep 1

if sudo fuser "/dev/snd/pcmC${DAC_INDEX}D${DAC_DEVICE}p" >/dev/null 2>&1; then
    echo "The physical DAC is still owned after stopping services." >&2
    sudo fuser -v "/dev/snd/pcmC${DAC_INDEX}D${DAC_DEVICE}p" >>"$REPORT_FILE" 2>&1 || true
    exit 1
fi
printf 'physical-dac-released\tPASS\tno playback owner\n' | tee -a "$RESULTS_FILE"

sudo install -o root -g root -m 0644 "$CANDIDATE_ALSA" "$ALSA_CONFIG"
printf 'temporary-direct-failback-route\tPASS\talarm bypasses Music Master\n' | tee -a "$RESULTS_FILE"

aplay -q -D acp_plexamp -t raw -f "$FORMAT" -r "$SAMPLE_RATE" -c "$CHANNELS" \
    "$MUSIC_SIGNAL" >"$LAB_ROOT/music-tone.log" 2>&1 &
MUSIC_PROBE_PID=$!
for _ in {1..20}; do
    if [[ -r "$DAC_HW_PARAMS" ]] && grep -q 'rate: 44100' "$DAC_HW_PARAMS" 2>/dev/null; then
        break
    fi
    sleep 0.1
done
if [[ -r "$DAC_HW_PARAMS" ]]; then cat "$DAC_HW_PARAMS" >"$DAC_ACTIVE"; else printf 'unavailable\n' >"$DAC_ACTIVE"; fi
if ! wait "$MUSIC_PROBE_PID"; then
    printf 'music-route-open\tFAIL\tsee music-tone.log\n' | tee -a "$RESULTS_FILE"
    exit 1
fi
printf 'music-route-open\tPASS\tfinite low-level signal\n' | tee -a "$RESULTS_FILE"

if grep -q 'format: S16_LE' "$DAC_ACTIVE" && grep -q 'rate: 44100' "$DAC_ACTIVE"; then
    printf 'physical-dac-format\tPASS\t44100/S16_LE\n' | tee -a "$RESULTS_FILE"
else
    printf 'physical-dac-format\tFAIL\tsee dac-active.txt\n' | tee -a "$RESULTS_FILE"
    exit 1
fi

if timeout 5 aplay -q -D acp_alarm -t raw -f "$FORMAT" -r "$SAMPLE_RATE" -c "$CHANNELS" "$ALARM_SIGNAL" >"$LAB_ROOT/alarm-tone.log" 2>&1; then
    printf 'alarm-route-open\tPASS\tfinite low-level signal\n' | tee -a "$RESULTS_FILE"
else
    printf 'alarm-route-open\tFAIL\tsee alarm-tone.log\n' | tee -a "$RESULTS_FILE"
    exit 1
fi

restore_services
sleep 3
for service in "${SERVICES[@]}"; do
    if service_was_active "$service"; then
        systemctl is-active --quiet "$service" || { echo "$service did not restart." >&2; exit 1; }
        printf 'rehearsal-service-%s\tPASS\tactive\n' "$service" | tee -a "$RESULTS_FILE"
    fi
done

cat <<EOF_WINDOW

Stage C0 direct alarm-bypass failback rehearsal is ACTIVE for at most $DURATION_SECONDS seconds.

Original Music Master: $ORIGINAL_MASTER_PERCENT%
Live-only control helper: $CONTROL_HELPER

Do not use the Settings volume faders during this temporary route. In a second
SSH session use:

  "$CONTROL_HELPER" master-zero
  "$CONTROL_HELPER" master-restore
  "$CONTROL_HELPER" status

Manual acceptance sequence:
  1. Confirm Plexamp starts and sounds normal.
  2. Confirm AirPlay starts, pauses Plexamp and sounds normal.
  3. Use master-zero and confirm Plexamp/AirPlay are silent.
  4. Let a real scheduled alarm ring while Music Master remains zero.
  5. Confirm the alarm is audible, takes over the screen and pauses music.
  6. Confirm Snooze stops it, it returns, and Dismiss ends the occurrence.
  7. Use master-restore and confirm music is audible again.

Press Enter to restore immediately, or wait for the automatic timeout.
Ctrl-C and ordinary failures trigger the same rollback.
EOF_WINDOW

if [[ -t 0 ]]; then read -r -t "$DURATION_SECONDS" _ || true; else sleep "$DURATION_SECONDS"; fi
rollback

cat <<EOF_DONE

Stage C0 direct alarm-bypass failback rehearsal complete and rolled back.

  Summary:       $RESULTS_FILE
  Detail:        $REPORT_FILE
  Snapshot:      $SNAPSHOT_DIR
  Mixer before:  $MIXER_BEFORE
  Mixer after:   $MIXER_AFTER
  Rollback failures: $ROLLBACK_FAILURES

The exact original direct shared mixer is active again. No route was retained.
EOF_DONE

[[ "$ROLLBACK_FAILURES" -eq 0 ]]
