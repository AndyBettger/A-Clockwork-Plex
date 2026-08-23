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
PROJECT_USER="${ACP_PROJECT_USER:-${SUDO_USER:-${USER:-$(id -un)}}}"
PROJECT_DIR="${ACP_PROJECT_DIR:-}"
DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:8088}"
SERVICE_NAME=a-clockwork-plex.service
UNIT_TARGET=/etc/systemd/system/a-clockwork-plex.service
UNIT_SOURCE="$REPO_ROOT/systemd/a-clockwork-plex.service"
LAUNCHER_SOURCE="$REPO_ROOT/scripts/launch-dashboard-kiosk.sh"

usage() {
    cat <<'EOF'
Usage: bash scripts/install-dashboard-integration.sh [options]

Guarded shared owner for the dashboard systemd service and desktop kiosk
entrypoint. Prepare-only is the default and does not change production state.

Options:
  --prepare-only
  --activate --confirm INSTALL-DASHBOARD-INTEGRATION
  --project-user USER
  --project-dir PATH   logical installed repository path
  --root PATH          alternate filesystem root for non-production tests
  --dashboard-url URL  production dashboard base URL
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
        --project-dir)
            [[ $# -ge 2 ]] || { echo '--project-dir requires a path.' >&2; exit 64; }
            PROJECT_DIR="$2"; shift 2 ;;
        --root)
            [[ $# -ge 2 ]] || { echo '--root requires a path.' >&2; exit 64; }
            ROOT="$2"; shift 2 ;;
        --dashboard-url)
            [[ $# -ge 2 ]] || { echo '--dashboard-url requires a URL.' >&2; exit 64; }
            DASHBOARD_URL="${2%/}"; shift 2 ;;
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
[[ "$PROJECT_DIR" == /* ]] || { echo '--project-dir must be absolute.' >&2; exit 64; }

if acp_is_production_root; then
    PROJECT_HOME="$(getent passwd "$PROJECT_USER" | cut -d: -f6)"
    [[ -n "$PROJECT_HOME" && "$PROJECT_HOME" == /* ]] || {
        echo "Could not resolve a home directory for $PROJECT_USER." >&2
        exit 1
    }
else
    PROJECT_HOME="/home/$PROJECT_USER"
fi

KIOSK_TARGET="$PROJECT_HOME/.config/autostart/a-clockwork-plex-dashboard.desktop"

for source in "$UNIT_SOURCE" "$LAUNCHER_SOURCE"; do
    [[ -f "$source" && ! -L "$source" ]] || {
        echo "Required dashboard source is unavailable: $source" >&2
        exit 1
    }
done
bash -n "$LAUNCHER_SOURCE"

CANDIDATE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/a-clockwork-plex-dashboard-candidates.XXXXXX")"
UNIT_CANDIDATE="$CANDIDATE_DIR/a-clockwork-plex.service"
KIOSK_CANDIDATE="$CANDIDATE_DIR/a-clockwork-plex-dashboard.desktop"
cleanup_candidates() { rm -rf "$CANDIDATE_DIR"; }
trap cleanup_candidates EXIT

sed \
    -e "s/^User=.*/User=$PROJECT_USER/" \
    -e "s/^Group=.*/Group=$PROJECT_USER/" \
    -e "s|^WorkingDirectory=.*|WorkingDirectory=$PROJECT_DIR|" \
    -e "s|^ExecStart=.*|ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/app/runner.py|" \
    "$UNIT_SOURCE" >"$UNIT_CANDIDATE"

cat >"$KIOSK_CANDIDATE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=A Clockwork Plex Dashboard
Comment=Start the bedside dashboard after the desktop session opens
Exec=/usr/bin/env bash "$PROJECT_DIR/scripts/launch-dashboard-kiosk.sh"
Terminal=false
StartupNotify=false
X-GNOME-Autostart-enabled=true
Hidden=false
EOF

for expected in \
    "User=$PROJECT_USER" \
    "Group=$PROJECT_USER" \
    "WorkingDirectory=$PROJECT_DIR" \
    "ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/app/runner.py"; do
    grep -Fxq "$expected" "$UNIT_CANDIDATE" || {
        echo "Rendered dashboard unit is missing: $expected" >&2
        exit 1
    }
done
grep -Fq "Exec=/usr/bin/env bash \"$PROJECT_DIR/scripts/launch-dashboard-kiosk.sh\"" "$KIOSK_CANDIDATE"
grep -Fq 'X-GNOME-Autostart-enabled=true' "$KIOSK_CANDIDATE"

if command -v systemd-analyze >/dev/null 2>&1; then
    systemd-analyze verify "$UNIT_CANDIDATE" >/dev/null
fi
if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "$KIOSK_CANDIDATE"
fi

cat <<EOF
A Clockwork Plex guarded dashboard integration plan

Mode:            $MODE
Filesystem root: $ROOT
Project user:    $PROJECT_USER
Project dir:     $PROJECT_DIR

Managed targets:
  $UNIT_TARGET
  $KIOSK_TARGET

The service and kiosk candidates are rendered and validated before activation.
One transaction captures both targets before mutation. Production activation
reloads/restarts only $SERVICE_NAME and verifies $DASHBOARD_URL/api/state.
EOF

if [[ "$MODE" == prepare-only ]]; then
    echo
    echo 'No production file, service, route, mixer, PCM or configuration was changed.'
    exit 0
fi
[[ "$MODE" == activate ]] || { echo "Unsupported mode: $MODE" >&2; exit 64; }
[[ "$CONFIRM" == INSTALL-DASHBOARD-INTEGRATION ]] || {
    echo 'Activation requires --confirm INSTALL-DASHBOARD-INTEGRATION.' >&2
    exit 64
}

if acp_is_production_root; then
    [[ "${EUID}" -ne 0 ]] || {
        echo 'Run this installer as the normal project user, not as root.' >&2
        exit 1
    }
    for command in sudo systemctl curl; do
        acp_require_command "$command"
    done
fi

TRANSACTION_PARENT="$(mktemp -d "${TMPDIR:-/tmp}/a-clockwork-plex-dashboard-install.XXXXXX")"
TRANSACTION="$TRANSACTION_PARENT/transaction"
cleanup_transaction() { rm -rf "$TRANSACTION_PARENT"; }
trap 'cleanup_transaction; cleanup_candidates' EXIT
acp_transaction_begin "$TRANSACTION"
acp_transaction_capture_path "$TRANSACTION" "$UNIT_TARGET"
acp_transaction_capture_path "$TRANSACTION" "$KIOSK_TARGET"

SERVICE_PREEXISTED=false
if acp_is_production_root && sudo test -f "$UNIT_TARGET"; then
    SERVICE_PREEXISTED=true
    acp_transaction_capture_service "$TRANSACTION" "$SERVICE_NAME"
fi

rollback() {
    local failed=0
    if acp_is_production_root; then
        sudo -- systemctl stop "$SERVICE_NAME" >/dev/null 2>&1 || true
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
    acp_install_file "$KIOSK_CANDIDATE" "$KIOSK_TARGET" 0644 || return 1

    if acp_is_production_root; then
        sudo -- chown "$PROJECT_USER:$PROJECT_USER" "$KIOSK_TARGET" || return 1
    fi

    if [[ "$ROOT" != / && "${ACP_DASHBOARD_TEST_FAIL_AFTER_INSTALL:-0}" == 1 ]]; then
        echo 'Injected non-production failure after dashboard files were installed.' >&2
        return 1
    fi

    cmp -s "$UNIT_CANDIDATE" "$(acp_path "$UNIT_TARGET")" || return 1
    cmp -s "$KIOSK_CANDIDATE" "$(acp_path "$KIOSK_TARGET")" || return 1

    if ! acp_is_production_root; then
        return 0
    fi

    sudo -- systemctl daemon-reload || return 1
    sudo -- systemctl enable "$SERVICE_NAME" >/dev/null || return 1
    sudo -- systemctl restart "$SERVICE_NAME" || return 1

    local attempt
    for attempt in {1..20}; do
        if systemctl is-active --quiet "$SERVICE_NAME" && curl -fsS "$DASHBOARD_URL/api/state" >/dev/null; then
            return 0
        fi
        sleep 0.5
    done
    echo "Dashboard service did not expose $DASHBOARD_URL/api/state." >&2
    return 1
}

if ! activate; then
    echo 'Dashboard integration activation failed; restoring captured state.' >&2
    if rollback; then
        echo 'Captured dashboard pre-state restored.' >&2
    else
        echo 'WARNING: dashboard rollback failed; inspect the host before continuing.' >&2
    fi
    exit 1
fi

acp_transaction_mark_complete "$TRANSACTION"
echo
echo '[A Clockwork Plex] Dashboard service and kiosk integration installed successfully.'
