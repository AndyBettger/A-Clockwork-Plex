#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIRED_CONFIRMATION="STAGE-C5-PRODUCTION-TRANSACTION-PLAN-REVIEW"
MODE="prepare"
PACKAGE_ROOT=""
STAGE_C3_ROOT=""
STAGE_C4_ROOT=""
REVIEW_ROOT=""
CONFIRM=""

usage() {
  cat <<'EOF'
Usage:
  prepare-stage-c-production-transaction-plan.sh \
    --package-root /var/tmp/<stage-c1-package> \
    --stage-c3-root /var/tmp/<stage-c3-snapshot> \
    --stage-c4-root /var/tmp/<stage-c4-sandbox>

  prepare-stage-c-production-transaction-plan.sh \
    --generate-review \
    --confirm STAGE-C5-PRODUCTION-TRANSACTION-PLAN-REVIEW \
    --package-root /var/tmp/<stage-c1-package> \
    --stage-c3-root /var/tmp/<stage-c3-snapshot> \
    --stage-c4-root /var/tmp/<stage-c4-sandbox> \
    --review-root /var/tmp/a-clockwork-plex-stage-c5-review.<suffix>

The default is prepare-only. It invokes no sudo and creates no review directory.
The guarded generation writes only review evidence beneath the supplied Stage C5
directory. It has no root adapter, activation, installation or rollback interface.
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
    --review-root)
      [[ $# -ge 2 ]] || { echo "--review-root requires a value" >&2; exit 2; }
      REVIEW_ROOT="$2"
      shift 2
      ;;
    --confirm)
      [[ $# -ge 2 ]] || { echo "--confirm requires a value" >&2; exit 2; }
      CONFIRM="$2"
      shift 2
      ;;
    --generate-review)
      MODE="generate"
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
[[ -f "$PACKAGE_ROOT/manifest.tsv" && -d "$PACKAGE_ROOT/rootfs" ]] || {
  echo "Stage C1 package is missing manifest.tsv or rootfs/: $PACKAGE_ROOT" >&2
  exit 2
}
[[ -f "$STAGE_C3_ROOT/results.tsv" && -f "$STAGE_C3_ROOT/evidence-manifest.tsv" ]] || {
  echo "Stage C3 evidence is missing results.tsv or evidence-manifest.tsv: $STAGE_C3_ROOT" >&2
  exit 2
}
[[ -f "$STAGE_C4_ROOT/results.tsv" && -f "$STAGE_C4_ROOT/evidence-manifest.tsv" ]] || {
  echo "Stage C4 evidence is missing results.tsv or evidence-manifest.tsv: $STAGE_C4_ROOT" >&2
  exit 2
}

if [[ "$MODE" == "prepare" ]]; then
  PACKAGE_ABS="$(cd "$PACKAGE_ROOT" && pwd -P)"
  STAGE_C3_ABS="$(cd "$STAGE_C3_ROOT" && pwd -P)"
  STAGE_C4_ABS="$(cd "$STAGE_C4_ROOT" && pwd -P)"
  cat <<EOF
A Clockwork Plex Stage C5 production transaction plan review is prepared.

Stage C1 package: $PACKAGE_ABS
Stage C3 evidence: $STAGE_C3_ABS
Stage C4 evidence: $STAGE_C4_ABS

Prepare-only invoked no sudo and created no review directory.

After review, generate the exact review-only evidence:

  REVIEW="\$(mktemp -d /var/tmp/a-clockwork-plex-stage-c5-review.XXXXXX)"
  chmod 0700 "\$REVIEW"
  echo "REVIEW=\$REVIEW"

  bash scripts/prepare-stage-c-production-transaction-plan.sh \\
    --generate-review \\
    --confirm $REQUIRED_CONFIRMATION \\
    --package-root "$PACKAGE_ABS" \\
    --stage-c3-root "$STAGE_C3_ABS" \\
    --stage-c4-root "$STAGE_C4_ABS" \\
    --review-root "\$REVIEW"

The generation has no sudo command and cannot write outside the fresh review directory.
It does not acquire the production route lock or execute any service or audio command.
EOF
  exit 0
fi

[[ "$CONFIRM" == "$REQUIRED_CONFIRMATION" ]] || {
  echo "Exact review confirmation token required: $REQUIRED_CONFIRMATION" >&2
  exit 2
}
[[ -n "$REVIEW_ROOT" ]] || { echo "--review-root is required for --generate-review" >&2; exit 2; }

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -B -m stage_c_transaction.production_plan \
  --confirm "$CONFIRM" \
  --package-root "$PACKAGE_ROOT" \
  --stage-c3-root "$STAGE_C3_ROOT" \
  --stage-c4-root "$STAGE_C4_ROOT" \
  --review-root "$REVIEW_ROOT"
