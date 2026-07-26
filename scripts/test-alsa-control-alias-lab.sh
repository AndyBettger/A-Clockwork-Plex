#!/bin/bash
set -euo pipefail

# Read-only ALSA control-alias laboratory for the A Clockwork Plex shared mixer.
#
# Plexamp selects the named PCM acp_plexamp and may also try to attach an ALSA
# control using the same identifier. The production graph currently defines the
# PCM but not ctl.acp_plexamp, producing "Invalid CTL acp_plexamp" after a
# Plexamp Headless restart. This laboratory validates matching named control
# aliases against the real DAC card without writing /etc or opening any PCM.

MODE=prepare
LAB_ROOT="${LAB_ROOT:-}"
ALSA_CARD="${ALSA_CARD:-Pro}"
LIVE_CONFIG="${LIVE_CONFIG:-/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf}"

usage() {
    cat <<'EOF'
Usage: bash scripts/test-alsa-control-alias-lab.sh [options]

Options:
  --prepare-only       Generate the isolated ALSA configuration only (default).
  --run                Perform read-only named-control opens with amixer.
  --lab-root PATH      Reuse or create PATH instead of a new /tmp directory.
  --card NAME          Physical ALSA card ID (default: Pro).
  --live-config PATH   Existing shared ALSA fragment to copy into the lab.
  -h, --help           Show this help.

Neither mode writes /etc, changes mixer values, restarts services or opens audio.
The --run mode uses only `amixer -D NAME scontrols`, which reads control names.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prepare-only) MODE=prepare; shift ;;
        --run) MODE=run; shift ;;
        --lab-root)
            [[ $# -ge 2 ]] || { echo "--lab-root requires a path." >&2; exit 64; }
            LAB_ROOT="$2"; shift 2 ;;
        --card)
            [[ $# -ge 2 ]] || { echo "--card requires a name." >&2; exit 64; }
            ALSA_CARD="$2"; shift 2 ;;
        --live-config)
            [[ $# -ge 2 ]] || { echo "--live-config requires a path." >&2; exit 64; }
            LIVE_CONFIG="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 64 ;;
    esac
done

[[ "$ALSA_CARD" =~ ^[A-Za-z0-9_.@-]+$ ]] || { echo "Invalid ALSA card: $ALSA_CARD" >&2; exit 64; }
[[ -r "$LIVE_CONFIG" ]] || { echo "Shared ALSA fragment is not readable: $LIVE_CONFIG" >&2; exit 1; }
for command in python3 amixer aplay; do
    command -v "$command" >/dev/null 2>&1 || { echo "Required command not found: $command" >&2; exit 1; }
done

if [[ -z "$LAB_ROOT" ]]; then
    LAB_ROOT="$(mktemp -d /tmp/a-clockwork-plex-ctl-alias.XXXXXX)"
else
    mkdir -p "$LAB_ROOT"
    LAB_ROOT="$(cd "$LAB_ROOT" && pwd)"
fi
chmod 0700 "$LAB_ROOT"

ALIASES="$LAB_ROOT/control-aliases.conf"
ISOLATED_ROOT="$LAB_ROOT/alsa-isolated.conf"
RESULTS="$LAB_ROOT/results.tsv"
REPORT="$LAB_ROOT/report.txt"

cat >"$ALIASES" <<EOF_ALIASES
# A Clockwork Plex named ALSA control aliases — laboratory only.
ctl.acp_dmix {
    type hw
    card "$ALSA_CARD"
}
ctl.acp_master {
    type hw
    card "$ALSA_CARD"
}
ctl.acp_master_volume {
    type hw
    card "$ALSA_CARD"
}
ctl.acp_plexamp {
    type hw
    card "$ALSA_CARD"
}
ctl.acp_plexamp_volume {
    type hw
    card "$ALSA_CARD"
}
ctl.acp_airplay {
    type hw
    card "$ALSA_CARD"
}
ctl.acp_airplay_volume {
    type hw
    card "$ALSA_CARD"
}
ctl.acp_alarm {
    type hw
    card "$ALSA_CARD"
}
ctl.acp_alarm_volume {
    type hw
    card "$ALSA_CARD"
}
EOF_ALIASES

python3 - /usr/share/alsa/alsa.conf "$LIVE_CONFIG" "$ALIASES" "$ISOLATED_ROOT" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

base_path = Path(sys.argv[1])
live_path = Path(sys.argv[2])
alias_path = Path(sys.argv[3])
output_path = Path(sys.argv[4])

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

result.extend(("", live_path.read_text(encoding="utf-8"), "", alias_path.read_text(encoding="utf-8")))
output_path.write_text("\n".join(result).rstrip() + "\n", encoding="utf-8")
PY

printf 'check\texpected\tobserved\tresult\n' >"$RESULTS"
{
    echo "A Clockwork Plex ALSA named-control alias laboratory"
    echo "Generated: $(date --iso-8601=seconds)"
    echo "Directory: $LAB_ROOT"
    echo "Mode: $MODE"
    echo "Live fragment copied from: $LIVE_CONFIG"
    echo "Physical control target: hw:$ALSA_CARD"
    echo "Audio opened: no"
} >"$REPORT"

if ALSA_CONFIG_PATH="$ISOLATED_ROOT" aplay -L >"$LAB_ROOT/pcms.txt" 2>"$LAB_ROOT/alsa-parse.log"; then
    printf 'isolated-config-parse\tvalid\tvalid\tPASS\n' | tee -a "$RESULTS"
else
    printf 'isolated-config-parse\tvalid\tinvalid\tFAIL\n' | tee -a "$RESULTS"
    exit 1
fi

cat <<EOF_STATUS

A Clockwork Plex control-alias laboratory prepared.

  Directory:       $LAB_ROOT
  Alias fragment:  $ALIASES
  Isolated config: $ISOLATED_ROOT
  Card target:     hw:$ALSA_CARD

No production file, service, mixer value or audio route has been changed.
EOF_STATUS

if [[ "$MODE" == prepare ]]; then
    cat <<EOF_PREPARE

To perform the read-only control-open matrix:

  bash scripts/test-alsa-control-alias-lab.sh --run --lab-root "$LAB_ROOT"
EOF_PREPARE
    exit 0
fi

# Record the present production behaviour for the exact Plexamp identifier.
if amixer -D acp_plexamp scontrols >"$LAB_ROOT/live-acp-plexamp.txt" 2>"$LAB_ROOT/live-acp-plexamp.err"; then
    printf 'live-ctl-acp_plexamp\topen\topen\tPASS\n' | tee -a "$RESULTS"
else
    live_error="$(tr '\n' ' ' <"$LAB_ROOT/live-acp-plexamp.err" | sed 's/[[:space:]]\+/ /g' | cut -c1-180)"
    printf 'live-ctl-acp_plexamp\topen\t%s\tINFO\n' "${live_error:-failed}" | tee -a "$RESULTS"
fi

failures=0
for name in acp_dmix acp_master acp_master_volume acp_plexamp acp_plexamp_volume acp_airplay acp_airplay_volume acp_alarm acp_alarm_volume; do
    if ALSA_CONFIG_PATH="$ISOLATED_ROOT" amixer -D "$name" scontrols >"$LAB_ROOT/$name.txt" 2>"$LAB_ROOT/$name.err"; then
        printf 'isolated-ctl-%s\topen\topen\tPASS\n' "$name" | tee -a "$RESULTS"
    else
        observed="$(tr '\n' ' ' <"$LAB_ROOT/$name.err" | sed 's/[[:space:]]\+/ /g' | cut -c1-180)"
        printf 'isolated-ctl-%s\topen\t%s\tFAIL\n' "$name" "${observed:-failed}" | tee -a "$RESULTS"
        failures=$((failures + 1))
    fi
done

{
    echo
    echo "Results:"
    cat "$RESULTS"
    echo
    echo "Live acp_plexamp stderr:"
    cat "$LAB_ROOT/live-acp-plexamp.err" 2>/dev/null || true
    echo
    echo "Isolated parser diagnostics:"
    cat "$LAB_ROOT/alsa-parse.log" 2>/dev/null || true
} >>"$REPORT"

cat <<EOF_DONE

Control-alias laboratory complete.

  Summary:  $RESULTS
  Detail:   $REPORT
  Failures: $failures

Only ALSA control handles were opened. No PCM/audio device was opened.
EOF_DONE

[[ "$failures" -eq 0 ]]
