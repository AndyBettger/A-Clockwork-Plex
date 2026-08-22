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

ALARM_SOURCE="$REPO_ROOT/scripts/a-clockwork-plex-alarm-audio-helper.sh"
ALARM_TARGET=/usr/local/bin/a-clockwork-plex-alarm-audio
ALARM_SUDOERS=/etc/sudoers.d/a-clockwork-plex-alarm-audio
NAME_SOURCE="$REPO_ROOT/scripts/a-clockwork-plex-shairport-name.py"
NAME_TARGET=/usr/local/bin/a-clockwork-plex-shairport-name
NAME_SUDOERS=/etc/sudoers.d/a-clockwork-plex-shairport-name
WEATHER_SOURCE="$REPO_ROOT/scripts/a-clockwork-plex-weather-secret.py"
WEATHER_TARGET=/usr/local/bin/a-clockwork-plex-weather-secret
WEATHER_SUDOERS=/etc/sudoers.d/a-clockwork-plex-weather-secret
MIXER_SOURCE="$REPO_ROOT/scripts/a-clockwork-plex-audio-mixer.py"
MIXER_TARGET=/usr/local/bin/a-clockwork-plex-audio-mixer
MIXER_SUDOERS=/etc/sudoers.d/a-clockwork-plex-audio-mixer
MIXER_DEFAULTS=/etc/default/a-clockwork-plex-audio

usage() {
    cat <<'EOF'
Usage: bash scripts/install-appliance-helpers.sh [options]

Guarded installer for the restricted appliance helpers used by the alarm engine,
managed Shairport receiver-name Settings, write-only Weather Underground
credential commissioning/status, and persistent shared-audio mixer controls.
Prepare-only is the default and does not change production state.

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
            [[ $# -ge 2 ]] || { echo '--confirm requires a value.' >&2; exit 64; }
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

for source in "$ALARM_SOURCE" "$NAME_SOURCE" "$WEATHER_SOURCE" "$MIXER_SOURCE"; do
    [[ -f "$source" && ! -L "$source" ]] || {
        echo "Required helper source is unavailable: $source" >&2
        exit 1
    }
done

ALARM_POLICY="# Managed by A Clockwork Plex. The helper validates every action and argument.\n$PROJECT_USER ALL=(root) NOPASSWD: $ALARM_TARGET release\n$PROJECT_USER ALL=(root) NOPASSWD: $ALARM_TARGET restore *\n"
NAME_POLICY="$PROJECT_USER ALL=(root) NOPASSWD: $NAME_TARGET status\n$PROJECT_USER ALL=(root) NOPASSWD: $NAME_TARGET set *\n"
WEATHER_POLICY="# Managed by A Clockwork Plex. Secret value is supplied on stdin, never argv; status returns presence only.\n$PROJECT_USER ALL=(root) NOPASSWD: $WEATHER_TARGET status\n$PROJECT_USER ALL=(root) NOPASSWD: $WEATHER_TARGET set\n$PROJECT_USER ALL=(root) NOPASSWD: $WEATHER_TARGET remove\n"
MIXER_POLICY="# Managed by A Clockwork Plex. The helper validates channel names and 0-100 levels.\n$PROJECT_USER ALL=(root) NOPASSWD: $MIXER_TARGET status\n$PROJECT_USER ALL=(root) NOPASSWD: $MIXER_TARGET set *\n$PROJECT_USER ALL=(root) NOPASSWD: $MIXER_TARGET live *\n"
MIXER_DEFAULTS_TEXT="# Managed by A Clockwork Plex.\nALSA_CARD=Pro\nALSA_DEVICE=0\nSAMPLE_RATE=44100\nCHANNELS=2\n"

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
validate_policy "$WEATHER_POLICY"
validate_policy "$MIXER_POLICY"

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
  $WEATHER_TARGET
  $WEATHER_SUDOERS
  $MIXER_TARGET
  $MIXER_SUDOERS
  $MIXER_DEFAULTS

The runtime helper implementations remain in their existing specialist source
files. This installer owns guarded packaging, restricted sudo policy and the
fixed shared-audio helper defaults. On production activation it opens each named
A Clockwork Plex PCM with silence so ALSA creates the softvol controls before the
read-only appliance verifier and dashboard API inspect them.
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
    for command in sudo aplay timeout python3; do
        acp_require_command "$command"
    done
fi

TRANSACTION_PARENT="$(mktemp -d "${TMPDIR:-/tmp}/a-clockwork-plex-helper-install.XXXXXX")"
TRANSACTION="$TRANSACTION_PARENT/transaction"
cleanup() { rm -rf "$TRANSACTION_PARENT"; }
trap cleanup EXIT
acp_transaction_begin "$TRANSACTION"
for target in \
    "$ALARM_TARGET" "$ALARM_SUDOERS" \
    "$NAME_TARGET" "$NAME_SUDOERS" \
    "$WEATHER_TARGET" "$WEATHER_SUDOERS" \
    "$MIXER_TARGET" "$MIXER_SUDOERS" "$MIXER_DEFAULTS"; do
    acp_transaction_capture_path "$TRANSACTION" "$target"
done

rollback() {
    acp_transaction_restore_paths "$TRANSACTION"
}

verify_regular_file() {
    local logical="$1" physical
    physical="$(acp_path "$logical")" || return 1
    if ! acp_run_root test -f "$physical" || acp_run_root test -L "$physical"; then
        acp_error "Installed helper target is not a regular non-symlink file: $logical"
        return 1
    fi
}

verify_mode() {
    local logical="$1" expected="$2" physical actual
    physical="$(acp_path "$logical")" || return 1
    if ! actual="$(acp_run_root stat -c '%a' "$physical")"; then
        acp_error "Unable to inspect installed helper target mode: $logical"
        return 1
    fi
    if [[ "$actual" != "$expected" ]]; then
        acp_error "Installed helper target has mode $actual; expected $expected: $logical"
        return 1
    fi
}

verify_contains() {
    local logical="$1" expected="$2" physical
    physical="$(acp_path "$logical")" || return 1
    if ! acp_run_root grep -Fq -- "$expected" "$physical"; then
        acp_error "Installed helper policy is missing required rule: $logical"
        return 1
    fi
}

prime_mixer_controls() {
    acp_is_production_root || return 0
    local pcm rc status_file
    for pcm in acp_master acp_plexamp acp_airplay acp_alarm; do
        rc=0
        timeout 0.35 /usr/bin/aplay -q -D "$pcm" -f S16_LE -r 44100 -c 2 /dev/zero >/dev/null 2>&1 || rc=$?
        if [[ "$rc" -ne 0 && "$rc" -ne 124 ]]; then
            acp_error "Could not initialise shared-audio PCM: $pcm"
            return 1
        fi
    done

    status_file="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-mixer-status.XXXXXX")" || return 1
    if ! sudo -n "$MIXER_TARGET" status >"$status_file"; then
        rm -f "$status_file"
        acp_error 'Installed mixer helper status command failed.'
        return 1
    fi
    if ! python3 - "$status_file" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
channels = payload.get("channels") if isinstance(payload, dict) else None
required = {"master", "plexamp", "airplay", "alarm"}
ok = (
    payload.get("available") is True
    and payload.get("configured") is True
    and isinstance(channels, dict)
    and required.issubset(channels)
    and all(channels[name].get("available") is True and channels[name].get("pcm_available") is True for name in required)
)
raise SystemExit(0 if ok else 1)
PY
    then
        rm -f "$status_file"
        acp_error 'Installed mixer helper reports one or more unavailable controls/PCMs.'
        return 1
    fi
    rm -f "$status_file"
}

activate() {
    local installed
    acp_install_file "$ALARM_SOURCE" "$ALARM_TARGET" 0755 || return 1
    acp_install_text "$ALARM_POLICY" "$ALARM_SUDOERS" 0440 || return 1
    acp_install_file "$NAME_SOURCE" "$NAME_TARGET" 0755 || return 1
    acp_install_text "$NAME_POLICY" "$NAME_SUDOERS" 0440 || return 1
    acp_install_file "$WEATHER_SOURCE" "$WEATHER_TARGET" 0755 || return 1
    acp_install_text "$WEATHER_POLICY" "$WEATHER_SUDOERS" 0440 || return 1
    acp_install_file "$MIXER_SOURCE" "$MIXER_TARGET" 0755 || return 1
    acp_install_text "$MIXER_POLICY" "$MIXER_SUDOERS" 0440 || return 1
    acp_install_text "$MIXER_DEFAULTS_TEXT" "$MIXER_DEFAULTS" 0644 || return 1

    if [[ "$ROOT" != / && "${ACP_HELPERS_TEST_FAIL_AFTER_INSTALL:-0}" == 1 ]]; then
        echo 'Injected non-production failure after restricted helper install.' >&2
        return 1
    fi

    for installed in \
        "$ALARM_TARGET" "$ALARM_SUDOERS" \
        "$NAME_TARGET" "$NAME_SUDOERS" \
        "$WEATHER_TARGET" "$WEATHER_SUDOERS" \
        "$MIXER_TARGET" "$MIXER_SUDOERS" "$MIXER_DEFAULTS"; do
        verify_regular_file "$installed" || return 1
    done
    verify_mode "$ALARM_TARGET" 755 || return 1
    verify_mode "$NAME_TARGET" 755 || return 1
    verify_mode "$WEATHER_TARGET" 755 || return 1
    verify_mode "$MIXER_TARGET" 755 || return 1
    verify_mode "$ALARM_SUDOERS" 440 || return 1
    verify_mode "$NAME_SUDOERS" 440 || return 1
    verify_mode "$WEATHER_SUDOERS" 440 || return 1
    verify_mode "$MIXER_SUDOERS" 440 || return 1
    verify_mode "$MIXER_DEFAULTS" 644 || return 1
    verify_contains "$ALARM_SUDOERS" "$PROJECT_USER ALL=(root) NOPASSWD: $ALARM_TARGET release" || return 1
    verify_contains "$NAME_SUDOERS" "$PROJECT_USER ALL=(root) NOPASSWD: $NAME_TARGET status" || return 1
    verify_contains "$WEATHER_SUDOERS" "$PROJECT_USER ALL=(root) NOPASSWD: $WEATHER_TARGET status" || return 1
    verify_contains "$WEATHER_SUDOERS" "$PROJECT_USER ALL=(root) NOPASSWD: $WEATHER_TARGET set" || return 1
    verify_contains "$WEATHER_SUDOERS" "$PROJECT_USER ALL=(root) NOPASSWD: $WEATHER_TARGET remove" || return 1
    verify_contains "$MIXER_SUDOERS" "$PROJECT_USER ALL=(root) NOPASSWD: $MIXER_TARGET status" || return 1
    verify_contains "$MIXER_SUDOERS" "$PROJECT_USER ALL=(root) NOPASSWD: $MIXER_TARGET set *" || return 1
    verify_contains "$MIXER_SUDOERS" "$PROJECT_USER ALL=(root) NOPASSWD: $MIXER_TARGET live *" || return 1
    verify_contains "$MIXER_DEFAULTS" 'ALSA_CARD=Pro' || return 1
    verify_contains "$MIXER_DEFAULTS" 'ALSA_DEVICE=0' || return 1
    verify_contains "$MIXER_DEFAULTS" 'SAMPLE_RATE=44100' || return 1
    verify_contains "$MIXER_DEFAULTS" 'CHANNELS=2' || return 1
    prime_mixer_controls || return 1
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
