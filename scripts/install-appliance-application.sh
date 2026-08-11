#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export ACP_REPO_ROOT="$REPO_ROOT"

# shellcheck source=installer/lib/common.sh
source "$REPO_ROOT/installer/lib/common.sh"
# shellcheck source=installer/lib/application_transaction.sh
source "$REPO_ROOT/installer/lib/application_transaction.sh"

MODE=prepare-only
CONFIRM=
CONFIRM_TOKEN=INSTALL-APPLIANCE-APPLICATION
ROOT="${ACP_ROOT:-/}"
AUDIO_PROFILE="${ACP_AUDIO_PROFILE:-eq}"
WEATHER_PROVIDER="${ACP_WEATHER_OBSERVATIONS:-ecowitt-push}"
PROJECT_USER="${ACP_PROJECT_USER:-${SUDO_USER:-${USER:-andy}}}"
PROJECT_DIR="${ACP_PROJECT_DIR:-}"
CAMILLA_BINARY="${ACP_CAMILLA_BINARY:-}"
WU_STATION_ID="${ACP_WU_STATION_ID:-}"
WU_API_KEY_FILE="${ACP_WU_API_KEY_FILE:-}"
DASHBOARD_URL="${ACP_DASHBOARD_URL:-http://localhost:8088}"

usage() {
    cat <<EOF
Usage: bash scripts/install-appliance-application.sh [options]

Guarded whole-appliance application transaction. Package/venv bootstrap is a
prerequisite baseline and is deliberately outside this transaction.

Options:
  --prepare-only
  --activate --confirm $CONFIRM_TOKEN
  --audio direct|eq
  --weather-observations ecowitt-push|weather-underground
  --project-user USER
  --project-dir PATH
  --camilladsp-binary PATH
  --wu-station-id ID
  --wu-api-key-file PATH
  --dashboard-url URL
  --root PATH          alternate filesystem root for non-production tests
  -h, --help
EOF
}

error() { printf '[A Clockwork Plex] ERROR: %s\n' "$*" >&2; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prepare-only) MODE=prepare-only; shift ;;
        --activate) MODE=activate; shift ;;
        --confirm)
            [[ $# -ge 2 ]] || { error '--confirm requires a token.'; exit 64; }
            CONFIRM="$2"; shift 2 ;;
        --audio)
            [[ $# -ge 2 ]] || { error '--audio requires a profile.'; exit 64; }
            AUDIO_PROFILE="$2"; shift 2 ;;
        --weather-observations)
            [[ $# -ge 2 ]] || { error '--weather-observations requires a provider.'; exit 64; }
            WEATHER_PROVIDER="$2"; shift 2 ;;
        --project-user)
            [[ $# -ge 2 ]] || { error '--project-user requires a user.'; exit 64; }
            PROJECT_USER="$2"; shift 2 ;;
        --project-dir)
            [[ $# -ge 2 ]] || { error '--project-dir requires a path.'; exit 64; }
            PROJECT_DIR="$2"; shift 2 ;;
        --camilladsp-binary)
            [[ $# -ge 2 ]] || { error '--camilladsp-binary requires a path.'; exit 64; }
            CAMILLA_BINARY="$2"; shift 2 ;;
        --wu-station-id)
            [[ $# -ge 2 ]] || { error '--wu-station-id requires a station ID.'; exit 64; }
            WU_STATION_ID="$2"; shift 2 ;;
        --wu-api-key-file)
            [[ $# -ge 2 ]] || { error '--wu-api-key-file requires a path.'; exit 64; }
            WU_API_KEY_FILE="$2"; shift 2 ;;
        --dashboard-url)
            [[ $# -ge 2 ]] || { error '--dashboard-url requires a URL.' >&2; exit 64; }
            DASHBOARD_URL="${2%/}"; shift 2 ;;
        --root)
            [[ $# -ge 2 ]] || { error '--root requires a path.'; exit 64; }
            ROOT="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) error "Unknown option: $1"; usage >&2; exit 64 ;;
    esac
done

case "$AUDIO_PROFILE" in direct|eq) ;; *) error "Unsupported audio profile: $AUDIO_PROFILE"; exit 64 ;; esac
case "$WEATHER_PROVIDER" in ecowitt-push|weather-underground) ;; *) error "Unsupported weather provider: $WEATHER_PROVIDER"; exit 64 ;; esac
[[ "$PROJECT_USER" =~ ^[A-Za-z_][A-Za-z0-9_.-]*$ ]] || { error "Invalid project user: $PROJECT_USER"; exit 64; }
ROOT="$(acp_normalise_root "$ROOT")" || exit 1
[[ -d "$ROOT" ]] || { error "Filesystem root does not exist: $ROOT"; exit 1; }
export ACP_ROOT="$ROOT"

if [[ -z "$PROJECT_DIR" ]]; then
    if acp_is_production_root; then
        PROJECT_DIR="$REPO_ROOT"
    else
        PROJECT_DIR=/project
    fi
fi
[[ "$PROJECT_DIR" == /* ]] || { error '--project-dir must be absolute.'; exit 64; }
PROJECT_PATH="$(acp_path "$PROJECT_DIR")" || exit 1
[[ -d "$PROJECT_PATH" && ! -L "$PROJECT_PATH" ]] || {
    error "Project directory is unavailable or unsafe: $PROJECT_PATH"
    exit 1
}

if [[ "$AUDIO_PROFILE" == eq ]]; then
    [[ -n "$CAMILLA_BINARY" ]] || { error 'EQ application install requires --camilladsp-binary PATH.'; exit 64; }
elif [[ -n "$CAMILLA_BINARY" ]]; then
    error '--camilladsp-binary is only valid with --audio eq.'
    exit 64
fi

if [[ "$WEATHER_PROVIDER" == weather-underground ]]; then
    [[ "$WU_STATION_ID" =~ ^[A-Za-z0-9_-]+$ ]] || {
        error 'Weather Underground requires --wu-station-id.'
        exit 64
    }
    if [[ "$MODE" == activate ]]; then
        [[ -n "$WU_API_KEY_FILE" ]] || { error 'Weather Underground activation requires --wu-api-key-file PATH.'; exit 64; }
    fi
elif [[ -n "$WU_STATION_ID" || -n "$WU_API_KEY_FILE" ]]; then
    error 'Weather Underground station/key options require --weather-observations weather-underground.'
    exit 64
fi

if [[ "$MODE" == activate ]]; then
    [[ "$CONFIRM" == "$CONFIRM_TOKEN" ]] || { error "Activation requires --confirm $CONFIRM_TOKEN."; exit 64; }
elif [[ -n "$CONFIRM" ]]; then
    error '--confirm is only valid with --activate.'
    exit 64
fi

if acp_is_production_root; then
    [[ "$EUID" -ne 0 ]] || { error 'Run the appliance installer as the normal project user, not as root.'; exit 1; }
    acp_require_command sudo
    [[ -z "${ACP_APPLICATION_TEST_FAIL_AFTER:-}" ]] || {
        error 'ACP_APPLICATION_TEST_FAIL_AFTER is forbidden on the production root.'
        exit 1
    }
fi

EQ_PREEXISTED=false
[[ -f "$(acp_path '/var/lib/a-clockwork-plex/split-bus/installed')" ]] && EQ_PREEXISTED=true
if [[ "$AUDIO_PROFILE" == direct && "$EQ_PREEXISTED" == true ]]; then
    error 'Direct profile switching from an already-installed EQ appliance is not enabled by this fresh/repeatable transaction yet.'
    exit 1
fi

cat <<EOF
A Clockwork Plex whole-appliance application transaction

Mode:                 $MODE
Filesystem root:      $ROOT
Project user:         $PROJECT_USER
Project directory:    $PROJECT_DIR
Audio profile:        $AUDIO_PROFILE
Weather observations: $WEATHER_PROVIDER
Package/venv baseline: already established before this transaction
EQ already installed: $EQ_PREEXISTED

Activation order:
  1. capture the complete application-managed pre-state;
  2. configure weather observations and managed secret reference;
  3. install dashboard service + kiosk integration;
  4. establish alarm-safe Direct audio when required;
  5. install/repair EQ when selected;
  6. install restricted appliance helpers;
  7. install validated AirPlay/Shairport integration;
  8. run the whole-appliance verifier as the commit gate.

Any failure before the verifier commits is rolled back. A fresh EQ install is
unwound through scripts/audio/uninstall-eq.sh before generic application state
is restored. Package additions and the verified venv remain the prerequisite
baseline by explicit policy.
EOF

if [[ "$MODE" == prepare-only ]]; then
    echo
    echo 'Prepare-only complete. No application file, service, route, mixer, PCM or configuration was changed.'
    exit 0
fi

TRANSACTION_PARENT="$(mktemp -d "${TMPDIR:-/tmp}/a-clockwork-plex-application.XXXXXX")"
TRANSACTION="$TRANSACTION_PARENT/transaction"
EQ_INSTALLED_BY_TRANSACTION=false
SUCCESS=false

cleanup() { rm -rf "$TRANSACTION_PARENT"; }
trap cleanup EXIT

acp_application_transaction_begin "$TRANSACTION" "$PROJECT_USER" "$PROJECT_DIR"

inject_failure() {
    local stage="$1"
    if ! acp_is_production_root && [[ "${ACP_APPLICATION_TEST_FAIL_AFTER:-}" == "$stage" ]]; then
        error "Injected non-production whole-appliance failure after $stage."
        return 1
    fi
}

rollback_application() {
    local failures=0 marker
    marker="$(acp_path '/var/lib/a-clockwork-plex/split-bus/installed')"
    if [[ "$EQ_INSTALLED_BY_TRANSACTION" == true && -f "$marker" ]]; then
        if ! bash "$REPO_ROOT/scripts/audio/uninstall-eq.sh" \
            --root "$ROOT" \
            --activate \
            --confirm UNINSTALL-EQ-AUDIO; then
            error 'EQ uninstall failed during whole-appliance rollback.'
            failures=$((failures + 1))
        fi
    fi
    if ! acp_application_transaction_restore "$TRANSACTION"; then
        error 'Generic application-state restoration reported a failure.'
        failures=$((failures + 1))
    fi
    [[ "$failures" -eq 0 ]]
}

fail_transaction() {
    local stage="$1"
    error "Whole-appliance application transaction failed at stage: $stage"
    if rollback_application; then
        error 'Whole-appliance managed pre-state restored.'
    else
        error 'ROLLBACK INCOMPLETE: inspect the host before retrying.'
    fi
    exit 1
}

weather_args=(
    --activate --confirm INSTALL-WEATHER-CONFIG
    --provider "$WEATHER_PROVIDER"
    --root "$ROOT"
)
if [[ "$WEATHER_PROVIDER" == weather-underground ]]; then
    weather_args+=(--wu-station-id "$WU_STATION_ID" --wu-api-key-file "$WU_API_KEY_FILE")
fi
if acp_is_production_root; then
    sudo -- bash "$REPO_ROOT/scripts/install-weather-config.sh" "${weather_args[@]}" || fail_transaction weather
else
    bash "$REPO_ROOT/scripts/install-weather-config.sh" "${weather_args[@]}" || fail_transaction weather
fi
inject_failure weather || fail_transaction weather-injection

bash "$REPO_ROOT/scripts/install-dashboard-integration.sh" \
    --activate --confirm INSTALL-DASHBOARD-INTEGRATION \
    --project-user "$PROJECT_USER" \
    --project-dir "$PROJECT_DIR" \
    --dashboard-url "$DASHBOARD_URL" \
    --root "$ROOT" || fail_transaction dashboard
inject_failure dashboard || fail_transaction dashboard-injection

if [[ "$AUDIO_PROFILE" == direct || "$EQ_PREEXISTED" == false ]]; then
    bash "$REPO_ROOT/scripts/audio/install-direct.sh" \
        --activate --confirm INSTALL-DIRECT-AUDIO \
        --root "$ROOT" || fail_transaction direct-audio
    inject_failure direct || fail_transaction direct-injection
fi

if [[ "$AUDIO_PROFILE" == eq ]]; then
    eq_args=(
        --activate --confirm INSTALL-EQ-AUDIO
        --binary "$CAMILLA_BINARY"
        --project-user "$PROJECT_USER"
        --baseline alarm-safe-direct
        --root "$ROOT"
    )
    bash "$REPO_ROOT/scripts/audio/install-eq.sh" "${eq_args[@]}" || fail_transaction eq-audio
    if [[ "$EQ_PREEXISTED" == false ]]; then
        EQ_INSTALLED_BY_TRANSACTION=true
    fi
    inject_failure eq || fail_transaction eq-injection
fi

bash "$REPO_ROOT/scripts/install-appliance-helpers.sh" \
    --activate --confirm INSTALL-APPLIANCE-HELPERS \
    --project-user "$PROJECT_USER" \
    --root "$ROOT" || fail_transaction helpers
inject_failure helpers || fail_transaction helpers-injection

bash "$REPO_ROOT/scripts/install-airplay-integration.sh" \
    --activate --confirm INSTALL-AIRPLAY-INTEGRATION \
    --project-user "$PROJECT_USER" \
    --dashboard-base "$DASHBOARD_URL" \
    --root "$ROOT" || fail_transaction airplay
inject_failure airplay || fail_transaction airplay-injection

verify_args=(
    --root "$ROOT"
    --audio "$AUDIO_PROFILE"
    --weather-observations "$WEATHER_PROVIDER"
    --project-user "$PROJECT_USER"
    --project-dir "$PROJECT_DIR"
    --config "$PROJECT_DIR/config.json"
    --dashboard-url "$DASHBOARD_URL"
)

run_final_verifier() {
    local wu_verify_key
    if [[ "$WEATHER_PROVIDER" != weather-underground ]]; then
        bash "$REPO_ROOT/scripts/verify-appliance.sh" "${verify_args[@]}"
        return
    fi

    wu_verify_key="$(python3 - "$WU_API_KEY_FILE" <<'PY'
import sys
from pathlib import Path

raw = Path(sys.argv[1]).read_bytes().rstrip(b"\r\n")
if not raw or b"\x00" in raw or b"\n" in raw or b"\r" in raw:
    raise SystemExit(1)
try:
    key = raw.decode("utf-8")
except UnicodeDecodeError:
    raise SystemExit(1)
if not key.strip():
    raise SystemExit(1)
print(key, end="")
PY
)" || return 1

    WEATHER_UNDERGROUND_API_KEY="$wu_verify_key" \
        bash "$REPO_ROOT/scripts/verify-appliance.sh" "${verify_args[@]}"
}

run_final_verifier || fail_transaction verifier
inject_failure verifier || fail_transaction verifier-injection

acp_transaction_mark_complete "$TRANSACTION"
SUCCESS=true
echo
echo '[A Clockwork Plex] Whole-appliance application transaction committed.'
echo 'APPLICATION_TRANSACTION=COMMITTED'
echo 'PACKAGE_VENV_BASELINE=RETAINED'