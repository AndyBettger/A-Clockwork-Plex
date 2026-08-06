#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
REQUIRED_CONFIRMATION="INSTALL-AND-ENABLE-STAGE-C-EQ"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/install-and-enable-stage-c-eq.sh \
    --confirm INSTALL-AND-ENABLE-STAGE-C-EQ \
    --package-root PATH \
    --baseline-root PATH \
    --stage-c21-root PATH \
    --stage-c22-root PATH \
    --stage-c23-root PATH \
    --stage-c25-root PATH \
    --evidence-root PATH

This is the single guarded persistent Stage C split-bus EQ installation.
It installs the fixed 28-file package, starts and verifies the managed runtime,
runs finite music and alarm lane probes, restores the application services,
retains the exact pre-EQ uninstall snapshot, publishes the committed approval
and enables the route and CamillaDSP units for boot.

The legacy install-master-eq.sh path is not used.
EOF
}

CONFIRMATION=""
PACKAGE_ROOT=""
BASELINE_ROOT=""
STAGE_C21_ROOT=""
STAGE_C22_ROOT=""
STAGE_C23_ROOT=""
STAGE_C25_ROOT=""
EVIDENCE_ROOT=""

while (($#)); do
  case "$1" in
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
    --stage-c25-root)
      [[ $# -ge 2 ]] || { echo "Missing value for --stage-c25-root" >&2; exit 64; }
      STAGE_C25_ROOT="$2"
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

if [[ "$EUID" -eq 0 ]]; then
  echo "Run this wrapper as the normal project user; it invokes one fixed sudo entry." >&2
  exit 64
fi

[[ "$CONFIRMATION" == "$REQUIRED_CONFIRMATION" ]] || {
  echo "Persistent EQ installation requires --confirm $REQUIRED_CONFIRMATION" >&2
  exit 64
}

for required in \
  PACKAGE_ROOT \
  BASELINE_ROOT \
  STAGE_C21_ROOT \
  STAGE_C22_ROOT \
  STAGE_C23_ROOT \
  STAGE_C25_ROOT \
  EVIDENCE_ROOT
do
  [[ -n "${!required}" ]] || {
    echo "--${required,,} is required" >&2
    exit 64
  }
done

exec sudo env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="$REPO_ROOT:$REPO_ROOT/scripts" \
  python3 -B -m stage_c_transaction.current_package_terminal_install_v16 \
    --package-root "$PACKAGE_ROOT" \
    --baseline-root "$BASELINE_ROOT" \
    --stage-c21-root "$STAGE_C21_ROOT" \
    --stage-c22-root "$STAGE_C22_ROOT" \
    --stage-c23-root "$STAGE_C23_ROOT" \
    --stage-c25-root "$STAGE_C25_ROOT" \
    --evidence-root "$EVIDENCE_ROOT" \
    --confirm "$CONFIRMATION"
