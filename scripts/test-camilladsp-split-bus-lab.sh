#!/bin/bash
set -euo pipefail

# A Clockwork Plex split-bus CamillaDSP laboratory.
# Proves that Music Master and music EQ affect Plexamp/AirPlay only, while the
# alarm lane bypasses both and rejoins immediately before the final limiter.
# The default mode prepares files only. --run uses snd_aloop exclusively.

MODE=prepare
LAB_ROOT="${LAB_ROOT:-}"
LOOPBACK_INDEX="${LOOPBACK_INDEX:-7}"
CAMILLADSP_BINARY="${CAMILLADSP_BINARY:-}"
CAMILLADSP_VERSION="4.1.3"
SAMPLERATE=48000
FORMAT=S32_LE
CAPTURE_CHANNELS=4
PLAYBACK_CHANNELS=2
CHUNKSIZE=1024
LIMIT_DB=-1.0
DAC_HW_PARAMS="${DAC_HW_PARAMS:-/proc/asound/Pro/pcm0p/sub0/hw_params}"
DSP_PID=""
SINK_PID=""

usage() {
    cat <<'EOF_USAGE'
Usage: bash scripts/test-camilladsp-split-bus-lab.sh [options]

Options:
  --prepare-only       Generate the isolated laboratory files only (default).
  --run                Run the split music/alarm bus measurements.
  --binary PATH        Verified CamillaDSP 4.1.3 aarch64 executable.
  --lab-root PATH      Reuse or create PATH instead of a new /tmp directory.
  --loopback-index N   Existing snd_aloop ALSA card index (default: 7).
  -h, --help           Show this help.

This laboratory never uses sudo, loads modules, edits /etc, restarts services,
changes mixer controls or opens the physical DAC. Music occupies loopback
channels 0/1 and alarm occupies channels 2/3. CamillaDSP applies Music Master
and EQ only to channels 0/1, combines both buses, then applies a final limiter.
EOF_USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prepare-only) MODE=prepare; shift ;;
        --run) MODE=run; shift ;;
        --binary)
            [[ $# -ge 2 ]] || { echo "--binary requires a path." >&2; exit 64; }
            CAMILLADSP_BINARY="$2"; shift 2 ;;
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

if [[ -z "$LAB_ROOT" ]]; then
    LAB_ROOT="$(mktemp -d /tmp/a-clockwork-plex-split-bus.XXXXXX)"
else
    mkdir -p "$LAB_ROOT"
    LAB_ROOT="$(cd "$LAB_ROOT" && pwd)"
fi

REPORT_FILE="$LAB_ROOT/report.txt"
RESULTS_FILE="$LAB_ROOT/results.tsv"
ACTIVE_CONFIG="$LAB_ROOT/active.yml"
DSP_LOG="$LAB_ROOT/camilladsp-split-bus.log"
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

write_config() {
    local path="$1" title="$2" music_eq="$3" music_master="$4" music_extra="$5"
    cat >"$path" <<EOF_CONFIG
---
title: "A Clockwork Plex split-bus laboratory - $title"
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
    channels: $CAPTURE_CHANNELS
    device: "$DSP_CAPTURE"
    format: $FORMAT
  playback:
    type: Alsa
    channels: $PLAYBACK_CHANNELS
    device: "$DSP_PLAYBACK"
    format: $FORMAT
filters:
  music_eq:
    type: Biquad
    parameters: {type: Peaking, freq: 1000, gain: $music_eq, q: 1.0}
  music_master:
    type: Gain
    parameters: {gain: $music_master, scale: dB, inverted: false, mute: false}
  music_test_gain:
    type: Gain
    parameters: {gain: $music_extra, scale: dB, inverted: false, mute: false}
  final_safety_limiter:
    type: Limiter
    parameters: {soft_clip: false, clip_limit: $LIMIT_DB}
mixers:
  combine_music_and_alarm:
    description: "Music 0/1 plus independent alarm 2/3 into stereo output"
    channels: {in: 4, out: 2}
    mapping:
      - dest: 0
        sources:
          - {channel: 0, gain: 0, scale: dB, inverted: false}
          - {channel: 2, gain: 0, scale: dB, inverted: false}
      - dest: 1
        sources:
          - {channel: 1, gain: 0, scale: dB, inverted: false}
          - {channel: 3, gain: 0, scale: dB, inverted: false}
pipeline:
  - type: Filter
    description: "Music-only EQ and Music Master"
    channels: [0, 1]
    names: [music_eq, music_master, music_test_gain]
  - type: Mixer
    description: "Join alarm after music processing"
    name: combine_music_and_alarm
  - type: Filter
    description: "Final limiter protects the shared DAC output"
    channels: [0, 1]
    names: [final_safety_limiter]
EOF_CONFIG
}

write_config "$LAB_ROOT/neutral.yml" neutral 0.0 0.0 0.0
write_config "$LAB_ROOT/music-master-minus-20.yml" music-master-minus-20 0.0 -20.0 0.0
write_config "$LAB_ROOT/music-eq-plus-6.yml" music-eq-plus-6 6.0 0.0 0.0
write_config "$LAB_ROOT/limiter-stress.yml" limiter-stress 0.0 0.0 12.0

python3 - "$LAB_ROOT" "$SAMPLERATE" <<'PY_SIGNAL'
from __future__ import annotations

import array
import math
import sys
from pathlib import Path

root = Path(sys.argv[1])
rate = int(sys.argv[2])
duration = 3.0


def write_signal(path: Path, music_level: float, alarm_level: float) -> None:
    values = array.array('i')
    full_scale = 2**31 - 1
    for frame in range(int(rate * duration)):
        music = int(full_scale * music_level * math.sin(2.0 * math.pi * 1000.0 * frame / rate))
        alarm = int(full_scale * alarm_level * math.sin(2.0 * math.pi * 2711.0 * frame / rate))
        values.extend((music, music, alarm, alarm))
    if sys.byteorder != 'little':
        values.byteswap()
    with path.open('wb') as handle:
        values.tofile(handle)


write_signal(root / 'combined-moderate.raw', 0.04, 0.04)
write_signal(root / 'combined-stress.raw', 0.55, 0.55)
PY_SIGNAL

cat >"$REPORT_FILE" <<EOF_REPORT
A Clockwork Plex split music/alarm bus laboratory
Generated: $(date --iso-8601=seconds)
Directory: $LAB_ROOT
Mode: $MODE
Required CamillaDSP version: $CAMILLADSP_VERSION
Loopback card: hw:$LOOPBACK_INDEX
Capture layout: 4 channels (music L/R, alarm L/R)
Playback layout: stereo combined output
Final limiter: $LIMIT_DB dBFS
Physical DAC opened: no
EOF_REPORT

cat <<EOF_STATUS

A Clockwork Plex split-bus laboratory prepared.

  Directory:       $LAB_ROOT
  Music lane:      capture channels 0/1; Music Master and EQ applied
  Alarm lane:      capture channels 2/3; Music Master and EQ bypassed
  Final stage:     both lanes combined, then limited at $LIMIT_DB dBFS
  Audio endpoints: snd_aloop only

No production file, service, PCM definition or mixer level has been changed.
The physical DAC has not been opened.
EOF_STATUS

if [[ "$MODE" == prepare ]]; then
    cat <<EOF_PREPARE

Nothing has been executed. Run on the Pi with the verified binary:

  bash scripts/test-camilladsp-split-bus-lab.sh --run \
    --binary /path/to/camilladsp \
    --lab-root "$LAB_ROOT"
EOF_PREPARE
    exit 0
fi

for command in python3 timeout aplay arecord cmp grep cp mv kill awk; do
    command -v "$command" >/dev/null 2>&1 || { echo "Required command not found: $command" >&2; exit 1; }
done
[[ "$(uname -m)" == "aarch64" ]] || { echo "This laboratory expects aarch64; found $(uname -m)." >&2; exit 1; }
[[ -n "$CAMILLADSP_BINARY" ]] || { echo "--binary is required for --run." >&2; exit 64; }
[[ -x "$CAMILLADSP_BINARY" ]] || { echo "CamillaDSP executable not found: $CAMILLADSP_BINARY" >&2; exit 1; }

card_line="$(awk -v card="$LOOPBACK_INDEX" '$1 == card {print; exit}' /proc/asound/cards 2>/dev/null || true)"
if [[ -z "$card_line" ]] || ! grep -q 'Loopback' <<<"$card_line"; then
    echo "No snd_aloop card was found at ALSA index $LOOPBACK_INDEX." >&2
    exit 1
fi
for device in "/dev/snd/pcmC${LOOPBACK_INDEX}D0p" "/dev/snd/pcmC${LOOPBACK_INDEX}D1c"; do
    [[ -e "$device" ]] || { echo "Required loopback endpoint is missing: $device" >&2; exit 1; }
done

binary_version="$($CAMILLADSP_BINARY --version 2>&1 | head -n1)"
grep -Fq "$CAMILLADSP_VERSION" <<<"$binary_version" || { echo "Unexpected CamillaDSP binary version: $binary_version" >&2; exit 1; }
echo "Binary version: $binary_version" | tee -a "$REPORT_FILE"

for config in "$LAB_ROOT"/*.yml; do
    "$CAMILLADSP_BINARY" --check "$config" >>"$REPORT_FILE" 2>&1 || {
        echo "CamillaDSP rejected $config" >&2
        exit 1
    }
done

if [[ -r "$DAC_HW_PARAMS" ]]; then cat "$DAC_HW_PARAMS" >"$DAC_BEFORE"; else printf 'unavailable\n' >"$DAC_BEFORE"; fi

cp "$LAB_ROOT/neutral.yml" "$ACTIVE_CONFIG"
"$CAMILLADSP_BINARY" --gain=0 "$ACTIVE_CONFIG" >"$DSP_LOG" 2>&1 &
DSP_PID=$!
sleep 1
kill -0 "$DSP_PID" 2>/dev/null || { echo "CamillaDSP exited before testing began. See $DSP_LOG" >&2; exit 1; }

printf 'profile\tmusic_gain_db\talarm_gain_db\tpeak_dbfs\tresult\n' >"$RESULTS_FILE"
failures=0
reload_count=0

measure_output() {
    python3 - "$1" "$2" "$SAMPLERATE" <<'PY_ANALYZE'
from __future__ import annotations

import array
import math
import sys
from pathlib import Path


def read_interleaved(path: str, channels: int) -> list[list[int]]:
    data = array.array('i')
    source = Path(path)
    with source.open('rb') as handle:
        data.fromfile(handle, source.stat().st_size // data.itemsize)
    if sys.byteorder != 'little':
        data.byteswap()
    return [list(data[index::channels]) for index in range(channels)]


def goertzel(samples: list[int], rate: int, frequency: float) -> float:
    coeff = 2.0 * math.cos(2.0 * math.pi * frequency / rate)
    previous = previous2 = 0.0
    for value in samples:
        current = value + coeff * previous - previous2
        previous2, previous = previous, current
    power = previous2**2 + previous**2 - coeff * previous * previous2
    return 2.0 * math.sqrt(max(power, 0.0)) / max(1, len(samples))


def best_level(samples: list[int], rate: int, frequency: float) -> float:
    window = rate // 2
    step = rate // 4
    levels = [
        goertzel(samples[start:start + window], rate, frequency)
        for start in range(0, max(1, len(samples) - window + 1), step)
        if len(samples[start:start + window]) == window
    ]
    if not levels:
        raise SystemExit('no complete analysis window')
    return max(levels)


input_channels = read_interleaved(sys.argv[1], 4)
output_channels = read_interleaved(sys.argv[2], 2)
rate = int(sys.argv[3])
output_left = output_channels[0]
music_gain = 20.0 * math.log10(best_level(output_left, rate, 1000.0) / best_level(input_channels[0], rate, 1000.0))
alarm_gain = 20.0 * math.log10(best_level(output_left, rate, 2711.0) / best_level(input_channels[2], rate, 2711.0))
peak = max(abs(value) for channel in output_channels for value in channel)
peak_dbfs = 20.0 * math.log10(peak / (2**31 - 1)) if peak else -999.0
print(f'{music_gain:.3f}\t{alarm_gain:.3f}\t{peak_dbfs:.3f}')
PY_ANALYZE
}

run_profile() {
    local name="$1" config="$2" signal="$3"
    local music_min="$4" music_max="$5" alarm_min="$6" alarm_max="$7" peak_max="$8"
    local output="$LAB_ROOT/${name}-output.raw" music_gain alarm_gain peak_dbfs result=PASS

    cp "$config" "$ACTIVE_CONFIG.tmp"
    mv "$ACTIVE_CONFIG.tmp" "$ACTIVE_CONFIG"
    kill -HUP "$DSP_PID"
    reload_count=$((reload_count + 1))
    sleep 0.8
    kill -0 "$DSP_PID" 2>/dev/null || result=FAIL

    rm -f "$output"
    arecord -q -D "$OUTPUT_CAPTURE" -t raw -f "$FORMAT" -r "$SAMPLERATE" -c "$PLAYBACK_CHANNELS" -d 6 "$output" >"$LAB_ROOT/${name}-capture.log" 2>&1 &
    SINK_PID=$!
    sleep 0.25
    timeout 6 aplay -q -D "$INPUT_PLAYBACK" -t raw -f "$FORMAT" -r "$SAMPLERATE" -c "$CAPTURE_CHANNELS" "$signal" >"$LAB_ROOT/${name}-playback.log" 2>&1 || result=FAIL
    wait "$SINK_PID" 2>/dev/null || true
    SINK_PID=""

    if [[ "$result" == PASS ]]; then
        IFS=$'\t' read -r music_gain alarm_gain peak_dbfs <<<"$(measure_output "$signal" "$output")"
        python3 - "$music_gain" "$music_min" "$music_max" "$alarm_gain" "$alarm_min" "$alarm_max" "$peak_dbfs" "$peak_max" <<'PY_RANGE' || result=FAIL
import sys
music, music_min, music_max, alarm, alarm_min, alarm_max, peak, peak_max = map(float, sys.argv[1:])
ok = music_min <= music <= music_max and alarm_min <= alarm <= alarm_max and peak <= peak_max
raise SystemExit(0 if ok else 1)
PY_RANGE
    else
        music_gain=-; alarm_gain=-; peak_dbfs=-
    fi

    printf '%s\t%s\t%s\t%s\t%s\n' "$name" "$music_gain" "$alarm_gain" "$peak_dbfs" "$result" | tee -a "$RESULTS_FILE"
    [[ "$result" == PASS ]] || failures=$((failures + 1))
}

run_profile neutral "$LAB_ROOT/neutral.yml" "$LAB_ROOT/combined-moderate.raw" -0.35 0.35 -0.35 0.35 0.0
run_profile music-master-isolation "$LAB_ROOT/music-master-minus-20.yml" "$LAB_ROOT/combined-moderate.raw" -20.6 -19.4 -0.35 0.35 0.0
run_profile music-eq-isolation "$LAB_ROOT/music-eq-plus-6.yml" "$LAB_ROOT/combined-moderate.raw" 5.2 6.6 -0.35 0.35 0.0
run_profile final-limiter "$LAB_ROOT/limiter-stress.yml" "$LAB_ROOT/combined-stress.raw" -20.0 20.0 -20.0 20.0 -0.7

if [[ -r "$DAC_HW_PARAMS" ]]; then cat "$DAC_HW_PARAMS" >"$DAC_AFTER"; else printf 'unavailable\n' >"$DAC_AFTER"; fi
if cmp -s "$DAC_BEFORE" "$DAC_AFTER"; then
    printf 'physical-dac-unchanged\t-\t-\t-\tPASS\n' | tee -a "$RESULTS_FILE"
else
    printf 'physical-dac-unchanged\t-\t-\t-\tFAIL\n' | tee -a "$RESULTS_FILE"
    failures=$((failures + 1))
fi

if kill -0 "$DSP_PID" 2>/dev/null && [[ "$reload_count" -eq 4 ]]; then
    printf 'single-process-survival\t-\t-\t-\tPASS\n' | tee -a "$RESULTS_FILE"
else
    printf 'single-process-survival\t-\t-\t-\tFAIL\n' | tee -a "$RESULTS_FILE"
    failures=$((failures + 1))
fi

{
    echo
    echo "Results:"
    cat "$RESULTS_FILE"
    echo
    echo "Failures: $failures"
} | tee -a "$REPORT_FILE"

if [[ "$failures" -ne 0 ]]; then
    echo "Split-bus laboratory failed. See $REPORT_FILE" >&2
    exit 1
fi

echo "Split-bus laboratory passed. Alarm level remained independent of Music Master and music EQ."
