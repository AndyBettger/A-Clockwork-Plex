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
DASHBOARD_BASE="${DASHBOARD_BASE:-http://localhost:8088}"

SHAIRPORT_CONFIG=/etc/shairport-sync.conf
START_WRAPPER=/usr/local/bin/a-clockwork-plex-airplay-start
END_WRAPPER=/usr/local/bin/a-clockwork-plex-airplay-end
LEGACY_SESSION_END_WRAPPER=/usr/local/bin/a-clockwork-plex-airplay-session-end
LEGACY_SUDOERS=/etc/sudoers.d/a-clockwork-plex-airplay
METADATA_UNIT=/etc/systemd/system/a-clockwork-plex-airplay-metadata.service
METADATA_FIFO=/tmp/shairport-sync-metadata
SHAIRPORT_SERVICE=shairport-sync.service
METADATA_SERVICE=a-clockwork-plex-airplay-metadata.service

WRAPPER_RENDERER="$REPO_ROOT/scripts/a-clockwork-plex-airplay-wrappers.py"
CONFIG_RENDERER="$REPO_ROOT/scripts/a-clockwork-plex-shairport-integration.py"
CONFIG_VALIDATOR="$REPO_ROOT/scripts/a-clockwork-plex-shairport-name.py"
METADATA_LISTENER="$REPO_ROOT/scripts/airplay-metadata-listener.py"

usage() {
    cat <<'EOF'
Usage: bash scripts/install-airplay-integration.sh [options]

Guarded owner for A Clockwork Plex Shairport integration: lifecycle wrappers,
metadata FIFO/service and the validated Shairport configuration. Prepare-only is
the default and makes no production changes.

Options:
  --prepare-only
  --activate --confirm INSTALL-AIRPLAY-INTEGRATION
  --project-user USER
  --dashboard-base URL
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
        --dashboard-base)
            [[ $# -ge 2 ]] || { echo '--dashboard-base requires a URL.' >&2; exit 64; }
            DASHBOARD_BASE="$2"; shift 2 ;;
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
ROOT="$(acp_normalise_root "$ROOT")" || exit 1
[[ -d "$ROOT" ]] || { echo "Filesystem root does not exist: $ROOT" >&2; exit 1; }
export ACP_ROOT="$ROOT"

for source in "$WRAPPER_RENDERER" "$CONFIG_RENDERER" "$CONFIG_VALIDATOR" "$METADATA_LISTENER"; do
    [[ -f "$source" && ! -L "$source" ]] || {
        echo "Required AirPlay integration source is unavailable: $source" >&2
        exit 1
    }
done

acp_require_command python3
acp_require_command sha256sum
acp_require_command stat
acp_require_command mkfifo

CONFIG_PATH="$(acp_path "$SHAIRPORT_CONFIG")"
[[ -f "$CONFIG_PATH" && ! -L "$CONFIG_PATH" ]] || {
    echo "Shairport configuration must be a regular file: $SHAIRPORT_CONFIG" >&2
    exit 1
}
FIFO_PATH="$(acp_path "$METADATA_FIFO")"
if [[ -L "$FIFO_PATH" || ( -e "$FIFO_PATH" && ! -p "$FIFO_PATH" ) ]]; then
    echo "Metadata path must be absent or a FIFO: $METADATA_FIFO" >&2
    exit 1
fi

if acp_is_production_root; then
    [[ "${EUID}" -ne 0 ]] || {
        echo 'Run this installer as the normal project user, not as root.' >&2
        exit 1
    }
    id "$PROJECT_USER" >/dev/null 2>&1 || {
        echo "Project user does not exist: $PROJECT_USER" >&2
        exit 1
    }
    acp_require_command sudo
    acp_require_command systemctl
    [[ -x /usr/bin/shairport-sync ]] || {
        echo 'Shairport Sync binary is required at /usr/bin/shairport-sync.' >&2
        exit 1
    }
    [[ "$(systemctl show "$SHAIRPORT_SERVICE" -p LoadState --value 2>/dev/null || true)" != not-found ]] || {
        echo "Required service is not installed: $SHAIRPORT_SERVICE" >&2
        exit 1
    }
fi

WORK_PARENT="$(mktemp -d "${TMPDIR:-/tmp}/a-clockwork-plex-airplay-integration.XXXXXX")"
CANDIDATES="$WORK_PARENT/candidates"
TRANSACTION="$WORK_PARENT/transaction"
mkdir -p "$CANDIDATES"
cleanup() { rm -rf "$WORK_PARENT"; }
trap cleanup EXIT

python3 "$WRAPPER_RENDERER" \
    --output-dir "$CANDIDATES" \
    --dashboard-base "$DASHBOARD_BASE"
bash -n "$CANDIDATES/a-clockwork-plex-airplay-start"
bash -n "$CANDIDATES/a-clockwork-plex-airplay-end"

python3 "$CONFIG_RENDERER" \
    --input "$CONFIG_PATH" \
    --output "$CANDIDATES/shairport-sync.conf" \
    --start-wrapper "$START_WRAPPER" \
    --end-wrapper "$END_WRAPPER" \
    --metadata-pipe "$METADATA_FIFO"

VALIDATOR_BINARY=/usr/bin/shairport-sync
if ! acp_is_production_root && [[ -n "${ACP_AIRPLAY_TEST_SHAIRPORT_BINARY:-}" ]]; then
    VALIDATOR_BINARY="$ACP_AIRPLAY_TEST_SHAIRPORT_BINARY"
fi
[[ -x "$VALIDATOR_BINARY" ]] || {
    echo "Shairport validation binary is unavailable: $VALIDATOR_BINARY" >&2
    exit 1
}
if ! python3 - "$CONFIG_VALIDATOR" "$CANDIDATES/shairport-sync.conf" "$VALIDATOR_BINARY" <<'PY'
import importlib.util
import sys
from pathlib import Path

module_path = Path(sys.argv[1])
candidate = Path(sys.argv[2])
validator_binary = Path(sys.argv[3])
spec = importlib.util.spec_from_file_location("acp_shairport_config_validator", module_path)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
module.SHAIRPORT_BINARY = validator_binary
ok, detail = module.validate_config(candidate)
if not ok:
    print(detail or "unknown validation error", file=sys.stderr)
    raise SystemExit(1)
PY
then
    echo 'Shairport candidate validation failed.' >&2
    exit 1
fi

cat >"$CANDIDATES/$METADATA_SERVICE" <<EOF
[Unit]
Description=A Clockwork Plex AirPlay Metadata Listener
After=a-clockwork-plex.service shairport-sync.service
Wants=a-clockwork-plex.service

[Service]
Type=simple
User=$PROJECT_USER
WorkingDirectory=$REPO_ROOT
Environment=PYTHONUNBUFFERED=1
Environment=SHAIRPORT_METADATA_PIPE=$METADATA_FIFO
Environment=ACP_BASE_DIR=$REPO_ROOT
Environment=ACP_STATE_PATH=$REPO_ROOT/state.json
Environment=ACP_ARTWORK_DIR=$REPO_ROOT/app/static/generated
ExecStart=/usr/bin/python3 $METADATA_LISTENER
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

CONFIG_MODE="$(stat -c '%a' "$CONFIG_PATH")"
CONFIG_UID="$(stat -c '%u' "$CONFIG_PATH")"
CONFIG_GID="$(stat -c '%g' "$CONFIG_PATH")"
CANDIDATE_CONFIG_SHA="$(sha256sum "$CANDIDATES/shairport-sync.conf" | awk '{print $1}')"

cat <<EOF
A Clockwork Plex guarded AirPlay integration plan

Mode:                    $MODE
Filesystem root:         $ROOT
Project user:            $PROJECT_USER
Dashboard base:          $DASHBOARD_BASE
Shairport config:        $SHAIRPORT_CONFIG
Candidate config SHA:    $CANDIDATE_CONFIG_SHA
Lifecycle wrappers:      $START_WRAPPER, $END_WRAPPER
Metadata FIFO:           $METADATA_FIFO
Metadata service:        $METADATA_SERVICE

The candidate Shairport configuration has passed the Shairport parser before any
live replacement. Activation owns only the integration paths above, retires the
old play-end wrapper/sudo policy, preserves unrelated Shairport settings such as
the receiver name, and rolls back exact captured files/FIFO/service state if any
activation step fails.
EOF

if [[ "$MODE" == prepare-only ]]; then
    echo
    echo 'No production file, FIFO, service, route, mixer, PCM or configuration was changed.'
    exit 0
fi
[[ "$MODE" == activate ]] || { echo "Unsupported mode: $MODE" >&2; exit 64; }
[[ "$CONFIRM" == INSTALL-AIRPLAY-INTEGRATION ]] || {
    echo 'Activation requires --confirm INSTALL-AIRPLAY-INTEGRATION.' >&2
    exit 64
}

FIFO_BEFORE_STATE=absent
FIFO_BEFORE_MODE=-
FIFO_BEFORE_UID=-
FIFO_BEFORE_GID=-
if [[ -p "$FIFO_PATH" ]]; then
    FIFO_BEFORE_STATE=fifo
    FIFO_BEFORE_MODE="$(stat -c '%a' "$FIFO_PATH")"
    FIFO_BEFORE_UID="$(stat -c '%u' "$FIFO_PATH")"
    FIFO_BEFORE_GID="$(stat -c '%g' "$FIFO_PATH")"
fi

METADATA_BEFORE_ACTIVE=false
METADATA_BEFORE_ENABLED=not-found
if acp_is_production_root; then
    systemctl is-active --quiet "$METADATA_SERVICE" && METADATA_BEFORE_ACTIVE=true
    METADATA_BEFORE_ENABLED="$(systemctl is-enabled "$METADATA_SERVICE" 2>/dev/null || true)"
    [[ -n "$METADATA_BEFORE_ENABLED" ]] || METADATA_BEFORE_ENABLED=not-found
fi

acp_transaction_begin "$TRANSACTION"
for target in \
    "$SHAIRPORT_CONFIG" \
    "$START_WRAPPER" \
    "$END_WRAPPER" \
    "$LEGACY_SESSION_END_WRAPPER" \
    "$LEGACY_SUDOERS" \
    "$METADATA_UNIT"
do
    acp_transaction_capture_path "$TRANSACTION" "$target"
done
if acp_is_production_root; then
    acp_transaction_capture_service "$TRANSACTION" "$SHAIRPORT_SERVICE"
fi

restore_fifo() {
    local current
    current="$(acp_path "$METADATA_FIFO")" || return 1
    case "$FIFO_BEFORE_STATE" in
        absent)
            if [[ -L "$current" || ( -e "$current" && ! -p "$current" ) ]]; then
                echo "Cannot restore absent FIFO state over unexpected object: $METADATA_FIFO" >&2
                return 1
            fi
            [[ -p "$current" ]] && acp_run_root rm -f -- "$current"
            ;;
        fifo)
            if [[ -L "$current" || ( -e "$current" && ! -p "$current" ) ]]; then
                echo "Cannot restore FIFO over unexpected object: $METADATA_FIFO" >&2
                return 1
            fi
            if [[ ! -p "$current" ]]; then
                acp_run_root mkfifo "$current" || return 1
            fi
            acp_run_root chmod "$FIFO_BEFORE_MODE" "$current" || return 1
            if acp_is_production_root; then
                acp_run_root chown "$FIFO_BEFORE_UID:$FIFO_BEFORE_GID" "$current" || return 1
            fi
            ;;
        *)
            echo "Unknown captured FIFO state: $FIFO_BEFORE_STATE" >&2
            return 1
            ;;
    esac
}

restore_metadata_service() {
    local load_state
    acp_is_production_root || return 0
    case "$METADATA_BEFORE_ENABLED" in
        enabled) sudo -- systemctl enable "$METADATA_SERVICE" >/dev/null || return 1 ;;
        disabled) sudo -- systemctl disable "$METADATA_SERVICE" >/dev/null || return 1 ;;
        static|indirect|generated|alias|masked|masked-runtime|transient|unknown|not-found) ;;
        *) echo "Unrecognised saved enablement '$METADATA_BEFORE_ENABLED' for $METADATA_SERVICE" >&2; return 1 ;;
    esac
    load_state="$(systemctl show "$METADATA_SERVICE" -p LoadState --value 2>/dev/null || true)"
    if [[ "$METADATA_BEFORE_ACTIVE" == true ]]; then
        [[ "$load_state" != not-found ]] || return 1
        sudo -- systemctl start "$METADATA_SERVICE" || return 1
    elif [[ "$load_state" != not-found ]]; then
        sudo -- systemctl stop "$METADATA_SERVICE" || return 1
    fi
}

rollback() {
    local rc=0
    if acp_is_production_root; then
        sudo -- systemctl stop "$METADATA_SERVICE" >/dev/null 2>&1 || true
        sudo -- systemctl stop "$SHAIRPORT_SERVICE" >/dev/null 2>&1 || true
    fi
    acp_transaction_restore_paths "$TRANSACTION" || rc=1
    restore_fifo || rc=1
    if acp_is_production_root; then
        sudo -- systemctl daemon-reload >/dev/null || rc=1
        restore_metadata_service || rc=1
        acp_transaction_restore_services "$TRANSACTION" || rc=1
    fi
    return "$rc"
}

activate() {
    local live_config observed_sha fifo
    if acp_is_production_root; then
        sudo -- systemctl stop "$METADATA_SERVICE" >/dev/null 2>&1 || true
        sudo -- systemctl stop "$SHAIRPORT_SERVICE" || return 1
    fi

    acp_install_file "$CANDIDATES/a-clockwork-plex-airplay-start" "$START_WRAPPER" 0755 || return 1
    acp_install_file "$CANDIDATES/a-clockwork-plex-airplay-end" "$END_WRAPPER" 0755 || return 1
    acp_remove_file "$LEGACY_SESSION_END_WRAPPER" || return 1
    acp_remove_file "$LEGACY_SUDOERS" || return 1

    fifo="$(acp_path "$METADATA_FIFO")" || return 1
    if [[ ! -p "$fifo" ]]; then
        acp_run_root mkfifo "$fifo" || return 1
    fi
    acp_run_root chmod 0666 "$fifo" || return 1

    acp_install_file "$CANDIDATES/$METADATA_SERVICE" "$METADATA_UNIT" 0644 || return 1
    acp_install_file "$CANDIDATES/shairport-sync.conf" "$SHAIRPORT_CONFIG" "0$CONFIG_MODE" || return 1
    live_config="$(acp_path "$SHAIRPORT_CONFIG")" || return 1
    if acp_is_production_root; then
        acp_run_root chown "$CONFIG_UID:$CONFIG_GID" "$live_config" || return 1
    fi
    observed_sha="$(acp_run_root sha256sum "$live_config" | awk '{print $1}')" || return 1
    [[ "$observed_sha" == "$CANDIDATE_CONFIG_SHA" ]] || return 1

    if [[ "$ROOT" != / && "${ACP_AIRPLAY_TEST_FAIL_AFTER_INSTALL:-0}" == 1 ]]; then
        echo 'Injected non-production failure after AirPlay integration install.' >&2
        return 1
    fi

    if acp_is_production_root; then
        sudo -- systemctl daemon-reload || return 1
        sudo -- systemctl enable --now "$METADATA_SERVICE" || return 1
        acp_transaction_restore_services "$TRANSACTION" || return 1
        systemctl is-active --quiet "$METADATA_SERVICE" || return 1
    fi

    [[ -p "$fifo" ]] || return 1
    [[ "$(stat -c '%a' "$fifo")" == 666 ]] || return 1
    [[ -f "$(acp_path "$START_WRAPPER")" && ! -L "$(acp_path "$START_WRAPPER")" ]] || return 1
    [[ -f "$(acp_path "$END_WRAPPER")" && ! -L "$(acp_path "$END_WRAPPER")" ]] || return 1
    [[ ! -e "$(acp_path "$LEGACY_SESSION_END_WRAPPER")" ]] || return 1
    [[ ! -e "$(acp_path "$LEGACY_SUDOERS")" ]] || return 1
}

if ! activate; then
    echo 'AirPlay integration activation failed; restoring captured state.' >&2
    if rollback; then
        echo 'Captured AirPlay integration pre-state restored.' >&2
    else
        echo 'WARNING: AirPlay integration rollback failed; inspect the host before continuing.' >&2
    fi
    exit 1
fi

acp_transaction_mark_complete "$TRANSACTION"
echo
echo '[A Clockwork Plex] Guarded AirPlay integration installed successfully.'
