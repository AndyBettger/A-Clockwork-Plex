#!/bin/bash
set -euo pipefail

# Stage C21 package preparation only. This wrapper generates a disposable,
# separately versioned runtime-authority package. It has no install or
# activation mode and performs no privileged, service, module, mixer or PCM
# mutation.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 -B "$SCRIPT_DIR/stage_c_activation_package/prepare.py" "$@"
