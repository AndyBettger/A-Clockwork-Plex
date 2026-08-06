#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
REQUIRED_CONFIRMATION="STAGE-C22-CURRENT-PACKAGE-SERVICE-QUIESCE-RESTORE"
MODE="prepare"
CONFIRMATION=""
PACKAGE_ROOT=""
BASELINE_ROOT=""
STAGE_C21_ROOT=""
EVIDENCE_ROOT=""

usage() {
  cat <<'EOF'
Usage:
  bash scripts/test-stage-c22-current-package-service-quiescence.sh

  bash scripts/test-stage-c22-current-package-service-quiescence.sh \
    --rehearse-service-quiescence \
    --confirm STAGE-C22-CURRENT-PACKAGE-SERVICE-QUIESCE-RESTORE \
    --package-root /var/tmp/a-clockwork-plex-stage-c21-activation-package-v2.XXXXXX \
    --baseline-root /var/tmp/a-clockwork-plex-stage-c21-production-baseline.XXXXXX \
    --stage-c21-root /var/tmp/a-clockwork-plex-stage-c21-current-package-preparation.XXXXXX \
    --evidence-root /var/tmp/a-clockwork-plex-stage-c22-current-package-service-quiescence.XXXXXX

The default invocation is inert prepare-only mode. The separately approved
guarded rehearsal repeats the accepted current-package validation transaction,
briefly stops only captured-active Plexamp, Shairport Sync and dashboard,
proves DAC release, restores the exact accepted appliance state, closes and
removes the transaction, and releases the production lock.

It exposes no managed-file installation, systemd reload, route selection, mixer
write, approval publication, CamillaDSP startup, audio probe, commit or
activation operation.
EOF
}

while (($#)); do
  case "$1" in
    --rehearse-service-quiescence)
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
    --stage-c21-root)
      [[ $# -ge 2 ]] || { echo "Missing value for --stage-c21-root" >&2; exit 64; }
      STAGE_C21_ROOT="$2"
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
A Clockwork Plex Stage C22 current-package service rehearsal is prepared.

Prepare-only invoked no sudo, performed no host observation, stopped no service
and created no evidence root, production lock, transaction or candidate tree.

The intended separately approved Pi inputs are the accepted Stage C21 objects:

  PACKAGE=/var/tmp/a-clockwork-plex-stage-c21-activation-package-v2.R2GyTo
  BASELINE=/var/tmp/a-clockwork-plex-stage-c21-production-baseline.5m73n8ac
  STAGE_C21=/var/tmp/a-clockwork-plex-stage-c21-current-package-preparation.rLFDFg
  EVIDENCE="$(mktemp -d /var/tmp/a-clockwork-plex-stage-c22-current-package-service-quiescence.XXXXXX)"
  chmod 0700 "$EVIDENCE"

Do not run guarded mode without a new explicit approval. It will briefly stop
Plexamp, Shairport Sync and the dashboard, so dashboard/touchscreen and playback
will be temporarily unavailable. SSH remains outside the application service
boundary. Exact restoration is mandatory; a restoration failure deliberately
retains the lock and transaction for review rather than pretending success.
EOF
  exit 0
fi

if [[ "$EUID" -eq 0 ]]; then
  echo "Run this wrapper as the normal project user; it invokes one fixed sudo command." >&2
  exit 64
fi
[[ "$CONFIRMATION" == "$REQUIRED_CONFIRMATION" ]] || {
  echo "Guarded Stage C22 rehearsal requires --confirm $REQUIRED_CONFIRMATION" >&2
  exit 64
}
[[ -n "$PACKAGE_ROOT" ]] || { echo "--package-root is required" >&2; exit 64; }
[[ -n "$BASELINE_ROOT" ]] || { echo "--baseline-root is required" >&2; exit 64; }
[[ -n "$STAGE_C21_ROOT" ]] || { echo "--stage-c21-root is required" >&2; exit 64; }
[[ -n "$EVIDENCE_ROOT" ]] || { echo "--evidence-root is required" >&2; exit 64; }

exec sudo env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="$REPO_ROOT:$REPO_ROOT/scripts" \
  python3 -B -m stage_c_transaction.current_package_service_quiescence_rehearsal_v8 \
    --package-root "$PACKAGE_ROOT" \
    --baseline-root "$BASELINE_ROOT" \
    --stage-c21-root "$STAGE_C21_ROOT" \
    --evidence-root "$EVIDENCE_ROOT" \
    --confirm "$CONFIRMATION"
