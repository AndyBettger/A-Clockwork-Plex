#!/bin/bash
set -euo pipefail

# Stage C21 production baseline observation only. This wrapper is deliberately
# unprivileged and has no install, activation, lock, approval, service, route,
# mixer, PCM, DAC or CamillaDSP mutation mode.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/prepare-stage-c21-production-baseline.sh \
    --package-fingerprint <lowercase-sha256>

The fingerprint must be copied from the separately validated Stage C21 package
review. The digest is review evidence only and grants no installation or
activation authority.

This command runs as the normal project user, invokes no sudo, performs only the
fixed read-only Stage C21 baseline observations, and writes three evidence files
inside one fresh user-owned mode-0700 directory beneath /var/tmp.

It exits zero only when the exact untouched production baseline is ready for
human review. Every existing lock, approval object, unavailable observation or
host mismatch exits non-zero after preserving its review evidence.
EOF
}

if [[ $# -eq 1 && ( "$1" == "--help" || "$1" == "-h" ) ]]; then
  usage
  exit 0
fi

if [[ $# -ne 2 || "$1" != "--package-fingerprint" ]]; then
  usage >&2
  exit 2
fi

if [[ "$EUID" -eq 0 ]]; then
  echo "Run this wrapper as the normal project user, not as root." >&2
  exit 2
fi

PACKAGE_FINGERPRINT="$2"
if [[ ! "$PACKAGE_FINGERPRINT" =~ ^[0-9a-f]{64}$ ]]; then
  echo "--package-fingerprint must be one lowercase SHA-256 digest." >&2
  exit 2
fi

export PYTHONDONTWRITEBYTECODE=1
PYTHONPATH_VALUE="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"

exec env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="$PYTHONPATH_VALUE" \
  python3 -B -m stage_c_transaction.production_prepare_only_evidence_v7 \
    --package-fingerprint "$PACKAGE_FINGERPRINT"
