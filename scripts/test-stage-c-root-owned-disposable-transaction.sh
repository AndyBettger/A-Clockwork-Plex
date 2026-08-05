#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIRED_CONFIRMATION="STAGE-C7-ROOT-OWNED-DISPOSABLE-TRANSACTION"
MODE="prepare"
PACKAGE_ROOT=""
STAGE_C6_ROOT=""
REHEARSAL_ROOT=""
CONFIRM=""

usage() {
  cat <<'EOF'
Usage:
  test-stage-c-root-owned-disposable-transaction.sh \
    --package-root /var/tmp/<stage-c1-package> \
    --stage-c6-root /var/tmp/<stage-c6-snapshot>

  test-stage-c-root-owned-disposable-transaction.sh \
    --run-disposable-root \
    --confirm STAGE-C7-ROOT-OWNED-DISPOSABLE-TRANSACTION \
    --package-root /var/tmp/<stage-c1-package> \
    --stage-c6-root /var/tmp/<stage-c6-snapshot> \
    --rehearsal-root /var/tmp/a-clockwork-plex-stage-c7-root-transaction.<suffix>

The default is prepare-only. It invokes no sudo and creates no rehearsal root.
The guarded run uses one constrained sudo command and writes only beneath the
fresh disposable Stage C7 root. It has no production route, service or audio action.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --package-root)
      [[ $# -ge 2 ]] || { echo "--package-root requires a value" >&2; exit 2; }
      PACKAGE_ROOT="$2"
      shift 2
      ;;
    --stage-c6-root)
      [[ $# -ge 2 ]] || { echo "--stage-c6-root requires a value" >&2; exit 2; }
      STAGE_C6_ROOT="$2"
      shift 2
      ;;
    --rehearsal-root)
      [[ $# -ge 2 ]] || { echo "--rehearsal-root requires a value" >&2; exit 2; }
      REHEARSAL_ROOT="$2"
      shift 2
      ;;
    --confirm)
      [[ $# -ge 2 ]] || { echo "--confirm requires a value" >&2; exit 2; }
      CONFIRM="$2"
      shift 2
      ;;
    --run-disposable-root)
      MODE="run"
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
[[ -n "$STAGE_C6_ROOT" ]] || { echo "--stage-c6-root is required" >&2; exit 2; }

[[ -f "$PACKAGE_ROOT/manifest.tsv" && -d "$PACKAGE_ROOT/rootfs" ]] || {
  echo "Stage C1 package is missing manifest.tsv or rootfs/: $PACKAGE_ROOT" >&2
  exit 2
}
[[ -f "$STAGE_C6_ROOT/results.tsv" && -f "$STAGE_C6_ROOT/evidence-manifest.tsv" ]] || {
  echo "Stage C6 evidence is incomplete: $STAGE_C6_ROOT" >&2
  exit 2
}

if [[ "$MODE" == "prepare" ]]; then
  PACKAGE_ABS="$(cd "$PACKAGE_ROOT" && pwd -P)"
  STAGE_C6_ABS="$(cd "$STAGE_C6_ROOT" && pwd -P)"
  cat <<EOF
A Clockwork Plex Stage C7 root-owned disposable transaction rehearsal is prepared.

Stage C1 package: $PACKAGE_ABS
Stage C6 evidence: $STAGE_C6_ABS

Prepare-only invoked no sudo and created no Stage C7 rehearsal directory.

After review, run the exact disposable-root rehearsal:

  ROOT="\$(mktemp -d /var/tmp/a-clockwork-plex-stage-c7-root-transaction.XXXXXX)"
  chmod 0700 "\$ROOT"
  echo "ROOT=\$ROOT"

  bash scripts/test-stage-c-root-owned-disposable-transaction.sh \\
    --run-disposable-root \\
    --confirm $REQUIRED_CONFIRMATION \\
    --package-root "$PACKAGE_ABS" \\
    --stage-c6-root "$STAGE_C6_ABS" \\
    --rehearsal-root "\$ROOT"

The run uses one constrained sudo command. Root writes only beneath the fresh
Stage C7 directory. All production-style destinations are remapped into four
disposable system roots. No service, mixer, module, PCM, DAC or CamillaDSP
command exists, and the real production lock path is never opened.
EOF
  exit 0
fi

[[ "$EUID" -ne 0 ]] || {
  echo "Run the outer Stage C7 wrapper as the normal project user, not as root." >&2
  exit 2
}
[[ "$CONFIRM" == "$REQUIRED_CONFIRMATION" ]] || {
  echo "Exact confirmation token required: $REQUIRED_CONFIRMATION" >&2
  exit 2
}
[[ -n "$REHEARSAL_ROOT" ]] || { echo "--rehearsal-root is required" >&2; exit 2; }

export PYTHONDONTWRITEBYTECODE=1
PYTHONPATH_VALUE="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"

exec sudo env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="$PYTHONPATH_VALUE" \
  python3 -B -m stage_c_transaction.root_owned_transaction \
    --confirm "$CONFIRM" \
    --package-root "$PACKAGE_ROOT" \
    --stage-c6-root "$STAGE_C6_ROOT" \
    --rehearsal-root "$REHEARSAL_ROOT"
