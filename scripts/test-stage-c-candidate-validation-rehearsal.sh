#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
REQUIRED_CONFIRMATION="STAGE-C16-CANDIDATE-STAGE-VALIDATE-ABORT"
MODE="prepare"
CONFIRMATION=""
PACKAGE_ROOT=""
STAGE_C15_ROOT=""
EVIDENCE_ROOT=""

usage() {
  cat <<'EOF'
Usage:
  bash scripts/test-stage-c-candidate-validation-rehearsal.sh

  bash scripts/test-stage-c-candidate-validation-rehearsal.sh \
    --rehearse-candidate-validation \
    --confirm STAGE-C16-CANDIDATE-STAGE-VALIDATE-ABORT \
    --package-root /var/tmp/a-clockwork-plex-stage-c1-review-v2.XXXXXX \
    --stage-c15-root /var/tmp/a-clockwork-plex-stage-c15-authoritative-snapshot.XXXXXX \
    --evidence-root /var/tmp/a-clockwork-plex-stage-c16-candidate-validation.XXXXXX

The default invocation is prepare-only. The guarded rehearsal stages and validates
candidate files only inside a fresh authoritative transaction, then aborts before
any service, route, mixer, PCM, DAC or production-file mutation.
EOF
}

while (($#)); do
  case "$1" in
    --rehearse-candidate-validation)
      MODE="rehearse"
      shift
      ;;
    --confirm)
      [[ $# -ge 2 ]] || { echo "Missing value for --confirm" >&2; exit 64; }
      CONFIRMATION="$2"
      shift 2
      ;;
    --package-root)
      [[ $# -ge 2 ]] || { echo "Missing value for --package-root" >&2; exit 64; }
      PACKAGE_ROOT="$2"
      shift 2
      ;;
    --stage-c15-root)
      [[ $# -ge 2 ]] || { echo "Missing value for --stage-c15-root" >&2; exit 64; }
      STAGE_C15_ROOT="$2"
      shift 2
      ;;
    --evidence-root)
      [[ $# -ge 2 ]] || { echo "Missing value for --evidence-root" >&2; exit 64; }
      EVIDENCE_ROOT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 64
      ;;
  esac
done

if [[ "$MODE" == "prepare" ]]; then
  cat <<'EOF'
A Clockwork Plex Stage C16 candidate staging and validation rehearsal is prepared.

Prepare-only invoked no sudo, performed no host observation, created no Stage C16
evidence directory, production lock, production transaction or candidate tree.

After review, run the exact guarded rehearsal using the retained Stage C1 package
and successful Stage C15 evidence:

  PACKAGE=/var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY
  STAGE_C15=/var/tmp/a-clockwork-plex-stage-c15-authoritative-snapshot.wg3sxB
  EVIDENCE="$(mktemp -d /var/tmp/a-clockwork-plex-stage-c16-candidate-validation.XXXXXX)"
  chmod 0700 "$EVIDENCE"
  echo "EVIDENCE=$EVIDENCE"

  bash scripts/test-stage-c-candidate-validation-rehearsal.sh \
    --rehearse-candidate-validation \
    --confirm STAGE-C16-CANDIDATE-STAGE-VALIDATE-ABORT \
    --package-root "$PACKAGE" \
    --stage-c15-root "$STAGE_C15" \
    --evidence-root "$EVIDENCE" \
    2>&1 | tee /tmp/acp-stage-c16-run.txt

The guarded rehearsal uses one constrained sudo command. It creates a fresh
root-owned transaction while the production lock is held, captures the exact
snapshot, stages all twelve package files only beneath that transaction, performs
isolated read-only candidate validation, retains non-authoritative evidence,
then aborts and removes the transaction before any appliance mutation. Service
stop, DAC release, installation, route selection, audio and commit remain blocked.
EOF
  exit 0
fi

[[ "$CONFIRMATION" == "$REQUIRED_CONFIRMATION" ]] || {
  echo "Guarded Stage C16 rehearsal requires --confirm $REQUIRED_CONFIRMATION" >&2
  exit 64
}
[[ -n "$PACKAGE_ROOT" ]] || { echo "--package-root is required" >&2; exit 64; }
[[ -n "$STAGE_C15_ROOT" ]] || { echo "--stage-c15-root is required" >&2; exit 64; }
[[ -n "$EVIDENCE_ROOT" ]] || { echo "--evidence-root is required" >&2; exit 64; }

exec sudo env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="$REPO_ROOT:$REPO_ROOT/scripts" \
  python3 -m stage_c_transaction.candidate_validation_rehearsal \
    --package-root "$PACKAGE_ROOT" \
    --stage-c15-root "$STAGE_C15_ROOT" \
    --evidence-root "$EVIDENCE_ROOT" \
    --confirm "$CONFIRMATION"
