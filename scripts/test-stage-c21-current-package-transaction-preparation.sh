#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
REQUIRED_CONFIRMATION="STAGE-C21-CURRENT-PACKAGE-STAGE-VALIDATE-ABORT"
MODE="prepare"
CONFIRMATION=""
PACKAGE_ROOT=""
BASELINE_ROOT=""
EVIDENCE_ROOT=""

usage() {
  cat <<'EOF'
Usage:
  bash scripts/test-stage-c21-current-package-transaction-preparation.sh

  bash scripts/test-stage-c21-current-package-transaction-preparation.sh \
    --rehearse-current-package \
    --confirm STAGE-C21-CURRENT-PACKAGE-STAGE-VALIDATE-ABORT \
    --package-root /var/tmp/a-clockwork-plex-stage-c21-activation-package-v2.XXXXXX \
    --baseline-root /var/tmp/a-clockwork-plex-stage-c21-production-baseline.XXXXXX \
    --evidence-root /var/tmp/a-clockwork-plex-stage-c21-current-package-preparation.XXXXXX

The default invocation is prepare-only and invokes no sudo or host observation.
The guarded rehearsal acquires the canonical production lock, creates one fresh
authoritative transaction, captures the exact five-domain snapshot, stages and
validates the accepted current package only below that transaction, retains
review evidence, then aborts and releases the lock before any appliance mutation.
EOF
}

while (($#)); do
  case "$1" in
    --rehearse-current-package)
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
    --baseline-root)
      [[ $# -ge 2 ]] || { echo "Missing value for --baseline-root" >&2; exit 64; }
      BASELINE_ROOT="$2"
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
A Clockwork Plex Stage C21 current-package transaction rehearsal is prepared.

Prepare-only invoked no sudo, performed no host observation and created no
production lock, transaction, evidence root, candidate tree or approval object.

The separately approved guarded mode requires:

  PACKAGE="$(ls -dt /var/tmp/a-clockwork-plex-stage-c21-activation-package-v2.* | head -n1)"
  BASELINE=/var/tmp/a-clockwork-plex-stage-c21-production-baseline.5m73n8ac
  EVIDENCE="$(mktemp -d /var/tmp/a-clockwork-plex-stage-c21-current-package-preparation.XXXXXX)"
  chmod 0700 "$EVIDENCE"
  echo "PACKAGE=$PACKAGE"
  echo "BASELINE=$BASELINE"
  echo "EVIDENCE=$EVIDENCE"

  bash scripts/test-stage-c21-current-package-transaction-preparation.sh \
    --rehearse-current-package \
    --confirm STAGE-C21-CURRENT-PACKAGE-STAGE-VALIDATE-ABORT \
    --package-root "$PACKAGE" \
    --baseline-root "$BASELINE" \
    --evidence-root "$EVIDENCE"

Do not run the guarded mode without a separate explicit approval. It stops before
service stop, DAC release, installation, systemd reload, route selection, mixer
write, approval publication, CamillaDSP startup, audio probes or activation.
EOF
  exit 0
fi

if [[ "$EUID" -eq 0 ]]; then
  echo "Run this wrapper as the normal project user; it invokes one fixed sudo command." >&2
  exit 64
fi
[[ "$CONFIRMATION" == "$REQUIRED_CONFIRMATION" ]] || {
  echo "Guarded Stage C21 rehearsal requires --confirm $REQUIRED_CONFIRMATION" >&2
  exit 64
}
[[ -n "$PACKAGE_ROOT" ]] || { echo "--package-root is required" >&2; exit 64; }
[[ -n "$BASELINE_ROOT" ]] || { echo "--baseline-root is required" >&2; exit 64; }
[[ -n "$EVIDENCE_ROOT" ]] || { echo "--evidence-root is required" >&2; exit 64; }

exec sudo env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="$REPO_ROOT:$REPO_ROOT/scripts" \
  python3 -B -m stage_c_transaction.current_package_candidate_rehearsal_v7 \
    --package-root "$PACKAGE_ROOT" \
    --baseline-root "$BASELINE_ROOT" \
    --evidence-root "$EVIDENCE_ROOT" \
    --confirm "$CONFIRMATION"
