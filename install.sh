#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUDIO_PROFILE="${ACP_AUDIO_PROFILE:-eq}"
WEATHER_OBSERVATIONS="${ACP_WEATHER_OBSERVATIONS:-ecowitt-push}"
PROJECT_USER="${ACP_PROJECT_USER:-${SUDO_USER:-${USER:-andy}}}"
CAMILLA_BINARY="${ACP_CAMILLA_BINARY:-}"
NON_INTERACTIVE=false
MODE=plan
CONFIRM_TOKEN=
APPLY_CONFIRMATION_TOKEN=APPLY-A-CLOCKWORK-PLEX

# The legacy install-shared-audio.sh remains historical input only. The root
# appliance installer must never execute it as a competing audio authority.
#
# Phase 7 now exposes a guarded --apply boundary, but production mutation is
# intentionally refused after the matching read-only package and host/preflight
# gates. The outer transaction is not begun until package/weather/dashboard
# ownership and rollback policy are implemented and green.

usage() {
    cat <<EOF
Usage:
  bash install.sh [--audio direct|eq] [--weather-observations ecowitt-push|weather-underground]
                  [--project-user USER] [--camilladsp-binary PATH]
                  [--non-interactive] [--plan]
  bash install.sh --apply --confirm $APPLY_CONFIRMATION_TOKEN [profile options]

Current Phase 7 modes:
  --plan                           print the read-only installation plan (default)
  --apply                          repeat matching read-only package/preflight gates,
                                   then fail closed before any production mutation
  --confirm TOKEN                  required with --apply; expected token:
                                   $APPLY_CONFIRMATION_TOKEN

Profile options:
  --audio PROFILE                  direct or eq (default: eq)
  --weather-observations PROVIDER  ecowitt-push or weather-underground
  --project-user USER              normal appliance account (default: invoking user)
  --camilladsp-binary PATH         verified CamillaDSP 4.1.3 binary for EQ --apply
  --non-interactive                require all future choices from arguments/env
  -h, --help                       show this help

The guarded --apply boundary does not yet install packages, files, services,
audio routes, weather configuration, dashboard startup or any other appliance
state. A successful gate run exits non-zero with MUTATION_BLOCKED until the
remaining Phase 7 mutation owners and rollback policy are complete.
EOF
}

fail() {
    printf 'A Clockwork Plex installer: %s\n' "$*" >&2
    exit 2
}

blocked() {
    printf 'A Clockwork Plex installer: %s\n' "$*" >&2
    exit 3
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

if [[ "$MODE" == apply ]]; then
    [[ "$CONFIRM_TOKEN" == "$APPLY_CONFIRMATION_TOKEN" ]] || {
        fail "--apply requires --confirm $APPLY_CONFIRMATION_TOKEN"
    }
    if [[ "$AUDIO_PROFILE" == eq && -z "$CAMILLA_BINARY" ]]; then
        fail "EQ --apply requires --camilladsp-binary PATH (or ACP_CAMILLA_BINARY)"
    fi
elif [[ -n "$CONFIRM_TOKEN" ]]; then
    fail "--confirm is only valid with --apply"
fi

required_sources=(
    "$REPO_ROOT/scripts/install-dashboard-service.sh"
    "$REPO_ROOT/scripts/install-dashboard-kiosk.sh"
    "$REPO_ROOT/scripts/install-airplay-hooks.sh"
    "$REPO_ROOT/scripts/install-airplay-metadata-listener.sh"
    "$REPO_ROOT/scripts/install-alarm-audio-helper.sh"
    "$REPO_ROOT/scripts/install-shairport-name-helper.sh"
    "$REPO_ROOT/scripts/install-appliance-helpers.sh"
    "$REPO_ROOT/scripts/install-airplay-integration.sh"
    "$REPO_ROOT/scripts/check-appliance-components.sh"
    "$REPO_ROOT/scripts/check-appliance-packages.sh"
    "$REPO_ROOT/scripts/preflight-appliance.sh"
    "$REPO_ROOT/scripts/verify-appliance.sh"
    "$REPO_ROOT/scripts/audio/install-direct.sh"
    "$REPO_ROOT/scripts/audio/install-eq.sh"
    "$REPO_ROOT/scripts/audio/verify-audio.sh"
    "$REPO_ROOT/installer/lib/components.sh"
    "$REPO_ROOT/installer/lib/packages.sh"
    "$REPO_ROOT/installer/lib/prerequisites.sh"
    "$REPO_ROOT/installer/lib/direct_audio.sh"
    "$REPO_ROOT/installer/lib/transaction.sh"
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
# shellcheck source=installer/lib/transaction.sh
source "$REPO_ROOT/installer/lib/transaction.sh"

acp_verify_component_sources || fail "Appliance component source validation failed"
acp_verify_direct_audio_sources || fail "Direct-audio component source validation failed"
declare -F acp_transaction_begin >/dev/null || fail "Whole-appliance transaction boundary is unavailable"
declare -F acp_transaction_restore_paths >/dev/null || fail "Whole-appliance transaction rollback is unavailable"

if [[ "$MODE" == apply ]]; then
    DISPLAY_MODE='guarded apply gates only (mutation blocked)'
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

Planned orchestration boundary:
  1. validate Raspberry Pi OS, project user, packages and hardware prerequisites;
  2. install/verify the A Clockwork Plex application and dashboard service;
  3. install Shairport Sync integration, lifecycle hooks and metadata listener;
  4. install alarm-audio and managed Shairport-name helpers;
  5. configure one supported audio profile;
  6. configure one weather-observation provider while retaining Open-Meteo forecast;
  7. install/verify dashboard kiosk startup;
  8. run one appliance-level post-install verification report.
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
  EQ-capable audio will call scripts/audio/install-eq.sh and its accepted
  verifier/repair lifecycle. The top-level installer will not copy that logic.

  Fresh-appliance EQ will explicitly request:
    --baseline alarm-safe-direct

  That first-install selector validates the physically proven alarm-safe Direct
  SHA before capture, while the standalone script still defaults to the exact
  historical Phase 6 direct baseline. Uninstall continues to restore the exact
  route actually captured before EQ activation, so the existing bedroom-Pi
  rollback guarantee is not weakened.
EOF
else
    echo
    acp_direct_audio_plan
fi

if [[ "$WEATHER_OBSERVATIONS" == weather-underground ]]; then
    cat <<'EOF'

Weather component:
  Current outdoor observations will be pulled from the configured Weather
  Underground PWS station using an API key supplied outside config.json.
  Open-Meteo remains the forecast provider. Pressure-history bootstrap is a
  separate acceptance item and is not claimed by this guarded skeleton.
EOF
else
    cat <<'EOF'

Weather component:
  This appliance will retain the current Ecowitt custom-push observation path.
  Open-Meteo remains the forecast provider.
EOF
fi

if [[ "$MODE" == plan ]]; then
    cat <<EOF

Before guarded --apply can cross into mutation, it repeats the matching read-only gates:
  bash scripts/check-appliance-packages.sh --audio $AUDIO_PROFILE --weather-observations $WEATHER_OBSERVATIONS
  bash scripts/preflight-appliance.sh --audio $AUDIO_PROFILE --weather-observations $WEATHER_OBSERVATIONS --project-user $PROJECT_USER

After a future guarded installation, the selected profile must pass:
  bash scripts/verify-appliance.sh --audio $AUDIO_PROFILE --weather-observations $WEATHER_OBSERVATIONS --project-user $PROJECT_USER

No production file, package, service, route, mixer, PCM or configuration was changed.
EOF
    exit 0
fi

echo
echo 'Guarded --apply: repeating matching read-only pre-mutation gates now.'
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

cat <<'EOF'

Guarded --apply read-only gates passed.
Outer transaction boundary: READY, NOT STARTED.
Guarded specialist owners behind that boundary:
  scripts/audio/install-direct.sh
  scripts/audio/install-eq.sh
  scripts/install-appliance-helpers.sh
  scripts/install-airplay-integration.sh

No specialist --activate path was invoked and acp_transaction_begin was not
called. Package/venv rollback ownership and weather/dashboard mutation remain
unfinished Phase 7 gates, so production mutation is intentionally refused.
MUTATION_BLOCKED=PACKAGE-WEATHER-DASHBOARD-STAGES-INCOMPLETE
No production file, package, service, route, mixer, PCM or configuration was changed.
EOF

blocked "guarded --apply gates passed, but Phase 7 mutation ownership is incomplete"
