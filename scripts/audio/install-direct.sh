#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

export ACP_REPO_ROOT="$REPO_ROOT"
# shellcheck source=installer/lib/common.sh
source "$REPO_ROOT/installer/lib/common.sh"
# shellcheck source=installer/lib/direct_audio.sh
source "$REPO_ROOT/installer/lib/direct_audio.sh"
# shellcheck source=installer/lib/transaction.sh
source "$REPO_ROOT/installer/lib/transaction.sh"

MODE=prepare-only
CONFIRM=
ROOT="${ACP_ROOT:-/}"
TARGET_ROUTE=/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf
EXPECTED_SHA="$ACP_DIRECT_AUDIO_ROUTE_SHA256"

usage() {
    cat <<'EOF'
Usage: bash scripts/audio/install-direct.sh [options]

Guarded installer for the alarm-safe Direct audio profile used by fresh A
Clockwork Plex appliances. Prepare-only is the default and makes no production
changes.

Options:
  --prepare-only
  --activate --confirm INSTALL-DIRECT-AUDIO
  --root PATH       alternate filesystem root for non-production tests
  -h, --help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prepare-only)
            MODE=prepare-only
            shift
            ;;
        --activate)
            MODE=activate
            shift
            ;;
        --confirm)
            [[ $# -ge 2 ]] || { echo '--confirm requires a token.' >&2; exit 64; }
            CONFIRM="$2"
            shift 2
            ;;
        --root)
            [[ $# -ge 2 ]] || { echo '--root requires a path.' >&2; exit 64; }
            ROOT="$2"
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

if [[ "$ROOT" != / ]]; then
    ROOT="${ROOT%/}"
    [[ -d "$ROOT" ]] || { echo "Alternate root does not exist: $ROOT" >&2; exit 1; }
fi
export ACP_ROOT="$ROOT"

acp_verify_direct_audio_sources || exit 1
SOURCE_SHA="$(sha256sum "$ACP_DIRECT_AUDIO_ROUTE" | awk '{print $1}')"
[[ "$SOURCE_SHA" == "$EXPECTED_SHA" ]] || {
    echo "Direct profile source checksum mismatch: $SOURCE_SHA" >&2
    exit 1
}

cat <<EOF
A Clockwork Plex alarm-safe Direct audio plan

Mode:             $MODE
Filesystem root:  $ROOT
Source:           ${ACP_DIRECT_AUDIO_ROUTE#$REPO_ROOT/}
Active route:     $TARGET_ROUTE
Expected SHA-256: $EXPECTED_SHA

Activation replaces only the active A Clockwork Plex ALSA route with the exact
physically proven alarm-safe Direct profile. On the production root it captures
and temporarily stops Plexamp, Shairport Sync and the dashboard, restores their
prior activity/enablement after the route switch, and rolls back the previous
route/service state if activation fails.
EOF

if [[ "$MODE" == prepare-only ]]; then
    echo
    echo 'No production file, service, route, mixer or PCM was changed.'
    exit 0
fi

[[ "$MODE" == activate ]] || { echo "Unsupported mode: $MODE" >&2; exit 64; }
[[ "$CONFIRM" == INSTALL-DIRECT-AUDIO ]] || {
    echo 'Activation requires --confirm INSTALL-DIRECT-AUDIO.' >&2
    exit 64
}

if acp_is_production_root; then
    [[ "${EUID}" -ne 0 ]] || {
        echo 'Run this installer as the normal project user, not as root.' >&2
        exit 1
    }
    acp_require_command sudo
    acp_require_command systemctl
fi

TRANSACTION_PARENT="$(mktemp -d "${TMPDIR:-/tmp}/a-clockwork-plex-direct-install.XXXXXX")"
TRANSACTION="$TRANSACTION_PARENT/transaction"
cleanup() {
    rm -rf "$TRANSACTION_PARENT"
}
trap cleanup EXIT
acp_transaction_begin "$TRANSACTION"
acp_transaction_capture_path "$TRANSACTION" "$TARGET_ROUTE"

SERVICES=(plexamp.service shairport-sync.service a-clockwork-plex.service)
if acp_is_production_root; then
    for unit in "${SERVICES[@]}"; do
        acp_transaction_capture_service "$TRANSACTION" "$unit"
    done
fi

rollback() {
    local rc=0
    acp_transaction_restore_paths "$TRANSACTION" || rc=1
    if acp_is_production_root; then
        sudo -- systemctl daemon-reload >/dev/null 2>&1 || rc=1
        acp_transaction_restore_services "$TRANSACTION" || rc=1
    fi
    return "$rc"
}

activate() {
    local destination observed
    if acp_is_production_root; then
        for unit in "${SERVICES[@]}"; do
            sudo -- systemctl stop "$unit" || return 1
        done
    fi

    acp_install_file "$ACP_DIRECT_AUDIO_ROUTE" "$TARGET_ROUTE" 0644 || return 1
    destination="$(acp_path "$TARGET_ROUTE")" || return 1
    observed="$(sha256sum "$destination" | awk '{print $1}')" || return 1
    [[ "$observed" == "$EXPECTED_SHA" ]] || {
        echo "Installed Direct route checksum mismatch: $observed" >&2
        return 1
    }

    if [[ "$ROOT" != / && "${ACP_DIRECT_TEST_FAIL_AFTER_ROUTE:-0}" == 1 ]]; then
        echo 'Injected non-production failure after Direct route install.' >&2
        return 1
    fi

    if acp_is_production_root; then
        acp_transaction_restore_services "$TRANSACTION" || return 1
    fi

    observed="$(sha256sum "$destination" | awk '{print $1}')" || return 1
    [[ "$observed" == "$EXPECTED_SHA" ]] || return 1
}

if ! activate; then
    echo 'Direct audio activation failed; restoring captured state.' >&2
    if rollback; then
        echo 'Captured Direct-audio pre-state restored.' >&2
    else
        echo 'WARNING: Direct-audio rollback reported a failure; inspect the host before continuing.' >&2
    fi
    exit 1
fi

acp_transaction_mark_complete "$TRANSACTION"
echo
echo "[A Clockwork Plex] Alarm-safe Direct audio installed successfully."
