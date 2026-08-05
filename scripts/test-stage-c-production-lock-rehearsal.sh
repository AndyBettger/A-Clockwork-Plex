#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIRED_CONFIRMATION="STAGE-C14-PRODUCTION-LOCK-ONLY"
MODE="prepare"
EVIDENCE_ROOT=""
CONFIRM=""

usage() {
  cat <<'EOF'
Usage:
  test-stage-c-production-lock-rehearsal.sh

  test-stage-c-production-lock-rehearsal.sh \
    --rehearse-production-lock \
    --confirm STAGE-C14-PRODUCTION-LOCK-ONLY \
    --evidence-root /var/tmp/a-clockwork-plex-stage-c14-production-lock.<suffix>

The default is prepare-only. It invokes no sudo, creates no evidence directory,
performs no host observation and does not create the production lock.

The guarded rehearsal temporarily creates and exclusively holds only:
  /run/lock/a-clockwork-plex-audio-route.lock

It proves contention, takes the existing six typed read-only observations,
then releases and removes the exact original lock inode. No production
transaction, filesystem snapshot, service, mixer, audio or route mutation exists.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rehearse-production-lock)
      MODE="rehearse"
      shift
      ;;
    --confirm)
      [[ $# -ge 2 ]] || { echo "--confirm requires a value" >&2; exit 2; }
      CONFIRM="$2"
      shift 2
      ;;
    --evidence-root)
      [[ $# -ge 2 ]] || { echo "--evidence-root requires a value" >&2; exit 2; }
      EVIDENCE_ROOT="$2"
      shift 2
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

if [[ "$MODE" == "prepare" ]]; then
  cat <<EOF
A Clockwork Plex Stage C14 production-lock-only rehearsal is prepared.

Prepare-only invoked no sudo, performed no host observation, created no
Stage C14 evidence directory and did not create the production lock.

After review, run the exact guarded rehearsal:

  EVIDENCE="\$(mktemp -d /var/tmp/a-clockwork-plex-stage-c14-production-lock.XXXXXX)"
  chmod 0700 "\$EVIDENCE"
  echo "EVIDENCE=\$EVIDENCE"

  bash scripts/test-stage-c-production-lock-rehearsal.sh \\
    --rehearse-production-lock \\
    --confirm $REQUIRED_CONFIRMATION \\
    --evidence-root "\$EVIDENCE" \\
    2>&1 | tee /tmp/acp-stage-c14-run.txt

The guarded rehearsal uses one constrained sudo command. Root writes only to
the fresh evidence directory and the temporary fixed production-lock pathname.
The exact lock inode is held, contention-tested, unlinked while held, unlocked
and closed. No production transaction or audio-appliance mutation is available.
EOF
  exit 0
fi

[[ "$EUID" -ne 0 ]] || {
  echo "Run the outer Stage C14 wrapper as the normal project user, not as root." >&2
  exit 2
}
[[ "$CONFIRM" == "$REQUIRED_CONFIRMATION" ]] || {
  echo "Exact confirmation token required: $REQUIRED_CONFIRMATION" >&2
  exit 2
}
[[ -n "$EVIDENCE_ROOT" ]] || { echo "--evidence-root is required" >&2; exit 2; }

export PYTHONDONTWRITEBYTECODE=1
PYTHONPATH_VALUE="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"

exec sudo env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="$PYTHONPATH_VALUE" \
  python3 -B -m stage_c_transaction.production_lock_rehearsal \
    --confirm "$CONFIRM" \
    --evidence-root "$EVIDENCE_ROOT"