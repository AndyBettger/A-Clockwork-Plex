#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUDIO_PROFILE="${ACP_AUDIO_PROFILE:-eq}"
if [[ -n "${ACP_WEATHER_OBSERVATIONS:-}" ]]; then
    WEATHER_OBSERVATIONS="$ACP_WEATHER_OBSERVATIONS"
    WEATHER_OBSERVATIONS_EXPLICIT=true
else
    WEATHER_OBSERVATIONS=ecowitt-push
    WEATHER_OBSERVATIONS_EXPLICIT=false
fi
PRESERVE_WEATHER_OBSERVATIONS="${ACP_PRESERVE_WEATHER_OBSERVATIONS:-false}"
PROJECT_USER="${ACP_PROJECT_USER:-${SUDO_USER:-${USER:-andy}}}"
CAMILLA_BINARY="${ACP_CAMILLA_BINARY:-}"
WU_STATION_ID="${ACP_WU_STATION_ID:-}"
WU_API_KEY_FILE="${ACP_WU_API_KEY_FILE:-}"
DASHBOARD_URL="${ACP_DASHBOARD_URL:-http://localhost:8088}"
NON_INTERACTIVE=false
FRESH_BOOTSTRAP=false
MODE=plan
CONFIRM_TOKEN=
APPLY_CONFIRMATION_TOKEN=APPLY-A-CLOCKWORK-PLEX

# The legacy install-shared-audio.sh remains historical input only. The root
# appliance installer must never execute it as a competing audio authority.
#
# Package/main/NFC-venv bootstrap is an additive prerequisite baseline.
# Application mutation is delegated to one guarded transaction owner, which
# contains the final appliance verifier inside its commit boundary.
#
# --fresh-bootstrap is the supported staged fresh-appliance route. The existing
# compatibility --apply route remains available and is not weakened.

usage() {
    cat <<EOF
Usage:
  bash appliance-installer.sh [--audio direct|eq] [--weather-observations ecowitt-push|weather-underground]
                  [--project-user USER] [--camilladsp-binary PATH]
                  [--wu-station-id ID] [--wu-api-key-file PATH]
                  [--dashboard-url URL] [--non-interactive] [--fresh-bootstrap] [--plan]
  bash appliance-installer.sh --apply --confirm $APPLY_CONFIRMATION_TOKEN [profile options]

Modes:
  --plan                           print the read-only installation plan (default)
  --apply                          run the selected guarded installation route
  --fresh-bootstrap                opt into staged fresh-Raspberry-Pi bootstrap:
                                   package/venv -> hardware -> player -> NFC ->
                                   full preflight -> application transaction.
                                   This route fails closed at any unready or
                                   unvalidated hardware/player boundary.
  --confirm TOKEN                  required with --apply; expected token:
                                   $APPLY_CONFIRMATION_TOKEN

Profile options:
  --audio PROFILE                  direct or eq (default: eq)
  --weather-observations PROVIDER  ecowitt-push or weather-underground
  --preserve-weather-observations  preserve the commissioned provider/credential;
                                   intended for repeat setup orchestration
  --project-user USER              normal appliance account (default: invoking user)
  --camilladsp-binary PATH         verified CamillaDSP 4.1.3 binary for EQ --apply
  --wu-station-id ID               Weather Underground PWS station ID
  --wu-api-key-file PATH           Weather Underground API-key file; secret value is
                                   never accepted as a literal installer argument
  --dashboard-url URL              local dashboard base URL (default: $DASHBOARD_URL)
  --non-interactive                require all choices from arguments/env
  -h, --help                       show this help

Rollback / bootstrap policy:
  * successfully installed additive APT prerequisites and the verified paired
    main/NFC venvs form a prerequisite baseline and are retained after later failure;
  * fresh hardware bootstrap may require an operator-controlled reboot and prints
    a deterministic appliance-installer resume command; it never reboots automatically;
  * fresh bootstrap stops before application mutation if exact DAC commissioning
    or pinned Plexamp runtime ownership is not ready;
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
            WEATHER_OBSERVATIONS_EXPLICIT=true
            shift 2
            ;;
        --preserve-weather-observations)
            PRESERVE_WEATHER_OBSERVATIONS=true
            shift
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
        --fresh-bootstrap)
            FRESH_BOOTSTRAP=true
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

case "$PRESERVE_WEATHER_OBSERVATIONS" in
    true|false) ;;
    *) fail "ACP_PRESERVE_WEATHER_OBSERVATIONS must be true or false" ;;
esac
if [[ "$PRESERVE_WEATHER_OBSERVATIONS" == true ]]; then
    [[ "$WEATHER_OBSERVATIONS_EXPLICIT" == false ]] || fail "--preserve-weather-observations cannot be combined with an explicit weather provider"
    [[ -z "$WU_STATION_ID" && -z "$WU_API_KEY_FILE" ]] || fail "Weather Underground station/key options cannot be combined with commissioned Weather preservation"
    CONFIG_FILE="$REPO_ROOT/config.json"
    [[ -f "$CONFIG_FILE" && ! -L "$CONFIG_FILE" ]] || fail "commissioned Weather preservation requires a safe existing config.json"
    command -v python3 >/dev/null 2>&1 || fail "commissioned Weather preservation requires python3"
    configured_weather_provider="$(python3 - "$CONFIG_FILE" <<'PYCFG'
import json
import sys
from pathlib import Path

try:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except (OSError, UnicodeError, json.JSONDecodeError):
    raise SystemExit(1)
provider = data.get("weather", {}).get("provider")
if provider not in {"ecowitt_push", "weather_underground"}:
    raise SystemExit(1)
print(provider)
PYCFG
    )" || fail "could not resolve the commissioned Weather provider from config.json"
    case "$configured_weather_provider" in
        ecowitt_push) WEATHER_OBSERVATIONS=ecowitt-push ;;
        weather_underground) WEATHER_OBSERVATIONS=weather-underground ;;
    esac
fi
export ACP_PRESERVE_WEATHER_OBSERVATIONS="$PRESERVE_WEATHER_OBSERVATIONS"

case "$WEATHER_OBSERVATIONS" in
    ecowitt-push|weather-underground) ;;
    *)
        fail "unsupported weather observation provider '$WEATHER_OBSERVATIONS' (use ecowitt-push or weather-underground)"
        ;;
esac

[[ "$PROJECT_USER" =~ ^[A-Za-z_][A-Za-z0-9_.-]*$ ]] || fail "invalid project user '$PROJECT_USER'"
[[ "$DASHBOARD_URL" =~ ^https?://[^[:space:]\"\'\`\\]+$ ]] || fail "invalid dashboard URL '$DASHBOARD_URL'"

if [[ "$PRESERVE_WEATHER_OBSERVATIONS" != true && "$WEATHER_OBSERVATIONS" == weather-underground ]]; then
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
    if [[ "$PRESERVE_WEATHER_OBSERVATIONS" != true && "$WEATHER_OBSERVATIONS" == weather-underground ]]; then
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
    "$REPO_ROOT/scripts/install-platform-hardware.sh"
    "$REPO_ROOT/scripts/install-plexamp-runtime.sh"
    "$REPO_ROOT/scripts/install-nfc-listener.sh"
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
    "$REPO_ROOT/installer/lib/platform_hardware.sh"
    "$REPO_ROOT/installer/lib/plexamp_runtime.sh"
    "$REPO_ROOT/installer/lib/direct_audio.sh"
    "$REPO_ROOT/installer/lib/transaction.sh"
    "$REPO_ROOT/installer/lib/application_transaction.sh"
    "$REPO_ROOT/installer/profiles/direct/alarm-safe.conf"
    "$REPO_ROOT/vendor/plexamp-nfc-listener/SOURCE.md"
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
# shellcheck source=installer/lib/platform_hardware.sh
source "$REPO_ROOT/installer/lib/platform_hardware.sh"
# shellcheck source=installer/lib/plexamp_runtime.sh
source "$REPO_ROOT/installer/lib/plexamp_runtime.sh"
# shellcheck source=installer/lib/direct_audio.sh
source "$REPO_ROOT/installer/lib/direct_audio.sh"

acp_verify_component_sources || fail "Appliance component source validation failed"
acp_verify_direct_audio_sources || fail "Direct-audio component source validation failed"

if [[ "$MODE" == apply ]]; then
    if [[ "$FRESH_BOOTSTRAP" == true ]]; then
        DISPLAY_MODE='guarded fresh bootstrap apply'
    else
        DISPLAY_MODE='guarded compatibility apply'
    fi
else
    DISPLAY_MODE='read-only plan'
fi

cat <<EOF
A Clockwork Plex appliance installation plan

Mode:                 $DISPLAY_MODE
Repository:           $REPO_ROOT
Audio profile:        $AUDIO_PROFILE
Weather observations: $WEATHER_OBSERVATIONS
Weather mutation:     $(if [[ "$PRESERVE_WEATHER_OBSERVATIONS" == true ]]; then echo preserve-commissioned-profile; else echo converge-selected-profile; fi)
Forecast provider:    open-meteo (retained)
Project user:         $PROJECT_USER
Fresh bootstrap:      $FRESH_BOOTSTRAP
Non-interactive:      $NON_INTERACTIVE
EOF

if [[ "$FRESH_BOOTSTRAP" == true ]]; then
    cat <<'EOF'

Fresh-bootstrap orchestration target:
  1. package/artifact availability + fresh stage-zero read-only gate;
  2. additive package + paired main/NFC venv prerequisite baseline;
  3. guarded Pi hardware commissioning (I2C/PN532/DAC, explicit reboot/resume);
  4. post-hardware/player-pending read-only gate;
  5. guarded pinned Plexamp compatibility runtime;
  6. guarded pinned NFC listener service;
  7. full host preflight with package/hardware/player requirements now mandatory;
  8. one guarded whole-application transaction;
  9. final read-only appliance verifier inside the application commit boundary.

The staged route is allowed to stop at explicit bootstrap blockers. It never treats
an unexpected DAC identity or unverified Plexamp artifact as success and never falls
through to application mutation after a blocked bootstrap owner.
EOF
else
    cat <<'EOF'

Compatibility orchestration:
  1. validate package/artifact availability plus existing platform/external prerequisites read-only;
  2. establish the additive package + paired verified-venv prerequisite baseline;
  3. repeat full host preflight with every package-owned prerequisite now required;
  4. capture the complete application-managed pre-state;
  5. configure the selected weather-observation provider;
  6. install dashboard service + kiosk integration;
  7. establish the selected Direct/EQ audio profile;
  8. install restricted appliance helpers and validated AirPlay integration;
  9. run one read-only appliance verifier inside the application commit boundary.
EOF
fi

echo
acp_prerequisite_plan "$AUDIO_PROFILE" "$WEATHER_OBSERVATIONS" "$PROJECT_USER"
echo
acp_package_plan "$AUDIO_PROFILE" "$WEATHER_OBSERVATIONS"
if [[ "$FRESH_BOOTSTRAP" == true ]]; then
    echo
    acp_platform_hardware_plan "$PROJECT_USER"
    echo
    acp_plexamp_runtime_plan "$PROJECT_USER"
fi
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

if [[ "$PRESERVE_WEATHER_OBSERVATIONS" == true ]]; then
    cat <<EOF

Weather component:
  Repeat-run preservation is active. The commissioned $WEATHER_OBSERVATIONS provider
  and its managed credential/configuration are verified but are not rewritten.
  Open-Meteo remains the forecast provider.
EOF
elif [[ "$WEATHER_OBSERVATIONS" == weather-underground ]]; then
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
    if [[ "$FRESH_BOOTSTRAP" == true ]]; then
        cat <<EOF

Guarded --fresh-bootstrap --apply uses these gates/owners in order:
  1. bash scripts/check-appliance-packages.sh --audio $AUDIO_PROFILE --weather-observations $WEATHER_OBSERVATIONS
  2. bash scripts/preflight-appliance.sh --fresh-bootstrap-pending --audio $AUDIO_PROFILE --weather-observations $WEATHER_OBSERVATIONS --project-user $PROJECT_USER
  3. bash scripts/install-appliance-packages.sh --activate --confirm INSTALL-APPLIANCE-PACKAGES --audio $AUDIO_PROFILE --weather-observations $WEATHER_OBSERVATIONS
  4. bash scripts/install-platform-hardware.sh --activate --confirm INSTALL-PLATFORM-HARDWARE --project-user $PROJECT_USER
  5. bash scripts/preflight-appliance.sh --player-pending --audio $AUDIO_PROFILE --weather-observations $WEATHER_OBSERVATIONS --project-user $PROJECT_USER
  6. bash scripts/install-plexamp-runtime.sh --activate --confirm INSTALL-PLEXAMP-RUNTIME --project-user $PROJECT_USER
  7. bash scripts/install-nfc-listener.sh --activate --confirm INSTALL-NFC-LISTENER --project-user $PROJECT_USER --project-dir $REPO_ROOT
  8. bash scripts/preflight-appliance.sh --audio $AUDIO_PROFILE --weather-observations $WEATHER_OBSERVATIONS --project-user $PROJECT_USER

Hardware exit 75 is a controlled reboot checkpoint. Re-running this exact root
command after reboot is the supported resume mechanism; successful additive and
idempotent bootstrap stages are rechecked rather than assumed.

Hardware/player exit 78 is an explicit source/commissioning blocker and prevents
NFC/application mutation from starting.
EOF
    else
        cat <<EOF

Guarded compatibility --apply uses these gates in order:
  1. bash scripts/check-appliance-packages.sh --audio $AUDIO_PROFILE --weather-observations $WEATHER_OBSERVATIONS
  2. bash scripts/preflight-appliance.sh --bootstrap-pending --audio $AUDIO_PROFILE --weather-observations $WEATHER_OBSERVATIONS --project-user $PROJECT_USER
  3. bash scripts/install-appliance-packages.sh --activate --confirm INSTALL-APPLIANCE-PACKAGES --audio $AUDIO_PROFILE --weather-observations $WEATHER_OBSERVATIONS
  4. bash scripts/preflight-appliance.sh --audio $AUDIO_PROFILE --weather-observations $WEATHER_OBSERVATIONS --project-user $PROJECT_USER

The first compatibility preflight proves platform, project-user, existing DAC,
existing Plexamp and profile-specific safety before additive package mutation.
Package-owned tools may be READY there. The second preflight runs after bootstrap
and requires those owned prerequisites.
EOF
    fi

    cat <<EOF

For a fresh Weather Underground install, host preflights receive the API-key file
path so they can validate the candidate credential without requiring a secret to
be pre-exported in the shell environment.

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
echo 'Guarded --apply: checking package/artifact availability.'
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
if [[ "$WEATHER_OBSERVATIONS" == weather-underground && "$PRESERVE_WEATHER_OBSERVATIONS" != true ]]; then
    preflight_args+=(--weather-api-key-file "$WU_API_KEY_FILE")
fi

if [[ "$FRESH_BOOTSTRAP" == true ]]; then
    echo
echo 'Running fresh stage-zero platform/bootstrap ownership gate.'
    bash "$REPO_ROOT/scripts/preflight-appliance.sh" \
        --fresh-bootstrap-pending \
        "${preflight_args[@]}" \
        || fail "fresh stage-zero preflight failed; no mutation was attempted"
else
    echo
echo 'Running compatibility pre-bootstrap platform/external prerequisite gate.'
    bash "$REPO_ROOT/scripts/preflight-appliance.sh" \
        --bootstrap-pending \
        "${preflight_args[@]}" \
        || fail "platform/external preflight failed; no mutation was attempted"
fi

echo
echo 'Platform gate passed. Establishing guarded package/main/NFC-venv prerequisite baseline.'
bash "$REPO_ROOT/scripts/install-appliance-packages.sh" \
    --activate \
    --confirm INSTALL-APPLIANCE-PACKAGES \
    --audio "$AUDIO_PROFILE" \
    --weather-observations "$WEATHER_OBSERVATIONS" \
    || fail "package/venv prerequisite baseline failed; application transaction was not started"

if [[ "$FRESH_BOOTSTRAP" == true ]]; then
    echo
echo 'Package/venv baseline established. Running guarded Pi hardware commissioning.'
    hardware_rc=0
    bash "$REPO_ROOT/scripts/install-platform-hardware.sh" \
        --activate \
        --confirm INSTALL-PLATFORM-HARDWARE \
        --project-user "$PROJECT_USER" \
        || hardware_rc=$?

    if [[ "$hardware_rc" -eq 75 ]]; then
        resume_args=(
            --fresh-bootstrap
            --apply
            --confirm "$APPLY_CONFIRMATION_TOKEN"
            --audio "$AUDIO_PROFILE"
            --project-user "$PROJECT_USER"
            --dashboard-url "$DASHBOARD_URL"
        )
        if [[ "$PRESERVE_WEATHER_OBSERVATIONS" == true ]]; then
            resume_args+=(--preserve-weather-observations)
        else
            resume_args+=(--weather-observations "$WEATHER_OBSERVATIONS")
        fi
        [[ "$NON_INTERACTIVE" == true ]] && resume_args+=(--non-interactive)
        if [[ "$AUDIO_PROFILE" == eq ]]; then
            resume_args+=(--camilladsp-binary "$CAMILLA_BINARY")
        fi
        if [[ "$WEATHER_OBSERVATIONS" == weather-underground && "$PRESERVE_WEATHER_OBSERVATIONS" != true ]]; then
            resume_args+=(--wu-station-id "$WU_STATION_ID" --wu-api-key-file "$WU_API_KEY_FILE")
        fi
        echo
        echo 'ROOT_INSTALL=REBOOT-REQUIRED'
        echo 'REBOOT_POLICY=OPERATOR-CONTROLLED'
        printf 'RESUME_COMMAND='
        printf '%q ' bash "$REPO_ROOT/appliance-installer.sh" "${resume_args[@]}"
        echo
        exit 75
    elif [[ "$hardware_rc" -ne 0 ]]; then
        echo 'ROOT_INSTALL=BLOCKED-BEFORE-PLAYER'
        echo "PLATFORM_HARDWARE_EXIT=$hardware_rc"
        exit "$hardware_rc"
    fi

    echo
echo 'Hardware commissioning passed. Running post-hardware/player-pending gate.'
    bash "$REPO_ROOT/scripts/preflight-appliance.sh" \
        --player-pending \
        "${preflight_args[@]}" \
        || fail "post-hardware/player-pending preflight failed; player/NFC/application stages were not started"

    echo
echo 'Hardware gate passed. Running guarded Plexamp compatibility-runtime owner.'
    plexamp_rc=0
    bash "$REPO_ROOT/scripts/install-plexamp-runtime.sh" \
        --activate \
        --confirm INSTALL-PLEXAMP-RUNTIME \
        --project-user "$PROJECT_USER" \
        || plexamp_rc=$?
    if [[ "$plexamp_rc" -ne 0 ]]; then
        echo 'ROOT_INSTALL=BLOCKED-BEFORE-NFC'
        echo "PLEXAMP_RUNTIME_EXIT=$plexamp_rc"
        exit "$plexamp_rc"
    fi
    echo
echo 'Plexamp runtime passed. Installing guarded NFC listener service.'
    bash "$REPO_ROOT/scripts/install-nfc-listener.sh" \
        --activate \
        --confirm INSTALL-NFC-LISTENER \
        --project-user "$PROJECT_USER" \
        --project-dir "$REPO_ROOT" \
        || fail "NFC listener bootstrap failed; application transaction was not started"

    echo
echo 'Fresh bootstrap owners passed. Running full host preflight.'
else
    echo
echo 'Package/venv baseline established. Repeating full compatibility host preflight.'
fi

bash "$REPO_ROOT/scripts/preflight-appliance.sh" "${preflight_args[@]}" \
    || fail "post-bootstrap host preflight failed; application transaction was not started"

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
if [[ "$WEATHER_OBSERVATIONS" == weather-underground && "$PRESERVE_WEATHER_OBSERVATIONS" != true ]]; then
    application_args+=(
        --wu-station-id "$WU_STATION_ID"
        --wu-api-key-file "$WU_API_KEY_FILE"
    )
fi

echo
echo 'Full host preflight passed. Starting one guarded application transaction.'
if ! bash "$REPO_ROOT/scripts/install-appliance-application.sh" "${application_args[@]}"; then
    fail "whole-appliance application transaction failed; package/venv prerequisite baseline was retained by policy"
fi

cat <<EOF

A Clockwork Plex guarded appliance installation completed successfully.
ROOT_INSTALL=COMMITTED
INSTALL_ROUTE=$(if [[ "$FRESH_BOOTSTRAP" == true ]]; then echo fresh-bootstrap; else echo compatibility; fi)
PACKAGE_VENV_BASELINE=RETAINED
APPLICATION_VERIFY=PASS
EOF
