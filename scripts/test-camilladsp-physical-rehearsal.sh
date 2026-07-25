#!/bin/bash
set -euo pipefail

# Seventh-stage A Clockwork Plex audio laboratory.
#
# This is a rollback-first, time-limited rehearsal of the post-mix DSP route on
# the physical DAC. Prepare-only is the default. Activation requires an explicit
# confirmation token, snapshots the live ALSA fragment and service state before
# stopping audio, and always restores the original direct mixer on exit.

MODE=prepare
CONFIRM_TOKEN=""
LAB_ROOT="${LAB_ROOT:-}"
CAMILLADSP_BINARY="${CAMILLADSP_BINARY:-}"
PROJECT_USER="${PROJECT_USER:-${SUDO_USER:-$(id -un)}}"
LOOPBACK_INDEX="${LOOPBACK_INDEX:-7}"
DAC_CARD="${DAC_CARD:-Pro}"
DAC_DEVICE="${DAC_DEVICE:-0}"
DURATION_SECONDS="${DURATION_SECONDS:-180}"
ALSA_CONFIG="${ALSA_CONFIG:-/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf}"
MIXER_HELPER="${MIXER_HELPER:-/usr/local/bin/a-clockwork-plex-audio-mixer}"
DAC_HW_PARAMS="${DAC_HW_PARAMS:-/proc/asound/Pro/pcm0p/sub0/hw_params}"
CAMILLADSP_VERSION="4.1.3"
SAMPLE_RATE=44100
FORMAT=S16_LE
CHANNELS=2
CHUNKSIZE=1024
TARGET_LEVEL=2048
LIMIT_DB=-1.0
REHEARSAL_IPC_KEY=1094932536
REQUIRED_CONFIRMATION="STAGE-SEVEN-REAL-DAC"
SERVICES=(plexamp.service shairport-sync.service a-clockwork-plex.service)

DSP_PID=""
SUDO_KEEPALIVE_PID=""
DAC_INDEX=""
ROLLBACK_NEEDED=false
ROLLBACK_DONE=false
SNAPSHOT_READY=false
ORIGINAL_CONFIG_PRESENT=false
ROLLBACK_FAILURES=0

usage() {
    cat <<'EOF_USAGE'
Usage: bash scripts/test-camilladsp-physical-rehearsal.sh [options]

Options:
  --prepare-only       Generate and validate rehearsal files only (default).
  --activate           Run the time-limited physical-DAC rehearsal.
  --confirm TOKEN      Required with --activate: STAGE-SEVEN-REAL-DAC
  --binary PATH        Verified CamillaDSP 4.1.3 aarch64 executable.
  --duration SECONDS   Rehearsal window, 30 to 900 seconds (default: 180).
  --lab-root PATH      Reuse or create PATH instead of a new /var/tmp directory.
  --loopback-index N   Existing snd_aloop card index (default: 7).
  -h, --help           Show this help.

Prepare-only writes only inside its laboratory directory and opens no audio.
Activation temporarily stops Plexamp, Shairport Sync and the dashboard if they
were active, snapshots the live ALSA fragment, routes the existing source trims
and Master through ALSA Loopback and CamillaDSP, and then automatically restores
the original direct mixer and prior service states. There is no keep-active mode.
EOF_USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prepare-only) MODE=prepare; shift ;;
        --activate) MODE=activate; shift ;;
        --confirm)
            [[ $# -ge 2 ]] || { echo "--confirm requires a token." >&2; exit 64; }
            CONFIRM_TOKEN="$2"; shift 2 ;;
        --binary)
            [[ $# -ge 2 ]] || { echo "--binary requires a path." >&2; exit 64; }
            CAMILLADSP_BINARY="$2"; shift 2 ;;
        --duration)
            [[ $# -ge 2 ]] || { echo "--duration requires seconds." >&2; exit 64; }
            DURATION_SECONDS="$2"; shift 2 ;;
        --lab-root)
            [[ $# -ge 2 ]] || { echo "--lab-root requires a path." >&2; exit 64; }
            LAB_ROOT="$2"; shift 2 ;;
        --loopback-index)
            [[ $# -ge 2 ]] || { echo "--loopback-index requires a number." >&2; exit 64; }
            LOOPBACK_INDEX="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 64 ;;
    esac
done

[[ "$LOOPBACK_INDEX" =~ ^[0-9]+$ ]] || { echo "Invalid loopback index: $LOOPBACK_INDEX" >&2; exit 64; }
[[ "$DURATION_SECONDS" =~ ^[0-9]+$ ]] || { echo "Duration must be numeric." >&2; exit 64; }
(( DURATION_SECONDS >= 30 && DURATION_SECONDS <= 900 )) || { echo "Duration must be from 30 to 900 seconds." >&2; exit 64; }
[[ "$PROJECT_USER" =~ ^[A-Za-z0-9_.@-]+$ ]] || { echo "Invalid project user: $PROJECT_USER" >&2; exit 64; }
[[ "$DAC_CARD" =~ ^[A-Za-z0-9_.@-]+$ ]] || { echo "Invalid DAC card: $DAC_CARD" >&2; exit 64; }
[[ "$DAC_DEVICE" =~ ^[0-9]+$ ]] || { echo "Invalid DAC device: $DAC_DEVICE" >&2; exit 64; }
[[ "$(uname -m)" == "aarch64" ]] || { echo "This rehearsal expects aarch64; found $(uname -m)." >&2; exit 1; }
[[ "$EUID" -ne 0 ]] || { echo "Run this script as $PROJECT_USER, not with sudo; it invokes sudo only for guarded system changes." >&2; exit 1; }

if [[ "$MODE" == activate && "$CONFIRM_TOKEN" != "$REQUIRED_CONFIRMATION" ]]; then
    echo "Physical activation is blocked without: --confirm $REQUIRED_CONFIRMATION" >&2
    exit 64
fi

if [[ -z "$LAB_ROOT" ]]; then
    LAB_ROOT="$(mktemp -d /var/tmp/a-clockwork-plex-dsp-physical.XXXXXX)"
else
    mkdir -p "$LAB_ROOT"
    LAB_ROOT="$(cd "$LAB_ROOT" && pwd)"
fi
chmod 0700 "$LAB_ROOT"

REHEARSAL_ALSA="$LAB_ROOT/99-a-clockwork-plex-rehearsal.conf"
ALSA_VALIDATION_ROOT="$LAB_ROOT/alsa-validation.conf"
CAMILLADSP_CONFIG="$LAB_ROOT/camilladsp-physical.yml"
TEST_SIGNAL="$LAB_ROOT/low-level-997.raw"
REPORT_FILE="$LAB_ROOT/report.txt"
RESULTS_FILE="$LAB_ROOT/results.tsv"
DSP_LOG="$LAB_ROOT/camilladsp-physical.log"
SNAPSHOT_DIR="$LAB_ROOT/rollback-snapshot"
SERVICE_STATE_FILE="$LAB_ROOT/service-state.tsv"
ORIGINAL_SHA_FILE="$LAB_ROOT/original-alsa.sha256"
RESTORED_SHA_FILE="$LAB_ROOT/restored-alsa.sha256"
MIXER_BEFORE="$LAB_ROOT/mixer-before.json"
MIXER_AFTER="$LAB_ROOT/mixer-after.json"
DAC_BEFORE="$LAB_ROOT/dac-before.txt"
DAC_ACTIVE="$LAB_ROOT/dac-active.txt"
DAC_AFTER="$LAB_ROOT/dac-after.txt"

require_command() {
    command -v "$1" >/dev/null 2>&1 || { echo "Required command not found: $1" >&2; exit 1; }
}

for command in python3 aplay systemctl timeout cmp sha256sum grep awk; do
    require_command "$command"
done

cat >"$REHEARSAL_ALSA" <<EOF_ALSA
# A Clockwork Plex stage-seven physical rehearsal.
# Temporary only: existing source softvols and Master feed a Loopback dmix.

pcm.acp_dmix {
    type dmix
    ipc_key $REHEARSAL_IPC_KEY
    ipc_key_add_uid false
    ipc_perm 0666
    slave {
        pcm "hw:$LOOPBACK_INDEX,0,0"
        format $FORMAT
        rate $SAMPLE_RATE
        channels $CHANNELS
        period_size 1024
        buffer_size 8192
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
        description "A Clockwork Plex - Shared master (DSP rehearsal)"
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
    slave.pcm "acp_master"
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
        description "A Clockwork Plex - Alarm"
    }
}
EOF_ALSA

python3 - /usr/share/alsa/alsa.conf "$REHEARSAL_ALSA" "$ALSA_VALIDATION_ROOT" <<'PY_ALSA_ROOT'
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

cat >"$CAMILLADSP_CONFIG" <<EOF_CAMILLA
---
title: "A Clockwork Plex stage-seven physical rehearsal"
description: "44.1 kHz / S16_LE neutral post-mix route with rate adjust and limiter"
devices:
  samplerate: $SAMPLE_RATE
  chunksize: $CHUNKSIZE
  queuelimit: 4
  silence_timeout: 0
  target_level: $TARGET_LEVEL
  adjust_period: 1
  enable_rate_adjust: true
  resampler: null
  volume_ramp_time: 100
  volume_limit: 0.0
  capture:
    type: Alsa
    channels: $CHANNELS
    device: "hw:$LOOPBACK_INDEX,1,0"
    format: $FORMAT
  playback:
    type: Alsa
    channels: $CHANNELS
    device: "hw:CARD=$DAC_CARD,DEV=$DAC_DEVICE"
    format: $FORMAT
filters:
  bass:
    type: Biquad
    parameters: {type: Lowshelf, freq: 125, gain: 0.0, slope: 6}
  mid:
    type: Biquad
    parameters: {type: Peaking, freq: 1000, gain: 0.0, q: 0.7}
  treble:
    type: Biquad
    parameters: {type: Highshelf, freq: 4000, gain: 0.0, slope: 6}
  headroom:
    type: Gain
    parameters: {gain: 0.0, scale: dB, inverted: false, mute: false}
  safety_limiter:
    type: Limiter
    parameters: {soft_clip: false, clip_limit: $LIMIT_DB}
pipeline:
  - type: Filter
    channels: [0, 1]
    names: [bass, mid, treble, headroom, safety_limiter]
EOF_CAMILLA

python3 - "$TEST_SIGNAL" "$SAMPLE_RATE" <<'PY_SIGNAL'
from __future__ import annotations
import array
import math
import sys
from pathlib import Path

path = Path(sys.argv[1])
rate = int(sys.argv[2])
duration = 1.0
frequency = 997.0
amplitude = int((2**15 - 1) * 10.0 ** (-36.0 / 20.0))
samples = array.array("h")
for frame in range(int(rate * duration)):
    value = int(amplitude * math.sin(2.0 * math.pi * frequency * frame / rate))
    samples.extend((value, value))
if sys.byteorder != "little":
    samples.byteswap()
with path.open("wb") as handle:
    samples.tofile(handle)
PY_SIGNAL

cat >"$REPORT_FILE" <<EOF_REPORT
A Clockwork Plex stage-seven physical DSP rehearsal
Generated: $(date --iso-8601=seconds)
Directory: $LAB_ROOT
Mode: $MODE
Project user: $PROJECT_USER
Loopback card: hw:$LOOPBACK_INDEX
Physical DAC: hw:CARD=$DAC_CARD,DEV=$DAC_DEVICE
Rehearsal format: $SAMPLE_RATE Hz / $FORMAT / stereo
CamillaDSP target level: $TARGET_LEVEL samples
Rate adjust: enabled (ALSA Loopback clock tuning expected)
Limiter: $LIMIT_DB dBFS
Automatic rollback: mandatory
EOF_REPORT

printf 'check\tresult\tdetail\n' >"$RESULTS_FILE"

if ALSA_CONFIG_PATH="$ALSA_VALIDATION_ROOT" aplay -L >"$LAB_ROOT/alsa-pcms.txt" 2>"$LAB_ROOT/alsa-validation.log"; then
    printf 'alsa-config-parse\tPASS\ttemporary fragment parsed\n' | tee -a "$RESULTS_FILE"
else
    printf 'alsa-config-parse\tFAIL\tsee alsa-validation.log\n' | tee -a "$RESULTS_FILE"
    echo "Temporary ALSA rehearsal fragment did not parse." >&2
    exit 1
fi

if [[ -n "$CAMILLADSP_BINARY" ]]; then
    [[ -x "$CAMILLADSP_BINARY" ]] || { echo "CamillaDSP executable not found: $CAMILLADSP_BINARY" >&2; exit 1; }
    binary_version="$($CAMILLADSP_BINARY --version 2>&1 | head -n1)"
    grep -Fq "$CAMILLADSP_VERSION" <<<"$binary_version" || { echo "Unexpected CamillaDSP binary version: $binary_version" >&2; exit 1; }
    if "$CAMILLADSP_BINARY" --check "$CAMILLADSP_CONFIG" >>"$REPORT_FILE" 2>&1; then
        printf 'camilladsp-config-check\tPASS\t%s\n' "$binary_version" | tee -a "$RESULTS_FILE"
    else
        printf 'camilladsp-config-check\tFAIL\tsee report\n' | tee -a "$RESULTS_FILE"
        exit 1
    fi
else
    printf 'camilladsp-config-check\tSKIP\tprovide --binary PATH\n' | tee -a "$RESULTS_FILE"
fi

cat <<EOF_STATUS

A Clockwork Plex stage-seven rehearsal prepared.

  Directory:      $LAB_ROOT
  ALSA fragment:  $REHEARSAL_ALSA
  Camilla config: $CAMILLADSP_CONFIG
  Format:         $SAMPLE_RATE Hz / $FORMAT / stereo
  Duration:       $DURATION_SECONDS seconds maximum

No production file, service, mixer level or audio route has been changed.
EOF_STATUS

if [[ "$MODE" == prepare ]]; then
    cat <<EOF_PREPARE

Review the generated files and report first. Physical activation remains blocked
unless all of these are supplied explicitly:

  bash scripts/test-camilladsp-physical-rehearsal.sh --activate \
    --confirm $REQUIRED_CONFIRMATION \
    --binary /tmp/a-clockwork-plex-camilladsp.EXAMPLE/bin/camilladsp \
    --lab-root "$LAB_ROOT"

Activation is time-limited and always rolls back to the original direct mixer.
EOF_PREPARE
    exit 0
fi

[[ -n "$CAMILLADSP_BINARY" ]] || { echo "--binary is required for --activate." >&2; exit 64; }
for command in sudo fuser install curl pgrep; do require_command "$command"; done

card_line="$(awk -v card="$LOOPBACK_INDEX" '$1 == card {print; exit}' /proc/asound/cards 2>/dev/null || true)"
[[ -n "$card_line" ]] && grep -q 'Loopback' <<<"$card_line" || { echo "No snd_aloop card found at index $LOOPBACK_INDEX." >&2; exit 1; }
for endpoint in "/dev/snd/pcmC${LOOPBACK_INDEX}D0p" "/dev/snd/pcmC${LOOPBACK_INDEX}D1c"; do
    [[ -e "$endpoint" ]] || { echo "Required Loopback endpoint is missing: $endpoint" >&2; exit 1; }
done
if fuser "/dev/snd/pcmC${LOOPBACK_INDEX}D0p" "/dev/snd/pcmC${LOOPBACK_INDEX}D1c" >/dev/null 2>&1; then
    echo "A Loopback rehearsal endpoint is already in use." >&2
    fuser -v "/dev/snd/pcmC${LOOPBACK_INDEX}D0p" "/dev/snd/pcmC${LOOPBACK_INDEX}D1c" >&2 || true
    exit 1
fi
DAC_INDEX="$(awk -v wanted="$DAC_CARD" '$0 ~ "\[" wanted "[[:space:]]*\]" {print $1; exit}' /proc/asound/cards 2>/dev/null || true)"
[[ "$DAC_INDEX" =~ ^[0-9]+$ ]] || { echo "Physical DAC card $DAC_CARD was not found." >&2; exit 1; }
[[ -f "$ALSA_CONFIG" ]] || { echo "Live ALSA fragment is missing: $ALSA_CONFIG" >&2; exit 1; }
for expected in 'pcm.acp_dmix' 'pcm.acp_master_volume' 'pcm.acp_plexamp_volume' 'pcm.acp_airplay_volume' 'pcm.acp_alarm_volume' 'format S16_LE' 'rate 44100'; do
    grep -Fq "$expected" "$ALSA_CONFIG" || { echo "Live ALSA graph is not the expected stable shared mixer: missing $expected" >&2; exit 1; }
done
pgrep -x camilladsp >/dev/null 2>&1 && { echo "Another CamillaDSP process is already running; refusing physical rehearsal." >&2; exit 1; }

record_service_state() {
    : >"$SERVICE_STATE_FILE"
    local service active enabled
    for service in "${SERVICES[@]}"; do
        active="$(systemctl is-active "$service" 2>/dev/null || true)"
        enabled="$(systemctl is-enabled "$service" 2>/dev/null || true)"
        printf '%s\t%s\t%s\n' "$service" "$active" "$enabled" >>"$SERVICE_STATE_FILE"
    done
}

service_was_active() {
    awk -F '\t' -v wanted="$1" '$1 == wanted && $2 == "active" {found=1} END {exit(found ? 0 : 1)}' "$SERVICE_STATE_FILE"
}

stop_rehearsal_services() {
    local index service
    for ((index=${#SERVICES[@]}-1; index>=0; index--)); do
        service="${SERVICES[$index]}"
        if systemctl is-active --quiet "$service" 2>/dev/null; then
            sudo systemctl stop "$service"
        fi
    done
}

restore_original_services() {
    local service
    for service in "${SERVICES[@]}"; do
        if service_was_active "$service"; then
            sudo systemctl start "$service" || ROLLBACK_FAILURES=$((ROLLBACK_FAILURES + 1))
        fi
    done
}

stop_sudo_keepalive() {
    if [[ -n "$SUDO_KEEPALIVE_PID" ]]; then
        kill "$SUDO_KEEPALIVE_PID" 2>/dev/null || true
        wait "$SUDO_KEEPALIVE_PID" 2>/dev/null || true
        SUDO_KEEPALIVE_PID=""
    fi
}

stop_dsp() {
    if [[ -n "$DSP_PID" ]]; then
        kill -INT "$DSP_PID" 2>/dev/null || true
        for _ in {1..30}; do
            kill -0 "$DSP_PID" 2>/dev/null || break
            sleep 0.1
        done
        if kill -0 "$DSP_PID" 2>/dev/null; then kill "$DSP_PID" 2>/dev/null || true; fi
        wait "$DSP_PID" 2>/dev/null || true
        DSP_PID=""
    fi
}

rollback() {
    [[ "$ROLLBACK_DONE" == false ]] || return 0
    ROLLBACK_DONE=true
    set +e
    echo
    echo "Restoring the original direct audio graph..."
    sudo -v >/dev/null 2>&1 || ROLLBACK_FAILURES=$((ROLLBACK_FAILURES + 1))
    stop_rehearsal_services
    stop_dsp

    if [[ "$SNAPSHOT_READY" == true ]]; then
        if [[ "$ORIGINAL_CONFIG_PRESENT" == true ]]; then
            sudo cp -a "$SNAPSHOT_DIR/original-alsa.conf" "$ALSA_CONFIG" || ROLLBACK_FAILURES=$((ROLLBACK_FAILURES + 1))
        else
            sudo rm -f "$ALSA_CONFIG" || ROLLBACK_FAILURES=$((ROLLBACK_FAILURES + 1))
        fi
    fi

    restore_original_services
    for _ in {1..50}; do
        if [[ -r "$DAC_HW_PARAMS" ]] && grep -q 'rate: 44100' "$DAC_HW_PARAMS" 2>/dev/null; then break; fi
        sleep 0.2
    done
    stop_sudo_keepalive

    if pgrep -x camilladsp >/dev/null 2>&1; then
        printf 'rollback-camilladsp-stopped\tFAIL\tprocess still running\n' | tee -a "$RESULTS_FILE"
        ROLLBACK_FAILURES=$((ROLLBACK_FAILURES + 1))
    else
        printf 'rollback-camilladsp-stopped\tPASS\tno DSP process\n' | tee -a "$RESULTS_FILE"
    fi

    if [[ "$ORIGINAL_CONFIG_PRESENT" == true && -f "$ALSA_CONFIG" ]]; then
        sudo sha256sum "$ALSA_CONFIG" | awk '{print $1}' >"$RESTORED_SHA_FILE" 2>/dev/null || true
        if cmp -s "$ORIGINAL_SHA_FILE" "$RESTORED_SHA_FILE"; then
            printf 'rollback-alsa-config\tPASS\toriginal checksum restored\n' | tee -a "$RESULTS_FILE"
        else
            printf 'rollback-alsa-config\tFAIL\tchecksum mismatch\n' | tee -a "$RESULTS_FILE"
            ROLLBACK_FAILURES=$((ROLLBACK_FAILURES + 1))
        fi
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

    if [[ -r "$DAC_HW_PARAMS" ]]; then cat "$DAC_HW_PARAMS" >"$DAC_AFTER"; else printf 'unavailable\n' >"$DAC_AFTER"; fi
    if [[ -x "$MIXER_HELPER" ]]; then
        sudo "$MIXER_HELPER" status >"$MIXER_AFTER" 2>/dev/null || true
        if [[ -s "$MIXER_BEFORE" && -s "$MIXER_AFTER" ]] && cmp -s "$MIXER_BEFORE" "$MIXER_AFTER"; then
            printf 'rollback-mixer-state\tPASS\tcontrols unchanged\n' | tee -a "$RESULTS_FILE"
        elif [[ -s "$MIXER_BEFORE" && -s "$MIXER_AFTER" ]]; then
            printf 'rollback-mixer-state\tWARN\tstatus differs; inspect JSON snapshots\n' | tee -a "$RESULTS_FILE"
        fi
    fi

    ROLLBACK_NEEDED=false
    {
        echo
        echo "Rollback completed: $(date --iso-8601=seconds)"
        echo "Rollback failures: $ROLLBACK_FAILURES"
        echo "Restored DAC hw_params:"
        cat "$DAC_AFTER"
    } >>"$REPORT_FILE"
    set -e
}

on_exit() {
    local status=$?
    trap - EXIT
    if [[ "$ROLLBACK_NEEDED" == true ]]; then rollback; fi
    if (( ROLLBACK_FAILURES > 0 )) && (( status == 0 )); then status=1; fi
    exit "$status"
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

sudo -v
(
    while sleep 30; do sudo -n true >/dev/null 2>&1 || exit 0; done
) &
SUDO_KEEPALIVE_PID=$!
sudo install -d -m 0700 "$SNAPSHOT_DIR"
record_service_state
sudo cp -a "$ALSA_CONFIG" "$SNAPSHOT_DIR/original-alsa.conf"
ORIGINAL_CONFIG_PRESENT=true
sudo sha256sum "$ALSA_CONFIG" | awk '{print $1}' >"$ORIGINAL_SHA_FILE"
if [[ -x "$MIXER_HELPER" ]]; then sudo "$MIXER_HELPER" status >"$MIXER_BEFORE" 2>/dev/null || true; fi
if [[ -r "$DAC_HW_PARAMS" ]]; then cat "$DAC_HW_PARAMS" >"$DAC_BEFORE"; else printf 'unavailable\n' >"$DAC_BEFORE"; fi
sudo fuser -v "/dev/snd/pcmC${DAC_INDEX}D${DAC_DEVICE}p" >"$LAB_ROOT/dac-owners-before.txt" 2>&1 || true
SNAPSHOT_READY=true
ROLLBACK_NEEDED=true
printf 'rollback-snapshot\tPASS\t%s\n' "$SNAPSHOT_DIR" | tee -a "$RESULTS_FILE"

# Politely pause Plexamp before the maintenance stop. Failure is harmless because
# the service is stopped immediately afterwards.
curl -fsS --max-time 2 http://localhost:32500/player/playback/pause >/dev/null 2>&1 || true
stop_rehearsal_services
sleep 1

if sudo fuser "/dev/snd/pcmC${DAC_INDEX}D${DAC_DEVICE}p" >/dev/null 2>&1; then
    echo "The physical DAC playback device is still owned after stopping services." >&2
    sudo fuser -v "/dev/snd/pcmC${DAC_INDEX}D${DAC_DEVICE}p" >>"$REPORT_FILE" 2>&1 || true
    exit 1
fi
printf 'physical-dac-released\tPASS\tno playback owner\n' | tee -a "$RESULTS_FILE"

sudo install -o root -g root -m 0644 "$REHEARSAL_ALSA" "$ALSA_CONFIG"
printf 'temporary-alsa-route\tPASS\tloopback dmix installed\n' | tee -a "$RESULTS_FILE"

"$CAMILLADSP_BINARY" --gain=0 "$CAMILLADSP_CONFIG" >"$DSP_LOG" 2>&1 &
DSP_PID=$!
sleep 2
kill -0 "$DSP_PID" 2>/dev/null || { echo "CamillaDSP exited during physical-DAC startup. See $DSP_LOG" >&2; exit 1; }
printf 'camilladsp-physical-start\tPASS\tpid=%s\n' "$DSP_PID" | tee -a "$RESULTS_FILE"
if grep -q 'Capture device supports rate adjust' "$DSP_LOG"; then
    printf 'loopback-rate-adjust\tPASS\tcapture clock tuning available\n' | tee -a "$RESULTS_FILE"
else
    printf 'loopback-rate-adjust\tWARN\tcapability line not yet present; inspect DSP log\n' | tee -a "$RESULTS_FILE"
fi

if [[ -r "$DAC_HW_PARAMS" ]]; then cat "$DAC_HW_PARAMS" >"$DAC_ACTIVE"; else printf 'unavailable\n' >"$DAC_ACTIVE"; fi
if grep -q 'format: S16_LE' "$DAC_ACTIVE" && grep -q 'rate: 44100' "$DAC_ACTIVE"; then
    printf 'physical-dac-format\tPASS\t44100/S16_LE\n' | tee -a "$RESULTS_FILE"
else
    printf 'physical-dac-format\tFAIL\tsee dac-active.txt\n' | tee -a "$RESULTS_FILE"
    exit 1
fi

if timeout 5 aplay -q -D acp_plexamp -t raw -f "$FORMAT" -r "$SAMPLE_RATE" -c "$CHANNELS" "$TEST_SIGNAL" >"$LAB_ROOT/low-level-tone.log" 2>&1; then
    printf 'low-level-tone-route\tPASS\t-36 dBFS finite signal\n' | tee -a "$RESULTS_FILE"
else
    printf 'low-level-tone-route\tFAIL\tsee low-level-tone.log\n' | tee -a "$RESULTS_FILE"
    exit 1
fi

restore_original_services
sleep 3
for service in "${SERVICES[@]}"; do
    if service_was_active "$service"; then
        if systemctl is-active --quiet "$service"; then
            printf 'rehearsal-service-%s\tPASS\tactive\n' "$service" | tee -a "$RESULTS_FILE"
        else
            printf 'rehearsal-service-%s\tFAIL\tnot active\n' "$service" | tee -a "$RESULTS_FILE"
            exit 1
        fi
    fi
done
kill -0 "$DSP_PID" 2>/dev/null || { echo "CamillaDSP did not survive service restoration." >&2; exit 1; }
printf 'rehearsal-route-active\tPASS\tCamillaDSP survived source startup\n' | tee -a "$RESULTS_FILE"

cat <<EOF_WINDOW

Stage-seven physical rehearsal is ACTIVE for at most $DURATION_SECONDS seconds.

Please test, at low volume:
  1. Plexamp playback starts and sounds normal.
  2. AirPlay connects, pauses Plexamp and plays normally.
  3. AirPlay pauses/ends cleanly and the dashboard handoff remains sensible.

Press Enter to restore immediately, or wait for the automatic timeout.
Ctrl-C also triggers the same rollback.
EOF_WINDOW

if (( DURATION_SECONDS >= 660 )); then
    echo "This extended window is long enough to observe the full ten-minute AirPlay hold."
else
    echo "The full ten-minute AirPlay hold is intentionally deferred to an extended rehearsal."
fi

if [[ -t 0 ]]; then
    read -r -t "$DURATION_SECONDS" _ || true
else
    sleep "$DURATION_SECONDS"
fi

rollback

cat <<EOF_DONE

Stage-seven physical rehearsal complete and rolled back.

  Summary:  $RESULTS_FILE
  Detail:   $REPORT_FILE
  DSP log:  $DSP_LOG
  Snapshot: $SNAPSHOT_DIR
  Rollback failures: $ROLLBACK_FAILURES

The original direct shared mixer is active again. No production DSP route was retained.
EOF_DONE

[[ "$ROLLBACK_FAILURES" -eq 0 ]]
