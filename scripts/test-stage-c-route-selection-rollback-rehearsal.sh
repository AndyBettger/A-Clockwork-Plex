#!/usr/bin/env bash
set -euo pipefail

REQUIRED_CONFIRMATION="STAGE-C20-SPLIT-BUS-ROUTE-EXACT-ROLLBACK"
MODE="prepare"
CONFIRMATION=""
PACKAGE_ROOT=""
STAGE_C19_ROOT=""
EVIDENCE_ROOT=""

usage() {
  cat <<'EOF'
Usage:
  bash scripts/test-stage-c-route-selection-rollback-rehearsal.sh
  bash scripts/test-stage-c-route-selection-rollback-rehearsal.sh \
    --rehearse-route-selection-rollback \
    --confirm STAGE-C20-SPLIT-BUS-ROUTE-EXACT-ROLLBACK \
    --package-root PATH \
    --stage-c19-root PATH \
    --evidence-root PATH

The default invocation is prepare-only. There is no keep-active mode.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rehearse-route-selection-rollback)
      MODE="rehearse"
      shift
      ;;
    --confirm)
      [[ $# -ge 2 ]] || { echo "--confirm requires a value" >&2; exit 64; }
      CONFIRMATION="$2"
      shift 2
      ;;
    --package-root)
      [[ $# -ge 2 ]] || { echo "--package-root requires a value" >&2; exit 64; }
      PACKAGE_ROOT="$2"
      shift 2
      ;;
    --stage-c19-root)
      [[ $# -ge 2 ]] || { echo "--stage-c19-root requires a value" >&2; exit 64; }
      STAGE_C19_ROOT="$2"
      shift 2
      ;;
    --evidence-root)
      [[ $# -ge 2 ]] || { echo "--evidence-root requires a value" >&2; exit 64; }
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

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ "$MODE" == "prepare" ]]; then
  cat <<'EOF'
A Clockwork Plex Stage C20 split-bus route-selection and exact-rollback
rehearsal is prepared.

Prepare-only invoked no sudo, performed no host observation, stopped no service,
wrote no managed or route file, reloaded no systemd manager, and created no
Stage C20 evidence directory, production lock, transaction or candidate tree.

The guarded run repeats the accepted Stage C19 prefix while the application
services and DAC are quiesced. After the first daemon reload it selects the
reviewed split-bus route once by atomic inode exchange. No service or PCM is
started. It then exchanges the original active-route inode back before removing
the managed files, restoring systemd's manager view and restarting the captured
application services.

The corrected route rollback derives the exchange phase from the two exact
on-disk inode identities. It does not rely only on an in-memory flag written
after the exchange syscall.

After review, run the exact guarded rehearsal using the retained Stage C1 package
and successful Stage C19 evidence:

  PACKAGE=/var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY
  STAGE_C19=/var/tmp/a-clockwork-plex-stage-c19-systemd-reload-rollback.knbfOY
  EVIDENCE="$(mktemp -d /var/tmp/a-clockwork-plex-stage-c20-route-selection-rollback.XXXXXX)"
  chmod 0700 "$EVIDENCE"
  echo "EVIDENCE=$EVIDENCE"

  bash scripts/test-stage-c-route-selection-rollback-rehearsal.sh \
    --rehearse-route-selection-rollback \
    --confirm STAGE-C20-SPLIT-BUS-ROUTE-EXACT-ROLLBACK \
    --package-root "$PACKAGE" \
    --stage-c19-root "$STAGE_C19" \
    --evidence-root "$EVIDENCE" \
    2>&1 | tee /tmp/acp-stage-c20-run.txt

The guarded rehearsal uses one constrained sudo command. The dashboard and local
touchscreen will be unavailable while Plexamp, Shairport Sync and the dashboard
are stopped. SSH remains available. Exactly two `systemctl daemon-reload`
commands and one atomic split-bus route exchange plus its exact reverse may run.

Managed Stage C service startup, split-bus health checks, music or alarm probes,
direct-failback selection, mixer mutation and commit remain blocked. Persistent
Stage C activation remains blocked.
EOF
  exit 0
fi

[[ "$CONFIRMATION" == "$REQUIRED_CONFIRMATION" ]] || {
  echo "Guarded Stage C20 rehearsal requires --confirm $REQUIRED_CONFIRMATION" >&2
  exit 64
}
[[ -n "$PACKAGE_ROOT" ]] || { echo "--package-root is required" >&2; exit 64; }
[[ -n "$STAGE_C19_ROOT" ]] || { echo "--stage-c19-root is required" >&2; exit 64; }
[[ -n "$EVIDENCE_ROOT" ]] || { echo "--evidence-root is required" >&2; exit 64; }

exec sudo env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="$REPO_ROOT:$REPO_ROOT/scripts" \
  python3 -m stage_c_transaction.route_selection_rollback_rehearsal_v2 \
    --package-root "$PACKAGE_ROOT" \
    --stage-c19-root "$STAGE_C19_ROOT" \
    --evidence-root "$EVIDENCE_ROOT" \
    --confirm "$CONFIRMATION"
