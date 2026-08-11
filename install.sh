#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUDIO_PROFILE="${ACP_AUDIO_PROFILE:-eq}"
WEATHER_OBSERVATIONS="${ACP_WEATHER_OBSERVATIONS:-ecowitt-push}"
PROJECT_USER="${ACP_PROJECT_USER:-${SUDO_USER:-${USER:-andy}}}"
CAMILLA_BINARY="${ACP_CAMILLA_BINARY:-}"
WU_STATION_ID="${ACP_WU_STATION_ID:-}"
WU_API_KEY_FILE="${ACP_WU_API_KEY_FILE:-}"
DASHBOARD_URL="${ACP_DASHBOARD_URL:-http://localhost:8088}"
NON_INTERACTIVE=false
MODE=plan
CONFIRM_TOKEN=
APPLY_CONFIRMATION_TOKEN=APPLY-A-CLOCKWORK-PLEX

# The legacy install-shared-audio.sh remains historical input only. The root
# appliance installer must never execute it as a competing audio authority.
#
# Package/venv bootstrap is an additive prerequisite baseline. Application
# mutation is delegated to one guarded transaction owner, which contains the
# final appliance verifier inside its commit boundary.

usage() {
    cat <<EOF
Usage:
  bash install.sh [--audio direct|eq] [--weather-observations ecowitt-push|weather-underground]
                  [--project-user USER] [--camilladsp-binary PATH]
                  [--wu-station-id ID] [--wu-api-key-file PATH]
                  [--dashboard-url URL] [--non-interactive] [--plan]
  bash install.sh --apply --confirm $APPLY_CONFIRMATION_TOKEN [profile options]

Modes:
  --plan                           print the read-only installation plan (default)
  --apply                          repeat matching read-only gates, establish the
                                   guarded package/venv prerequisite baseline,
                                   then run one guarded application transaction
  --confirm TOKEN                  required with --apply; expected token:
                                   $APPLY_CONFIRMATION_TOKEN

Profile options:
  --audio PROFILE                  direct or eq (default: eq)
  --weather-observations PROVIDER  ecowitt-push or weather-underground
  --project-user USER              normal appliance account (default: invoking user)
  --camilladsp-binary PATH         verified CamillaDSP 4.1.3 binary for EQ --apply
  --wu-station-id ID               Weather Underground PWS station ID
  --wu-api-key-file PATH           Weather Underground API-key file; secret value is
                                   never accepted as a literal installer argument
  --dashboard-url URL              local dashboard base URL (default: $DASHBOARD_URL)
  --non-interactive                require all choices from arguments/env
  -h, --help                       show this help

Rollback policy:
  * successfully installed APT prerequisites and the verified venv form the
    prerequisite baseline and are retained after a later application failure;
  * application-managed files, FIFO and service state are captured before
    application mutation and restored on failure;
  * a fresh EQ install is unwound through the accepted EQ uninstaller before
    generic application-state restoration;
  * scripts/verify-appliance.sh must pass before the application transaction commits.
EOF
}

fail() {
    printf 'A Clockwork Plex installer: %s\n' "$*" >&2
    exit 2
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --audio)
            [[ $# -ge 2 ]] || fail "--audio requires direct or eq"
            AUDIO_PROFILE="$2"
            shift 2
            ;;
        --weather-observations)
            [[ $# -ge 2 ]] || fail "--weather-observations requires a provider"
            WEATHER_OBSERVATIONS="$2"
            shift 2
            ;;
        --project-user)
            [[ $# -ge 2 ]] || fail "--project-user requires a user"
            PROJECT_USER="$2"
            shift 2
            ;;
        --camilladsp-binary)
            [[ $# -ge 2 ]] || fail "--camilladsp-binary requires a path"
            CAMILLA_BINARY="$2"
            shift 2
            ;;
        --wu-station-id)
            [[ $# -ge 2 ]] || fail "--wu-station-id requires an ID"
            WU_STATION_ID="$2"
            shift 2
            ;;
        --wu-api-key-file)
            [[ $# -ge 2 ]] || fail "--wu-api-key-file requires a path"
            WU_API_KEY_FILE="$2"
            shift 2
            ;;
        --dashboard-url)
            [[ $# -ge 2 ]] || fail "--dashboard-url requires a URL"
            DASHBOARD_URL="${2%/}"
            shift 2
            ;;
        --non-interactive)
            NON_INTERACTIVE=true
            shift
            ;;
        --plan)
            MODE=plan
            shift
            ;;
        --apply)
            MODE=apply
            shift
            ;;
        --confirm)
            [[ $# -ge 2 ]] || fail "--confirm requires a token"
            CONFIRM_TOKEN="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fail "unknown argument: $1"
            ;;
    esac
done

case "$AUDIO_PROFILE" in
    direct|eq) ;;
    *) fail "unsupported audio profile '$AUDIO_PROFILE' (use direct or eq)" ;;
esac

case "$WEATHER_OBSERVATIONS" in
    ecowitt-push|weather-underground) ;;
    *)
        fail "unsupported weather observation provider '$WEATHER_OBSERVATIONS' (use ecowitt-push or weather-underground)"
        ;;
esac

[[ "$PROJECT_USER" =~ ^[A-Za-z_][A-Za-z0-9_.-]*$ ]] || fail "invalid project user '$PROJECT_USER'"
[[ "$DASHBOARD_URL" =~ ^https?://[^[:space:]\"\'\`\\]+$ ]] || fail "invalid dashboard URL '$DASHBOARD_URL'"

if [[ "$WEATHER_OBSERVATIONS" == weather-underground ]]; then
    if [[ -n "$WU_STATION_ID" ]]; then
        [[ "$WU_STATION_ID" =~ ^[A-Za-z0-9_-]+$ ]] || fail "invalid Weather Underground station ID"
    fi
else
    [[ -z "$WU_STATION_ID" && -z "$WU_API_KEY_FILE" ]] || {
        fail "Weather Underground station/key options require --weather-observations weather-underground"
    }
fi

if [[ "$MODE" == apply ]]; then
    [[ "$CONFIRM_TOKEN" == "$APPLY_CONFIRMATION_TOKEN" ]] || {
        fail "--apply requires --confirm $APPLY_CONFIRMATION_TOKEN"
    }
    [[ "${EUID}" -ne 0 ]] || fail "run --apply as the normal project user, not as root"
    if [[ "$AUDIO_PROFILE" == eq && -z "$CAMILLA_BINARY" ]]; then
        fail "EQ --apply requires --camilladsp-binary PATH (or ACP_CAMILLA_BINARY)"
    fi
    if [[ "$WEATHER_OBSERVATIONS" == weather-underground ]]; then
        [[ -n "$WU_STATION_ID" ]] || fail "Weather Underground --apply requires --wu-station-id ID"
        [[ -n "$WU_API_KEY_FILE" ]] || fail "Weather Underground --apply requires --wu-api-key-file PATH"
        [[ -f "$WU_API_KEY_FILE" && ! -L "$WU_API_KEY_FILE" && -r "$WU_API_KEY_FILE" ]] || {
            fail "Weather Underground API-key file must be a readable regular file, not a symlink"
        }
    fi
elif [[ -n "$CONFIRM_TOKEN" ]]; then
    fail "--confirm is only valid with --apply"
fi

required_sources=(
    "$REPO_ROOT/scripts/install-dashboard-integration.sh"
    "$REPO_ROOT/scripts/install-weather-config.sh"
    "$REPO_ROOT/scripts/install-appliance-packages.sh"
    "$REPO_ROOT/scripts/install-appliance-application.sh"
    "$REPO_ROOT/scripts/install-appliance-helpers.sh"
    "$REPO_ROOT/scripts/install-airplay-integration.sh"
    "$REPO_ROOT/scripts/check-appliance-components.sh"
    "$REPO_ROOT/scripts/check-appliance-packages.sh"
    "$REPO_ROOT/scripts/preflight-appliance.sh"
    "$REPO_ROOT/scripts/verify-appliance.sh"
    "$REPO_ROOT/scripts/audio/install-direct.sh"
    "$REPO_ROOT/scripts/audio/install-eq.sh"
    "$REPO_ROOT/scripts/audio/uninstall-eq.sh"
    "$REPO_ROOT/scripts/audio/verify-audio.sh"
    "$REPO_ROOT/installer/lib/components.sh"
    "$REPO_ROOT/installer/lib/packages.sh"
    "$REPO_ROOT/installer/lib/prerequisites.sh"
    "$REPO_ROOT/installer/lib/direct_audio.sh"
    "$REPO_ROOT/installer/lib/transaction.sh"
    "$REPO_ROOT/installer/lib/application_transaction.sh"
    "$REPO_ROOT/installer/profiles/direct/alarm-safe.conf"
)

missing=0
for source in "${required_sources[@]}"; do
    if [[ ! -f "$source" ]]; then
        printf 'MISSING: %s\n' "${source#"$REPO_ROOT/"}" >&2
        missing=$((missing + 1))
    fi
done
[[ "$missing" -eq 0 ]] || fail "$missing required component source(s) are missing"

ACP_REPO_ROOT="$REPO_ROOT"
# shellcheck source=installer/lib/components.sh
source "$REPO_ROOT/installer/lib/components.sh"
# shellcheck source=installer/lib/packages.sh
source "$REPO_ROOT/installer/lib/packages.sh"
# shellcheck source=installer/lib/prerequisites.sh
source "$REPO_ROOT/installer/lib/prerequisites.sh"
# shellcheck source=installer/lib/direct_audio.sh
source "$REPO_ROOT/installer/lib/direct_audio.sh"

acp_verify_component_sources || fail "Appliance component source validation failed"
acp_verify_direct_audio_sources || fail "Direct-audio component source validation failed"

if [[ "$MODE" == apply ]]; then
    DISPLAY_MODE='guarded apply'
else
    DISPLAY_MODE='read-only plan'
fi

cat <<EOF
A Clockwork Plex appliance installation plan

Mode:                 $DISPLAY_MODE
Repository:           $REPO_ROOT
Audio profile:        $AUDIO_PROFILE
Weather observations: $WEATHER_OBSERVATIONS
Forecast provider:    open-meteo (retained)
Project user:         $PROJECT_USER
Non-interactive:      $NON_INTERACTIVE

Supported orchestration:
  1. validate package/artifact and Raspberry Pi host prerequisites read-only;
  2. establish the additive package + verified-venv prerequisite baseline;
  3. capture the complete application-managed pre-state;
  4. configure the selected weather-observation provider;
  5. install dashboard service + kiosk integration;
  6. establish the selected Direct/EQ audio profile;
  7. install restricted appliance helpers and validated AirPlay integration;
  8. run one read-only appliance verifier inside the application commit boundary.
EOF

echo
acp_prerequisite_plan "$AUDIO_PROFILE" "$WEATHER_OBSERVATIONS" "$PROJECT_USER"
echo
acp_package_plan "$AUDIO_PROFILE" "$WEATHER_OBSERVATIONS"
echo
acp_component_plan "$PROJECT_USER"

if [[ "$AUDIO_PROFILE" == eq ]]; then
    cat <<'EOF'

Audio component:
  EQ-capable audio delegates to scripts/audio/install-eq.sh and its accepted
  verifier/repair/uninstall lifecycle. The top-level installer does not copy
  that logic.

  Fresh-appliance EQ will explicitly request:
    --baseline alarm-safe-direct

  Rollback unwinds a newly installed EQ through the accepted EQ uninstaller
  before restoring the outer generic application state.
EOF
else
    echo
    acp_direct_audio_plan
fi

if [[ "$WEATHER_OBSERVATIONS" == weather-underground ]]; then
    cat <<'EOF'

Weather component:
  Current outdoor observations are pulled from the selected Weather Underground
  PWS. Station ID is ordinary configuration; API key supplied outside config.json
  through a key-file path is stored only in the managed root-readable environment
  file. Open-Meteo remains the forecast provider. No literal API secret is stored
  in config.json or browser state.
EOF
else
    cat <<'EOF'

Weather component:
  This appliance retains the Ecowitt custom-push observation path.
  Open-Meteo remains the forecast provider.
EOF
fi

if [[ "$MODE" == plan ]]; then
    cat <<EOF

Guarded --apply first repeats these matching read-only gates:
  bash scripts/check-appliance-packages.sh --audio $AUDIO_PROFILE --weather-observations $WEATHER_OBSERVATIONS
  bash scripts/preflight-appliance.sh --audio $AUDIO_PROFILE --weather-observations $WEATHER_OBSERVATIONS --project-user $PROJECT_USER

Then it establishes the prerequisite baseline through:
  bash scripts/install-appliance-packages.sh --activate --confirm INSTALL-APPLIANCE-PACKAGES --audio $AUDIO_PROFILE --weather-observations $WEATHER_OBSERVATIONS

Application mutation is delegated intact to:
  bash scripts/install-appliance-application.sh --activate --confirm INSTALL-APPLIANCE-APPLICATION --audio $AUDIO_PROFILE --weather-observations $WEATHER_OBSERVATIONS --project-user $PROJECT_USER

Commit gate inside that application transaction:
  bash scripts/verify-appliance.sh --audio $AUDIO_PROFILE --weather-observations $WEATHER_OBSERVATIONS --project-user $PROJECT_USER

The application owner captures rollback state before mutation and the verifier
must pass before its transaction can commit.

No production file, package, service, route, mixer, PCM or configuration was changed.
EOF
    exit 0
fi

echo
echo 'Guarded --apply: repeating matching read-only pre-mutation gates.'
bash "$REPO_ROOT/scripts/check-appliance-packages.sh" \
    --audio "$AUDIO_PROFILE" \
    --weather-observations "$WEATHER_OBSERVATIONS" \
    || fail "package/artifact gate failed; no mutation was attempted"

preflight_args=(
    --audio "$AUDIO_PROFILE"
    --weather-observations "$WEATHER_OBSERVATIONS"
    --project-user "$PROJECT_USER"
)
if [[ "$AUDIO_PROFILE" == eq ]]; then
    preflight_args+=(--binary "$CAMILLA_BINARY")
fi

bash "$REPO_ROOT/scripts/preflight-appliance.sh" "${preflight_args[@]}" \
    || fail "appliance host/preflight gate failed; no mutation was attempted"

echo
echo 'Read-only gates passed. Establishing guarded package/venv prerequisite baseline.'
bash "$REPO_ROOT/scripts/install-appliance-packages.sh" \
    --activate \
    --confirm INSTALL-APPLIANCE-PACKAGES \
    --audio "$AUDIO_PROFILE" \
    --weather-observations "$WEATHER_OBSERVATIONS" \
    || fail "package/venv prerequisite baseline failed; application transaction was not started"

application_args=(
    --activate
    --confirm INSTALL-APPLIANCE-APPLICATION
    --audio "$AUDIO_PROFILE"
    --weather-observations "$WEATHER_OBSERVATIONS"
    --project-user "$PROJECT_USER"
    --project-dir "$REPO_ROOT"
    --dashboard-url "$DASHBOARD_URL"
)
if [[ "$AUDIO_PROFILE" == eq ]]; then
    application_args+=(--camilladsp-binary "$CAMILLA_BINARY")
fi
if [[ "$WEATHER_OBSERVATIONS" == weather-underground ]]; then
    application_args+=(
        --wu-station-id "$WU_STATION_ID"
        --wu-api-key-file "$WU_API_KEY_FILE"
    )
fi

echo
echo 'Package/venv baseline verified. Starting one guarded application transaction.'
if ! bash "$REPO_ROOT/scripts/install-appliance-application.sh" "${application_args[@]}"; then
    fail "whole-appliance application transaction failed; package/venv prerequisite baseline was retained by policy"
fi

cat <<'EOF'

A Clockwork Plex guarded appliance installation completed successfully.
ROOT_INSTALL=COMMITTED
PACKAGE_VENV_BASELINE=RETAINED
APPLICATION_VERIFY=PASS
EOF
