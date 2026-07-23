#!/bin/bash
set -euo pipefail

# Second-stage A Clockwork Plex EQ laboratory.
#
# This script answers two questions left open by the first matrix:
#   1. Does the exact rolled-back production order work?
#      client plug -> source softvol -> equal -> existing Master
#   2. Can the simplest successful order be opened repeatedly and concurrently?
#      client plug -> equal -> existing Master
#
# It never edits /etc/alsa, Shairport Sync, systemd, config.json or runtime state,
# and it never restarts a service. By default it prepares files only. --run opens
# the existing shared Master with finite digital-silence streams.

RUN_TESTS=false
LAB_ROOT="${LAB_ROOT:-}"
ALSA_CARD="${ALSA_CARD:-Pro}"
MASTER_PCM="${MASTER_PCM:-acp_master}"
SYSTEM_ALSA_CONFIG="${SYSTEM_ALSA_CONFIG:-/usr/share/alsa/alsa.conf}"
REOPEN_COUNT="${REOPEN_COUNT:-12}"

usage() {
    cat <<'EOF'
Usage: bash scripts/test-master-eq-lab-stage2.sh [options]

Options:
  --prepare-only       Generate the temporary configuration only (default).
  --run                Run finite silent matrix, reopen and concurrency tests.
  --lab-root PATH      Reuse or create PATH instead of a new /tmp directory.
  --card NAME          ALSA card used by the temporary softvol control.
  --master-pcm NAME    Existing shared output PCM (default: acp_master).
  --reopen-count N     Number of repeated opens for the reference graph.
  -h, --help           Show this help.

No production files or services are changed. The exact-production-order test
creates a uniquely named temporary ALSA softvol control on the selected card;
it does not alter any A Clockwork Plex Master, Plexamp, AirPlay or Alarm level.
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
        --lab-root)
            [[ $# -ge 2 ]] || { echo "--lab-root requires a path." >&2; exit 64; }
            LAB_ROOT="$2"
            shift 2
            ;;
        --card)
            [[ $# -ge 2 ]] || { echo "--card requires a name." >&2; exit 64; }
            ALSA_CARD="$2"
            shift 2
            ;;
        --master-pcm)
            [[ $# -ge 2 ]] || { echo "--master-pcm requires a name." >&2; exit 64; }
            MASTER_PCM="$2"
            shift 2
            ;;
        --reopen-count)
            [[ $# -ge 2 ]] || { echo "--reopen-count requires a number." >&2; exit 64; }
            REOPEN_COUNT="$2"
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

[[ "$ALSA_CARD" =~ ^[A-Za-z0-9_.@-]+$ ]] || { echo "Invalid ALSA card: $ALSA_CARD" >&2; exit 64; }
[[ "$MASTER_PCM" =~ ^[A-Za-z0-9_.@-]+$ ]] || { echo "Invalid Master PCM: $MASTER_PCM" >&2; exit 64; }
[[ "$REOPEN_COUNT" =~ ^[1-9][0-9]*$ ]] || { echo "REOPEN_COUNT must be a positive integer." >&2; exit 64; }
[[ -f "$SYSTEM_ALSA_CONFIG" ]] || { echo "System ALSA configuration not found: $SYSTEM_ALSA_CONFIG" >&2; exit 1; }

if [[ -z "$LAB_ROOT" ]]; then
    LAB_ROOT="$(mktemp -d /tmp/a-clockwork-plex-eq-stage2.XXXXXX)"
else
    mkdir -p "$LAB_ROOT"
    LAB_ROOT="$(cd "$LAB_ROOT" && pwd)"
fi

CONFIG_FILE="$LAB_ROOT/asound-stage2.conf"
CONTROL_A="$LAB_ROOT/alsaequal-a.bin"
CONTROL_E="$LAB_ROOT/alsaequal-e.bin"
REPORT_FILE="$LAB_ROOT/report-stage2.txt"
RESULTS_FILE="$LAB_ROOT/results-stage2.tsv"

find_caps_library() {
    if [[ -n "${CAPS_LIBRARY:-}" && -f "$CAPS_LIBRARY" ]]; then
        printf '%s\n' "$CAPS_LIBRARY"
        return 0
    fi
    if command -v dpkg-query >/dev/null 2>&1; then
        local candidate
        candidate="$(dpkg-query -L caps 2>/dev/null | awk '/\/caps\.so$/ { print; exit }')"
        if [[ -n "$candidate" && -f "$candidate" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    fi
    local candidate
    for candidate in /usr/lib/ladspa/caps.so /usr/lib/*/ladspa/caps.so; do
        if [[ -f "$candidate" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

CAPS_PATH="$(find_caps_library || true)"
if [[ -z "$CAPS_PATH" ]]; then
    echo "CAPS LADSPA library was not found." >&2
    exit 1
fi

cat > "$CONFIG_FILE" <<EOF
<$SYSTEM_ALSA_CONFIG>

# Temporary stage-two EQ graphs. Loaded only through ALSA_CONFIG_PATH.

ctl.acp_lab2_equal_a {
    type equal
    controls "$CONTROL_A"
    library "$CAPS_PATH"
    module "Eq10"
    channels 2
}

# Reference A1/A2: client plug -> equal -> existing Master.
# A1 and A2 share one curve, matching the intended identical-EQ-per-source model.
pcm.acp_lab2_a1_equal {
    type equal
    slave.pcm "$MASTER_PCM"
    controls "$CONTROL_A"
    library "$CAPS_PATH"
    module "Eq10"
    channels 2
}
pcm.acp_lab2_a1 {
    type plug
    slave.pcm "acp_lab2_a1_equal"
}
pcm.acp_lab2_a2_equal {
    type equal
    slave.pcm "$MASTER_PCM"
    controls "$CONTROL_A"
    library "$CAPS_PATH"
    module "Eq10"
    channels 2
}
pcm.acp_lab2_a2 {
    type plug
    slave.pcm "acp_lab2_a2_equal"
}

ctl.acp_lab2_equal_e {
    type equal
    controls "$CONTROL_E"
    library "$CAPS_PATH"
    module "Eq10"
    channels 2
}

# Replica E: exact rolled-back production order.
# client plug -> source softvol -> equal -> existing Master.
pcm.acp_lab2_e_equal {
    type equal
    slave.pcm "$MASTER_PCM"
    controls "$CONTROL_E"
    library "$CAPS_PATH"
    module "Eq10"
    channels 2
}
pcm.acp_lab2_e_volume {
    type softvol
    slave.pcm "acp_lab2_e_equal"
    control {
        name "A Clockwork EQ Lab Stage2"
        card "$ALSA_CARD"
    }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}
pcm.acp_lab2_e {
    type plug
    slave.pcm "acp_lab2_e_volume"
}
EOF

cat > "$REPORT_FILE" <<EOF
A Clockwork Plex EQ laboratory stage two
Generated: $(date --iso-8601=seconds)
Configuration: $CONFIG_FILE
Reference control: $CONTROL_A
Production-replica control: $CONTROL_E
CAPS library: $CAPS_PATH
Existing Master PCM: $MASTER_PCM
Softvol card: $ALSA_CARD
Mode: $([[ "$RUN_TESTS" == true ]] && echo "silent tests" || echo "prepare only")
EOF

cat <<EOF

A Clockwork Plex EQ stage-two laboratory prepared.

  Directory:       $LAB_ROOT
  ALSA config:     $CONFIG_FILE
  Existing Master: $MASTER_PCM
  CAPS library:    $CAPS_PATH

No production files or services have been changed.
EOF

if [[ "$RUN_TESTS" != true ]]; then
    cat <<EOF

Nothing has been opened or played. To run the finite silent tests:

  bash scripts/test-master-eq-lab-stage2.sh --run --lab-root "$LAB_ROOT"
EOF
    exit 0
fi

for command in aplay amixer timeout; do
    command -v "$command" >/dev/null 2>&1 || {
        echo "Required command not found: $command" >&2
        exit 1
    }
done

export ALSA_CONFIG_PATH="$CONFIG_FILE"
rm -f "$CONTROL_A" "$CONTROL_E"

if ! amixer -D acp_lab2_equal_a scontrols >>"$REPORT_FILE" 2>&1; then
    echo "Reference Eq10 controls could not be initialised. See $REPORT_FILE" >&2
    exit 1
fi
if ! amixer -D acp_lab2_equal_e scontrols >>"$REPORT_FILE" 2>&1; then
    echo "Production-replica Eq10 controls could not be initialised. See $REPORT_FILE" >&2
    exit 1
fi

printf 'test\tpcm\trate\tformat\tresult\n' > "$RESULTS_FILE"
formats=(
    '44100:S16_LE'
    '48000:S16_LE'
    '48000:S24_LE'
    '48000:S32_LE'
    '96000:S24_LE'
    '96000:S32_LE'
)

failures=0
run_case() {
    local test_name="$1"
    local pcm="$2"
    local rate="$3"
    local format="$4"
    local duration="${5:-1}"
    local log="$LAB_ROOT/${test_name}-${pcm}-${rate}-${format}.log"
    local result
    if timeout 6 aplay -q -D "$pcm" -f "$format" -r "$rate" -c 2 -d "$duration" /dev/zero >"$log" 2>&1; then
        result=PASS
    else
        result=FAIL
        failures=$((failures + 1))
    fi
    printf '%s\t%s\t%s\t%s\t%s\n' "$test_name" "$pcm" "$rate" "$format" "$result" | tee -a "$RESULTS_FILE"
}

for item in "${formats[@]}"; do
    rate="${item%%:*}"
    format="${item#*:}"
    run_case reference acp_lab2_a1 "$rate" "$format"
    run_case production-replica acp_lab2_e "$rate" "$format"
done

reopen_result=PASS
for ((attempt = 1; attempt <= REOPEN_COUNT; attempt += 1)); do
    log="$LAB_ROOT/reopen-${attempt}.log"
    if ! timeout 5 aplay -q -D acp_lab2_a1 -f S32_LE -r 48000 -c 2 -d 1 /dev/zero >"$log" 2>&1; then
        reopen_result=FAIL
        failures=$((failures + 1))
        break
    fi
done
printf 'reopen-%s-times\tacp_lab2_a1\t48000\tS32_LE\t%s\n' "$REOPEN_COUNT" "$reopen_result" | tee -a "$RESULTS_FILE"

concurrency_result=PASS
concurrency_a="$LAB_ROOT/concurrency-a1-44100.log"
concurrency_b="$LAB_ROOT/concurrency-a2-48000.log"
timeout 8 aplay -q -D acp_lab2_a1 -f S16_LE -r 44100 -c 2 -d 3 /dev/zero >"$concurrency_a" 2>&1 &
pid_a=$!
timeout 8 aplay -q -D acp_lab2_a2 -f S32_LE -r 48000 -c 2 -d 3 /dev/zero >"$concurrency_b" 2>&1 &
pid_b=$!
if ! wait "$pid_a"; then concurrency_result=FAIL; failures=$((failures + 1)); fi
if ! wait "$pid_b"; then concurrency_result=FAIL; failures=$((failures + 1)); fi
printf 'concurrency\tacp_lab2_a1+acp_lab2_a2\t44100+48000\tS16_LE+S32_LE\t%s\n' "$concurrency_result" | tee -a "$RESULTS_FILE"

{
    echo
    echo "Results:"
    cat "$RESULTS_FILE"
    echo
    echo "Reference controls:"
    amixer -D acp_lab2_equal_a scontents || true
    echo
    echo "Production-replica controls:"
    amixer -D acp_lab2_equal_e scontents || true
} >> "$REPORT_FILE" 2>&1

cat <<EOF

Stage-two laboratory run complete.

  Summary:  $RESULTS_FILE
  Detail:   $REPORT_FILE
  Logs:     $LAB_ROOT/*.log
  Failures: $failures
EOF

if [[ "$failures" -ne 0 ]]; then
    exit 1
fi
