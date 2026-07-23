#!/bin/bash
set -euo pipefail

# Sixth-stage A Clockwork Plex audio laboratory.
# Validate live CamillaDSP EQ reloads, boost headroom and the final limiter while
# one DSP process remains running. All audio endpoints are on snd_aloop; the
# physical DAC is read before/after but never opened.

MODE=prepare
LAB_ROOT="${LAB_ROOT:-}"
LOOPBACK_INDEX="${LOOPBACK_INDEX:-7}"
CAMILLADSP_BINARY="${CAMILLADSP_BINARY:-}"
CAMILLADSP_VERSION="4.1.3"
SAMPLERATE=48000
FORMAT=S32_LE
CHANNELS=2
CHUNKSIZE=1024
LIMIT_DB=-1.0
DAC_HW_PARAMS="${DAC_HW_PARAMS:-/proc/asound/Pro/pcm0p/sub0/hw_params}"
DSP_PID=""
SINK_PID=""

usage() {
    cat <<'EOF_USAGE'
Usage: bash scripts/test-camilladsp-live-headroom-lab.sh [options]

Options:
  --prepare-only       Generate the laboratory files only (default).
  --run                Run live reload, headroom and limiter tests.
  --binary PATH        Verified CamillaDSP 4.1.3 aarch64 executable.
  --lab-root PATH      Reuse or create PATH instead of a new /tmp directory.
  --loopback-index N   snd_aloop ALSA card index (default: 7).
  -h, --help           Show this help.

The script downloads and installs nothing, does not load modules, edit /etc,
restart services, alter mixer controls or open the physical DAC. It uses one
CamillaDSP process and finite signals on an already-loaded snd_aloop card.
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
[[ "$(uname -m)" == "aarch64" ]] || { echo "This laboratory expects aarch64; found $(uname -m)." >&2; exit 1; }

if [[ -z "$LAB_ROOT" ]]; then
    LAB_ROOT="$(mktemp -d /tmp/a-clockwork-plex-camilladsp-live.XXXXXX)"
else
    mkdir -p "$LAB_ROOT"
    LAB_ROOT="$(cd "$LAB_ROOT" && pwd)"
fi

REPORT_FILE="$LAB_ROOT/report.txt"
RESULTS_FILE="$LAB_ROOT/results.tsv"
ACTIVE_CONFIG="$LAB_ROOT/active.yml"
DAC_BEFORE="$LAB_ROOT/dac-hw-params-before.txt"
DAC_AFTER="$LAB_ROOT/dac-hw-params-after.txt"
DSP_LOG="$LAB_ROOT/camilladsp-live.log"
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
for device in "/dev/snd/pcmC${LOOPBACK_INDEX}D0p" "/dev/snd/pcmC${LOOPBACK_INDEX}D1c"; do
    [[ -e "$device" ]] || { echo "Required loopback endpoint is missing: $device" >&2; exit 1; }
done

python3 - "$LAB_ROOT" "$SAMPLERATE" <<'PY_SIGNAL'
from __future__ import annotations
import array
import math
import sys
from pathlib import Path

root = Path(sys.argv[1])
rate = int(sys.argv[2])
duration = 3.0
signals = {
    "bass-63.raw": (63.0, 0.04),
    "mid-1000.raw": (1000.0, 0.04),
    "treble-12000.raw": (12000.0, 0.04),
    "stress-997.raw": (997.0, 0.50),
}
for filename, (frequency, fraction) in signals.items():
    amplitude = int((2**31 - 1) * fraction)
    samples = array.array("i")
    for frame in range(int(rate * duration)):
        value = int(amplitude * math.sin(2.0 * math.pi * frequency * frame / rate))
        samples.extend((value, value))
    if sys.byteorder != "little":
        samples.byteswap()
    with (root / filename).open("wb") as handle:
        samples.tofile(handle)
PY_SIGNAL

cat >"$REPORT_FILE" <<EOF_REPORT
A Clockwork Plex CamillaDSP live reload and headroom laboratory
Generated: $(date --iso-8601=seconds)
Directory: $LAB_ROOT
Mode: $MODE
Required CamillaDSP version: $CAMILLADSP_VERSION
Loopback card: hw:$LOOPBACK_INDEX
Format: $SAMPLERATE Hz / $FORMAT / stereo
Limiter threshold: $LIMIT_DB dBFS
Physical DAC opened: no
EOF_REPORT

cat <<EOF_STATUS

A Clockwork Plex CamillaDSP live/headroom laboratory prepared.

  Directory:       $LAB_ROOT
  Loopback card:   hw:$LOOPBACK_INDEX
  Processing:      live EQ reloads, protected boosts and limiter catch
  Test format:     $SAMPLERATE Hz / $FORMAT / stereo

No production file, service, PCM definition or mixer level has been changed.
The physical DAC has not been opened.
EOF_STATUS

if [[ "$MODE" == prepare ]]; then
    cat <<EOF_PREPARE

Nothing has been executed. Run with the verified stage-four binary:

  bash scripts/test-camilladsp-live-headroom-lab.sh --run \
    --binary /tmp/a-clockwork-plex-camilladsp.EXAMPLE/bin/camilladsp \
    --lab-root "$LAB_ROOT"
EOF_PREPARE
    exit 0
fi

for command in python3 timeout aplay arecord cmp grep cp mv kill; do
    command -v "$command" >/dev/null 2>&1 || { echo "Required command not found: $command" >&2; exit 1; }
done
[[ -n "$CAMILLADSP_BINARY" ]] || { echo "--binary is required for --run." >&2; exit 64; }
[[ -x "$CAMILLADSP_BINARY" ]] || { echo "CamillaDSP executable not found: $CAMILLADSP_BINARY" >&2; exit 1; }

binary_version="$($CAMILLADSP_BINARY --version 2>&1 | head -n1)"
grep -Fq "$CAMILLADSP_VERSION" <<<"$binary_version" || { echo "Unexpected CamillaDSP binary version: $binary_version" >&2; exit 1; }
echo "Binary version: $binary_version" | tee -a "$REPORT_FILE"

if [[ -r "$DAC_HW_PARAMS" ]]; then cat "$DAC_HW_PARAMS" >"$DAC_BEFORE"; else printf 'unavailable\n' >"$DAC_BEFORE"; fi

write_config() {
    local path="$1" title="$2" bass="$3" mid="$4" treble="$5" headroom="$6"
    cat >"$path" <<EOF_CONFIG
---
title: "A Clockwork Plex live laboratory - $title"
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
    parameters: {type: Lowshelf, freq: 125, gain: $bass, slope: 6}
  mid:
    type: Biquad
    parameters: {type: Peaking, freq: 1000, gain: $mid, q: 0.7}
  treble:
    type: Biquad
    parameters: {type: Highshelf, freq: 4000, gain: $treble, slope: 6}
  headroom:
    type: Gain
    parameters: {gain: $headroom, scale: dB, inverted: false, mute: false}
  safety_limiter:
    type: Limiter
    parameters: {soft_clip: false, clip_limit: $LIMIT_DB}
pipeline:
  - type: Filter
    channels: [0, 1]
    names: [bass, mid, treble, headroom, safety_limiter]
EOF_CONFIG
}

write_config "$LAB_ROOT/neutral.yml" neutral 0.0 0.0 0.0 0.0
write_config "$LAB_ROOT/bass.yml" bass 6.0 0.0 0.0 0.0
write_config "$LAB_ROOT/mid.yml" mid 0.0 6.0 0.0 0.0
write_config "$LAB_ROOT/treble.yml" treble 0.0 0.0 6.0 0.0
write_config "$LAB_ROOT/all-protected.yml" all-protected 6.0 6.0 6.0 -6.5
write_config "$LAB_ROOT/limiter.yml" limiter 0.0 0.0 0.0 12.0
for config in "$LAB_ROOT"/*.yml; do
    "$CAMILLADSP_BINARY" --check "$config" >>"$REPORT_FILE" 2>&1 || { echo "CamillaDSP rejected $config" >&2; exit 1; }
done

cp "$LAB_ROOT/neutral.yml" "$ACTIVE_CONFIG"
"$CAMILLADSP_BINARY" --gain=0 "$ACTIVE_CONFIG" >"$DSP_LOG" 2>&1 &
DSP_PID=$!
sleep 1
kill -0 "$DSP_PID" 2>/dev/null || { echo "CamillaDSP exited before live testing began. See $DSP_LOG" >&2; exit 1; }

printf 'profile\tfrequency_hz\tobserved_gain_db\tpeak_dbfs\tresult\n' >"$RESULTS_FILE"
failures=0
reload_count=0

measure_tone() {
    python3 - "$1" "$2" "$SAMPLERATE" "$3" <<'PY_ANALYZE'
from __future__ import annotations
import array
import math
import sys
from pathlib import Path


def read_left(path: str) -> list[int]:
    data = array.array("i")
    file_path = Path(path)
    with file_path.open("rb") as handle:
        data.fromfile(handle, file_path.stat().st_size // data.itemsize)
    if sys.byteorder != "little":
        data.byteswap()
    return list(data[0::2])


def goertzel(samples: list[int], rate: int, frequency: float) -> float:
    coeff = 2.0 * math.cos(2.0 * math.pi * frequency / rate)
    previous = previous2 = 0.0
    for value in samples:
        current = value + coeff * previous - previous2
        previous2, previous = previous, current
    power = previous2**2 + previous**2 - coeff * previous * previous2
    return 2.0 * math.sqrt(max(power, 0.0)) / len(samples)


def best_level(samples: list[int], rate: int, frequency: float) -> float:
    window = rate // 2
    step = rate // 4
    levels = [goertzel(samples[start:start + window], rate, frequency)
              for start in range(0, max(1, len(samples) - window + 1), step)
              if len(samples[start:start + window]) == window]
    if not levels:
        raise SystemExit("no complete analysis window")
    return max(levels)

input_values = read_left(sys.argv[1])
output_values = read_left(sys.argv[2])
rate = int(sys.argv[3])
frequency = float(sys.argv[4])
gain = 20.0 * math.log10(best_level(output_values, rate, frequency) / best_level(input_values, rate, frequency))
peak = max(abs(value) for value in output_values)
peak_dbfs = 20.0 * math.log10(peak / (2**31 - 1)) if peak else -999.0
print(f"{gain:.3f}\t{peak_dbfs:.3f}")
PY_ANALYZE
}

run_profile() {
    local name="$1" config="$2" signal="$3" frequency="$4" minimum="$5" maximum="$6"
    local output="$LAB_ROOT/${name}-output.raw" observed peak result=PASS
    cp "$config" "$ACTIVE_CONFIG.tmp"
    mv "$ACTIVE_CONFIG.tmp" "$ACTIVE_CONFIG"
    kill -HUP "$DSP_PID"
    reload_count=$((reload_count + 1))
    sleep 0.8
    if ! kill -0 "$DSP_PID" 2>/dev/null; then
        printf '%s\t%s\t-\t-\tFAIL\n' "$name" "$frequency" | tee -a "$RESULTS_FILE"
        failures=$((failures + 1)); return 0
    fi
    rm -f "$output"
    arecord -q -D "$OUTPUT_CAPTURE" -t raw -f "$FORMAT" -r "$SAMPLERATE" -c "$CHANNELS" -d 6 "$output" >"$LAB_ROOT/${name}-capture.log" 2>&1 &
    SINK_PID=$!
    sleep 0.25
    if ! timeout 6 aplay -q -D "$INPUT_PLAYBACK" -t raw -f "$FORMAT" -r "$SAMPLERATE" -c "$CHANNELS" "$signal" >"$LAB_ROOT/${name}-playback.log" 2>&1; then result=FAIL; fi
    wait "$SINK_PID" 2>/dev/null || true
    SINK_PID=""
    if [[ "$result" == PASS ]]; then
        IFS=$'\t' read -r observed peak <<<"$(measure_tone "$signal" "$output" "$frequency")"
        python3 - "$observed" "$minimum" "$maximum" <<'PY_RANGE' || result=FAIL
import sys
value, minimum, maximum = map(float, sys.argv[1:])
raise SystemExit(0 if minimum <= value <= maximum else 1)
PY_RANGE
    else
        observed=-; peak=-
    fi
    printf '%s\t%s\t%s\t%s\t%s\n' "$name" "$frequency" "$observed" "$peak" "$result" | tee -a "$RESULTS_FILE"
    [[ "$result" == PASS ]] || failures=$((failures + 1))
}

run_profile neutral-start "$LAB_ROOT/neutral.yml" "$LAB_ROOT/mid-1000.raw" 1000 -0.25 0.25
run_profile bass-live "$LAB_ROOT/bass.yml" "$LAB_ROOT/bass-63.raw" 63 4.2 5.3
run_profile mid-live "$LAB_ROOT/mid.yml" "$LAB_ROOT/mid-1000.raw" 1000 5.5 6.3
run_profile treble-live "$LAB_ROOT/treble.yml" "$LAB_ROOT/treble-12000.raw" 12000 5.0 6.1
run_profile all-boost-protected "$LAB_ROOT/all-protected.yml" "$LAB_ROOT/mid-1000.raw" 1000 -0.6 0.4
run_profile neutral-return "$LAB_ROOT/neutral.yml" "$LAB_ROOT/mid-1000.raw" 1000 -0.25 0.25

# Deliberately overload the final stage: -6 dBFS input plus +12 dB Gain. The
# hard limiter must hold the recorded output to -1 dBFS.
limiter_output="$LAB_ROOT/limiter-catch-output.raw"
cp "$LAB_ROOT/limiter.yml" "$ACTIVE_CONFIG.tmp"
mv "$ACTIVE_CONFIG.tmp" "$ACTIVE_CONFIG"
kill -HUP "$DSP_PID"
reload_count=$((reload_count + 1))
sleep 0.8
if ! kill -0 "$DSP_PID" 2>/dev/null; then
    echo "CamillaDSP exited during the limiter reload." >&2
    exit 1
fi
rm -f "$limiter_output"
arecord -q -D "$OUTPUT_CAPTURE" -t raw -f "$FORMAT" -r "$SAMPLERATE" -c "$CHANNELS" -d 6 "$limiter_output" >"$LAB_ROOT/limiter-catch-capture.log" 2>&1 &
SINK_PID=$!
sleep 0.25
timeout 6 aplay -q -D "$INPUT_PLAYBACK" -t raw -f "$FORMAT" -r "$SAMPLERATE" -c "$CHANNELS" "$LAB_ROOT/stress-997.raw" >"$LAB_ROOT/limiter-catch-playback.log" 2>&1
wait "$SINK_PID" 2>/dev/null || true
SINK_PID=""
limiter_line="$(python3 - "$limiter_output" "$LIMIT_DB" <<'PY_LIMITER'
from __future__ import annotations
import array
import math
import sys
from pathlib import Path
path = Path(sys.argv[1])
limit_db = float(sys.argv[2])
data = array.array("i")
with path.open("rb") as handle:
    data.fromfile(handle, path.stat().st_size // data.itemsize)
if sys.byteorder != "little": data.byteswap()
peak = max(abs(value) for value in data)
peak_dbfs = 20.0 * math.log10(peak / (2**31 - 1))
limit_value = (2**31 - 1) * 10.0 ** (limit_db / 20.0)
near_limit = sum(1 for value in data if abs(abs(value) - limit_value) <= 3.0)
passed = limit_db - 0.08 <= peak_dbfs <= limit_db + 0.08 and near_limit > 100
print(f"{peak_dbfs:.3f}\t{near_limit}\t{'PASS' if passed else 'FAIL'}")
PY_LIMITER
)"
IFS=$'\t' read -r limiter_peak limiter_samples limiter_result <<<"$limiter_line"
printf 'limiter-threshold\t-\t-\t%s\t%s\n' "$limiter_peak" "$limiter_result" | tee -a "$RESULTS_FILE"
[[ "$limiter_result" == PASS ]] || failures=$((failures + 1))

if kill -0 "$DSP_PID" 2>/dev/null; then
    printf 'single-process-survival\t-\t-\t-\tPASS\n' | tee -a "$RESULTS_FILE"
else
    printf 'single-process-survival\t-\t-\t-\tFAIL\n' | tee -a "$RESULTS_FILE"
    failures=$((failures + 1))
fi
kill -INT "$DSP_PID" 2>/dev/null || true
wait "$DSP_PID" 2>/dev/null || true
DSP_PID=""

if [[ -r "$DAC_HW_PARAMS" ]]; then cat "$DAC_HW_PARAMS" >"$DAC_AFTER"; else printf 'unavailable\n' >"$DAC_AFTER"; fi
if cmp -s "$DAC_BEFORE" "$DAC_AFTER"; then dac_result=PASS; else dac_result=FAIL; failures=$((failures + 1)); fi
printf 'physical-dac-unchanged\t-\t-\t-\t%s\n' "$dac_result" | tee -a "$RESULTS_FILE"

{
    echo
    echo "Live reloads applied: $reload_count"
    echo "Limiter near-threshold samples: $limiter_samples"
    echo
    echo "Results:"
    cat "$RESULTS_FILE"
    echo
    echo "Physical DAC before:"
    cat "$DAC_BEFORE"
    echo
    echo "Physical DAC after:"
    cat "$DAC_AFTER"
    echo
    echo "CamillaDSP live log:"
    cat "$DSP_LOG"
} >>"$REPORT_FILE"

cat <<EOF_DONE

CamillaDSP live reload/headroom laboratory complete.

  Binary:        $binary_version
  Reloads:       $reload_count
  Limiter peak:  $limiter_peak dBFS
  Summary:       $RESULTS_FILE
  Detail:        $REPORT_FILE
  DSP log:       $DSP_LOG
  Failures:      $failures

One CamillaDSP process handled every EQ configuration. The physical DAC was not opened.
EOF_DONE

[[ "$failures" -eq 0 ]]
