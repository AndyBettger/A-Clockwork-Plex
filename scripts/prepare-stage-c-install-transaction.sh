#!/bin/bash
set -euo pipefail

# Stage C2 replays a validated Stage C1 package against the current host and
# prepares a transaction/snapshot review. It has no activation mode and makes
# no privileged, service, module, mixer or audio-route change.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
exec python3 -B "$SCRIPT_DIR/stage_c_transaction/prepare.py" "$@"
