#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=installer/lib/plexamp_runtime.sh
source "$REPO_ROOT/installer/lib/plexamp_runtime.sh"

AUDIO_PROFILE="${ACP_AUDIO_PROFILE:-eq}"
WEATHER_OBSERVATIONS="${ACP_WEATHER_OBSERVATIONS:-ecowitt-push}"
PROJECT_USER="${ACP_PROJECT_USER:-${USER:-andy}}"
CAMILLA_BINARY="${ACP_CAMILLA_BINARY:-}"
WU_STATION_ID="${ACP_WU_STATION_ID:-}"
WU_API_KEY_FILE="${ACP_WU_API_KEY_FILE:-}"
DASHBOARD_URL="${ACP_DASHBOARD_URL:-http://localhost:8088}"
NON_INTERACTIVE=false

usage() {
    cat <<'USAGE'
Usage: bash setup.sh [options]

User-facing A Clockwork Plex appliance setup. The normal fresh install is simply:

  bash setup.sh

The setup wrapper acquires the pinned CamillaDSP artifact when EQ is selected,
runs the guarded fresh-appliance installer, and launches the local Plexamp claim
flow automatically when a new player needs claiming.

Options:
  --audio direct|eq
  --weather-observations ecowitt-push|weather-underground
  --project-user USER
  --camilladsp-binary PATH
  --wu-station-id ID
  --wu-api-key-file PATH
  --dashboard-url URL
  --non-interactive
  -h, --help

For the normal installation, leave Weather on ecowitt-push here and commission
Weather Underground later from Settings. This keeps WU API-key material out of
shell history and installer arguments.
USAGE
}

fail() {
    printf '[A Clockwork Plex] setup: %s\n' "$*" >&2
    exit 2
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --audio)
            [[ $# -ge 2 ]] || fail '--audio requires direct or eq'
            AUDIO_PROFILE="$2"
            shift 2
            ;;
        --weather-observations)
            [[ $# -ge 2 ]] || fail '--weather-observations requires ecowitt-push or weather-underground'
            WEATHER_OBSERVATIONS="$2"
            shift 2
            ;;
        --project-user)
            [[ $# -ge 2 ]] || fail '--project-user requires a user'
            PROJECT_USER="$2"
            shift 2
            ;;
        --camilladsp-binary)
            [[ $# -ge 2 ]] || fail '--camilladsp-binary requires a path'
            CAMILLA_BINARY="$2"
            shift 2
            ;;
        --wu-station-id)
            [[ $# -ge 2 ]] || fail '--wu-station-id requires a station ID'
            WU_STATION_ID="$2"
            shift 2
            ;;
        --wu-api-key-file)
            [[ $# -ge 2 ]] || fail '--wu-api-key-file requires a path'
            WU_API_KEY_FILE="$2"
            shift 2
            ;;
        --dashboard-url)
            [[ $# -ge 2 ]] || fail '--dashboard-url requires a URL'
            DASHBOARD_URL="${2%/}"
            shift 2
            ;;
        --non-interactive)
            NON_INTERACTIVE=true
            shift
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
    *) fail "unsupported audio profile '$AUDIO_PROFILE'" ;;
esac
case "$WEATHER_OBSERVATIONS" in
    ecowitt-push|weather-underground) ;;
    *) fail "unsupported weather observations provider '$WEATHER_OBSERVATIONS'" ;;
esac
[[ "$PROJECT_USER" =~ ^[A-Za-z_][A-Za-z0-9_.-]*$ ]] || fail "invalid project user '$PROJECT_USER'"
[[ "$EUID" -ne 0 ]] || fail 'run setup as the normal appliance user, not as root'
[[ "$(id -un)" == "$PROJECT_USER" ]] || fail "run setup while logged in as project user '$PROJECT_USER'"
[[ "$DASHBOARD_URL" =~ ^https?://[^[:space:]\"\'\`\\]+$ ]] || fail 'invalid dashboard URL'

PROJECT_HOME="$(getent passwd "$PROJECT_USER" | cut -d: -f6)"
[[ -n "$PROJECT_HOME" && -d "$PROJECT_HOME" && ! -L "$PROJECT_HOME" ]] || fail "could not resolve a safe home directory for $PROJECT_USER"

if [[ "$WEATHER_OBSERVATIONS" == weather-underground ]]; then
    [[ "$WU_STATION_ID" =~ ^[A-Za-z0-9_-]+$ ]] || fail 'Weather Underground requires --wu-station-id'
    [[ -n "$WU_API_KEY_FILE" && -f "$WU_API_KEY_FILE" && ! -L "$WU_API_KEY_FILE" && -r "$WU_API_KEY_FILE" ]] || \
        fail 'Weather Underground requires a readable --wu-api-key-file'
else
    [[ -z "$WU_STATION_ID" && -z "$WU_API_KEY_FILE" ]] || \
        fail 'Weather Underground station/key options require --weather-observations weather-underground'
fi

if [[ "$AUDIO_PROFILE" == eq && -z "$CAMILLA_BINARY" ]]; then
    echo
    echo '[A Clockwork Plex] Acquiring and verifying the pinned CamillaDSP 4.1.3 artifact...'
    bash "$REPO_ROOT/scripts/fetch-camilladsp-4.1.3.sh" \
        --activate \
        --confirm FETCH-CAMILLADSP-4.1.3
    CAMILLA_BINARY="$PROJECT_HOME/.cache/a-clockwork-plex/artifacts/camilladsp-4.1.3/camilladsp"
fi

if [[ "$AUDIO_PROFILE" == eq ]]; then
    [[ -x "$CAMILLA_BINARY" && ! -L "$CAMILLA_BINARY" ]] || fail "verified CamillaDSP binary is unavailable: $CAMILLA_BINARY"
fi

NODE_BIN="/opt/a-clockwork-plex/node-v${ACP_NODE_VERSION}-${ACP_NODE_PLATFORM}/bin/node"
PLEXAMP_HOME="$PROJECT_HOME/plexamp"
PLEXAMP_SETTINGS="$PROJECT_HOME/.local/share/Plexamp/Settings"

plexamp_claim_state_present() {
    [[ -d "$PLEXAMP_SETTINGS" ]] && \
        find "$PLEXAMP_SETTINGS" -maxdepth 1 -type f -print -quit 2>/dev/null | grep -q .
}

run_plexamp_claim() {
    [[ -x "$NODE_BIN" ]] || fail "Plexamp claim cannot start because pinned Node is missing: $NODE_BIN"
    [[ -f "$PLEXAMP_HOME/js/index.js" ]] || fail "Plexamp claim cannot start because the runtime is incomplete: $PLEXAMP_HOME"

    cat <<EOF

[A Clockwork Plex] Plexamp Headless needs to be claimed before setup can continue.

1. Open https://plex.tv/claim on another device and obtain a fresh claim code.
2. Enter that code into the Plexamp prompt below, then enter the player name.
3. Wait until Plexamp reports that it has started successfully.
4. Press Ctrl-C once. A Clockwork Plex setup will detect the saved claim state and continue automatically.

The claim code is entered directly into Plexamp and is never accepted by this setup script.
EOF

    set +e
    trap ':' INT
    (
        cd "$PLEXAMP_HOME"
        "$NODE_BIN" js/index.js
    )
    claim_rc=$?
    trap - INT
    set -e

    if plexamp_claim_state_present; then
        echo
        echo '[A Clockwork Plex] Plexamp claim state detected. Continuing appliance setup...'
        return 0
    fi

    echo >&2
    echo '[A Clockwork Plex] Plexamp claim state was not detected; setup has stopped before NFC/application installation.' >&2
    echo '[A Clockwork Plex] Re-run bash setup.sh when you are ready to claim the player.' >&2
    return "${claim_rc:-$ACP_PLEXAMP_CLAIM_EXIT}"
}

run_guarded_installer() {
    local args=(
        bash "$REPO_ROOT/install.sh"
        --fresh-bootstrap
        --audio "$AUDIO_PROFILE"
        --weather-observations "$WEATHER_OBSERVATIONS"
        --project-user "$PROJECT_USER"
        --dashboard-url "$DASHBOARD_URL"
        --apply
        --confirm APPLY-A-CLOCKWORK-PLEX
    )
    [[ "$NON_INTERACTIVE" == true ]] && args+=(--non-interactive)
    [[ "$AUDIO_PROFILE" == eq ]] && args+=(--camilladsp-binary "$CAMILLA_BINARY")
    if [[ "$WEATHER_OBSERVATIONS" == weather-underground ]]; then
        args+=(--wu-station-id "$WU_STATION_ID" --wu-api-key-file "$WU_API_KEY_FILE")
    fi
    "${args[@]}"
}

while true; do
    set +e
    run_guarded_installer
    installer_rc=$?
    set -e

    case "$installer_rc" in
        0)
            cat <<'EOF'

[A Clockwork Plex] Setup completed successfully.
Reboot once to enter the installed appliance and confirm dashboard kiosk startup.
EOF
            exit 0
            ;;
        75)
            cat <<'EOF'

[A Clockwork Plex] Raspberry Pi hardware commissioning requires a reboot.
Run:

  sudo reboot

After the Pi returns, open a terminal in ~/A-Clockwork-Plex and run:

  bash setup.sh

Already-completed bootstrap stages will be checked and reused.
EOF
            exit 75
            ;;
        "$ACP_PLEXAMP_CLAIM_EXIT")
            if [[ "$NON_INTERACTIVE" == true ]]; then
                echo '[A Clockwork Plex] Non-interactive setup cannot perform the local Plexamp claim; re-run interactively.' >&2
                exit "$installer_rc"
            fi
            run_plexamp_claim || exit "$ACP_PLEXAMP_CLAIM_EXIT"
            ;;
        *)
            echo "[A Clockwork Plex] Guarded appliance installer stopped with exit $installer_rc." >&2
            exit "$installer_rc"
            ;;
    esac
done
