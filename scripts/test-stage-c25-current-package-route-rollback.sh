#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
REQUIRED_CONFIRMATION="STAGE-C25-CURRENT-PACKAGE-ROUTE-EXACT-ROLLBACK"
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
  bash scripts/test-stage-c25-current-package-route-rollback.sh

  bash scripts/test-stage-c25-current-package-route-rollback.sh \
    --rehearse-integrated-route-rollback \
    --confirm STAGE-C25-CURRENT-PACKAGE-ROUTE-EXACT-ROLLBACK \
    --package-root /var/tmp/a-clockwork-plex-stage-c21-activation-package-v2.XXXXXX \
    --baseline-root /var/tmp/a-clockwork-plex-stage-c21-production-baseline.XXXXXX \
    --stage-c21-root /var/tmp/a-clockwork-plex-stage-c21-current-package-preparation.XXXXXX \
    --stage-c22-root /var/tmp/a-clockwork-plex-stage-c22-current-package-service-quiescence.XXXXXX \
    --stage-c23-root /var/tmp/a-clockwork-plex-stage-c23-current-package-managed-file-rollback.XXXXXX \
    --evidence-root /var/tmp/a-clockwork-plex-stage-c25-current-package-route-rollback.XXXXXX

The guarded action is the final rollback-only physical checkpoint. It briefly
stops Plexamp, AirPlay and the dashboard, installs all 28 accepted files,
performs exactly two daemon-reload attempts in total, selects the reviewed
split-bus route exactly once, then restores the exact route, filesystem,
systemd-manager and application baseline.

Managed Stage C service startup, CamillaDSP, audio probes, approval publication,
commit and persistent activation are not exposed by this wrapper.
EOF
}

while (($#)); do
  case "$1" in
    --rehearse-integrated-route-rollback)
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
The integrated current-package route rollback checkpoint is prepared.

Prepare-only invoked no sudo, performed no host observation, stopped no service,
wrote no production file, called no systemctl command, selected no ALSA route
and created no evidence root, lock or transaction.

This is the final rollback-only checkpoint. After it passes, work proceeds to
the guarded terminal install/enable transaction rather than another micro-stage.
EOF
  exit 0
fi

if [[ "$EUID" -eq 0 ]]; then
  echo "Run this wrapper as the normal project user; it invokes one fixed sudo command." >&2
  exit 64
fi
[[ "$CONFIRMATION" == "$REQUIRED_CONFIRMATION" ]] || {
  echo "Guarded integrated rehearsal requires --confirm $REQUIRED_CONFIRMATION" >&2
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
  python3 -B -m stage_c_transaction.current_package_route_selection_rollback_rehearsal_v13 \
    --package-root "$PACKAGE_ROOT" \
    --baseline-root "$BASELINE_ROOT" \
    --stage-c21-root "$STAGE_C21_ROOT" \
    --stage-c22-root "$STAGE_C22_ROOT" \
    --stage-c23-root "$STAGE_C23_ROOT" \
    --evidence-root "$EVIDENCE_ROOT" \
    --confirm "$CONFIRMATION"
