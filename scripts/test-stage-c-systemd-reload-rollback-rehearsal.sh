#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
REQUIRED_CONFIRMATION="STAGE-C19-SYSTEMD-RELOAD-EXACT-ROLLBACK"
MODE="prepare"
CONFIRMATION=""
PACKAGE_ROOT=""
STAGE_C18_ROOT=""
EVIDENCE_ROOT=""

usage() {
  cat <<'EOF'
Usage:
  bash scripts/test-stage-c-systemd-reload-rollback-rehearsal.sh

  bash scripts/test-stage-c-systemd-reload-rollback-rehearsal.sh \
    --rehearse-systemd-reload-rollback \
    --confirm STAGE-C19-SYSTEMD-RELOAD-EXACT-ROLLBACK \
    --package-root /var/tmp/a-clockwork-plex-stage-c1-review-v2.XXXXXX \
    --stage-c18-root /var/tmp/a-clockwork-plex-stage-c18-managed-file-rollback.XXXXXX \
    --evidence-root /var/tmp/a-clockwork-plex-stage-c19-systemd-reload-rollback.XXXXXX

The default invocation is prepare-only. The guarded rehearsal repeats the
accepted Stage C18 prefix, reloads systemd while the twelve reviewed files are
installed, proves the three managed units are loaded but inactive, removes the
files exactly, reloads systemd again and proves all three units are not-found.
Route selection, managed Stage C service startup, audio probes and commit remain
blocked. There is no keep-active mode.
EOF
}

while (($#)); do
  case "$1" in
    --rehearse-systemd-reload-rollback)
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
    --stage-c18-root)
      [[ $# -ge 2 ]] || { echo "Missing value for --stage-c18-root" >&2; exit 64; }
      STAGE_C18_ROOT="$2"
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
A Clockwork Plex Stage C19 systemd reload and exact-manager rollback rehearsal
is prepared.

Prepare-only invoked no sudo, performed no host observation, stopped no service,
wrote no managed file, reloaded no systemd manager, and created no Stage C19
evidence directory, production lock, transaction or candidate tree.

The guarded run installs the twelve reviewed files while the application services
and DAC are quiesced. It performs one fixed daemon reload and proves the three
managed units are loaded but inactive. It then removes the files, performs a
second fixed daemon reload and proves the units are not-found before restoring
the application services.

After review, run the exact guarded rehearsal using the retained Stage C1 package
and successful Stage C18 evidence:

  PACKAGE=/var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY
  STAGE_C18=/var/tmp/a-clockwork-plex-stage-c18-managed-file-rollback.H3P4Po
  EVIDENCE="$(mktemp -d /var/tmp/a-clockwork-plex-stage-c19-systemd-reload-rollback.XXXXXX)"
  chmod 0700 "$EVIDENCE"
  echo "EVIDENCE=$EVIDENCE"

  bash scripts/test-stage-c-systemd-reload-rollback-rehearsal.sh \
    --rehearse-systemd-reload-rollback \
    --confirm STAGE-C19-SYSTEMD-RELOAD-EXACT-ROLLBACK \
    --package-root "$PACKAGE" \
    --stage-c18-root "$STAGE_C18" \
    --evidence-root "$EVIDENCE" \
    2>&1 | tee /tmp/acp-stage-c19-run.txt

The guarded rehearsal uses one constrained sudo command. The dashboard and local
touchscreen will be unavailable while Plexamp, Shairport Sync and the dashboard
are stopped. SSH remains available. Exactly two `systemctl daemon-reload`
commands may run; no unit start, enable, disable, mask or route command is
available.

Split-bus or direct-failback route selection, managed Stage C service startup,
mixer mutation, audio probes and commit remain blocked. Persistent Stage C
activation remains blocked.
EOF
  exit 0
fi

[[ "$CONFIRMATION" == "$REQUIRED_CONFIRMATION" ]] || {
  echo "Guarded Stage C19 rehearsal requires --confirm $REQUIRED_CONFIRMATION" >&2
  exit 64
}
[[ -n "$PACKAGE_ROOT" ]] || { echo "--package-root is required" >&2; exit 64; }
[[ -n "$STAGE_C18_ROOT" ]] || { echo "--stage-c18-root is required" >&2; exit 64; }
[[ -n "$EVIDENCE_ROOT" ]] || { echo "--evidence-root is required" >&2; exit 64; }

exec sudo env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="$REPO_ROOT:$REPO_ROOT/scripts" \
  python3 -m stage_c_transaction.systemd_reload_rollback_rehearsal \
    --package-root "$PACKAGE_ROOT" \
    --stage-c18-root "$STAGE_C18_ROOT" \
    --evidence-root "$EVIDENCE_ROOT" \
    --confirm "$CONFIRMATION"
