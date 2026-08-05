#!/bin/bash
set -euo pipefail

# Stage C1 prepare-only wrapper. The Python implementation has no activation
# interface and performs no privileged, service, module, mixer or PCM mutation.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 -B "$SCRIPT_DIR/stage_c_package/prepare.py" "$@"
