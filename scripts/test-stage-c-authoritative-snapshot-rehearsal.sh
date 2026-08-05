#!/usr/bin/env bash
set -euo pipefail

REQUIRED_CONFIRMATION="STAGE-C15-AUTHORITATIVE-SNAPSHOT-ABORT"
MODE="prepare"
PACKAGE_ROOT=""
STAGE_C14_ROOT=""
EVIDENCE_ROOT=""
CONFIRM=""

usage() {
  cat <<'EOF'
Usage:
  bash scripts/test-stage-c-authoritative-snapshot-rehearsal.sh

  bash scripts/test-stage-c-authoritative-snapshot-rehearsal.sh \
    --rehearse-authoritative-snapshot \
    --confirm STAGE-C15-AUTHORITATIVE-SNAPSHOT-ABORT \
    --package-root /var/tmp/a-clockwork-plex-stage-c1-review-... \
    --stage-c14-root /var/tmp/a-clockwork-plex-stage-c14-production-lock.... \
    --evidence-root /var/tmp/a-clockwork-plex-stage-c15-authoritative-snapshot....

Prepare-only is the default. It invokes no sudo, performs no host observation
and creates neither the production lock nor a production transaction.
EOF
}

while (($#)); do
  case "$1" in
    --rehearse-authoritative-snapshot)
      MODE="rehearse"
      shift
      ;;
    --confirm)
      CONFIRM="${2-}"
      shift 2
      ;;
    --package-root)
      PACKAGE_ROOT="${2-}"
      shift 2
      ;;
    --stage-c14-root)
      STAGE_C14_ROOT="${2-}"
      shift 2
      ;;
    --evidence-root)
      EVIDENCE_ROOT="${2-}"
      shift 2
      ;;
    -h|--help)
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

if [[ "$MODE" == "prepare" ]]; then
  cat <<'EOF'
A Clockwork Plex Stage C15 authoritative snapshot transaction rehearsal is prepared.

Prepare-only invoked no sudo, performed no host observation, created no Stage C15
evidence directory, production lock or production transaction.

After review, run the exact guarded rehearsal using the retained Stage C1 package
and successful Stage C14 evidence:

  PACKAGE=/var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY
  STAGE_C14=/var/tmp/a-clockwork-plex-stage-c14-production-lock.qiZvzh
  EVIDENCE="$(mktemp -d /var/tmp/a-clockwork-plex-stage-c15-authoritative-snapshot.XXXXXX)"
  chmod 0700 "$EVIDENCE"
  echo "EVIDENCE=$EVIDENCE"

  bash scripts/test-stage-c-authoritative-snapshot-rehearsal.sh \
    --rehearse-authoritative-snapshot \
    --confirm STAGE-C15-AUTHORITATIVE-SNAPSHOT-ABORT \
    --package-root "$PACKAGE" \
    --stage-c14-root "$STAGE_C14" \
    --evidence-root "$EVIDENCE" \
    2>&1 | tee /tmp/acp-stage-c15-run.txt

The guarded rehearsal uses one constrained sudo command. It creates one fresh
root-owned transaction under the fixed production transaction root, captures an
exact snapshot while the real production lock is held, copies that transaction
as non-authoritative review evidence, aborts it before package staging, removes
it exactly and only then releases the lock. No audio-appliance mutation exists.
EOF
  exit 0
fi

if [[ "$CONFIRM" != "$REQUIRED_CONFIRMATION" ]]; then
  echo "Exact confirmation required: $REQUIRED_CONFIRMATION" >&2
  exit 2
fi
if [[ -z "$PACKAGE_ROOT" || -z "$STAGE_C14_ROOT" || -z "$EVIDENCE_ROOT" ]]; then
  echo "--package-root, --stage-c14-root and --evidence-root are required" >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$REPO_ROOT"

exec sudo env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="$REPO_ROOT/scripts" \
  python3 -m stage_c_transaction.authoritative_snapshot_rehearsal \
  --package-root "$PACKAGE_ROOT" \
  --stage-c14-root "$STAGE_C14_ROOT" \
  --evidence-root "$EVIDENCE_ROOT" \
  --confirm "$CONFIRM"
