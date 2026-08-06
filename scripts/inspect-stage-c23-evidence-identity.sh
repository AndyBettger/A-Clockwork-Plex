#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

if [[ "$EUID" -eq 0 ]]; then
  echo "Run this read-only inspector as the normal project user, not root." >&2
  exit 64
fi

if (($#)); then
  echo "This inspector accepts no arguments and reads only the fixed accepted Stage C23 evidence root." >&2
  exit 64
fi

exec env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="$REPO_ROOT:$REPO_ROOT/scripts" \
  python3 -B -m stage_c_transaction.stage_c23_evidence_identity
