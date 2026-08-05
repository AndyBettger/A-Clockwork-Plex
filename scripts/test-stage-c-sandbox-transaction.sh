#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIRED_CONFIRMATION="STAGE-C4-SANDBOX-TRANSACTION"
MODE="prepare"
PACKAGE_ROOT=""
STAGE_C3_ROOT=""
SANDBOX_ROOT=""
CONFIRM=""

usage() {
  cat <<'EOF'
Usage:
  test-stage-c-sandbox-transaction.sh \
    --package-root /var/tmp/<stage-c1-package> \
    --stage-c3-root /var/tmp/<stage-c3-snapshot>

  test-stage-c-sandbox-transaction.sh \
    --run-sandbox \
    --confirm STAGE-C4-SANDBOX-TRANSACTION \
    --package-root /var/tmp/<stage-c1-package> \
    --stage-c3-root /var/tmp/<stage-c3-snapshot> \
    --sandbox-root /var/tmp/a-clockwork-plex-stage-c4-sandbox.<suffix>

The default is prepare-only. It invokes no sudo and creates no sandbox.
The guarded run mutates only a synthetic root beneath the supplied Stage C4
sandbox directory. It has no production activation or install interface.
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
    --sandbox-root)
      [[ $# -ge 2 ]] || { echo "--sandbox-root requires a value" >&2; exit 2; }
      SANDBOX_ROOT="$2"
      shift 2
      ;;
    --confirm)
      [[ $# -ge 2 ]] || { echo "--confirm requires a value" >&2; exit 2; }
      CONFIRM="$2"
      shift 2
      ;;
    --run-sandbox)
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
[[ -n "$STAGE_C3_ROOT" ]] || { echo "--stage-c3-root is required" >&2; exit 2; }
[[ -f "$PACKAGE_ROOT/manifest.tsv" && -d "$PACKAGE_ROOT/rootfs" ]] || {
  echo "Stage C1 package is missing manifest.tsv or rootfs/: $PACKAGE_ROOT" >&2
  exit 2
}
[[ -f "$STAGE_C3_ROOT/results.tsv" && -f "$STAGE_C3_ROOT/evidence-manifest.tsv" ]] || {
  echo "Stage C3 evidence is missing results.tsv or evidence-manifest.tsv: $STAGE_C3_ROOT" >&2
  exit 2
}

if [[ "$MODE" == "prepare" ]]; then
  PACKAGE_ABS="$(cd "$PACKAGE_ROOT" && pwd -P)"
  STAGE_C3_ABS="$(cd "$STAGE_C3_ROOT" && pwd -P)"
  cat <<EOF
A Clockwork Plex Stage C4 sandbox transaction rehearsal is prepared.

Stage C1 package: $PACKAGE_ABS
Stage C3 evidence: $STAGE_C3_ABS

Prepare-only invoked no sudo and created no sandbox.

After review, run the exact sandbox-only rehearsal:

  SANDBOX="\$(mktemp -d /var/tmp/a-clockwork-plex-stage-c4-sandbox.XXXXXX)"
  chmod 0700 "\$SANDBOX"
  echo "SANDBOX=\$SANDBOX"

  bash scripts/test-stage-c-sandbox-transaction.sh \\
    --run-sandbox \\
    --confirm $REQUIRED_CONFIRMATION \\
    --package-root "$PACKAGE_ABS" \\
    --stage-c3-root "$STAGE_C3_ABS" \\
    --sandbox-root "\$SANDBOX"

The run has no sudo command and cannot write outside the fresh synthetic sandbox.
It executes no service, mixer, module, PCM, DAC or CamillaDSP command.
EOF
  exit 0
fi

[[ "$CONFIRM" == "$REQUIRED_CONFIRMATION" ]] || {
  echo "Exact confirmation token required: $REQUIRED_CONFIRMATION" >&2
  exit 2
}
[[ -n "$SANDBOX_ROOT" ]] || { echo "--sandbox-root is required for --run-sandbox" >&2; exit 2; }

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -B -m stage_c_transaction.sandbox_transaction_runtime \
  --confirm "$CONFIRM" \
  --package-root "$PACKAGE_ROOT" \
  --stage-c3-root "$STAGE_C3_ROOT" \
  --sandbox-root "$SANDBOX_ROOT"
