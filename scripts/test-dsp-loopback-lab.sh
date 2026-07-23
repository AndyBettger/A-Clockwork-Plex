#!/bin/bash
set -euo pipefail

# Third-stage A Clockwork Plex audio laboratory.
#
# This validates the kernel ALSA Loopback transport without changing the
# production A Clockwork Plex PCM graph and without opening the physical DAC.
# The default mode only explains the plan. --run loads snd_aloop for the current
# boot when necessary, performs finite digital-silence round trips, verifies the
# live DAC format did not change, and attempts to unload only a module loaded by
# this invocation.

RUN_TESTS=false
KEEP_LOADED=false
LAB_ROOT="${LAB_ROOT:-}"
LOOPBACK_ID="${LOOPBACK_ID:-ACP_Loopback}"
LOOPBACK_INDEX="${LOOPBACK_INDEX:-7}"
PCM_SUBSTREAMS="${PCM_SUBSTREAMS:-2}"
DAC_HW_PARAMS="${DAC_HW_PARAMS:-/proc/asound/Pro/pcm0p/sub0/hw_params}"
LOADED_BY_SCRIPT=false
ACTUAL_LOOPBACK_INDEX=""
ACTUAL_LOOPBACK_ID=""
CAPTURE_PIDS=()

usage() {
    cat <<'EOF'
Usage: bash scripts/test-dsp-loopback-lab.sh [options]

Options:
  --prepare-only       Show the planned checks only (default).
  --run                Load or reuse snd_aloop and run finite loopback tests.
  --keep-loaded        Leave snd_aloop loaded after a successful run.
  --lab-root PATH      Reuse or create PATH instead of a new /tmp directory.
  --loopback-id NAME   Requested ALSA card ID for a newly loaded card.
  --loopback-index N   Requested ALSA card index for a newly loaded card (default: 7).
  -h, --help           Show this help.

The run does not edit /etc, restart services, rewrite the A Clockwork Plex ALSA
configuration, alter mixer levels or open the physical DAC. Loading snd_aloop is
a current-boot kernel change. ALSA or WirePlumber may expose the card under a
normalised display ID rather than the requested ID, so the probe discovers the
actual loopback card from /proc/asound/cards and uses its numeric card index.

The script attempts to unload a module loaded by this invocation unless
--keep-loaded is supplied. A module already present when the script starts is
reused and left loaded. WirePlumber or another process may keep the card open;
if unload fails, the report says so and a reboot clears the module.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prepare-only)
            RUN_TESTS=false
            shift
            ;;
        --run)
            RUN_TESTS=true
            shift
            ;;
        --keep-loaded)
            KEEP_LOADED=true
            shift
            ;;
        --lab-root)
            [[ $# -ge 2 ]] || { echo "--lab-root requires a path." >&2; exit 64; }
            LAB_ROOT="$2"
            shift 2
            ;;
        --loopback-id)
            [[ $# -ge 2 ]] || { echo "--loopback-id requires a name." >&2; exit 64; }
            LOOPBACK_ID="$2"
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

[[ "$LOOPBACK_ID" =~ ^[A-Za-z0-9_.@-]+$ ]] || { echo "Invalid loopback ID: $LOOPBACK_ID" >&2; exit 64; }
[[ "$LOOPBACK_INDEX" =~ ^[0-9]+$ ]] || { echo "Invalid loopback index: $LOOPBACK_INDEX" >&2; exit 64; }
[[ "$PCM_SUBSTREAMS" =~ ^[1-8]$ ]] || { echo "PCM_SUBSTREAMS must be from 1 to 8." >&2; exit 64; }

if [[ -z "$LAB_ROOT" ]]; then
    LAB_ROOT="$(mktemp -d /tmp/a-clockwork-plex-dsp-loopback.XXXXXX)"
else
    mkdir -p "$LAB_ROOT"
    LAB_ROOT="$(cd "$LAB_ROOT" && pwd)"
fi

REPORT_FILE="$LAB_ROOT/report.txt"
RESULTS_FILE="$LAB_ROOT/results.tsv"
DAC_BEFORE="$LAB_ROOT/dac-hw-params-before.txt"
DAC_AFTER="$LAB_ROOT/dac-hw-params-after.txt"

cleanup_processes() {
    local pid
    for pid in "${CAPTURE_PIDS[@]:-}"; do
        if [[ -n "$pid" ]]; then
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
        fi
    done
    CAPTURE_PIDS=()
}

discover_loopback_card() {
    local index=""
    local card_id=""

    # snd_aloop cards identify themselves as "Loopback - Loopback" in the
    # authoritative /proc card list, even when their bracketed ALSA ID has been
    # normalised or differs from the id= module request.
    index="$(awk '/: Loopback - Loopback/ { print $1; exit }' /proc/asound/cards 2>/dev/null || true)"
    [[ "$index" =~ ^[0-9]+$ ]] || return 1

    if [[ -r "/sys/class/sound/card${index}/id" ]]; then
        card_id="$(tr -d '[:space:]' < "/sys/class/sound/card${index}/id")"
    fi
    if [[ -z "$card_id" ]]; then
        card_id="$(awk -v wanted="$index" '
            $1 == wanted {
                line=$0
                sub(/^.*\[/, "", line)
                sub(/\].*$/, "", line)
                gsub(/[[:space:]]/, "", line)
                print line
                exit
            }
        ' /proc/asound/cards 2>/dev/null || true)"
    fi

    ACTUAL_LOOPBACK_INDEX="$index"
    ACTUAL_LOOPBACK_ID="${card_id:-Loopback}"
    return 0
}

attempt_unload() {
    if [[ "$LOADED_BY_SCRIPT" != true || "$KEEP_LOADED" == true ]]; then
        return 0
    fi
    if sudo modprobe -r snd_aloop >>"$REPORT_FILE" 2>&1; then
        LOADED_BY_SCRIPT=false
        echo "Loopback cleanup: PASS (snd_aloop unloaded)" | tee -a "$REPORT_FILE"
        return 0
    fi
    echo "Loopback cleanup: FAIL (snd_aloop remains loaded for this boot)" | tee -a "$REPORT_FILE" >&2
    if [[ -n "$ACTUAL_LOOPBACK_INDEX" ]]; then
        echo "Inspect users with: sudo fuser -v /dev/snd/controlC${ACTUAL_LOOPBACK_INDEX} /dev/snd/pcmC${ACTUAL_LOOPBACK_INDEX}D*" | tee -a "$REPORT_FILE" >&2
    fi
    return 1
}

cleanup() {
    cleanup_processes
    if [[ "$LOADED_BY_SCRIPT" == true && "$KEEP_LOADED" != true ]]; then
        attempt_unload || true
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

cat >"$REPORT_FILE" <<EOF
A Clockwork Plex DSP loopback laboratory
Generated: $(date --iso-8601=seconds)
Directory: $LAB_ROOT
Requested loopback ID: $LOOPBACK_ID
Requested loopback index: $LOOPBACK_INDEX
Substreams: $PCM_SUBSTREAMS
Mode: $([[ "$RUN_TESTS" == true ]] && echo run || echo prepare-only)
EOF

cat <<EOF

A Clockwork Plex DSP loopback laboratory prepared.

  Directory:                $LAB_ROOT
  Requested loopback ID:    $LOOPBACK_ID
  Requested loopback index: $LOOPBACK_INDEX

No production file, service, PCM definition or mixer level has been changed.
EOF

if [[ "$RUN_TESTS" != true ]]; then
    cat <<EOF

Nothing has been loaded or opened. To run the current-boot loopback probe:

  bash scripts/test-dsp-loopback-lab.sh --run --lab-root "$LAB_ROOT"

The probe never opens hw:Pro,0. It tests only the snd_aloop card and compares the
physical DAC's live hw_params before and after.
EOF
    exit 0
fi

for command in aplay arecord timeout sudo modprobe lsmod grep cmp awk tr sleep; do
    command -v "$command" >/dev/null 2>&1 || {
        echo "Required command not found: $command" >&2
        exit 1
    }
done

if [[ -r "$DAC_HW_PARAMS" ]]; then
    cat "$DAC_HW_PARAMS" >"$DAC_BEFORE"
else
    printf 'unavailable\n' >"$DAC_BEFORE"
fi

if lsmod | grep -q '^snd_aloop[[:space:]]'; then
    echo "snd_aloop was already loaded; discovering and reusing its ALSA card." | tee -a "$REPORT_FILE"
else
    sudo modprobe snd_aloop \
        index="$LOOPBACK_INDEX" \
        id="$LOOPBACK_ID" \
        pcm_substreams="$PCM_SUBSTREAMS" \
        pcm_notify=1
    LOADED_BY_SCRIPT=true
fi

for _ in {1..40}; do
    if discover_loopback_card; then
        break
    fi
    sleep 0.1
done

if [[ -z "$ACTUAL_LOOPBACK_INDEX" ]]; then
    echo "snd_aloop is loaded, but no ALSA Loopback card could be discovered." | tee -a "$REPORT_FILE" >&2
    {
        echo
        echo "Current /proc/asound/cards:"
        cat /proc/asound/cards 2>&1 || true
        echo
        echo "snd_aloop module parameters:"
        for parameter in id index enable pcm_substreams pcm_notify; do
            printf '%s=' "$parameter"
            cat "/sys/module/snd_aloop/parameters/$parameter" 2>/dev/null || echo unavailable
        done
    } >>"$REPORT_FILE"
    exit 1
fi

{
    echo "Actual loopback index: $ACTUAL_LOOPBACK_INDEX"
    echo "Actual loopback ID: $ACTUAL_LOOPBACK_ID"
    if [[ "$ACTUAL_LOOPBACK_INDEX" != "$LOOPBACK_INDEX" ]]; then
        echo "Note: kernel assigned index $ACTUAL_LOOPBACK_INDEX instead of requested index $LOOPBACK_INDEX."
    fi
    if [[ "$ACTUAL_LOOPBACK_ID" != "$LOOPBACK_ID" ]]; then
        echo "Note: ALSA exposed ID $ACTUAL_LOOPBACK_ID instead of requested ID $LOOPBACK_ID."
    fi
} | tee -a "$REPORT_FILE"

{
    echo
    echo "ALSA cards after loading or discovering loopback:"
    cat /proc/asound/cards
    echo
    echo "snd_aloop module parameters:"
    for parameter in id index enable pcm_substreams pcm_notify; do
        printf '%s=' "$parameter"
        cat "/sys/module/snd_aloop/parameters/$parameter" 2>/dev/null || echo unavailable
    done
    echo
    echo "Playback devices:"
    aplay -l
    echo
    echo "Capture devices:"
    arecord -l
} >>"$REPORT_FILE" 2>&1

printf 'test\trate\tformat\tsubstream\tresult\n' >"$RESULTS_FILE"
failures=0

playback_device() {
    printf 'hw:%s,0,%s' "$ACTUAL_LOOPBACK_INDEX" "$1"
}

capture_device() {
    printf 'hw:%s,1,%s' "$ACTUAL_LOOPBACK_INDEX" "$1"
}

run_roundtrip() {
    local test_name="$1"
    local rate="$2"
    local format="$3"
    local substream="$4"
    local capture_log="$LAB_ROOT/${test_name}-capture.log"
    local playback_log="$LAB_ROOT/${test_name}-playback.log"
    local capture_pid
    local result=PASS

    timeout 8 arecord -q -D "$(capture_device "$substream")" -t raw -f "$format" -r "$rate" -c 2 -d 2 /dev/null >"$capture_log" 2>&1 &
    capture_pid=$!
    CAPTURE_PIDS+=("$capture_pid")
    sleep 0.25

    if ! timeout 7 aplay -q -D "$(playback_device "$substream")" -t raw -f "$format" -r "$rate" -c 2 -d 1 /dev/zero >"$playback_log" 2>&1; then
        result=FAIL
    fi
    if ! wait "$capture_pid"; then
        result=FAIL
    fi
    CAPTURE_PIDS=()

    if [[ "$result" == FAIL ]]; then
        failures=$((failures + 1))
    fi
    printf '%s\t%s\t%s\t%s\t%s\n' "$test_name" "$rate" "$format" "$substream" "$result" | tee -a "$RESULTS_FILE"
}

run_roundtrip loopback-44100-16 44100 S16_LE 0
run_roundtrip loopback-48000-32 48000 S32_LE 0
run_roundtrip loopback-96000-32 96000 S32_LE 0

concurrency_result=PASS
cap0_log="$LAB_ROOT/concurrency-capture-0.log"
cap1_log="$LAB_ROOT/concurrency-capture-1.log"
play0_log="$LAB_ROOT/concurrency-playback-0.log"
play1_log="$LAB_ROOT/concurrency-playback-1.log"

timeout 10 arecord -q -D "$(capture_device 0)" -t raw -f S16_LE -r 44100 -c 2 -d 3 /dev/null >"$cap0_log" 2>&1 &
cap0=$!
timeout 10 arecord -q -D "$(capture_device 1)" -t raw -f S32_LE -r 48000 -c 2 -d 3 /dev/null >"$cap1_log" 2>&1 &
cap1=$!
CAPTURE_PIDS=("$cap0" "$cap1")
sleep 0.25

timeout 8 aplay -q -D "$(playback_device 0)" -t raw -f S16_LE -r 44100 -c 2 -d 2 /dev/zero >"$play0_log" 2>&1 &
play0=$!
timeout 8 aplay -q -D "$(playback_device 1)" -t raw -f S32_LE -r 48000 -c 2 -d 2 /dev/zero >"$play1_log" 2>&1 &
play1=$!

if ! wait "$play0"; then concurrency_result=FAIL; fi
if ! wait "$play1"; then concurrency_result=FAIL; fi
if ! wait "$cap0"; then concurrency_result=FAIL; fi
if ! wait "$cap1"; then concurrency_result=FAIL; fi
CAPTURE_PIDS=()

if [[ "$concurrency_result" == FAIL ]]; then
    failures=$((failures + 1))
fi
printf 'concurrency-44100+48000\t44100+48000\tS16_LE+S32_LE\t0+1\t%s\n' "$concurrency_result" | tee -a "$RESULTS_FILE"

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
} >>"$REPORT_FILE" 2>&1

cleanup_failed=false
if [[ "$LOADED_BY_SCRIPT" == true && "$KEEP_LOADED" != true ]]; then
    if ! attempt_unload; then
        cleanup_failed=true
        failures=$((failures + 1))
    fi
fi

cat <<EOF

DSP loopback laboratory complete.

  Actual card: hw:$ACTUAL_LOOPBACK_INDEX ($ACTUAL_LOOPBACK_ID)
  Summary:     $RESULTS_FILE
  Detail:      $REPORT_FILE
  Logs:        $LAB_ROOT/*.log
  Failures:    $failures
EOF

if [[ "$KEEP_LOADED" == true ]]; then
    echo "snd_aloop was intentionally left loaded for this boot."
elif [[ "$LOADED_BY_SCRIPT" != true ]]; then
    echo "snd_aloop was already present when this run started and was left loaded."
elif [[ "$cleanup_failed" == true ]]; then
    echo "snd_aloop could not be unloaded automatically; see the report." >&2
fi

if [[ "$failures" -ne 0 ]]; then
    exit 1
fi
