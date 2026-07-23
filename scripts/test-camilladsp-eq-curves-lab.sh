#!/bin/bash
set -euo pipefail

# Fifth-stage A Clockwork Plex audio laboratory.
#
# Validate the intended three-band Master EQ shapes using a previously verified
# CamillaDSP 4.1.3 aarch64 binary. Every audio endpoint is on snd_aloop. The
# physical DAC is read before/after but is never opened by this script.

MODE=prepare
LAB_ROOT="${LAB_ROOT:-}"
LOOPBACK_INDEX="${LOOPBACK_INDEX:-7}"
CAMILLADSP_BINARY="${CAMILLADSP_BINARY:-}"
CAMILLADSP_VERSION="4.1.3"
SAMPLERATE=48000
FORMAT=S32_LE
CHANNELS=2
CHUNKSIZE=1024
DAC_HW_PARAMS="${DAC_HW_PARAMS:-/proc/asound/Pro/pcm0p/sub0/hw_params}"
DSP_PID=""
SINK_PID=""

usage() {
    cat <<'EOF_USAGE'
Usage: bash scripts/test-camilladsp-eq-curves-lab.sh [options]

Options:
  --prepare-only       Generate the loopback-only curve laboratory (default).
  --run                Validate configs and run all finite EQ curve tests.
  --binary PATH        Verified CamillaDSP 4.1.3 aarch64 executable.
  --lab-root PATH      Reuse or create PATH instead of a new /tmp directory.
  --loopback-index N   snd_aloop ALSA card index (default: 7).
  -h, --help           Show this help.

The script does not download or install software, load kernel modules, edit /etc,
restart services, alter mixer levels or open hw:Pro,0. It uses only two substreams
of an already-loaded snd_aloop card and finite generated test data.
EOF_USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prepare-only)
            MODE=prepare
            shift
            ;;
        --run)
            MODE=run
            shift
            ;;
        --binary)
            [[ $# -ge 2 ]] || { echo "--binary requires a path." >&2; exit 64; }
            CAMILLADSP_BINARY="$2"
            shift 2
            ;;
        --lab-root)
            [[ $# -ge 2 ]] || { echo "--lab-root requires a path." >&2; exit 64; }
            LAB_ROOT="$2"
            shift 2
            ;;
        --loopback-index)
            [[ $# -ge 2 ]] || { echo "--loopback-index requires a number." >&2; exit 64; }
            LOOPBACK_INDEX="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 64
            ;;
    esac
done

[[ "$LOOPBACK_INDEX" =~ ^[0-9]+$ ]] || { echo "Invalid loopback index: $LOOPBACK_INDEX" >&2; exit 64; }
[[ "$(uname -m)" == "aarch64" ]] || { echo "This laboratory expects aarch64; found $(uname -m)." >&2; exit 1; }

if [[ -z "$LAB_ROOT" ]]; then
    LAB_ROOT="$(mktemp -d /tmp/a-clockwork-plex-camilladsp-eq.XXXXXX)"
else
    mkdir -p "$LAB_ROOT"
    LAB_ROOT="$(cd "$LAB_ROOT" && pwd)"
fi

REPORT_FILE="$LAB_ROOT/report.txt"
RESULTS_FILE="$LAB_ROOT/results.tsv"
INPUT_RAW="$LAB_ROOT/multitone-48k-s32.raw"
DAC_BEFORE="$LAB_ROOT/dac-hw-params-before.txt"
DAC_AFTER="$LAB_ROOT/dac-hw-params-after.txt"
INPUT_PLAYBACK="hw:${LOOPBACK_INDEX},0,0"
DSP_CAPTURE="hw:${LOOPBACK_INDEX},1,0"
DSP_PLAYBACK="hw:${LOOPBACK_INDEX},0,1"
OUTPUT_CAPTURE="hw:${LOOPBACK_INDEX},1,1"

cleanup() {
    if [[ -n "$DSP_PID" ]]; then
        kill -INT "$DSP_PID" 2>/dev/null || true
        wait "$DSP_PID" 2>/dev/null || true
        DSP_PID=""
    fi
    if [[ -n "$SINK_PID" ]]; then
        kill "$SINK_PID" 2>/dev/null || true
        wait "$SINK_PID" 2>/dev/null || true
        SINK_PID=""
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

card_line="$(awk -v card="$LOOPBACK_INDEX" '$1 == card {print; exit}' /proc/asound/cards 2>/dev/null || true)"
if [[ -z "$card_line" ]] || ! grep -q 'Loopback' <<<"$card_line"; then
    echo "No snd_aloop card was found at ALSA index $LOOPBACK_INDEX." >&2
    exit 1
fi
for device in \
    "/dev/snd/pcmC${LOOPBACK_INDEX}D0p" \
    "/dev/snd/pcmC${LOOPBACK_INDEX}D1c"; do
    [[ -e "$device" ]] || { echo "Required loopback endpoint is missing: $device" >&2; exit 1; }
done

python3 - "$INPUT_RAW" "$SAMPLERATE" <<'PY_SIGNAL'
from __future__ import annotations

import array
import math
import sys
from pathlib import Path

path = Path(sys.argv[1])
rate = int(sys.argv[2])
duration = 3.0
frequencies = (63.0, 1000.0, 12000.0)
amplitude = int((2**31 - 1) * 0.05)
samples = array.array("i")
for frame in range(int(rate * duration)):
    value = sum(
        int(amplitude * math.sin(2.0 * math.pi * frequency * frame / rate))
        for frequency in frequencies
    )
    samples.extend((value, value))
if sys.byteorder != "little":
    samples.byteswap()
with path.open("wb") as handle:
    samples.tofile(handle)
PY_SIGNAL

cat >"$REPORT_FILE" <<EOF_REPORT
A Clockwork Plex CamillaDSP three-band EQ laboratory
Generated: $(date --iso-8601=seconds)
Directory: $LAB_ROOT
Mode: $MODE
Required CamillaDSP version: $CAMILLADSP_VERSION
Loopback card: hw:$LOOPBACK_INDEX
Input playback: $INPUT_PLAYBACK
DSP capture: $DSP_CAPTURE
DSP playback: $DSP_PLAYBACK
Output capture: $OUTPUT_CAPTURE
Format: $SAMPLERATE Hz / $FORMAT / stereo
Test frequencies: bass 63 Hz, mid 1000 Hz, treble 12000 Hz
Physical DAC opened: no
EOF_REPORT

cat <<EOF_STATUS

A Clockwork Plex CamillaDSP EQ-curve laboratory prepared.

  Directory:       $LAB_ROOT
  Loopback card:   hw:$LOOPBACK_INDEX
  Processing:      three-band Bass / Mid / Treble curve matrix
  Test format:     $SAMPLERATE Hz / $FORMAT / stereo

No production file, service, PCM definition or mixer level has been changed.
The physical DAC has not been opened.
EOF_STATUS

if [[ "$MODE" == prepare ]]; then
    cat <<EOF_PREPARE

Nothing has been executed. Run with the verified stage-four binary:

  bash scripts/test-camilladsp-eq-curves-lab.sh --run \\
    --binary /tmp/a-clockwork-plex-camilladsp.EXAMPLE/bin/camilladsp \\
    --lab-root "$LAB_ROOT"
EOF_PREPARE
    exit 0
fi

for command in python3 timeout aplay arecord cmp grep; do
    command -v "$command" >/dev/null 2>&1 || {
        echo "Required command not found: $command" >&2
        exit 1
    }
done
[[ -n "$CAMILLADSP_BINARY" ]] || { echo "--binary is required for --run." >&2; exit 64; }
[[ -x "$CAMILLADSP_BINARY" ]] || { echo "CamillaDSP executable not found: $CAMILLADSP_BINARY" >&2; exit 1; }

binary_version="$($CAMILLADSP_BINARY --version 2>&1 | head -n1)"
grep -Fq "$CAMILLADSP_VERSION" <<<"$binary_version" || {
    echo "Unexpected CamillaDSP binary version: $binary_version" >&2
    exit 1
}
echo "Binary version: $binary_version" | tee -a "$REPORT_FILE"

if [[ -r "$DAC_HW_PARAMS" ]]; then
    cat "$DAC_HW_PARAMS" >"$DAC_BEFORE"
else
    printf 'unavailable\n' >"$DAC_BEFORE"
fi

printf 'profile\tbass_db\tmid_db\ttreble_db\tresult\n' >"$RESULTS_FILE"
failures=0

write_config() {
    local config_file="$1"
    local title="$2"
    local bass_gain="$3"
    local mid_gain="$4"
    local treble_gain="$5"
    cat >"$config_file" <<EOF_CONFIG
---
title: "A Clockwork Plex EQ laboratory - $title"
description: "Loopback-only three-band response measurement"
devices:
  samplerate: $SAMPLERATE
  chunksize: $CHUNKSIZE
  queuelimit: 4
  silence_timeout: 0
  target_level: $CHUNKSIZE
  adjust_period: 1
  enable_rate_adjust: false
  resampler: null
  volume_ramp_time: 100
  volume_limit: 0.0
  capture:
    type: Alsa
    channels: $CHANNELS
    device: "$DSP_CAPTURE"
    format: $FORMAT
  playback:
    type: Alsa
    channels: $CHANNELS
    device: "$DSP_PLAYBACK"
    format: $FORMAT
filters:
  bass:
    type: Biquad
    parameters:
      type: Lowshelf
      freq: 125
      gain: $bass_gain
      slope: 6
  mid:
    type: Biquad
    parameters:
      type: Peaking
      freq: 1000
      gain: $mid_gain
      q: 0.7
  treble:
    type: Biquad
    parameters:
      type: Highshelf
      freq: 4000
      gain: $treble_gain
      slope: 6
pipeline:
  - type: Filter
    channels: [0, 1]
    names:
      - bass
      - mid
      - treble
EOF_CONFIG
}

run_profile() {
    local profile="$1"
    local bass_gain="$2"
    local mid_gain="$3"
    local treble_gain="$4"
    local expectation="$5"
    local config_file="$LAB_ROOT/${profile}.yml"
    local output_raw="$LAB_ROOT/${profile}-output.raw"
    local dsp_log="$LAB_ROOT/${profile}-camilladsp.log"
    local sink_log="$LAB_ROOT/${profile}-capture.log"
    local input_log="$LAB_ROOT/${profile}-playback.log"
    local analysis_line bass_db mid_db treble_db result

    write_config "$config_file" "$profile" "$bass_gain" "$mid_gain" "$treble_gain"
    if ! "$CAMILLADSP_BINARY" --check "$config_file" >>"$REPORT_FILE" 2>&1; then
        printf '%s\t-\t-\t-\tFAIL\n' "$profile" | tee -a "$RESULTS_FILE"
        failures=$((failures + 1))
        return 0
    fi

    rm -f "$output_raw"
    arecord -q -D "$OUTPUT_CAPTURE" -t raw -f "$FORMAT" -r "$SAMPLERATE" -c "$CHANNELS" -d 7 "$output_raw" >"$sink_log" 2>&1 &
    SINK_PID=$!
    sleep 0.25

    "$CAMILLADSP_BINARY" --gain=0 "$config_file" >"$dsp_log" 2>&1 &
    DSP_PID=$!
    sleep 1
    if ! kill -0 "$DSP_PID" 2>/dev/null; then
        printf '%s\t-\t-\t-\tFAIL\n' "$profile" | tee -a "$RESULTS_FILE"
        failures=$((failures + 1))
        DSP_PID=""
        wait "$SINK_PID" 2>/dev/null || true
        SINK_PID=""
        return 0
    fi

    if ! timeout 6 aplay -q -D "$INPUT_PLAYBACK" -t raw -f "$FORMAT" -r "$SAMPLERATE" -c "$CHANNELS" "$INPUT_RAW" >"$input_log" 2>&1; then
        printf '%s\t-\t-\t-\tFAIL\n' "$profile" | tee -a "$RESULTS_FILE"
        failures=$((failures + 1))
        kill -INT "$DSP_PID" 2>/dev/null || true
        wait "$DSP_PID" 2>/dev/null || true
        DSP_PID=""
        wait "$SINK_PID" 2>/dev/null || true
        SINK_PID=""
        return 0
    fi

    sleep 0.75
    kill -INT "$DSP_PID" 2>/dev/null || true
    wait "$DSP_PID" 2>/dev/null || true
    DSP_PID=""
    wait "$SINK_PID" 2>/dev/null || true
    SINK_PID=""

    analysis_line="$(python3 - "$INPUT_RAW" "$output_raw" "$SAMPLERATE" "$expectation" <<'PY_ANALYZE'
from __future__ import annotations

import array
import math
import sys
from pathlib import Path


def read_left(path: str) -> list[int]:
    values = array.array("i")
    file_path = Path(path)
    with file_path.open("rb") as handle:
        values.fromfile(handle, file_path.stat().st_size // values.itemsize)
    if sys.byteorder != "little":
        values.byteswap()
    return list(values[0::2])


def tone_level(samples: list[int], rate: int, frequency: float) -> float:
    length = rate
    if len(samples) < length:
        raise SystemExit("analysis window is too short")
    cos_sum = 0.0
    sin_sum = 0.0
    for index, value in enumerate(samples[:length]):
        angle = 2.0 * math.pi * frequency * index / rate
        cos_sum += value * math.cos(angle)
        sin_sum += value * math.sin(angle)
    return 2.0 * math.hypot(cos_sum, sin_sum) / length


input_path, output_path = sys.argv[1], sys.argv[2]
rate = int(sys.argv[3])
expectation = sys.argv[4]
frequencies = (63.0, 1000.0, 12000.0)
input_values = read_left(input_path)
output_values = read_left(output_path)
if not output_values or max(abs(value) for value in output_values) == 0:
    raise SystemExit("empty output")
threshold = max(abs(value) for value in output_values) * 0.02
active_start = next((index for index, value in enumerate(output_values) if abs(value) >= threshold), None)
if active_start is None:
    raise SystemExit("no active output")
start = active_start + int(rate * 0.75)
output_window = output_values[start:start + rate]
input_window = input_values[int(rate * 0.75):int(rate * 1.75)]
if len(output_window) < rate or len(input_window) < rate:
    raise SystemExit("insufficient steady-state data")

gains = []
for frequency in frequencies:
    input_level = tone_level(input_window, rate, frequency)
    output_level = tone_level(output_window, rate, frequency)
    gains.append(20.0 * math.log10(output_level / input_level))

bass, mid, treble = gains
checks = {
    "neutral": abs(bass) <= 0.25 and abs(mid) <= 0.25 and abs(treble) <= 0.25,
    "bass_boost": 3.5 <= bass <= 6.8 and abs(mid) <= 1.0 and abs(treble) <= 1.0,
    "mid_boost": abs(bass) <= 1.0 and 5.2 <= mid <= 6.8 and abs(treble) <= 1.0,
    "treble_boost": abs(bass) <= 1.0 and abs(mid) <= 1.0 and 3.5 <= treble <= 6.8,
    "bass_cut": -6.8 <= bass <= -3.5 and abs(mid) <= 1.0 and abs(treble) <= 1.0,
    "mid_cut": abs(bass) <= 1.0 and -6.8 <= mid <= -5.2 and abs(treble) <= 1.0,
    "treble_cut": abs(bass) <= 1.0 and abs(mid) <= 1.0 and -6.8 <= treble <= -3.5,
}
passed = checks.get(expectation, False)
print(f"{bass:.3f}\t{mid:.3f}\t{treble:.3f}\t{'PASS' if passed else 'FAIL'}")
PY_ANALYZE
    )" || analysis_line="-\t-\t-\tFAIL"

    IFS=$'\t' read -r bass_db mid_db treble_db result <<<"$analysis_line"
    printf '%s\t%s\t%s\t%s\t%s\n' "$profile" "$bass_db" "$mid_db" "$treble_db" "$result" | tee -a "$RESULTS_FILE"
    {
        echo "$profile: Bass ${bass_db} dB, Mid ${mid_db} dB, Treble ${treble_db} dB, $result"
        echo "  Config gains: bass=$bass_gain mid=$mid_gain treble=$treble_gain"
        echo "  CamillaDSP log: $dsp_log"
    } >>"$REPORT_FILE"
    if [[ "$result" != PASS ]]; then
        failures=$((failures + 1))
    fi
    sleep 0.25
}

run_profile neutral-start 0.0 0.0 0.0 neutral
run_profile bass-boost 6.0 0.0 0.0 bass_boost
run_profile mid-boost 0.0 6.0 0.0 mid_boost
run_profile treble-boost 0.0 0.0 6.0 treble_boost
run_profile bass-cut -6.0 0.0 0.0 bass_cut
run_profile mid-cut 0.0 -6.0 0.0 mid_cut
run_profile treble-cut 0.0 0.0 -6.0 treble_cut
run_profile neutral-return 0.0 0.0 0.0 neutral

if [[ -r "$DAC_HW_PARAMS" ]]; then
    cat "$DAC_HW_PARAMS" >"$DAC_AFTER"
else
    printf 'unavailable\n' >"$DAC_AFTER"
fi
if cmp -s "$DAC_BEFORE" "$DAC_AFTER"; then
    dac_result=PASS
else
    dac_result=FAIL
    failures=$((failures + 1))
fi
printf 'physical-dac-unchanged\t-\t-\t-\t%s\n' "$dac_result" | tee -a "$RESULTS_FILE"

{
    echo
    echo "Results:"
    cat "$RESULTS_FILE"
    echo
    echo "Physical DAC before:"
    cat "$DAC_BEFORE"
    echo
    echo "Physical DAC after:"
    cat "$DAC_AFTER"
} >>"$REPORT_FILE"

cat <<EOF_DONE

CamillaDSP three-band EQ laboratory complete.

  Binary:   $binary_version
  Summary:  $RESULTS_FILE
  Detail:   $REPORT_FILE
  Logs:     $LAB_ROOT/*-camilladsp.log
  Failures: $failures

Eight finite DSP starts were exercised entirely on ALSA Loopback.
The physical DAC was not opened.
EOF_DONE

[[ "$failures" -eq 0 ]]
