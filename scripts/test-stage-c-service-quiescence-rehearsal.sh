#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
REQUIRED_CONFIRMATION="STAGE-C17-SERVICE-QUIESCE-RESTORE"
MODE="prepare"
CONFIRMATION=""
PACKAGE_ROOT=""
STAGE_C16_ROOT=""
EVIDENCE_ROOT=""

usage() {
  cat <<'EOF'
Usage:
  bash scripts/test-stage-c-service-quiescence-rehearsal.sh

  bash scripts/test-stage-c-service-quiescence-rehearsal.sh \
    --rehearse-service-quiescence \
    --confirm STAGE-C17-SERVICE-QUIESCE-RESTORE \
    --package-root /var/tmp/a-clockwork-plex-stage-c1-review-v2.XXXXXX \
    --stage-c16-root /var/tmp/a-clockwork-plex-stage-c16-candidate-validation.XXXXXX \
    --evidence-root /var/tmp/a-clockwork-plex-stage-c17-service-quiescence.XXXXXX

The default invocation is prepare-only. The guarded rehearsal briefly stops only
the captured-active Plexamp, Shairport Sync and dashboard services, proves the
physical DAC and fixed loopback endpoints are released, restores the exact
captured application service state, waits boundedly for dashboard and DAC runtime
readiness, verifies the stable direct appliance and closes the restored rehearsal
transaction. It installs or activates nothing.
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
    --stage-c16-root)
      [[ $# -ge 2 ]] || { echo "Missing value for --stage-c16-root" >&2; exit 64; }
      STAGE_C16_ROOT="$2"
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
A Clockwork Plex Stage C17 service-quiescence and restoration rehearsal is prepared.

Prepare-only invoked no sudo, performed no host observation, stopped no service,
and created no Stage C17 evidence directory, production lock, transaction or
candidate tree.

This corrected retry waits for the dashboard HTTP response and then polls the
strict DAC runtime contract for up to 30 seconds. It does not use a blind delay.

After review, run the exact guarded rehearsal using the retained Stage C1 package
and successful corrected Stage C16 evidence:

  PACKAGE=/var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY
  STAGE_C16=/var/tmp/a-clockwork-plex-stage-c16-candidate-validation.FFT4Rq
  EVIDENCE="$(mktemp -d /var/tmp/a-clockwork-plex-stage-c17-service-quiescence.XXXXXX)"
  chmod 0700 "$EVIDENCE"
  echo "EVIDENCE=$EVIDENCE"

  bash scripts/test-stage-c-service-quiescence-rehearsal.sh \
    --rehearse-service-quiescence \
    --confirm STAGE-C17-SERVICE-QUIESCE-RESTORE \
    --package-root "$PACKAGE" \
    --stage-c16-root "$STAGE_C16" \
    --evidence-root "$EVIDENCE" \
    2>&1 | tee /tmp/acp-stage-c17-run.txt

The guarded rehearsal uses one constrained sudo command. It repeats the accepted
lock, snapshot, staging and validation prefix, then briefly stops Plexamp,
Shairport Sync and the dashboard. The dashboard and local touchscreen will be
unavailable for a short interval, but SSH remains available. It proves the DAC
released, restores the three captured services, waits for the dashboard and the
full known-good DAC runtime contract, verifies the stable direct route, mixer and
loopback, then closes and removes the restored transaction before releasing the
lock.

Managed-file installation, systemd reload, route selection, CamillaDSP startup,
audio probes and commit remain blocked.
EOF
  exit 0
fi

[[ "$CONFIRMATION" == "$REQUIRED_CONFIRMATION" ]] || {
  echo "Guarded Stage C17 rehearsal requires --confirm $REQUIRED_CONFIRMATION" >&2
  exit 64
}
[[ -n "$PACKAGE_ROOT" ]] || { echo "--package-root is required" >&2; exit 64; }
[[ -n "$STAGE_C16_ROOT" ]] || { echo "--stage-c16-root is required" >&2; exit 64; }
[[ -n "$EVIDENCE_ROOT" ]] || { echo "--evidence-root is required" >&2; exit 64; }

exec sudo env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="$REPO_ROOT:$REPO_ROOT/scripts" \
  python3 -m stage_c_transaction.service_quiescence_rehearsal_v2 \
    --package-root "$PACKAGE_ROOT" \
    --stage-c16-root "$STAGE_C16_ROOT" \
    --evidence-root "$EVIDENCE_ROOT" \
    --confirm "$CONFIRMATION"
