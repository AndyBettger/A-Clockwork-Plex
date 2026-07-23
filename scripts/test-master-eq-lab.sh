#!/bin/bash
set -euo pipefail

# Build temporary ALSA EQ graphs without editing the production configuration.
# By default this script only prepares the files and prints the test command.
# Passing --run performs finite silent aplay tests through the existing shared
# Master PCM and DAC. It never restarts Plexamp, Shairport or the dashboard.

RUN_TESTS=false
KEEP_LAB=true
ALSA_CARD="${ALSA_CARD:-Pro}"
MASTER_PCM="${MASTER_PCM:-acp_master}"
SYSTEM_ALSA_CONFIG="${SYSTEM_ALSA_CONFIG:-/usr/share/alsa/alsa.conf}"
LAB_ROOT="${LAB_ROOT:-}"

usage() {
    cat <<'EOF'
Usage: bash scripts/test-master-eq-lab.sh [options]

Options:
  --prepare-only       Create the temporary configuration only (default).
  --run                Run finite silent format and concurrency tests.
  --discard            Delete the laboratory directory after a successful run.
  --lab-root PATH      Use PATH instead of a new /tmp directory.
  --card NAME          ALSA card used for temporary softvol controls (default: Pro).
  --master-pcm NAME    Existing shared output PCM (default: acp_master).
  -h, --help           Show this help.

This harness does not edit /etc/alsa, Shairport Sync, systemd, config.json or
A Clockwork Plex runtime state. --run opens the existing shared Master PCM and
DAC with digital silence, so pause ordinary playback before using it.
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
        --discard)
            KEEP_LAB=false
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
[[ -f "$SYSTEM_ALSA_CONFIG" ]] || { echo "System ALSA configuration not found: $SYSTEM_ALSA_CONFIG" >&2; exit 1; }

if [[ -z "$LAB_ROOT" ]]; then
    LAB_ROOT="$(mktemp -d /tmp/a-clockwork-plex-eq-lab.XXXXXX)"
else
    mkdir -p "$LAB_ROOT"
    LAB_ROOT="$(cd "$LAB_ROOT" && pwd)"
fi

CONFIG_FILE="$LAB_ROOT/asound.conf"
CONTROL_FILE="$LAB_ROOT/alsaequal.bin"
REPORT_FILE="$LAB_ROOT/report.txt"
RESULTS_FILE="$LAB_ROOT/results.tsv"

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
    echo "CAPS LADSPA library was not found. Install the Debian 'caps' package before running the lab." >&2
    exit 1
fi

cat > "$CONFIG_FILE" <<EOF
<$SYSTEM_ALSA_CONFIG>

# A Clockwork Plex temporary EQ laboratory.
# Generated at $(date --iso-8601=seconds).
# This file is loaded only when ALSA_CONFIG_PATH points at it.

ctl.acp_lab_equal {
    type equal
    controls "$CONTROL_FILE"
    library "$CAPS_PATH"
    module "Eq10"
    channels 2
}

# Variant A: input plug -> equal -> existing Master.
pcm.acp_lab_a_equal {
    type equal
    slave.pcm "$MASTER_PCM"
    controls "$CONTROL_FILE"
    library "$CAPS_PATH"
    module "Eq10"
    channels 2
}
pcm.acp_lab_a {
    type plug
    slave.pcm "acp_lab_a_equal"
}

# Variant B: input plug -> equal -> output plug -> existing Master.
pcm.acp_lab_b_output {
    type plug
    slave.pcm "$MASTER_PCM"
}
pcm.acp_lab_b_equal {
    type equal
    slave.pcm "acp_lab_b_output"
    controls "$CONTROL_FILE"
    library "$CAPS_PATH"
    module "Eq10"
    channels 2
}
pcm.acp_lab_b {
    type plug
    slave.pcm "acp_lab_b_equal"
}

# Variant C: input plug -> softvol -> equal -> output plug -> Master.
pcm.acp_lab_c_output {
    type plug
    slave.pcm "$MASTER_PCM"
}
pcm.acp_lab_c_equal {
    type equal
    slave.pcm "acp_lab_c_output"
    controls "$CONTROL_FILE"
    library "$CAPS_PATH"
    module "Eq10"
    channels 2
}
pcm.acp_lab_c_volume {
    type softvol
    slave.pcm "acp_lab_c_equal"
    control {
        name "A Clockwork EQ Lab C"
        card "$ALSA_CARD"
    }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}
pcm.acp_lab_c {
    type plug
    slave.pcm "acp_lab_c_volume"
}

# Variant D: input plug -> equal -> softvol -> existing Master.
pcm.acp_lab_d_volume {
    type softvol
    slave.pcm "$MASTER_PCM"
    control {
        name "A Clockwork EQ Lab D"
        card "$ALSA_CARD"
    }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}
pcm.acp_lab_d_equal {
    type equal
    slave.pcm "acp_lab_d_volume"
    controls "$CONTROL_FILE"
    library "$CAPS_PATH"
    module "Eq10"
    channels 2
}
pcm.acp_lab_d {
    type plug
    slave.pcm "acp_lab_d_equal"
}
EOF

cat > "$REPORT_FILE" <<EOF
A Clockwork Plex EQ laboratory
Generated: $(date --iso-8601=seconds)
Configuration: $CONFIG_FILE
Control file: $CONTROL_FILE
CAPS library: $CAPS_PATH
Existing Master PCM: $MASTER_PCM
Softvol card: $ALSA_CARD
Mode: $([[ "$RUN_TESTS" == true ]] && echo "silent tests" || echo "prepare only")
EOF

cat <<EOF

A Clockwork Plex EQ laboratory prepared.

  Directory:      $LAB_ROOT
  ALSA config:    $CONFIG_FILE
  Existing Master: $MASTER_PCM
  CAPS library:   $CAPS_PATH

No production files or services have been changed.
EOF

if [[ "$RUN_TESTS" != true ]]; then
    cat <<EOF

Nothing has been opened or played. To perform the finite silent tests:

  bash scripts/test-master-eq-lab.sh --run

The results will compare four plugin orders across 44.1, 48 and 96 kHz
using 16-, 24- and 32-bit ALSA formats.
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

# alsaequal creates the binary control file itself. A zero-byte placeholder can
# cause mmap/SIGBUS failures, so never pre-create it.
rm -f "$CONTROL_FILE"

if ! amixer -D acp_lab_equal scontrols >>"$REPORT_FILE" 2>&1; then
    echo "The temporary Eq10 controls could not be initialised." >&2
    echo "See: $REPORT_FILE" >&2
    exit 1
fi

printf 'pcm\trate\tformat\tresult\n' > "$RESULTS_FILE"
variants=(acp_lab_a acp_lab_b acp_lab_c acp_lab_d)
formats=(
    '44100:S16_LE'
    '48000:S16_LE'
    '48000:S24_LE'
    '48000:S32_LE'
    '96000:S24_LE'
    '96000:S32_LE'
)

failures=0
for pcm in "${variants[@]}"; do
    for item in "${formats[@]}"; do
        rate="${item%%:*}"
        format="${item#*:}"
        log="$LAB_ROOT/${pcm}-${rate}-${format}.log"
        if timeout 4 aplay -q -D "$pcm" -f "$format" -r "$rate" -c 2 -d 1 /dev/zero >"$log" 2>&1; then
            result=PASS
        else
            result=FAIL
            failures=$((failures + 1))
        fi
        printf '%s\t%s\t%s\t%s\n' "$pcm" "$rate" "$format" "$result" | tee -a "$RESULTS_FILE"
    done
done

# A separate concurrency check asks two temporary source paths to negotiate the
# same shared dmix output at once. Both streams contain digital silence.
concurrency_result=PASS
concurrency_a="$LAB_ROOT/concurrency-a.log"
concurrency_b="$LAB_ROOT/concurrency-b.log"
timeout 6 aplay -q -D acp_lab_b -f S16_LE -r 44100 -c 2 -d 2 /dev/zero >"$concurrency_a" 2>&1 &
pid_a=$!
timeout 6 aplay -q -D acp_lab_c -f S16_LE -r 48000 -c 2 -d 2 /dev/zero >"$concurrency_b" 2>&1 &
pid_b=$!
if ! wait "$pid_a"; then concurrency_result=FAIL; failures=$((failures + 1)); fi
if ! wait "$pid_b"; then concurrency_result=FAIL; failures=$((failures + 1)); fi
printf '\nconcurrency\tacp_lab_b@44.1k + acp_lab_c@48k\t%s\n' "$concurrency_result" | tee -a "$RESULTS_FILE"

{
    echo
    echo "Results:"
    cat "$RESULTS_FILE"
    echo
    echo "ALSA controls:"
    amixer -D acp_lab_equal scontents || true
} >> "$REPORT_FILE" 2>&1

cat <<EOF

Laboratory run complete.

  Summary: $RESULTS_FILE
  Detail:  $REPORT_FILE
  Logs:    $LAB_ROOT/*.log
  Failures: $failures
EOF

if [[ "$KEEP_LAB" != true && "$failures" -eq 0 ]]; then
    rm -rf "$LAB_ROOT"
    echo "Laboratory directory removed after a clean run."
fi

if [[ "$failures" -ne 0 ]]; then
    exit 1
fi
