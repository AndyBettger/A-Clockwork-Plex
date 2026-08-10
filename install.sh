#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUDIO_PROFILE="${ACP_AUDIO_PROFILE:-eq}"
WEATHER_OBSERVATIONS="${ACP_WEATHER_OBSERVATIONS:-ecowitt-push}"
NON_INTERACTIVE=false
MODE=plan

# The legacy install-shared-audio.sh remains historical input only. The root
# appliance installer must never execute it as a competing audio authority.

usage() {
    cat <<'EOF'
Usage:
  bash install.sh [--audio direct|eq] [--weather-observations ecowitt-push|weather-underground]
                  [--non-interactive] [--plan]

Phase 7 currently implements a read-only installation plan only. It does not
change files, packages, services, audio routes or application configuration.

Options:
  --audio PROFILE                  direct or eq (default: eq)
  --weather-observations PROVIDER  ecowitt-push or weather-underground
  --non-interactive                require all future choices from arguments/env
  --plan                           print the installation plan (current default)
  -h, --help                       show this help
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
        --non-interactive)
            NON_INTERACTIVE=true
            shift
            ;;
        --plan)
            MODE=plan
            shift
            ;;
        --apply)
            fail "--apply is not implemented yet; Phase 7 is still plan-only"
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

[[ "$MODE" == plan ]] || fail "unsupported installer mode: $MODE"

required_sources=(
    "$REPO_ROOT/scripts/install-dashboard-service.sh"
    "$REPO_ROOT/scripts/install-dashboard-kiosk.sh"
    "$REPO_ROOT/scripts/install-airplay-hooks.sh"
    "$REPO_ROOT/scripts/install-airplay-metadata-listener.sh"
    "$REPO_ROOT/scripts/install-alarm-audio-helper.sh"
    "$REPO_ROOT/scripts/install-shairport-name-helper.sh"
    "$REPO_ROOT/scripts/check-appliance-components.sh"
    "$REPO_ROOT/scripts/audio/install-eq.sh"
    "$REPO_ROOT/scripts/audio/verify-audio.sh"
    "$REPO_ROOT/installer/lib/components.sh"
    "$REPO_ROOT/installer/lib/direct_audio.sh"
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
# shellcheck source=installer/lib/direct_audio.sh
source "$REPO_ROOT/installer/lib/direct_audio.sh"
acp_verify_component_sources || fail "Appliance component source validation failed"
acp_verify_direct_audio_sources || fail "Direct-audio component source validation failed"

cat <<EOF
A Clockwork Plex appliance installation plan

Mode:                 read-only plan
Repository:           $REPO_ROOT
Audio profile:        $AUDIO_PROFILE
Weather observations: $WEATHER_OBSERVATIONS
Forecast provider:    open-meteo (retained)
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
acp_component_plan

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
  separate acceptance item and is not claimed by this plan-only skeleton.
EOF
else
    cat <<'EOF'

Weather component:
  This appliance will retain the current Ecowitt custom-push observation path.
  Open-Meteo remains the forecast provider.
EOF
fi

cat <<'EOF'

No production file, package, service, route, mixer, PCM or configuration was changed.
EOF
