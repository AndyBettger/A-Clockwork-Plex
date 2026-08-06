#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
REQUIRED_CONFIRMATION="STAGE-C24-CURRENT-PACKAGE-SYSTEMD-RELOAD-EXACT-ROLLBACK"
MODE="prepare"
CONFIRMATION=""
PACKAGE_ROOT=""
BASELINE_ROOT=""
STAGE_C21_ROOT=""
STAGE_C22_ROOT=""
STAGE_C23_ROOT=""
EVIDENCE_ROOT=""

usage() {
  cat <<'EOF'
Usage:
  bash scripts/test-stage-c24-current-package-systemd-reload-rollback.sh

  bash scripts/test-stage-c24-current-package-systemd-reload-rollback.sh \
    --rehearse-systemd-reload-rollback \
    --confirm STAGE-C24-CURRENT-PACKAGE-SYSTEMD-RELOAD-EXACT-ROLLBACK \
    --package-root /var/tmp/a-clockwork-plex-stage-c21-activation-package-v2.XXXXXX \
    --baseline-root /var/tmp/a-clockwork-plex-stage-c21-production-baseline.XXXXXX \
    --stage-c21-root /var/tmp/a-clockwork-plex-stage-c21-current-package-preparation.XXXXXX \
    --stage-c22-root /var/tmp/a-clockwork-plex-stage-c22-current-package-service-quiescence.XXXXXX \
    --stage-c23-root /var/tmp/a-clockwork-plex-stage-c23-current-package-managed-file-rollback.XXXXXX \
    --evidence-root /var/tmp/a-clockwork-plex-stage-c24-current-package-systemd-reload-rollback.XXXXXX

The default invocation is inert prepare-only mode. The separately approved
rehearsal briefly stops captured-active Plexamp, Shairport Sync and dashboard,
proves DAC release, atomically writes all 28 accepted managed files, performs
one fixed systemd daemon-reload and observes three loaded but inactive managed
units. It then removes the exact installed inodes, performs a second fixed
reload that must forget those units, and restores the accepted appliance state.
The total daemon-reload command budget is two attempts, including failures; an
unapproved third attempt is refused before a command is issued.

Route selection, mixer writes, managed Stage C service startup, approval
publication, CamillaDSP startup, audio probes, commit and activation remain
blocked throughout.
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
    --stage-c22-root)
      [[ $# -ge 2 ]] || { echo "Missing value for --stage-c22-root" >&2; exit 64; }
      STAGE_C22_ROOT="$2"
      shift 2
      ;;
    --stage-c23-root)
      [[ $# -ge 2 ]] || { echo "Missing value for --stage-c23-root" >&2; exit 64; }
      STAGE_C23_ROOT="$2"
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
A Clockwork Plex Stage C24 current-package systemd rollback rehearsal is prepared.

Prepare-only invoked no sudo, performed no host observation, stopped no service,
wrote no production file, called no systemctl command and created no evidence
root, lock or transaction.

The intended separately approved inputs are:

  PACKAGE=/var/tmp/a-clockwork-plex-stage-c21-activation-package-v2.R2GyTo
  BASELINE=/var/tmp/a-clockwork-plex-stage-c21-production-baseline.5m73n8ac
  STAGE_C21=/var/tmp/a-clockwork-plex-stage-c21-current-package-preparation.rLFDFg
  STAGE_C22=/var/tmp/a-clockwork-plex-stage-c22-current-package-service-quiescence.LPNDwL
  STAGE_C23=/var/tmp/a-clockwork-plex-stage-c23-current-package-managed-file-rollback.DGdgaG
  EVIDENCE="$(mktemp -d /var/tmp/a-clockwork-plex-stage-c24-current-package-systemd-reload-rollback.XXXXXX)"
  chmod 0700 "$EVIDENCE"

Do not run guarded mode without a new explicit approval. Plexamp, AirPlay and
the dashboard will be temporarily unavailable. Twenty-eight fixed production
files will exist briefly and systemd has a hard budget of two daemon-reload
attempts before mandatory exact rollback. SSH remains outside the application
boundary. Any rollback or restoration failure deliberately retains the
canonical lock and transaction for inspection; leave all retained state
untouched and do not clean it manually.
EOF
  exit 0
fi

if [[ "$EUID" -eq 0 ]]; then
  echo "Run this wrapper as the normal project user; it invokes one fixed sudo command." >&2
  exit 64
fi
[[ "$CONFIRMATION" == "$REQUIRED_CONFIRMATION" ]] || {
  echo "Guarded Stage C24 rehearsal requires --confirm $REQUIRED_CONFIRMATION" >&2
  exit 64
}
[[ -n "$PACKAGE_ROOT" ]] || { echo "--package-root is required" >&2; exit 64; }
[[ -n "$BASELINE_ROOT" ]] || { echo "--baseline-root is required" >&2; exit 64; }
[[ -n "$STAGE_C21_ROOT" ]] || { echo "--stage-c21-root is required" >&2; exit 64; }
[[ -n "$STAGE_C22_ROOT" ]] || { echo "--stage-c22-root is required" >&2; exit 64; }
[[ -n "$STAGE_C23_ROOT" ]] || { echo "--stage-c23-root is required" >&2; exit 64; }
[[ -n "$EVIDENCE_ROOT" ]] || { echo "--evidence-root is required" >&2; exit 64; }

exec sudo env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="$REPO_ROOT:$REPO_ROOT/scripts" \
  python3 -B -m stage_c_transaction.current_package_systemd_reload_rollback_rehearsal_v11 \
    --package-root "$PACKAGE_ROOT" \
    --baseline-root "$BASELINE_ROOT" \
    --stage-c21-root "$STAGE_C21_ROOT" \
    --stage-c22-root "$STAGE_C22_ROOT" \
    --stage-c23-root "$STAGE_C23_ROOT" \
    --evidence-root "$EVIDENCE_ROOT" \
    --confirm "$CONFIRMATION"
