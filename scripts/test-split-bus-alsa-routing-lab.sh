#!/bin/bash
set -euo pipefail

# A Clockwork Plex split-bus ALSA routing laboratory.
# Proves that separate stereo source PCMs map music to loopback channels 0/1
# and alarm to channels 2/3 before the real-service physical rehearsal.
# The default mode prepares files only. --run uses snd_aloop exclusively.

MODE=prepare
LAB_ROOT="${LAB_ROOT:-}"
LOOPBACK_INDEX="${LOOPBACK_INDEX:-7}"
SAMPLERATE=44100
FORMAT=S16_LE
SOURCE_CHANNELS=2
BUS_CHANNELS=4
PERIOD_SIZE=1024
BUFFER_SIZE=8192
REHEARSAL_IPC_KEY=1094933536
DAC_HW_PARAMS="${DAC_HW_PARAMS:-/proc/asound/Pro/pcm0p/sub0/hw_params}"
CAPTURE_PID=""
PLAYBACK_PIDS=()

usage() {
    cat <<'EOF_USAGE'
Usage: bash scripts/test-split-bus-alsa-routing-lab.sh [options]

Options:
  --prepare-only       Generate and validate temporary routing files only (default).
  --run                Run finite music/alarm lane-routing measurements.
  --lab-root PATH      Reuse or create PATH instead of a new /tmp directory.
  --loopback-index N   Existing snd_aloop ALSA card index (default: 7).
  -h, --help           Show this help.

The laboratory never uses sudo, loads modules, edits /etc, restarts services,
changes mixer controls or opens the physical DAC. It creates a temporary ALSA
configuration under the laboratory directory and uses ALSA_CONFIG_PATH so the
live A Clockwork Plex graph is not read or replaced.

Music is routed to loopback channels 0/1 and alarm to channels 2/3. The run
checks each lane separately, checks simultaneous source opens, measures digital
crosstalk and confirms the physical DAC hw_params remained unchanged.
EOF_USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prepare-only) MODE=prepare; shift ;;
        --run) MODE=run; shift ;;
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

[[ "$LOOPBACK_INDEX" =~ ^[0-9]+$ ]] || {
    echo "Invalid loopback index: $LOOPBACK_INDEX" >&2
    exit 64
}

if [[ -z "$LAB_ROOT" ]]; then
    LAB_ROOT="$(mktemp -d /tmp/a-clockwork-plex-split-route.XXXXXX)"
else
    mkdir -p "$LAB_ROOT"
    LAB_ROOT="$(cd "$LAB_ROOT" && pwd)"
fi

ALSA_FRAGMENT="$LAB_ROOT/split-bus-routing.conf"
ALSA_ROOT="$LAB_ROOT/alsa-root.conf"
MUSIC_SIGNAL="$LAB_ROOT/music-997.raw"
ALARM_SIGNAL="$LAB_ROOT/alarm-2711.raw"
REPORT_FILE="$LAB_ROOT/report.txt"
RESULTS_FILE="$LAB_ROOT/results.tsv"
DAC_BEFORE="$LAB_ROOT/dac-hw-params-before.txt"
DAC_AFTER="$LAB_ROOT/dac-hw-params-after.txt"
MUSIC_CAPTURE="$LAB_ROOT/music-only.raw"
ALARM_CAPTURE="$LAB_ROOT/alarm-only.raw"
CONCURRENT_CAPTURE="$LAB_ROOT/concurrent.raw"
BUS_PLAYBACK="hw:${LOOPBACK_INDEX},0,0"
BUS_CAPTURE="hw:${LOOPBACK_INDEX},1,0"

cleanup() {
    local pid
    if [[ -n "$CAPTURE_PID" ]]; then
        kill "$CAPTURE_PID" 2>/dev/null || true
        wait "$CAPTURE_PID" 2>/dev/null || true
        CAPTURE_PID=""
    fi
    for pid in "${PLAYBACK_PIDS[@]:-}"; do
        if [[ -n "$pid" ]]; then
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
        fi
    done
    PLAYBACK_PIDS=()
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

cat >"$ALSA_FRAGMENT" <<EOF_ALSA
# A Clockwork Plex isolated split-bus routing laboratory.
# Temporary only; loaded through ALSA_CONFIG_PATH.

pcm.acp_split_lab_dmix {
    type dmix
    ipc_key $REHEARSAL_IPC_KEY
    ipc_key_add_uid false
    ipc_perm 0600
    slave {
        pcm "$BUS_PLAYBACK"
        format $FORMAT
        rate $SAMPLERATE
        channels $BUS_CHANNELS
        period_size $PERIOD_SIZE
        buffer_size $BUFFER_SIZE
    }
    bindings {
        0 0
        1 1
        2 2
        3 3
    }
}

pcm.acp_split_lab_music_route {
    type route
    slave {
        pcm "acp_split_lab_dmix"
        channels $BUS_CHANNELS
    }
    ttable {
        0.0 1
        1.1 1
    }
}

pcm.acp_split_lab_music {
    type plug
    slave.pcm "acp_split_lab_music_route"
    hint {
        show on
        description "A Clockwork Plex lab - Music lane 0/1"
    }
}

pcm.acp_split_lab_alarm_route {
    type route
    slave {
        pcm "acp_split_lab_dmix"
        channels $BUS_CHANNELS
    }
    ttable {
        0.2 1
        1.3 1
    }
}

pcm.acp_split_lab_alarm {
    type plug
    slave.pcm "acp_split_lab_alarm_route"
    hint {
        show on
        description "A Clockwork Plex lab - Alarm lane 2/3"
    }
}
EOF_ALSA

python3 - /usr/share/alsa/alsa.conf "$ALSA_FRAGMENT" "$ALSA_ROOT" <<'PY_ALSA_ROOT'
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

python3 - "$MUSIC_SIGNAL" "$ALARM_SIGNAL" "$SAMPLERATE" <<'PY_SIGNALS'
from __future__ import annotations

import array
import math
import sys
from pathlib import Path

music_path = Path(sys.argv[1])
alarm_path = Path(sys.argv[2])
rate = int(sys.argv[3])
duration = 2.0
amplitude = int((2**15 - 1) * 0.10)


def write_stereo(path: Path, frequency: float) -> None:
    samples = array.array("h")
    for frame in range(int(rate * duration)):
        value = int(amplitude * math.sin(2.0 * math.pi * frequency * frame / rate))
        samples.extend((value, value))
    if sys.byteorder != "little":
        samples.byteswap()
    with path.open("wb") as handle:
        samples.tofile(handle)


write_stereo(music_path, 997.0)
write_stereo(alarm_path, 2711.0)
PY_SIGNALS

cat >"$REPORT_FILE" <<EOF_REPORT
A Clockwork Plex split-bus ALSA routing laboratory
Generated: $(date --iso-8601=seconds)
Directory: $LAB_ROOT
Mode: $MODE
Loopback card: hw:$LOOPBACK_INDEX
Source format: $SAMPLERATE Hz / $FORMAT / stereo
Shared bus: $SAMPLERATE Hz / $FORMAT / four channels
Music mapping: source L/R -> bus 0/1
Alarm mapping: source L/R -> bus 2/3
Physical DAC opened: no
EOF_REPORT

printf 'profile\tchannel_0_rms\tchannel_1_rms\tchannel_2_rms\tchannel_3_rms\tresult\n' >"$RESULTS_FILE"

for command in python3 aplay; do
    command -v "$command" >/dev/null 2>&1 || {
        echo "Required command not found: $command" >&2
        exit 1
    }
done

if ALSA_CONFIG_PATH="$ALSA_ROOT" aplay -L >"$LAB_ROOT/alsa-pcms.txt" 2>"$LAB_ROOT/alsa-validation.log"; then
    grep -Fxq 'acp_split_lab_music' "$LAB_ROOT/alsa-pcms.txt" || {
        echo "Temporary music PCM was not registered." >&2
        exit 1
    }
    grep -Fxq 'acp_split_lab_alarm' "$LAB_ROOT/alsa-pcms.txt" || {
        echo "Temporary alarm PCM was not registered." >&2
        exit 1
    }
else
    echo "Temporary ALSA split-bus routing configuration did not parse." >&2
    exit 1
fi

cat <<EOF_STATUS

A Clockwork Plex split-bus ALSA routing laboratory prepared.

  Directory:       $LAB_ROOT
  Temporary music: acp_split_lab_music -> channels 0/1
  Temporary alarm: acp_split_lab_alarm -> channels 2/3
  Shared bus:      $BUS_PLAYBACK
  Capture probe:   $BUS_CAPTURE

No production file, service, PCM definition or mixer level has been changed.
The physical DAC has not been opened.
EOF_STATUS

if [[ "$MODE" == prepare ]]; then
    cat <<EOF_PREPARE

Nothing has been played or recorded. Run while snd_aloop remains loaded:

  bash scripts/test-split-bus-alsa-routing-lab.sh --run \
    --lab-root "$LAB_ROOT"
EOF_PREPARE
    exit 0
fi

for command in arecord timeout cmp grep awk fuser sleep; do
    command -v "$command" >/dev/null 2>&1 || {
        echo "Required command not found: $command" >&2
        exit 1
    }
done

card_line="$(awk -v card="$LOOPBACK_INDEX" '$1 == card {print; exit}' /proc/asound/cards 2>/dev/null || true)"
if [[ -z "$card_line" ]] || ! grep -q 'Loopback' <<<"$card_line"; then
    echo "No snd_aloop card was found at ALSA index $LOOPBACK_INDEX." >&2
    exit 1
fi

for endpoint in \
    "/dev/snd/pcmC${LOOPBACK_INDEX}D0p" \
    "/dev/snd/pcmC${LOOPBACK_INDEX}D1c"; do
    [[ -e "$endpoint" ]] || {
        echo "Required loopback endpoint is missing: $endpoint" >&2
        exit 1
    }
done

if fuser \
    "/dev/snd/pcmC${LOOPBACK_INDEX}D0p" \
    "/dev/snd/pcmC${LOOPBACK_INDEX}D1c" >/dev/null 2>&1; then
    echo "A split-bus laboratory endpoint is already in use." >&2
    fuser -v \
        "/dev/snd/pcmC${LOOPBACK_INDEX}D0p" \
        "/dev/snd/pcmC${LOOPBACK_INDEX}D1c" >&2 || true
    exit 1
fi

if [[ -r "$DAC_HW_PARAMS" ]]; then
    cat "$DAC_HW_PARAMS" >"$DAC_BEFORE"
else
    printf 'unavailable\n' >"$DAC_BEFORE"
fi

start_capture() {
    local output="$1"
    local log="$2"
    rm -f "$output"
    arecord -q \
        -D "$BUS_CAPTURE" \
        -t raw \
        -f "$FORMAT" \
        -r "$SAMPLERATE" \
        -c "$BUS_CHANNELS" \
        -d 6 \
        "$output" >"$log" 2>&1 &
    CAPTURE_PID=$!
    sleep 0.3
}

finish_capture() {
    if [[ -n "$CAPTURE_PID" ]]; then
        wait "$CAPTURE_PID" 2>/dev/null || true
        CAPTURE_PID=""
    fi
}

play_source() {
    local pcm="$1"
    local signal="$2"
    local log="$3"
    ALSA_CONFIG_PATH="$ALSA_ROOT" timeout 5 aplay -q \
        -D "$pcm" \
        -t raw \
        -f "$FORMAT" \
        -r "$SAMPLERATE" \
        -c "$SOURCE_CHANNELS" \
        "$signal" >"$log" 2>&1
}

start_capture "$MUSIC_CAPTURE" "$LAB_ROOT/music-capture.log"
play_source acp_split_lab_music "$MUSIC_SIGNAL" "$LAB_ROOT/music-playback.log"
finish_capture
sleep 0.5

start_capture "$ALARM_CAPTURE" "$LAB_ROOT/alarm-capture.log"
play_source acp_split_lab_alarm "$ALARM_SIGNAL" "$LAB_ROOT/alarm-playback.log"
finish_capture
sleep 0.5

start_capture "$CONCURRENT_CAPTURE" "$LAB_ROOT/concurrent-capture.log"
(
    play_source acp_split_lab_music "$MUSIC_SIGNAL" "$LAB_ROOT/concurrent-music.log"
) &
PLAYBACK_PIDS+=("$!")
sleep 0.05
(
    play_source acp_split_lab_alarm "$ALARM_SIGNAL" "$LAB_ROOT/concurrent-alarm.log"
) &
PLAYBACK_PIDS+=("$!")

playback_failed=0
for pid in "${PLAYBACK_PIDS[@]}"; do
    wait "$pid" || playback_failed=1
done
PLAYBACK_PIDS=()
finish_capture

if (( playback_failed != 0 )); then
    echo "One or more concurrent source playbacks failed." >&2
    exit 1
fi

analysis_output="$(
python3 - \
    "$MUSIC_CAPTURE" \
    "$ALARM_CAPTURE" \
    "$CONCURRENT_CAPTURE" \
    "$BUS_CHANNELS" <<'PY_ANALYSE'
from __future__ import annotations

import array
import math
import sys
from pathlib import Path

music_path = Path(sys.argv[1])
alarm_path = Path(sys.argv[2])
concurrent_path = Path(sys.argv[3])
channels = int(sys.argv[4])
active_minimum = 200.0
inactive_maximum = 5.0


def channel_rms(path: Path) -> list[float]:
    values = array.array("h")
    with path.open("rb") as handle:
        count = path.stat().st_size // values.itemsize
        values.fromfile(handle, count)
    if sys.byteorder != "little":
        values.byteswap()
    if not values or len(values) % channels:
        raise SystemExit(f"invalid capture: {path}")
    result: list[float] = []
    for channel in range(channels):
        lane = values[channel::channels]
        square_mean = sum(sample * sample for sample in lane) / len(lane)
        result.append(math.sqrt(square_mean))
    return result


def classify(name: str, rms: list[float], active: tuple[int, ...]) -> bool:
    passed = True
    for index, value in enumerate(rms):
        if index in active:
            passed = passed and value >= active_minimum
        else:
            passed = passed and value <= inactive_maximum
    print(
        "\t".join(
            [name, *(f"{value:.3f}" for value in rms), "PASS" if passed else "FAIL"]
        )
    )
    return passed


checks = [
    classify("music-lane", channel_rms(music_path), (0, 1)),
    classify("alarm-lane", channel_rms(alarm_path), (2, 3)),
    classify("concurrent-lanes", channel_rms(concurrent_path), (0, 1, 2, 3)),
]
raise SystemExit(0 if all(checks) else 1)
PY_ANALYSE
)" || {
    printf '%s\n' "$analysis_output" | tee -a "$RESULTS_FILE"
    echo "Split-bus channel-routing analysis failed." >&2
    exit 1
}
printf '%s\n' "$analysis_output" | tee -a "$RESULTS_FILE"

if [[ -r "$DAC_HW_PARAMS" ]]; then
    cat "$DAC_HW_PARAMS" >"$DAC_AFTER"
else
    printf 'unavailable\n' >"$DAC_AFTER"
fi

if cmp -s "$DAC_BEFORE" "$DAC_AFTER"; then
    printf 'physical-dac-unchanged\t-\t-\t-\t-\tPASS\n' | tee -a "$RESULTS_FILE"
else
    printf 'physical-dac-unchanged\t-\t-\t-\t-\tFAIL\n' | tee -a "$RESULTS_FILE"
    echo "The physical DAC hw_params changed during the loopback-only laboratory." >&2
    exit 1
fi

cat <<EOF_DONE

Results:
$(cat "$RESULTS_FILE")

Failures: 0
Split-bus ALSA routing laboratory passed. Music occupied channels 0/1, alarm
occupied channels 2/3, both source PCMs opened concurrently, and no digital
crosstalk crossed between the lanes.

  Summary: $RESULTS_FILE
  Detail:  $REPORT_FILE
  Logs:    $LAB_ROOT/*.log
EOF_DONE
