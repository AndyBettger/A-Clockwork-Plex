#!/bin/bash
set -euo pipefail

MODE=prepare
CONFIRM_TOKEN=""
PACKAGE_ROOT=""
STAGE_C2_ROOT=""
SNAPSHOT_ROOT=""
REQUIRED_CONFIRMATION="STAGE-C3-PRIVILEGED-SNAPSHOT-READ-ONLY"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$SCRIPT_DIR/stage_c_transaction/privileged_snapshot_entry.py"
PYTHON3="$(command -v python3 || true)"

usage() {
    cat <<'EOF_USAGE'
Usage: bash scripts/test-stage-c-privileged-snapshot.sh [options]

Required:
  --package-root PATH      Validated Stage C1 package directory.
  --stage-c2-root PATH     Validated Stage C2 transaction-review directory.

Modes:
  --prepare-only           Validate the unprivileged boundary and print the
                           exact capture command (default).
  --capture-read-only      Run the root-owned read-only snapshot rehearsal.

Capture-only:
  --confirm TOKEN          Must be:
                           STAGE-C3-PRIVILEGED-SNAPSHOT-READ-ONLY
  --snapshot-root PATH     Fresh empty mode-0700 directory directly under
                           /var/tmp. If omitted, capture creates one with mktemp.

There is deliberately no --activate, install, route, rollback or uninstall
mode. Prepare-only invokes no sudo. Capture invokes sudo once for the constrained
Python snapshot engine, which may write only inside the Stage C3 evidence
directory and performs no production mutation.
EOF_USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prepare-only)
            MODE=prepare
            shift
            ;;
        --capture-read-only)
            MODE=capture
            shift
            ;;
        --package-root)
            [[ $# -ge 2 ]] || { echo "--package-root requires a path." >&2; exit 64; }
            PACKAGE_ROOT="$2"
            shift 2
            ;;
        --stage-c2-root)
            [[ $# -ge 2 ]] || { echo "--stage-c2-root requires a path." >&2; exit 64; }
            STAGE_C2_ROOT="$2"
            shift 2
            ;;
        --snapshot-root)
            [[ $# -ge 2 ]] || { echo "--snapshot-root requires a path." >&2; exit 64; }
            SNAPSHOT_ROOT="$2"
            shift 2
            ;;
        --confirm)
            [[ $# -ge 2 ]] || { echo "--confirm requires a token." >&2; exit 64; }
            CONFIRM_TOKEN="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 64
            ;;
    esac
done

[[ "$EUID" -ne 0 ]] || {
    echo "Run this script as the normal project user, not with sudo." >&2
    exit 1
}
[[ -n "$PYTHON3" && "$PYTHON3" == /* && -x "$PYTHON3" ]] || {
    echo "python3 was not found as an absolute executable path." >&2
    exit 1
}
[[ -f "$ENGINE" ]] || { echo "Stage C3 engine is missing: $ENGINE" >&2; exit 1; }
[[ -n "$PACKAGE_ROOT" && -n "$STAGE_C2_ROOT" ]] || {
    echo "--package-root and --stage-c2-root are required." >&2
    exit 64
}

PACKAGE_ROOT="$(realpath -e "$PACKAGE_ROOT")"
STAGE_C2_ROOT="$(realpath -e "$STAGE_C2_ROOT")"
[[ "$PACKAGE_ROOT" == /var/tmp/a-clockwork-plex-stage-c1-review-* ]] || {
    echo "Unexpected Stage C1 package path: $PACKAGE_ROOT" >&2
    exit 1
}
[[ "$STAGE_C2_ROOT" == /var/tmp/a-clockwork-plex-stage-c2-review-* ]] || {
    echo "Unexpected Stage C2 review path: $STAGE_C2_ROOT" >&2
    exit 1
}
[[ -f "$PACKAGE_ROOT/manifest.tsv" && -d "$PACKAGE_ROOT/rootfs" ]] || {
    echo "Stage C1 package is incomplete: $PACKAGE_ROOT" >&2
    exit 1
}
[[ -f "$STAGE_C2_ROOT/results.tsv" && -f "$STAGE_C2_ROOT/report.txt" ]] || {
    echo "Stage C2 review is incomplete: $STAGE_C2_ROOT" >&2
    exit 1
}

if [[ "$MODE" == prepare ]]; then
    [[ -z "$CONFIRM_TOKEN" ]] || {
        echo "--confirm is accepted only with --capture-read-only." >&2
        exit 64
    }
    [[ -z "$SNAPSHOT_ROOT" ]] || {
        echo "--snapshot-root is accepted only with --capture-read-only." >&2
        exit 64
    }
    cat <<EOF_PREPARED
A Clockwork Plex Stage C3 privileged snapshot rehearsal is prepared.

Stage C1 package: $PACKAGE_ROOT
Stage C2 review:  $STAGE_C2_ROOT

Prepare-only invoked no sudo and changed nothing.

After review, run the exact read-only capture:

  SNAP="\$(mktemp -d /var/tmp/a-clockwork-plex-stage-c3-snapshot.XXXXXX)"
  chmod 0700 "\$SNAP"
  echo "SNAP=\$SNAP"

  bash scripts/test-stage-c-privileged-snapshot.sh \\
    --capture-read-only \\
    --confirm $REQUIRED_CONFIRMATION \\
    --package-root "$PACKAGE_ROOT" \\
    --stage-c2-root "$STAGE_C2_ROOT" \\
    --snapshot-root "\$SNAP"

The capture may read protected production paths as root, but it may write only
inside the fresh Stage C3 evidence directory. It has no activation or install
interface.
EOF_PREPARED
    exit 0
fi

[[ "$(uname -m)" == "aarch64" ]] || {
    echo "Stage C3 capture expects aarch64; found $(uname -m)." >&2
    exit 1
}
[[ "$CONFIRM_TOKEN" == "$REQUIRED_CONFIRMATION" ]] || {
    echo "Read-only privileged capture is blocked without: --confirm $REQUIRED_CONFIRMATION" >&2
    exit 64
}

if [[ -z "$SNAPSHOT_ROOT" ]]; then
    SNAPSHOT_ROOT="$(mktemp -d /var/tmp/a-clockwork-plex-stage-c3-snapshot.XXXXXX)"
else
    [[ "$SNAPSHOT_ROOT" == /var/tmp/a-clockwork-plex-stage-c3-snapshot.* ]] || {
        echo "--snapshot-root must be directly beneath /var/tmp with the Stage C3 prefix." >&2
        exit 1
    }
    [[ -d "$SNAPSHOT_ROOT" && ! -L "$SNAPSHOT_ROOT" ]] || {
        echo "--snapshot-root must already be a real directory." >&2
        exit 1
    }
fi
chmod 0700 "$SNAPSHOT_ROOT"
[[ -z "$(find "$SNAPSHOT_ROOT" -mindepth 1 -maxdepth 1 -print -quit)" ]] || {
    echo "--snapshot-root must be empty: $SNAPSHOT_ROOT" >&2
    exit 1
}

sudo env PYTHONDONTWRITEBYTECODE=1 \
    "$PYTHON3" -B "$ENGINE" \
    --package-root "$PACKAGE_ROOT" \
    --stage-c2-root "$STAGE_C2_ROOT" \
    --snapshot-root "$SNAPSHOT_ROOT" \
    --confirm "$CONFIRM_TOKEN"
