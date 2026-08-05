#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
REQUIRED_CONFIRMATION="STAGE-C18-MANAGED-FILES-EXACT-ROLLBACK"
MODE="prepare"
CONFIRMATION=""
PACKAGE_ROOT=""
STAGE_C17_ROOT=""
EVIDENCE_ROOT=""

usage() {
  cat <<'EOF'
Usage:
  bash scripts/test-stage-c-managed-file-rollback-rehearsal.sh

  bash scripts/test-stage-c-managed-file-rollback-rehearsal.sh \
    --rehearse-managed-file-rollback \
    --confirm STAGE-C18-MANAGED-FILES-EXACT-ROLLBACK \
    --package-root /var/tmp/a-clockwork-plex-stage-c1-review-v2.XXXXXX \
    --stage-c17-root /var/tmp/a-clockwork-plex-stage-c17-service-quiescence.XXXXXX \
    --evidence-root /var/tmp/a-clockwork-plex-stage-c18-managed-file-rollback.XXXXXX

The default invocation is prepare-only. The guarded rehearsal repeats the
accepted Stage C17 prefix, then writes the twelve reviewed managed files for the
first time while application services and the DAC are quiesced. Systemd reload,
route selection, managed Stage C services, audio probes and commit remain
blocked. The files are removed through the authoritative snapshot before the
application services are restored. There is no keep-active mode.
EOF
}

while (($#)); do
  case "$1" in
    --rehearse-managed-file-rollback)
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
    --stage-c17-root)
      [[ $# -ge 2 ]] || { echo "Missing value for --stage-c17-root" >&2; exit 64; }
      STAGE_C17_ROOT="$2"
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
A Clockwork Plex Stage C18 managed-file installation and exact-rollback rehearsal
is prepared.

Prepare-only invoked no sudo, performed no host observation, stopped no service,
wrote no managed file, and created no Stage C18 evidence directory, production
lock, transaction or candidate tree.

This is the first Stage C rehearsal permitted to write the twelve managed package
files. The guarded run immediately rolls them back before systemd reload or route
selection, then restores and verifies the accepted direct appliance state.

After review, run the exact guarded rehearsal using the retained Stage C1 package
and successful corrected Stage C17 evidence:

  PACKAGE=/var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY
  STAGE_C17=/var/tmp/a-clockwork-plex-stage-c17-service-quiescence.3ySKhd
  EVIDENCE="$(mktemp -d /var/tmp/a-clockwork-plex-stage-c18-managed-file-rollback.XXXXXX)"
  chmod 0700 "$EVIDENCE"
  echo "EVIDENCE=$EVIDENCE"

  bash scripts/test-stage-c-managed-file-rollback-rehearsal.sh \
    --rehearse-managed-file-rollback \
    --confirm STAGE-C18-MANAGED-FILES-EXACT-ROLLBACK \
    --package-root "$PACKAGE" \
    --stage-c17-root "$STAGE_C17" \
    --evidence-root "$EVIDENCE" \
    2>&1 | tee /tmp/acp-stage-c18-run.txt

The guarded rehearsal uses one constrained sudo command. The dashboard and local
touchscreen will be unavailable while Plexamp, Shairport Sync and the dashboard
are stopped. SSH remains available. Exactly twelve manifest files may be written.
They are verified, then removed and the exact filesystem state is proved before
the three application services are restored.

Systemd reload, split-bus or direct-failback route selection, managed Stage C
service startup, mixer mutation, audio probes and commit remain blocked.
Persistent Stage C activation remains blocked.
EOF
  exit 0
fi

[[ "$CONFIRMATION" == "$REQUIRED_CONFIRMATION" ]] || {
  echo "Guarded Stage C18 rehearsal requires --confirm $REQUIRED_CONFIRMATION" >&2
  exit 64
}
[[ -n "$PACKAGE_ROOT" ]] || { echo "--package-root is required" >&2; exit 64; }
[[ -n "$STAGE_C17_ROOT" ]] || { echo "--stage-c17-root is required" >&2; exit 64; }
[[ -n "$EVIDENCE_ROOT" ]] || { echo "--evidence-root is required" >&2; exit 64; }

exec sudo env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="$REPO_ROOT:$REPO_ROOT/scripts" \
  python3 -m stage_c_transaction.managed_file_rollback_rehearsal \
    --package-root "$PACKAGE_ROOT" \
    --stage-c17-root "$STAGE_C17_ROOT" \
    --evidence-root "$EVIDENCE_ROOT" \
    --confirm "$CONFIRMATION"
