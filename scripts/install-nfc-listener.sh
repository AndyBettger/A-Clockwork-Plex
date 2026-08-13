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
PROJECT_DIR="${ACP_PROJECT_DIR:-}"
CONFIRM_TOKEN=INSTALL-NFC-LISTENER
SERVICE_NAME=nfc-listener.service
UNIT_TARGET=/etc/systemd/system/nfc-listener.service
VENDORED_RELATIVE=vendor/plexamp-nfc-listener/nfc_listener.py
VENDORED_SOURCE="$REPO_ROOT/$VENDORED_RELATIVE"
VENDORED_GIT_BLOB=5f87b477bfdac27a34373cb7708af8236c33c2ab
UPSTREAM_COMMIT=8f5f04213b22cfb5affc6931cb2db91fd07de537

usage() {
    cat <<EOF
Usage: bash scripts/install-nfc-listener.sh [options]

Guarded A Clockwork Plex owner for the pinned Plexamp NFC listener service.
Prepare-only is the default.

Options:
  --prepare-only
  --activate --confirm $CONFIRM_TOKEN
  --project-user USER
  --project-dir PATH   logical installed A Clockwork Plex repository path
  --root PATH          alternate filesystem root for non-production tests
  -h, --help

This owner installs only nfc-listener.service. It does not install packages,
change I2C/boot settings, configure Chromium, configure Shairport Sync, or
stop/start Plexamp as a handoff mechanism.
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
        --project-dir)
            [[ $# -ge 2 ]] || { echo '--project-dir requires a path.' >&2; exit 64; }
            PROJECT_DIR="$2"; shift 2 ;;
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

if [[ -z "$PROJECT_DIR" ]]; then
    if acp_is_production_root; then
        PROJECT_DIR="$REPO_ROOT"
    else
        PROJECT_DIR="/home/$PROJECT_USER/A-Clockwork-Plex"
    fi
fi
[[ "$PROJECT_DIR" == /* && "$PROJECT_DIR" != */../* ]] || {
    echo '--project-dir must be a safe absolute path.' >&2
    exit 64
}

[[ -f "$VENDORED_SOURCE" && ! -L "$VENDORED_SOURCE" ]] || {
    echo "Vendored NFC listener source is unavailable: $VENDORED_SOURCE" >&2
    exit 1
}
[[ -f "$REPO_ROOT/vendor/plexamp-nfc-listener/SOURCE.md" ]] || {
    echo 'Vendored NFC provenance record is missing.' >&2
    exit 1
}

if command -v git >/dev/null 2>&1; then
    ACTUAL_BLOB="$(git hash-object "$VENDORED_SOURCE")"
    [[ "$ACTUAL_BLOB" == "$VENDORED_GIT_BLOB" ]] || {
        echo "Vendored NFC listener identity mismatch: $ACTUAL_BLOB" >&2
        exit 1
    }
fi

NFC_PYTHON="$PROJECT_DIR/nfc-venv/bin/python"
NFC_RUNTIME="$PROJECT_DIR/$VENDORED_RELATIVE"
DISPLAY_SWITCH="$PROJECT_DIR/scripts/nfc-plexamp-mode.sh"

CANDIDATE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/a-clockwork-plex-nfc-candidate.XXXXXX")"
UNIT_CANDIDATE="$CANDIDATE_DIR/nfc-listener.service"
cleanup_candidates() { rm -rf "$CANDIDATE_DIR"; }
trap cleanup_candidates EXIT

cat >"$UNIT_CANDIDATE" <<EOF
[Unit]
Description=A Clockwork Plex NFC Listener
After=network-online.target plexamp.service a-clockwork-plex.service
Wants=network-online.target

[Service]
Type=simple
User=$PROJECT_USER
SupplementaryGroups=i2c gpio spi
WorkingDirectory=$PROJECT_DIR
Environment=PYTHONUNBUFFERED=1
Environment=PLEXAMP_DISPLAY_SWITCH_COMMAND=$DISPLAY_SWITCH
Environment=PLEXAMP_DASHBOARD_MODE_URL=http://localhost:8088/api/mode/plexamp
ExecStart=$NFC_PYTHON $NFC_RUNTIME
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

for expected in \
    "User=$PROJECT_USER" \
    'SupplementaryGroups=i2c gpio spi' \
    "WorkingDirectory=$PROJECT_DIR" \
    "Environment=PLEXAMP_DISPLAY_SWITCH_COMMAND=$DISPLAY_SWITCH" \
    'Environment=PLEXAMP_DASHBOARD_MODE_URL=http://localhost:8088/api/mode/plexamp' \
    "ExecStart=$NFC_PYTHON $NFC_RUNTIME"; do
    grep -Fxq "$expected" "$UNIT_CANDIDATE" || {
        echo "Rendered NFC unit is missing: $expected" >&2
        exit 1
    }
done

cat <<EOF
A Clockwork Plex guarded NFC listener plan

Mode:             $MODE
Filesystem root:  $ROOT
Project user:     $PROJECT_USER
Project dir:      $PROJECT_DIR
Upstream commit:  $UPSTREAM_COMMIT
Runtime blob:     $VENDORED_GIT_BLOB
NFC Python:       $NFC_PYTHON
Managed target:   $UNIT_TARGET

Ownership exclusions:
  Chromium/kiosk:        not owned here
  Shairport/AirPlay:     not owned here
  Plexamp service state: not owned here
  I2C/boot config:       owned by install-platform-hardware.sh
  Python dependencies:  owned by install-appliance-packages.sh paired venv stage
EOF

if [[ "$MODE" == prepare-only ]]; then
    echo
    echo 'No production file, service, package, boot setting, audio route, mixer, PCM or configuration was changed.'
    exit 0
fi
[[ "$MODE" == activate ]] || { echo "Unsupported mode: $MODE" >&2; exit 64; }
[[ "$CONFIRM" == "$CONFIRM_TOKEN" ]] || {
    echo "Activation requires --confirm $CONFIRM_TOKEN." >&2
    exit 64
}

if acp_is_production_root; then
    [[ "$EUID" -ne 0 ]] || {
        echo 'Run this installer as the normal project user, not as root.' >&2
        exit 1
    }
    [[ "$PROJECT_DIR" == "$REPO_ROOT" ]] || {
        echo 'Production NFC installation requires --project-dir to match the running repository.' >&2
        exit 1
    }
    [[ -x "$NFC_PYTHON" && ! -L "$NFC_PYTHON" ]] || {
        echo "NFC venv is not ready: $NFC_PYTHON" >&2
        exit 1
    }
    [[ -f "$NFC_RUNTIME" && ! -L "$NFC_RUNTIME" ]] || {
        echo "Pinned NFC runtime is not ready: $NFC_RUNTIME" >&2
        exit 1
    }
    [[ -x "$DISPLAY_SWITCH" && ! -L "$DISPLAY_SWITCH" ]] || {
        echo "Dashboard NFC display helper is not ready: $DISPLAY_SWITCH" >&2
        exit 1
    }
    for command in sudo systemctl; do
        acp_require_command "$command"
    done
    if command -v systemd-analyze >/dev/null 2>&1; then
        systemd-analyze verify "$UNIT_CANDIDATE" >/dev/null
    fi
fi

TRANSACTION_PARENT="$(mktemp -d "${TMPDIR:-/tmp}/a-clockwork-plex-nfc-install.XXXXXX")"
TRANSACTION="$TRANSACTION_PARENT/transaction"
cleanup_transaction() { rm -rf "$TRANSACTION_PARENT"; }
trap 'cleanup_transaction; cleanup_candidates' EXIT
acp_transaction_begin "$TRANSACTION"
acp_transaction_capture_path "$TRANSACTION" "$UNIT_TARGET"

SERVICE_PREEXISTED=false
if acp_is_production_root && sudo test -f "$UNIT_TARGET"; then
    SERVICE_PREEXISTED=true
    acp_transaction_capture_service "$TRANSACTION" "$SERVICE_NAME"
fi

rollback() {
    local failed=0
    if acp_is_production_root; then
        sudo -- systemctl stop "$SERVICE_NAME" >/dev/null 2>&1 || true
        if [[ "$SERVICE_PREEXISTED" == false ]]; then
            sudo -- systemctl disable "$SERVICE_NAME" >/dev/null 2>&1 || true
        fi
    fi
    acp_transaction_restore_paths "$TRANSACTION" || failed=1
    if acp_is_production_root; then
        sudo -- systemctl daemon-reload || failed=1
        if [[ "$SERVICE_PREEXISTED" == true ]]; then
            acp_transaction_restore_services "$TRANSACTION" || failed=1
        fi
    fi
    return "$failed"
}

activate() {
    acp_install_file "$UNIT_CANDIDATE" "$UNIT_TARGET" 0644 || return 1

    if [[ "$ROOT" != / && "${ACP_NFC_TEST_FAIL_AFTER_INSTALL:-0}" == 1 ]]; then
        echo 'Injected non-production failure after NFC unit installation.' >&2
        return 1
    fi

    cmp -s "$UNIT_CANDIDATE" "$(acp_path "$UNIT_TARGET")" || return 1

    if ! acp_is_production_root; then
        return 0
    fi

    sudo -- systemctl daemon-reload || return 1
    sudo -- systemctl enable "$SERVICE_NAME" >/dev/null || return 1
    sudo -- systemctl restart "$SERVICE_NAME" || return 1

    local attempt
    for attempt in {1..20}; do
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            return 0
        fi
        sleep 0.5
    done
    echo 'NFC listener service did not remain active.' >&2
    return 1
}

if ! activate; then
    echo 'NFC listener activation failed; restoring captured state.' >&2
    if rollback; then
        echo 'Captured NFC pre-state restored.' >&2
    else
        echo 'WARNING: NFC rollback failed; inspect the host before continuing.' >&2
    fi
    exit 1
fi

acp_transaction_mark_complete "$TRANSACTION"
echo
echo '[A Clockwork Plex] NFC listener service installed successfully.'
