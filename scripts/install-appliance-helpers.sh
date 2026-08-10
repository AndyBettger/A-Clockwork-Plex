#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export ACP_REPO_ROOT="$REPO_ROOT"

# shellcheck source=installer/lib/common.sh
source "$REPO_ROOT/installer/lib/common.sh"
# shellcheck source=installer/lib/transaction.sh
source "$REPO_ROOT/installer/lib/transaction.sh"

MODE=prepare-only
CONFIRM=
ROOT="${ACP_ROOT:-/}"
PROJECT_USER="${ACP_PROJECT_USER:-${SUDO_USER:-${USER:-andy}}}"

ALARM_SOURCE="$REPO_ROOT/scripts/a-clockwork-plex-alarm-audio-helper.sh"
ALARM_TARGET=/usr/local/bin/a-clockwork-plex-alarm-audio
ALARM_SUDOERS=/etc/sudoers.d/a-clockwork-plex-alarm-audio
NAME_SOURCE="$REPO_ROOT/scripts/a-clockwork-plex-shairport-name.py"
NAME_TARGET=/usr/local/bin/a-clockwork-plex-shairport-name
NAME_SUDOERS=/etc/sudoers.d/a-clockwork-plex-shairport-name

usage() {
    cat <<'EOF'
Usage: bash scripts/install-appliance-helpers.sh [options]

Guarded installer for the two restricted appliance helpers used by the alarm
engine and managed Shairport receiver-name Settings. Prepare-only is the
default and does not change production state.

Options:
  --prepare-only
  --activate --confirm INSTALL-APPLIANCE-HELPERS
  --project-user USER
  --root PATH       alternate filesystem root for non-production tests
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
        --root)
            [[ $# -ge 2 ]] || { echo '--root requires a path.' >&2; exit 64; }
            ROOT="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 64 ;;
    esac
done

[[ "$PROJECT_USER" =~ ^[A-Za-z_][A-Za-z0-9_.-]*$ ]] || {
    echo "Invalid project user: $PROJECT_USER" >&2
    exit 64
}
if [[ "$ROOT" != / ]]; then
    ROOT="${ROOT%/}"
    [[ -d "$ROOT" ]] || { echo "Alternate root does not exist: $ROOT" >&2; exit 1; }
fi
export ACP_ROOT="$ROOT"

for source in "$ALARM_SOURCE" "$NAME_SOURCE"; do
    [[ -f "$source" && ! -L "$source" ]] || {
        echo "Required helper source is unavailable: $source" >&2
        exit 1
    }
done

ALARM_POLICY="# Managed by A Clockwork Plex. The helper validates every action and argument.\n$PROJECT_USER ALL=(root) NOPASSWD: $ALARM_TARGET release\n$PROJECT_USER ALL=(root) NOPASSWD: $ALARM_TARGET restore *\n"
NAME_POLICY="$PROJECT_USER ALL=(root) NOPASSWD: $NAME_TARGET status\n$PROJECT_USER ALL=(root) NOPASSWD: $NAME_TARGET set *\n"

validate_policy() {
    local text="$1" temporary
    if ! command -v visudo >/dev/null 2>&1; then
        if acp_is_production_root; then
            echo 'visudo is required for restricted helper installation.' >&2
            return 1
        fi
        return 0
    fi
    temporary="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-helper-sudoers.XXXXXX")"
    printf '%b' "$text" >"$temporary"
    chmod 0440 "$temporary"
    visudo -cf "$temporary" >/dev/null
    rm -f "$temporary"
}

validate_policy "$ALARM_POLICY"
validate_policy "$NAME_POLICY"

cat <<EOF
A Clockwork Plex restricted helper installation plan

Mode:             $MODE
Filesystem root:  $ROOT
Project user:     $PROJECT_USER

Managed targets:
  $ALARM_TARGET
  $ALARM_SUDOERS
  $NAME_TARGET
  $NAME_SUDOERS

The runtime helper implementations remain in their existing specialist source
files. This installer owns only guarded packaging and restricted sudo policy.
It captures every target before activation and restores exact prior presence,
content and mode if activation fails.
EOF

if [[ "$MODE" == prepare-only ]]; then
    echo
    echo 'No production file, service, route, mixer or PCM was changed.'
    exit 0
fi
[[ "$MODE" == activate ]] || { echo "Unsupported mode: $MODE" >&2; exit 64; }
[[ "$CONFIRM" == INSTALL-APPLIANCE-HELPERS ]] || {
    echo 'Activation requires --confirm INSTALL-APPLIANCE-HELPERS.' >&2
    exit 64
}
if acp_is_production_root; then
    [[ "${EUID}" -ne 0 ]] || {
        echo 'Run this installer as the normal project user, not as root.' >&2
        exit 1
    }
    acp_require_command sudo
fi

TRANSACTION_PARENT="$(mktemp -d "${TMPDIR:-/tmp}/a-clockwork-plex-helper-install.XXXXXX")"
TRANSACTION="$TRANSACTION_PARENT/transaction"
cleanup() { rm -rf "$TRANSACTION_PARENT"; }
trap cleanup EXIT
acp_transaction_begin "$TRANSACTION"
for target in "$ALARM_TARGET" "$ALARM_SUDOERS" "$NAME_TARGET" "$NAME_SUDOERS"; do
    acp_transaction_capture_path "$TRANSACTION" "$target"
done

rollback() {
    acp_transaction_restore_paths "$TRANSACTION"
}

activate() {
    local installed
    acp_install_file "$ALARM_SOURCE" "$ALARM_TARGET" 0755 || return 1
    acp_install_text "$ALARM_POLICY" "$ALARM_SUDOERS" 0440 || return 1
    acp_install_file "$NAME_SOURCE" "$NAME_TARGET" 0755 || return 1
    acp_install_text "$NAME_POLICY" "$NAME_SUDOERS" 0440 || return 1

    if [[ "$ROOT" != / && "${ACP_HELPERS_TEST_FAIL_AFTER_INSTALL:-0}" == 1 ]]; then
        echo 'Injected non-production failure after restricted helper install.' >&2
        return 1
    fi

    for installed in "$ALARM_TARGET" "$ALARM_SUDOERS" "$NAME_TARGET" "$NAME_SUDOERS"; do
        [[ -f "$(acp_path "$installed")" && ! -L "$(acp_path "$installed")" ]] || return 1
    done
    [[ "$(stat -c '%a' "$(acp_path "$ALARM_TARGET")")" == 755 ]] || return 1
    [[ "$(stat -c '%a' "$(acp_path "$NAME_TARGET")")" == 755 ]] || return 1
    [[ "$(stat -c '%a' "$(acp_path "$ALARM_SUDOERS")")" == 440 ]] || return 1
    [[ "$(stat -c '%a' "$(acp_path "$NAME_SUDOERS")")" == 440 ]] || return 1
    grep -Fq "$PROJECT_USER ALL=(root) NOPASSWD: $ALARM_TARGET release" "$(acp_path "$ALARM_SUDOERS")" || return 1
    grep -Fq "$PROJECT_USER ALL=(root) NOPASSWD: $NAME_TARGET status" "$(acp_path "$NAME_SUDOERS")" || return 1
}

if ! activate; then
    echo 'Restricted helper activation failed; restoring captured state.' >&2
    if rollback; then
        echo 'Captured helper pre-state restored.' >&2
    else
        echo 'WARNING: restricted helper rollback failed; inspect the host before continuing.' >&2
    fi
    exit 1
fi

acp_transaction_mark_complete "$TRANSACTION"
echo
echo '[A Clockwork Plex] Restricted appliance helpers installed successfully.'
