#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export ACP_REPO_ROOT="$REPO_ROOT"

# shellcheck source=installer/lib/common.sh
source "$REPO_ROOT/installer/lib/common.sh"
# shellcheck source=installer/lib/transaction.sh
source "$REPO_ROOT/installer/lib/transaction.sh"
# shellcheck source=installer/lib/plexamp_runtime.sh
source "$REPO_ROOT/installer/lib/plexamp_runtime.sh"

MODE=prepare-only
CONFIRM=
ROOT="${ACP_ROOT:-/}"
PROJECT_USER="${ACP_PROJECT_USER:-${SUDO_USER:-${USER:-andy}}}"
NODE_ARCHIVE_INPUT=
PLEXAMP_ARCHIVE_INPUT=

usage() {
    cat <<EOF
Usage: bash scripts/install-plexamp-runtime.sh [options]

Guarded Plexamp Headless $ACP_PLEXAMP_VERSION compatibility-runtime owner.
Prepare-only is the default. Production activation downloads only the exact
pinned Plexamp and Node archives, verifies SHA-256 before extraction, stages both
runtimes before live replacement, and owns plexamp.service.

Options:
  --prepare-only
  --activate --confirm $ACP_PLEXAMP_RUNTIME_CONFIRMATION
  --project-user USER
  --node-archive PATH      optional pre-downloaded pinned Node archive
  --plexamp-archive PATH   optional pre-downloaded pinned Plexamp archive
  --root PATH              alternate filesystem root for non-production tests
  -h, --help

Fresh claim checkpoint:
  If no Plexamp Settings state exists after the verified runtime is installed,
  activation exits $ACP_PLEXAMP_CLAIM_EXIT with PLEXAMP_RUNTIME=CLAIM-REQUIRED and prints
  a foreground CLAIM_COMMAND. Enter the Plex claim code and player name directly
  into Plexamp, wait for it to start, Ctrl-C, then rerun the root installer.
  No claim token is accepted by this installer as an argument or environment value.
EOF
}

error() {
    printf '[A Clockwork Plex] ERROR: %s\n' "$*" >&2
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prepare-only) MODE=prepare-only; shift ;;
        --activate) MODE=activate; shift ;;
        --confirm)
            [[ $# -ge 2 ]] || { error '--confirm requires a token.'; exit 64; }
            CONFIRM="$2"; shift 2 ;;
        --project-user)
            [[ $# -ge 2 ]] || { error '--project-user requires a user.'; exit 64; }
            PROJECT_USER="$2"; shift 2 ;;
        --node-archive)
            [[ $# -ge 2 ]] || { error '--node-archive requires a path.'; exit 64; }
            NODE_ARCHIVE_INPUT="$2"; shift 2 ;;
        --plexamp-archive)
            [[ $# -ge 2 ]] || { error '--plexamp-archive requires a path.'; exit 64; }
            PLEXAMP_ARCHIVE_INPUT="$2"; shift 2 ;;
        --root)
            [[ $# -ge 2 ]] || { error '--root requires a path.'; exit 64; }
            ROOT="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) error "Unknown option: $1"; usage >&2; exit 64 ;;
    esac
done

[[ "$PROJECT_USER" =~ ^[A-Za-z_][A-Za-z0-9_.-]*$ ]] || {
    error "Invalid project user: $PROJECT_USER"
    exit 64
}
if [[ "$ROOT" != / ]]; then
    ROOT="${ROOT%/}"
    [[ -d "$ROOT" ]] || { error "Alternate root does not exist: $ROOT"; exit 1; }
fi
export ACP_ROOT="$ROOT"

if [[ "$MODE" == activate ]]; then
    [[ "$CONFIRM" == "$ACP_PLEXAMP_RUNTIME_CONFIRMATION" ]] || {
        error "Activation requires --confirm $ACP_PLEXAMP_RUNTIME_CONFIRMATION."
        exit 64
    }
elif [[ -n "$CONFIRM" ]]; then
    error '--confirm is only valid with --activate.'
    exit 64
fi

if ! acp_plexamp_runtime_artifact_pinned; then
    error 'Plexamp artifact identity is not pinned in source.'
    exit 78
fi

# Test digest overrides exist solely to exercise the alternate-root transaction
# with tiny fixture archives. They are forbidden against the production root.
if [[ "$ROOT" == / && ( -n "${ACP_PLEXAMP_TEST_NODE_SHA256:-}" || -n "${ACP_PLEXAMP_TEST_ARCHIVE_SHA256:-}" ) ]]; then
    error 'ACP_PLEXAMP_TEST_* digest overrides are forbidden on the production root.'
    exit 1
fi
EXPECTED_NODE_SHA="$ACP_NODE_ARCHIVE_SHA256"
EXPECTED_PLEXAMP_SHA="$ACP_PLEXAMP_ARCHIVE_SHA256"
if [[ "$ROOT" != / ]]; then
    EXPECTED_NODE_SHA="${ACP_PLEXAMP_TEST_NODE_SHA256:-$EXPECTED_NODE_SHA}"
    EXPECTED_PLEXAMP_SHA="${ACP_PLEXAMP_TEST_ARCHIVE_SHA256:-$EXPECTED_PLEXAMP_SHA}"
fi
[[ "$EXPECTED_NODE_SHA" =~ ^[0-9a-f]{64}$ && "$EXPECTED_PLEXAMP_SHA" =~ ^[0-9a-f]{64}$ ]] || {
    error 'Expected archive digests must be lowercase SHA-256 values.'
    exit 1
}

logical_path() {
    local path="$1"
    if [[ "$ROOT" == / ]]; then
        printf '%s\n' "$path"
    else
        printf '%s%s\n' "$ROOT" "$path"
    fi
}

if [[ "$ROOT" == / ]]; then
    [[ "$EUID" -ne 0 ]] || { error 'Run activation as the normal project user, not as root.'; [[ "$MODE" == prepare-only ]] || exit 1; }
    if id "$PROJECT_USER" >/dev/null 2>&1; then
        PROJECT_HOME="$(getent passwd "$PROJECT_USER" | cut -d: -f6)"
    else
        PROJECT_HOME="/home/$PROJECT_USER"
    fi
else
    PROJECT_HOME="/home/$PROJECT_USER"
fi
[[ "$PROJECT_HOME" == /* ]] || { error 'Could not resolve a safe project-user home.'; exit 1; }

NODE_PARENT=/opt/a-clockwork-plex
NODE_TARGET="$NODE_PARENT/node-v${ACP_NODE_VERSION}-${ACP_NODE_PLATFORM}"
PLEXAMP_TARGET="$PROJECT_HOME/plexamp"
PLEXAMP_SETTINGS="$PROJECT_HOME/.local/share/Plexamp/Settings"
UNIT_TARGET=/etc/systemd/system/plexamp.service
NODE_TARGET_PATH="$(logical_path "$NODE_TARGET")"
PLEXAMP_TARGET_PATH="$(logical_path "$PLEXAMP_TARGET")"
PLEXAMP_SETTINGS_PATH="$(logical_path "$PLEXAMP_SETTINGS")"
NODE_MANIFEST="$NODE_TARGET_PATH/.a-clockwork-plex-runtime"
PLEXAMP_MANIFEST="$PLEXAMP_TARGET_PATH/.a-clockwork-plex-runtime"

acp_plexamp_runtime_plan "$PROJECT_USER"
cat <<EOF

Managed runtime targets:
  $NODE_TARGET
  $PLEXAMP_TARGET
  $UNIT_TARGET

Persistent Plexamp user state is deliberately outside the runtime transaction:
  $PLEXAMP_SETTINGS

Runtime replacement never removes that Settings directory. Existing claimed
state therefore survives a guarded runtime repair/update.
EOF

if [[ "$MODE" == prepare-only ]]; then
    cat <<'EOF'

Prepare-only complete. No network request, archive extraction, file, directory,
service, package, boot setting, audio route, mixer, PCM or configuration was changed.
EOF
    exit 0
fi
[[ "$MODE" == activate ]] || { error "Unsupported mode: $MODE"; exit 64; }

if [[ "$ROOT" == / ]]; then
    [[ "$(id -un)" == "$PROJECT_USER" ]] || {
        error "Production activation must be run by project user $PROJECT_USER."
        exit 1
    }
    for command in sudo curl tar sha256sum mktemp mv rm grep awk stat systemctl; do
        command -v "$command" >/dev/null 2>&1 || { error "Required command not found: $command"; exit 1; }
    done
    [[ -d "$PROJECT_HOME" && ! -L "$PROJECT_HOME" ]] || {
        error "Project home is unavailable or unsafe: $PROJECT_HOME"
        exit 1
    }
else
    for command in tar sha256sum mktemp mv rm grep awk stat; do
        command -v "$command" >/dev/null 2>&1 || { error "Required command not found: $command"; exit 1; }
    done
    mkdir -p "$(dirname "$PLEXAMP_TARGET_PATH")" "$(dirname "$NODE_TARGET_PATH")" "$PLEXAMP_SETTINGS_PATH"
fi

for input in "$NODE_ARCHIVE_INPUT" "$PLEXAMP_ARCHIVE_INPUT"; do
    [[ -z "$input" || ( -f "$input" && ! -L "$input" && -r "$input" ) ]] || {
        error "Archive input must be a readable regular file, not a symlink: $input"
        exit 1
    }
done

manifest_matches() {
    local manifest="$1" kind="$2" version="$3" digest="$4"
    [[ -f "$manifest" && ! -L "$manifest" ]] || return 1
    grep -Fxq "kind=$kind" "$manifest" && \
        grep -Fxq "version=$version" "$manifest" && \
        grep -Fxq "archive_sha256=$digest" "$manifest"
}

node_ready=false
if [[ -x "$NODE_TARGET_PATH/bin/node" ]] && \
   manifest_matches "$NODE_MANIFEST" node "$ACP_NODE_VERSION" "$EXPECTED_NODE_SHA" && \
   [[ "$($NODE_TARGET_PATH/bin/node --version 2>/dev/null || true)" == "v$ACP_NODE_VERSION" ]]; then
    node_ready=true
fi

plexamp_ready=false
if [[ -f "$PLEXAMP_TARGET_PATH/js/index.js" && ! -L "$PLEXAMP_TARGET_PATH/js/index.js" ]] && \
   manifest_matches "$PLEXAMP_MANIFEST" plexamp "$ACP_PLEXAMP_VERSION" "$EXPECTED_PLEXAMP_SHA"; then
    plexamp_ready=true
fi

DOWNLOAD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/a-clockwork-plex-plexamp-download.XXXXXX")"
NODE_DOWNLOAD="$DOWNLOAD_DIR/$ACP_NODE_ARCHIVE"
PLEXAMP_DOWNLOAD="$DOWNLOAD_DIR/$ACP_PLEXAMP_ARCHIVE"
cleanup_downloads() { rm -rf -- "$DOWNLOAD_DIR"; }

cleanup_stage_parents() {
    local previous
    if [[ -n "${NODE_STAGE_PARENT:-}" && -d "$NODE_STAGE_PARENT" ]]; then
        previous="${NODE_PREVIOUS:-}"
        if [[ -z "$previous" || ! -e "$previous" ]]; then
            if [[ "$ROOT" == / ]]; then
                sudo -- rm -rf -- "$NODE_STAGE_PARENT" >/dev/null 2>&1 || true
            else
                rm -rf -- "$NODE_STAGE_PARENT" >/dev/null 2>&1 || true
            fi
        fi
    fi
    if [[ -n "${PLEXAMP_STAGE_PARENT:-}" && -d "$PLEXAMP_STAGE_PARENT" ]]; then
        previous="${PLEXAMP_PREVIOUS:-}"
        if [[ -z "$previous" || ! -e "$previous" ]]; then
            rm -rf -- "$PLEXAMP_STAGE_PARENT" >/dev/null 2>&1 || true
        fi
    fi
}

cleanup_pretransaction() {
    cleanup_stage_parents
    cleanup_downloads
}
trap cleanup_pretransaction EXIT

obtain_archive() {
    local label="$1" supplied="$2" url="$3" destination="$4" expected="$5"
    if [[ -n "$supplied" ]]; then
        cp -- "$supplied" "$destination"
    else
        [[ "$ROOT" == / ]] || {
            error "$label alternate-root activation requires a local archive fixture."
            return 1
        }
        echo "Downloading pinned $label archive..."
        curl --fail --show-error --silent --location --proto '=https' --tlsv1.2 \
            --output "$destination" "$url"
    fi
    local observed
    observed="$(sha256sum "$destination" | awk '{print $1}')"
    if [[ "$observed" != "$expected" ]]; then
        error "$label archive SHA-256 mismatch: $observed"
        return 1
    fi
    echo "$label archive SHA-256 verified: $observed"
}

NODE_STAGE_PARENT=
PLEXAMP_STAGE_PARENT=
NODE_CANDIDATE=
PLEXAMP_CANDIDATE=

if [[ "$node_ready" != true ]]; then
    obtain_archive Node "$NODE_ARCHIVE_INPUT" "$ACP_NODE_ARCHIVE_URL" "$NODE_DOWNLOAD" "$EXPECTED_NODE_SHA" || exit 1
    if [[ "$ROOT" == / ]]; then
        sudo -- install -d -m 0755 "$NODE_PARENT"
        NODE_STAGE_PARENT="$(sudo -- mktemp -d "$NODE_PARENT/.acp-node-stage.XXXXXX")"
        sudo -- chown "$PROJECT_USER:$PROJECT_USER" "$NODE_STAGE_PARENT"
    else
        mkdir -p "$(logical_path "$NODE_PARENT")"
        NODE_STAGE_PARENT="$(mktemp -d "$(logical_path "$NODE_PARENT")/.acp-node-stage.XXXXXX")"
    fi
    tar -xJf "$NODE_DOWNLOAD" -C "$NODE_STAGE_PARENT"
    NODE_CANDIDATE="$NODE_STAGE_PARENT/node-v${ACP_NODE_VERSION}-${ACP_NODE_PLATFORM}"
    [[ -x "$NODE_CANDIDATE/bin/node" ]] || { error 'Staged Node candidate has no executable bin/node.'; exit 1; }
    [[ "$($NODE_CANDIDATE/bin/node --version 2>/dev/null || true)" == "v$ACP_NODE_VERSION" ]] || {
        error 'Staged Node candidate reported the wrong version.'
        exit 1
    }
    cat >"$NODE_CANDIDATE/.a-clockwork-plex-runtime" <<EOF
kind=node
version=$ACP_NODE_VERSION
archive_sha256=$EXPECTED_NODE_SHA
EOF
fi

if [[ "$plexamp_ready" != true ]]; then
    obtain_archive Plexamp "$PLEXAMP_ARCHIVE_INPUT" "$ACP_PLEXAMP_ARCHIVE_URL" "$PLEXAMP_DOWNLOAD" "$EXPECTED_PLEXAMP_SHA" || exit 1
    if [[ "$EXPECTED_PLEXAMP_SHA" == "$ACP_PLEXAMP_ARCHIVE_SHA256" ]]; then
        [[ "$(stat -c '%s' "$PLEXAMP_DOWNLOAD")" == "$ACP_PLEXAMP_ARCHIVE_BYTES" ]] || {
            error 'Pinned Plexamp archive size does not match the probed artifact.'
            exit 1
        }
    fi
    PLEXAMP_STAGE_PARENT="$(mktemp -d "$(dirname "$PLEXAMP_TARGET_PATH")/.acp-plexamp-stage.XXXXXX")"
    tar -xjf "$PLEXAMP_DOWNLOAD" -C "$PLEXAMP_STAGE_PARENT"
    PLEXAMP_CANDIDATE="$PLEXAMP_STAGE_PARENT/plexamp"
    [[ -f "$PLEXAMP_CANDIDATE/js/index.js" && ! -L "$PLEXAMP_CANDIDATE/js/index.js" ]] || {
        error 'Staged Plexamp candidate is missing plexamp/js/index.js.'
        exit 1
    }
    [[ -f "$PLEXAMP_CANDIDATE/plexamp.service" ]] || {
        error 'Staged Plexamp candidate is missing its reference plexamp.service.'
        exit 1
    }
    cat >"$PLEXAMP_CANDIDATE/.a-clockwork-plex-runtime" <<EOF
kind=plexamp
version=$ACP_PLEXAMP_VERSION
archive_sha256=$EXPECTED_PLEXAMP_SHA
archive_bytes=$(stat -c '%s' "$PLEXAMP_DOWNLOAD")
EOF
fi

UNIT_CANDIDATE="$DOWNLOAD_DIR/plexamp.service"
cat >"$UNIT_CANDIDATE" <<EOF
[Unit]
Description=Plexamp Headless for A Clockwork Plex
After=network-online.target
Requires=network-online.target

[Service]
Type=simple
User=$PROJECT_USER
WorkingDirectory=$PLEXAMP_TARGET
ExecStart=$NODE_TARGET/bin/node $PLEXAMP_TARGET/js/index.js
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
for expected in \
    "User=$PROJECT_USER" \
    "WorkingDirectory=$PLEXAMP_TARGET" \
    "ExecStart=$NODE_TARGET/bin/node $PLEXAMP_TARGET/js/index.js"; do
    grep -Fxq "$expected" "$UNIT_CANDIDATE" || { error "Rendered Plexamp unit is missing: $expected"; exit 1; }
done
# The unit uses exact-file transaction primitives. Runtime directories use a
# paired same-filesystem rename transaction because the shared path transaction
# intentionally supports regular files only.
TRANSACTION_PARENT="$(mktemp -d "${TMPDIR:-/tmp}/a-clockwork-plex-plexamp-install.XXXXXX")"
TRANSACTION="$TRANSACTION_PARENT/transaction"
acp_transaction_begin "$TRANSACTION"
acp_transaction_capture_path "$TRANSACTION" "$UNIT_TARGET"
SERVICE_PREEXISTED=false
if [[ "$ROOT" == / ]] && sudo test -f "$UNIT_TARGET"; then
    SERVICE_PREEXISTED=true
    acp_transaction_capture_service "$TRANSACTION" "$ACP_PLEXAMP_SERVICE"
fi

NODE_PREVIOUS=
PLEXAMP_PREVIOUS=
NODE_SWAPPED=false
PLEXAMP_SWAPPED=false

cleanup_transaction() { rm -rf -- "$TRANSACTION_PARENT"; }
trap 'cleanup_transaction; cleanup_stage_parents; cleanup_downloads' EXIT

rollback_runtime() {
    local failed=0
    set +e
    if [[ "$ROOT" == / ]]; then
        sudo -- systemctl stop "$ACP_PLEXAMP_SERVICE" >/dev/null 2>&1 || true
    fi
    acp_transaction_restore_paths "$TRANSACTION" || failed=1

    if [[ "$PLEXAMP_SWAPPED" == true && -d "$PLEXAMP_TARGET_PATH" ]]; then
        rm -rf -- "$PLEXAMP_TARGET_PATH" || failed=1
    fi
    if [[ -n "$PLEXAMP_PREVIOUS" && -d "$PLEXAMP_PREVIOUS" ]]; then
        mv -- "$PLEXAMP_PREVIOUS" "$PLEXAMP_TARGET_PATH" || failed=1
    fi
    if [[ "$NODE_SWAPPED" == true ]]; then
        if [[ "$ROOT" == / ]]; then sudo -- rm -rf -- "$NODE_TARGET_PATH" || failed=1; else rm -rf -- "$NODE_TARGET_PATH" || failed=1; fi
    fi
    if [[ -n "$NODE_PREVIOUS" ]]; then
        if [[ "$ROOT" == / && -d "$NODE_PREVIOUS" ]]; then sudo -- mv -- "$NODE_PREVIOUS" "$NODE_TARGET_PATH" || failed=1
        elif [[ "$ROOT" != / && -d "$NODE_PREVIOUS" ]]; then mv -- "$NODE_PREVIOUS" "$NODE_TARGET_PATH" || failed=1
        fi
    fi
    if [[ "$ROOT" == / ]]; then
        sudo -- systemctl daemon-reload >/dev/null 2>&1 || failed=1
        if [[ "$SERVICE_PREEXISTED" == true ]]; then
            acp_transaction_restore_services "$TRANSACTION" || failed=1
        else
            sudo -- systemctl disable "$ACP_PLEXAMP_SERVICE" >/dev/null 2>&1 || true
        fi
    fi
    set -e
    [[ "$failed" -eq 0 ]]
}

fail_after_mutation() {
    error "$1"
    if rollback_runtime; then
        error 'Captured Plexamp runtime/service pre-state restored.'
    else
        error 'WARNING: Plexamp runtime rollback reported a failure.'
    fi
    exit 1
}

if [[ "$ROOT" == / && "$SERVICE_PREEXISTED" == true ]]; then
    sudo -- systemctl stop "$ACP_PLEXAMP_SERVICE" || fail_after_mutation 'Could not stop the existing Plexamp service.'
fi

if [[ "$node_ready" != true ]]; then
    if [[ -e "$NODE_TARGET_PATH" || -L "$NODE_TARGET_PATH" ]]; then
        [[ -d "$NODE_TARGET_PATH" && ! -L "$NODE_TARGET_PATH" ]] || fail_after_mutation 'Existing Node target is not a safe directory.'
        NODE_PREVIOUS="$NODE_STAGE_PARENT/node.previous"
        if [[ "$ROOT" == / ]]; then sudo -- mv -- "$NODE_TARGET_PATH" "$NODE_PREVIOUS" || fail_after_mutation 'Could not preserve previous Node runtime.'
        else mv -- "$NODE_TARGET_PATH" "$NODE_PREVIOUS" || fail_after_mutation 'Could not preserve previous Node runtime.'; fi
    fi
    if [[ "$ROOT" == / ]]; then
        sudo -- mv -- "$NODE_CANDIDATE" "$NODE_TARGET_PATH" || fail_after_mutation 'Could not activate pinned Node runtime.'
        sudo -- chown -R root:root "$NODE_TARGET_PATH" || fail_after_mutation 'Could not set Node runtime ownership.'
    else
        mv -- "$NODE_CANDIDATE" "$NODE_TARGET_PATH" || fail_after_mutation 'Could not activate pinned Node runtime.'
    fi
    NODE_SWAPPED=true
fi

if [[ "$plexamp_ready" != true ]]; then
    if [[ -e "$PLEXAMP_TARGET_PATH" || -L "$PLEXAMP_TARGET_PATH" ]]; then
        [[ -d "$PLEXAMP_TARGET_PATH" && ! -L "$PLEXAMP_TARGET_PATH" ]] || fail_after_mutation 'Existing Plexamp target is not a safe directory.'
        PLEXAMP_PREVIOUS="$PLEXAMP_STAGE_PARENT/plexamp.previous"
        mv -- "$PLEXAMP_TARGET_PATH" "$PLEXAMP_PREVIOUS" || fail_after_mutation 'Could not preserve previous Plexamp runtime.'
    fi
    mv -- "$PLEXAMP_CANDIDATE" "$PLEXAMP_TARGET_PATH" || fail_after_mutation 'Could not activate pinned Plexamp runtime.'
    PLEXAMP_SWAPPED=true
fi

[[ -x "$NODE_TARGET_PATH/bin/node" ]] || fail_after_mutation 'Activated Node runtime is incomplete.'
[[ "$($NODE_TARGET_PATH/bin/node --version 2>/dev/null || true)" == "v$ACP_NODE_VERSION" ]] || fail_after_mutation 'Activated Node runtime version mismatch.'
manifest_matches "$NODE_MANIFEST" node "$ACP_NODE_VERSION" "$EXPECTED_NODE_SHA" || fail_after_mutation 'Activated Node runtime manifest mismatch.'
[[ -f "$PLEXAMP_TARGET_PATH/js/index.js" ]] || fail_after_mutation 'Activated Plexamp runtime is incomplete.'
manifest_matches "$PLEXAMP_MANIFEST" plexamp "$ACP_PLEXAMP_VERSION" "$EXPECTED_PLEXAMP_SHA" || fail_after_mutation 'Activated Plexamp runtime manifest mismatch.'

# systemd-analyze resolves ExecStart while verifying a unit. On a genuinely
# fresh Pi the pinned Node path does not exist until the runtime candidate has
# been promoted. Keep verification fail-closed, but perform it here inside the
# runtime transaction so the exact rendered paths exist and any failure can
# restore the captured runtime/service pre-state.
if [[ "$ROOT" == / ]] && command -v systemd-analyze >/dev/null 2>&1; then
    systemd-analyze verify "$UNIT_CANDIDATE" >/dev/null ||         fail_after_mutation 'Rendered plexamp.service failed systemd verification after runtime activation.'
fi

acp_install_file "$UNIT_CANDIDATE" "$UNIT_TARGET" 0644 || fail_after_mutation 'Could not install plexamp.service.'

if [[ "$ROOT" != / && "${ACP_PLEXAMP_TEST_FAIL_AFTER_SWAP:-0}" == 1 ]]; then
    fail_after_mutation 'Injected non-production failure after runtime swap.'
fi

claimed=false
if [[ -d "$PLEXAMP_SETTINGS_PATH" ]] && find "$PLEXAMP_SETTINGS_PATH" -maxdepth 1 -type f -print -quit 2>/dev/null | grep -q .; then
    claimed=true
fi

commit_directory_state() {
    if [[ -n "$PLEXAMP_PREVIOUS" && -d "$PLEXAMP_PREVIOUS" ]]; then rm -rf -- "$PLEXAMP_PREVIOUS"; fi
    if [[ -n "$NODE_PREVIOUS" ]]; then
        if [[ "$ROOT" == / && -d "$NODE_PREVIOUS" ]]; then sudo -- rm -rf -- "$NODE_PREVIOUS"
        elif [[ "$ROOT" != / && -d "$NODE_PREVIOUS" ]]; then rm -rf -- "$NODE_PREVIOUS"
        fi
    fi
    NODE_SWAPPED=false
    PLEXAMP_SWAPPED=false
    acp_transaction_mark_complete "$TRANSACTION"
}

if [[ "$claimed" != true ]]; then
    if [[ "$ROOT" == / ]]; then
        sudo -- systemctl daemon-reload
        sudo -- systemctl stop "$ACP_PLEXAMP_SERVICE" >/dev/null 2>&1 || true
        if [[ "$SERVICE_PREEXISTED" == false ]]; then
            sudo -- systemctl disable "$ACP_PLEXAMP_SERVICE" >/dev/null 2>&1 || true
        fi
    fi
    commit_directory_state
    cat <<EOF

PLEXAMP_RUNTIME=CLAIM-REQUIRED
PLEXAMP_VERSION=$ACP_PLEXAMP_VERSION
CLAIM_POLICY=INTERACTIVE-LOCAL-ONLY
CLAIM_INSTRUCTIONS=Enter a fresh code from https://plex.tv/claim and a player name; wait for Plexamp to start, then press Ctrl-C.
CLAIM_COMMAND=cd $(printf '%q' "$PLEXAMP_TARGET") && $(printf '%q' "$NODE_TARGET/bin/node") js/index.js
RERUN_ROOT_INSTALLER_AFTER_CLAIM=YES
EOF
    exit "$ACP_PLEXAMP_CLAIM_EXIT"
fi

if [[ "$ROOT" == / ]]; then
    sudo -- systemctl daemon-reload || fail_after_mutation 'systemd daemon-reload failed.'
    sudo -- systemctl enable "$ACP_PLEXAMP_SERVICE" >/dev/null || fail_after_mutation 'Could not enable plexamp.service.'
    sudo -- systemctl restart "$ACP_PLEXAMP_SERVICE" || fail_after_mutation 'Could not start plexamp.service.'

    ready=false
    for _attempt in {1..30}; do
        if systemctl is-active --quiet "$ACP_PLEXAMP_SERVICE" && curl -fsS "http://127.0.0.1:$ACP_PLEXAMP_PORT/" >/dev/null 2>&1; then
            ready=true
            break
        fi
        sleep 0.5
    done
    [[ "$ready" == true ]] || fail_after_mutation "plexamp.service did not expose local port $ACP_PLEXAMP_PORT."
fi

commit_directory_state

echo
echo '[A Clockwork Plex] Pinned Plexamp Headless runtime installed successfully.'
echo 'PLEXAMP_RUNTIME=PASS'
echo "PLEXAMP_VERSION=$ACP_PLEXAMP_VERSION"
echo "NODE_VERSION=$ACP_NODE_VERSION"
echo "PLEXAMP_PORT=$ACP_PLEXAMP_PORT"
