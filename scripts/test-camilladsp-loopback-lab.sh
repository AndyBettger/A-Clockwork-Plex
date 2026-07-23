#!/bin/bash
set -euo pipefail

# Fourth-stage A Clockwork Plex audio laboratory.
#
# This script downloads a pinned official CamillaDSP aarch64 release into /tmp,
# validates a loopback-only configuration, and optionally runs a finite -6 dB
# DSP round trip entirely on snd_aloop. It never installs CamillaDSP system-wide,
# edits /etc, restarts a service, or opens the physical RPi DAC Pro.

MODE=prepare
LAB_ROOT="${LAB_ROOT:-}"
LOOPBACK_INDEX="${LOOPBACK_INDEX:-7}"
CAMILLADSP_VERSION="4.1.3"
CAMILLADSP_ASSET="camilladsp-linux-aarch64.tar.gz"
SAMPLERATE=48000
FORMAT=S32_LE
CHANNELS=2
CHUNKSIZE=1024
GAIN_DB=-6.0
DAC_HW_PARAMS="${DAC_HW_PARAMS:-/proc/asound/Pro/pcm0p/sub0/hw_params}"
DSP_PID=""
SINK_PID=""

usage() {
    cat <<'EOF_USAGE'
Usage: bash scripts/test-camilladsp-loopback-lab.sh [options]

Options:
  --prepare-only       Generate the temporary config and test signal only (default).
  --fetch              Download and verify pinned CamillaDSP, then check the config.
  --run                Fetch/check, then run a finite loopback-only -6 dB DSP test.
  --lab-root PATH      Reuse or create PATH instead of a new /tmp directory.
  --loopback-index N   snd_aloop ALSA card index (default: 7).
  -h, --help           Show this help.

The script requires an already-loaded snd_aloop card with at least two substreams.
It never loads a kernel module, writes outside its laboratory directory, changes
mixer levels, restarts services, or opens hw:Pro,0. --fetch uses the official
HEnquist/camilladsp GitHub release API and verifies the asset SHA-256 digest when
GitHub supplies one. --run uses only hw:N loopback endpoints and finite test data.
EOF_USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prepare-only)
            MODE=prepare
            shift
            ;;
        --fetch)
            MODE=fetch
            shift
            ;;
        --run)
            MODE=run
            shift
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
[[ "$(uname -m)" == "aarch64" ]] || { echo "This pinned laboratory expects aarch64; found $(uname -m)." >&2; exit 1; }

if [[ -z "$LAB_ROOT" ]]; then
    LAB_ROOT="$(mktemp -d /tmp/a-clockwork-plex-camilladsp.XXXXXX)"
else
    mkdir -p "$LAB_ROOT"
    LAB_ROOT="$(cd "$LAB_ROOT" && pwd)"
fi

CONFIG_FILE="$LAB_ROOT/camilladsp-loopback.yml"
INPUT_RAW="$LAB_ROOT/input-48k-s32.raw"
OUTPUT_RAW="$LAB_ROOT/output-48k-s32.raw"
ARCHIVE_FILE="$LAB_ROOT/$CAMILLADSP_ASSET"
RELEASE_JSON="$LAB_ROOT/release-v${CAMILLADSP_VERSION}.json"
BINARY_DIR="$LAB_ROOT/bin"
BINARY_FILE="$BINARY_DIR/camilladsp"
REPORT_FILE="$LAB_ROOT/report.txt"
RESULTS_FILE="$LAB_ROOT/results.tsv"
CAMILLADSP_LOG="$LAB_ROOT/camilladsp.log"
SINK_LOG="$LAB_ROOT/output-capture.log"
INPUT_LOG="$LAB_ROOT/input-playback.log"
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
    echo "Run scripts/test-dsp-loopback-lab.sh --run first, or reboot and repeat that stage." >&2
    exit 1
fi

for device in \
    "/dev/snd/pcmC${LOOPBACK_INDEX}D0p" \
    "/dev/snd/pcmC${LOOPBACK_INDEX}D1c"; do
    [[ -e "$device" ]] || { echo "Required loopback endpoint is missing: $device" >&2; exit 1; }
done

cat >"$CONFIG_FILE" <<EOF_CONFIG
title: "A Clockwork Plex CamillaDSP loopback laboratory"
description: "Finite loopback-only transport with a fixed -6 dB gain filter"
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
  laboratory_gain:
    type: Gain
    parameters:
      gain: $GAIN_DB
      scale: dB
      inverted: false
      mute: false
pipeline:
  - type: Filter
    channels: [0, 1]
    names:
      - laboratory_gain
EOF_CONFIG

python3 - "$INPUT_RAW" "$SAMPLERATE" <<'PY_SIGNAL'
from __future__ import annotations

import array
import math
import sys
from pathlib import Path

path = Path(sys.argv[1])
rate = int(sys.argv[2])
duration = 2.0
frequency = 997.0
amplitude = int((2**31 - 1) * 0.20)
samples = array.array("i")
for frame in range(int(rate * duration)):
    value = int(amplitude * math.sin(2.0 * math.pi * frequency * frame / rate))
    samples.extend((value, value))
if sys.byteorder != "little":
    samples.byteswap()
with path.open("wb") as handle:
    samples.tofile(handle)
PY_SIGNAL

cat >"$REPORT_FILE" <<EOF_REPORT
A Clockwork Plex CamillaDSP loopback laboratory
Generated: $(date --iso-8601=seconds)
Directory: $LAB_ROOT
Mode: $MODE
CamillaDSP version: $CAMILLADSP_VERSION
Loopback card: hw:$LOOPBACK_INDEX
Input playback: $INPUT_PLAYBACK
DSP capture: $DSP_CAPTURE
DSP playback: $DSP_PLAYBACK
Output capture: $OUTPUT_CAPTURE
Format: $SAMPLERATE Hz / $FORMAT / stereo
Laboratory gain: $GAIN_DB dB
Physical DAC opened: no
EOF_REPORT

cat <<EOF_STATUS

A Clockwork Plex CamillaDSP laboratory prepared.

  Directory:       $LAB_ROOT
  Config:          $CONFIG_FILE
  Loopback card:   hw:$LOOPBACK_INDEX
  CamillaDSP:      pinned v$CAMILLADSP_VERSION aarch64
  Processing test: $GAIN_DB dB stereo gain at $SAMPLERATE Hz / $FORMAT

No production file, service, PCM definition or mixer level has been changed.
The physical DAC has not been opened.
EOF_STATUS

if [[ "$MODE" == prepare ]]; then
    cat <<EOF_PREPARE

Nothing has been downloaded or executed. To fetch and validate the official binary:

  bash scripts/test-camilladsp-loopback-lab.sh --fetch --lab-root "$LAB_ROOT"

After a successful fetch/check, the finite loopback-only DSP test is:

  bash scripts/test-camilladsp-loopback-lab.sh --run --lab-root "$LAB_ROOT"
EOF_PREPARE
    exit 0
fi

for command in curl tar sha256sum python3 timeout aplay arecord cmp; do
    command -v "$command" >/dev/null 2>&1 || {
        echo "Required command not found: $command" >&2
        exit 1
    }
done

fetch_camilladsp() {
    local api_url="https://api.github.com/repos/HEnquist/camilladsp/releases/tags/v${CAMILLADSP_VERSION}"
    local asset_url asset_digest expected_sha actual_sha

    mkdir -p "$BINARY_DIR"
    if [[ -x "$BINARY_FILE" ]]; then
        echo "Reusing laboratory binary: $BINARY_FILE" | tee -a "$REPORT_FILE"
        return 0
    fi

    echo "Fetching official release metadata for CamillaDSP v${CAMILLADSP_VERSION}." | tee -a "$REPORT_FILE"
    curl -fsSL --retry 3 --connect-timeout 15 \
        -H 'Accept: application/vnd.github+json' \
        -H 'X-GitHub-Api-Version: 2022-11-28' \
        "$api_url" -o "$RELEASE_JSON"

    mapfile -t asset_info < <(python3 - "$RELEASE_JSON" "$CAMILLADSP_ASSET" <<'PY_ASSET'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    release = json.load(handle)
name = sys.argv[2]
for asset in release.get("assets", []):
    if asset.get("name") == name:
        print(asset.get("browser_download_url", ""))
        print(asset.get("digest") or "")
        break
else:
    raise SystemExit(f"Release asset not found: {name}")
PY_ASSET
    )
    asset_url="${asset_info[0]:-}"
    asset_digest="${asset_info[1]:-}"
    [[ "$asset_url" == "https://github.com/HEnquist/camilladsp/releases/download/"* ]] || {
        echo "Unexpected release asset URL: $asset_url" >&2
        return 1
    }

    echo "Downloading $CAMILLADSP_ASSET into the laboratory directory." | tee -a "$REPORT_FILE"
    curl -fL --retry 3 --connect-timeout 15 "$asset_url" -o "$ARCHIVE_FILE"
    actual_sha="$(sha256sum "$ARCHIVE_FILE" | awk '{print $1}')"
    echo "Downloaded SHA-256: $actual_sha" | tee -a "$REPORT_FILE"

    if [[ "$asset_digest" == sha256:* ]]; then
        expected_sha="${asset_digest#sha256:}"
        if [[ "$actual_sha" != "$expected_sha" ]]; then
            echo "CamillaDSP archive digest mismatch." >&2
            return 1
        fi
        echo "GitHub release digest: PASS" | tee -a "$REPORT_FILE"
    else
        echo "GitHub did not expose a sha256 asset digest; refusing an unverified archive." >&2
        return 1
    fi

    tar -xzf "$ARCHIVE_FILE" -C "$BINARY_DIR"
    if [[ ! -x "$BINARY_FILE" ]]; then
        local extracted
        extracted="$(find "$BINARY_DIR" -maxdepth 2 -type f -name camilladsp -print -quit)"
        [[ -n "$extracted" ]] || { echo "CamillaDSP executable not found in archive." >&2; return 1; }
        mv "$extracted" "$BINARY_FILE"
        chmod 0755 "$BINARY_FILE"
    fi
}

fetch_camilladsp
BINARY_VERSION="$($BINARY_FILE --version 2>&1 | head -n1)"
echo "Binary version: $BINARY_VERSION" | tee -a "$REPORT_FILE"
grep -Fq "$CAMILLADSP_VERSION" <<<"$BINARY_VERSION" || {
    echo "Unexpected CamillaDSP binary version: $BINARY_VERSION" >&2
    exit 1
}

printf 'test\texpected\tobserved\tresult\n' >"$RESULTS_FILE"
printf 'binary-version\t%s\t%s\tPASS\n' "$CAMILLADSP_VERSION" "$BINARY_VERSION" | tee -a "$RESULTS_FILE"

if "$BINARY_FILE" --check "$CONFIG_FILE" >>"$REPORT_FILE" 2>&1; then
    printf 'config-check\tvalid\tvalid\tPASS\n' | tee -a "$RESULTS_FILE"
else
    printf 'config-check\tvalid\tinvalid\tFAIL\n' | tee -a "$RESULTS_FILE"
    echo "CamillaDSP rejected the generated configuration. See $REPORT_FILE" >&2
    exit 1
fi

if [[ "$MODE" == fetch ]]; then
    cat <<EOF_FETCH

CamillaDSP fetch and configuration check complete.

  Binary:  $BINARY_FILE
  Summary: $RESULTS_FILE
  Detail:  $REPORT_FILE

No audio device was opened. To run the loopback-only DSP test:

  bash scripts/test-camilladsp-loopback-lab.sh --run --lab-root "$LAB_ROOT"
EOF_FETCH
    exit 0
fi

if [[ -r "$DAC_HW_PARAMS" ]]; then
    cat "$DAC_HW_PARAMS" >"$DAC_BEFORE"
else
    printf 'unavailable\n' >"$DAC_BEFORE"
fi

rm -f "$OUTPUT_RAW"
arecord -q -D "$OUTPUT_CAPTURE" -t raw -f "$FORMAT" -r "$SAMPLERATE" -c "$CHANNELS" -d 7 "$OUTPUT_RAW" >"$SINK_LOG" 2>&1 &
SINK_PID=$!
sleep 0.25

"$BINARY_FILE" --gain=0 "$CONFIG_FILE" >"$CAMILLADSP_LOG" 2>&1 &
DSP_PID=$!
sleep 1
if ! kill -0 "$DSP_PID" 2>/dev/null; then
    echo "CamillaDSP exited before the test signal was sent. See $CAMILLADSP_LOG" >&2
    exit 1
fi

if timeout 5 aplay -q -D "$INPUT_PLAYBACK" -t raw -f "$FORMAT" -r "$SAMPLERATE" -c "$CHANNELS" "$INPUT_RAW" >"$INPUT_LOG" 2>&1; then
    input_result=PASS
else
    input_result=FAIL
fi
sleep 1
kill -INT "$DSP_PID" 2>/dev/null || true
wait "$DSP_PID" 2>/dev/null || true
DSP_PID=""
wait "$SINK_PID" 2>/dev/null || true
SINK_PID=""

printf 'input-playback\tfinite-test-signal\t%s\t%s\n' "$input_result" "$input_result" | tee -a "$RESULTS_FILE"
[[ "$input_result" == PASS ]] || exit 1

analysis_line="$(python3 - "$INPUT_RAW" "$OUTPUT_RAW" <<'PY_ANALYZE'
from __future__ import annotations

import array
import math
import sys
from pathlib import Path


def read_i32(path: str) -> array.array[int]:
    values = array.array("i")
    with Path(path).open("rb") as handle:
        values.fromfile(handle, Path(path).stat().st_size // values.itemsize)
    if sys.byteorder != "little":
        values.byteswap()
    return values

input_values = read_i32(sys.argv[1])
output_values = read_i32(sys.argv[2])
if not input_values or not output_values:
    raise SystemExit("empty input or output data")
input_peak = max(abs(value) for value in input_values)
output_peak = max(abs(value) for value in output_values)
if input_peak == 0 or output_peak == 0:
    raise SystemExit("zero-valued input or output data")
ratio = output_peak / input_peak
gain_db = 20.0 * math.log10(ratio)
active = sum(1 for value in output_values if abs(value) > input_peak * 0.01)
passed = -6.8 <= gain_db <= -5.2 and active > 1000
print(f"{gain_db:.3f}\t{input_peak}\t{output_peak}\t{active}\t{'PASS' if passed else 'FAIL'}")
PY_ANALYZE
)"
IFS=$'\t' read -r observed_gain input_peak output_peak active_samples dsp_result <<<"$analysis_line"
printf 'dsp-gain\t-6.0dB\t%sdB\t%s\n' "$observed_gain" "$dsp_result" | tee -a "$RESULTS_FILE"
{
    echo "Input peak: $input_peak"
    echo "Output peak: $output_peak"
    echo "Active output samples: $active_samples"
    echo "Observed DSP gain: $observed_gain dB"
} >>"$REPORT_FILE"

if [[ -r "$DAC_HW_PARAMS" ]]; then
    cat "$DAC_HW_PARAMS" >"$DAC_AFTER"
else
    printf 'unavailable\n' >"$DAC_AFTER"
fi
if cmp -s "$DAC_BEFORE" "$DAC_AFTER"; then
    dac_result=PASS
else
    dac_result=FAIL
fi
printf 'physical-dac-unchanged\tunchanged\t%s\t%s\n' "$dac_result" "$dac_result" | tee -a "$RESULTS_FILE"

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
    echo
    echo "CamillaDSP log:"
    cat "$CAMILLADSP_LOG"
} >>"$REPORT_FILE"

failures=0
[[ "$dsp_result" == PASS ]] || failures=$((failures + 1))
[[ "$dac_result" == PASS ]] || failures=$((failures + 1))

cat <<EOF_DONE

CamillaDSP loopback laboratory complete.

  Binary:        $BINARY_VERSION
  Observed gain: $observed_gain dB
  Summary:       $RESULTS_FILE
  Detail:        $REPORT_FILE
  DSP log:       $CAMILLADSP_LOG
  Failures:      $failures

The test used only the ALSA Loopback card. The physical DAC was not opened.
EOF_DONE

[[ "$failures" -eq 0 ]]
