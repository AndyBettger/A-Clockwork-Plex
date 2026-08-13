#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=installer/lib/plexamp_runtime.sh
source "$REPO_ROOT/installer/lib/plexamp_runtime.sh"

MODE=prepare-only
CONFIRM=
PROJECT_USER="${ACP_PROJECT_USER:-${SUDO_USER:-${USER:-andy}}}"

usage() {
    cat <<EOF
Usage: bash scripts/install-plexamp-runtime.sh [options]

Fail-closed Phase 7 Plexamp Headless compatibility-runtime owner.
Prepare-only is the default. Production activation remains deliberately blocked
until the exact Plexamp 4.13.2 archive SHA-256 is pinned and the reviewed
transactional install/claim implementation is promoted.

Options:
  --prepare-only
  --activate --confirm $ACP_PLEXAMP_RUNTIME_CONFIRMATION
  --project-user USER
  -h, --help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prepare-only) MODE=prepare-only; shift ;;
        --activate) MODE=activate; shift ;;
        --confirm)
            [[ $# -ge 2 ]] || { echo '--confirm requires a token.' >&2; exit 64; }
            CONFIRM="$2"; shift 2 ;;
        --project-user)
            [[ $# -ge 2 ]] || { echo '--project-user requires a user.' >&2; exit 64; }
            PROJECT_USER="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 64 ;;
    esac
done

[[ "$PROJECT_USER" =~ ^[A-Za-z_][A-Za-z0-9_.-]*$ ]] || {
    echo "Invalid project user: $PROJECT_USER" >&2
    exit 64
}

if [[ "$MODE" == activate ]]; then
    [[ "$CONFIRM" == "$ACP_PLEXAMP_RUNTIME_CONFIRMATION" ]] || {
        echo "Activation requires --confirm $ACP_PLEXAMP_RUNTIME_CONFIRMATION." >&2
        exit 64
    }
elif [[ -n "$CONFIRM" ]]; then
    echo '--confirm is only valid with --activate.' >&2
    exit 64
fi

acp_plexamp_runtime_plan "$PROJECT_USER"

if [[ "$MODE" == prepare-only ]]; then
    cat <<'EOF'

Prepare-only complete. No network request, archive extraction, file, service,
package, boot setting, audio route, mixer, PCM or configuration was changed.
EOF
    exit 0
fi

[[ "$MODE" == activate ]] || { echo "Unsupported mode: $MODE" >&2; exit 64; }

# This guard intentionally precedes every future production/network mutation.
if ! acp_plexamp_runtime_artifact_pinned; then
    cat <<'EOF'
PLEXAMP_RUNTIME=ARTIFACT-PIN-REQUIRED
PLEXAMP_VERSION=4.13.2
PLEXAMP_ARTIFACT_POLICY=SHA256-MUST-BE-PINNED-IN-SOURCE
MUTATION=NOT-ATTEMPTED
EOF
    exit 78
fi

# When the archive digest is reviewed into source, activation must still remain
# blocked until the transactional install + interactive claim boundary has its
# own tests. This prevents a future checksum edit alone from enabling mutation.
cat <<'EOF'
PLEXAMP_RUNTIME=INSTALLER-IMPLEMENTATION-REQUIRED
PLEXAMP_ARTIFACT_POLICY=PINNED-BUT-NOT-YET-PROMOTED
MUTATION=NOT-ATTEMPTED
EOF
exit 78
