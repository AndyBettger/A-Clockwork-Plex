#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIRED_CONFIRMATION="STAGE-C6-LOCKED-PRIVILEGED-SNAPSHOT-READ-ONLY"
MODE="prepare"
PACKAGE_ROOT=""
STAGE_C3_ROOT=""
STAGE_C4_ROOT=""
STAGE_C5_ROOT=""
SNAPSHOT_ROOT=""
CONFIRM=""

usage() {
  cat <<'EOF'
Usage:
  test-stage-c-locked-privileged-snapshot.sh \
    --package-root /var/tmp/<stage-c1-package> \
    --stage-c3-root /var/tmp/<stage-c3-snapshot> \
    --stage-c4-root /var/tmp/<stage-c4-sandbox> \
    --stage-c5-root /var/tmp/<stage-c5-review>

  test-stage-c-locked-privileged-snapshot.sh \
    --capture-read-only \
    --confirm STAGE-C6-LOCKED-PRIVILEGED-SNAPSHOT-READ-ONLY \
    --package-root /var/tmp/<stage-c1-package> \
    --stage-c3-root /var/tmp/<stage-c3-snapshot> \
    --stage-c4-root /var/tmp/<stage-c4-sandbox> \
    --stage-c5-root /var/tmp/<stage-c5-review> \
    --snapshot-root /var/tmp/a-clockwork-plex-stage-c6-snapshot.<suffix>

The default is prepare-only. It invokes no sudo and creates no evidence directory.
The guarded capture uses one constrained sudo command, writes only inside the
fresh Stage C6 evidence directory and does not open the production route lock.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --package-root)
      [[ $# -ge 2 ]] || { echo "--package-root requires a value" >&2; exit 2; }
      PACKAGE_ROOT="$2"
      shift 2
      ;;
    --stage-c3-root)
      [[ $# -ge 2 ]] || { echo "--stage-c3-root requires a value" >&2; exit 2; }
      STAGE_C3_ROOT="$2"
      shift 2
      ;;
    --stage-c4-root)
      [[ $# -ge 2 ]] || { echo "--stage-c4-root requires a value" >&2; exit 2; }
      STAGE_C4_ROOT="$2"
      shift 2
      ;;
    --stage-c5-root)
      [[ $# -ge 2 ]] || { echo "--stage-c5-root requires a value" >&2; exit 2; }
      STAGE_C5_ROOT="$2"
      shift 2
      ;;
    --snapshot-root)
      [[ $# -ge 2 ]] || { echo "--snapshot-root requires a value" >&2; exit 2; }
      SNAPSHOT_ROOT="$2"
      shift 2
      ;;
    --confirm)
      [[ $# -ge 2 ]] || { echo "--confirm requires a value" >&2; exit 2; }
      CONFIRM="$2"
      shift 2
      ;;
    --capture-read-only)
      MODE="capture"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[[ -n "$PACKAGE_ROOT" ]] || { echo "--package-root is required" >&2; exit 2; }
[[ -n "$STAGE_C3_ROOT" ]] || { echo "--stage-c3-root is required" >&2; exit 2; }
[[ -n "$STAGE_C4_ROOT" ]] || { echo "--stage-c4-root is required" >&2; exit 2; }
[[ -n "$STAGE_C5_ROOT" ]] || { echo "--stage-c5-root is required" >&2; exit 2; }

[[ -f "$PACKAGE_ROOT/manifest.tsv" && -d "$PACKAGE_ROOT/rootfs" ]] || {
  echo "Stage C1 package is missing manifest.tsv or rootfs/: $PACKAGE_ROOT" >&2
  exit 2
}
[[ -f "$STAGE_C3_ROOT/results.tsv" && -f "$STAGE_C3_ROOT/evidence-manifest.tsv" ]] || {
  echo "Stage C3 evidence is incomplete: $STAGE_C3_ROOT" >&2
  exit 2
}
[[ -f "$STAGE_C4_ROOT/scenario-state.tsv" && -f "$STAGE_C4_ROOT/evidence-manifest.tsv" ]] || {
  echo "Stage C4 evidence is incomplete: $STAGE_C4_ROOT" >&2
  exit 2
}
[[ -f "$STAGE_C5_ROOT/transaction-state-machine.tsv" && -f "$STAGE_C5_ROOT/evidence-manifest.tsv" ]] || {
  echo "Stage C5 evidence is incomplete: $STAGE_C5_ROOT" >&2
  exit 2
}

if [[ "$MODE" == "prepare" ]]; then
  PACKAGE_ABS="$(cd "$PACKAGE_ROOT" && pwd -P)"
  STAGE_C3_ABS="$(cd "$STAGE_C3_ROOT" && pwd -P)"
  STAGE_C4_ABS="$(cd "$STAGE_C4_ROOT" && pwd -P)"
  STAGE_C5_ABS="$(cd "$STAGE_C5_ROOT" && pwd -P)"
  cat <<EOF
A Clockwork Plex Stage C6 locked privileged snapshot rehearsal is prepared.

Stage C1 package: $PACKAGE_ABS
Stage C3 evidence: $STAGE_C3_ABS
Stage C4 evidence: $STAGE_C4_ABS
Stage C5 evidence: $STAGE_C5_ABS

Prepare-only invoked no sudo and created no Stage C6 evidence directory.

After review, run the exact read-only capture:

  SNAP="\$(mktemp -d /var/tmp/a-clockwork-plex-stage-c6-snapshot.XXXXXX)"
  chmod 0700 "\$SNAP"
  echo "SNAP=\$SNAP"

  bash scripts/test-stage-c-locked-privileged-snapshot.sh \\
    --capture-read-only \\
    --confirm $REQUIRED_CONFIRMATION \\
    --package-root "$PACKAGE_ABS" \\
    --stage-c3-root "$STAGE_C3_ABS" \\
    --stage-c4-root "$STAGE_C4_ABS" \\
    --stage-c5-root "$STAGE_C5_ABS" \\
    --snapshot-root "\$SNAP"

The capture uses one constrained sudo command. Root may read protected host state,
but it may write only inside the fresh Stage C6 evidence directory. The real
/run/lock/a-clockwork-plex-audio-route.lock path is inspected and must remain absent.
No service, mixer, module, PCM, DAC or CamillaDSP state is changed.
EOF
  exit 0
fi

[[ "$EUID" -ne 0 ]] || {
  echo "Run the outer Stage C6 wrapper as the normal project user, not as root." >&2
  exit 2
}
[[ "$CONFIRM" == "$REQUIRED_CONFIRMATION" ]] || {
  echo "Exact confirmation token required: $REQUIRED_CONFIRMATION" >&2
  exit 2
}
[[ -n "$SNAPSHOT_ROOT" ]] || { echo "--snapshot-root is required" >&2; exit 2; }

export PYTHONDONTWRITEBYTECODE=1
PYTHONPATH_VALUE="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"

exec sudo env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="$PYTHONPATH_VALUE" \
  python3 -B -m stage_c_transaction.locked_snapshot \
    --confirm "$CONFIRM" \
    --package-root "$PACKAGE_ROOT" \
    --stage-c3-root "$STAGE_C3_ROOT" \
    --stage-c4-root "$STAGE_C4_ROOT" \
    --stage-c5-root "$STAGE_C5_ROOT" \
    --snapshot-root "$SNAPSHOT_ROOT"
