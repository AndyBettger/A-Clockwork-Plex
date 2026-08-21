#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ACP_REPO_ROOT="$REPO_ROOT"

# shellcheck source=installer/lib/components.sh
source "$REPO_ROOT/installer/lib/components.sh"
# shellcheck source=installer/lib/direct_audio.sh
source "$REPO_ROOT/installer/lib/direct_audio.sh"
# shellcheck source=installer/lib/prerequisites.sh
source "$REPO_ROOT/installer/lib/prerequisites.sh"

MODE=host
BOOTSTRAP_PENDING=false
FRESH_BOOTSTRAP_PENDING=false
PLAYER_PENDING=false
AUDIO_PROFILE=eq
WEATHER_PROVIDER=ecowitt-push
PROJECT_USER="${SUDO_USER:-${USER:-andy}}"
CAMILLA_BINARY=
WU_KEY_ENV=WEATHER_UNDERGROUND_API_KEY
WU_KEY_FILE=
PRESERVE_WEATHER_OBSERVATIONS="${ACP_PRESERVE_WEATHER_OBSERVATIONS:-false}"
WEATHER_SECRET_HELPER="${ACP_WEATHER_SECRET_HELPER:-/usr/local/bin/a-clockwork-plex-weather-secret}"
FAILURES=0
WARNINGS=0

usage() {
    cat <<'EOF'
Usage: bash scripts/preflight-appliance.sh [options]

Read-only fresh-Pi prerequisite report for the whole-appliance installer.
It never installs packages/files, changes configuration, loads modules, opens an
audio PCM, or starts/stops/restarts/enables/disables services.

Options:
  --audio direct|eq
  --weather-observations ecowitt-push|weather-underground
  --project-user USER
  --binary PATH             verified CamillaDSP 4.1.3 executable for EQ host check
  --weather-api-key-env NAME
                            existing WU runtime credential environment name
  --weather-api-key-file PATH
                            fresh-install WU secret file; value is never displayed
  --bootstrap-pending       compatibility pre-package gate used by current root
                            orchestration: package-owned requirements may be READY,
                            but existing DAC and Plexamp remain required
  --fresh-bootstrap-pending future fresh-OS stage-zero gate: package-owned tools,
                            DAC/PN532 commissioning and Plexamp runtime may be READY
                            because later guarded bootstrap owners have not run yet
  --player-pending          post-package/post-hardware gate: package-owned tools,
                            DAC and PN532 must pass; Plexamp may still be READY
  --source-only             validate repository/component sources and print the
                            prerequisite contract without probing this host
  -h, --help
EOF
}

error() {
    printf '[A Clockwork Plex] ERROR: %s\n' "$*" >&2
}

pass() {
    printf 'PASS  %-22s %s\n' "$1" "$2"
}

ready_check() {
    printf 'READY %-22s %s\n' "$1" "$2"
}

fail_check() {
    printf 'FAIL  %-22s %s\n' "$1" "$2"
    FAILURES=$((FAILURES + 1))
}

warn_check() {
    printf 'WARN  %-22s %s\n' "$1" "$2"
    WARNINGS=$((WARNINGS + 1))
}

package_bootstrap_pending() {
    [[ "$BOOTSTRAP_PENDING" == true || "$FRESH_BOOTSTRAP_PENDING" == true ]]
}

owned_command_check() {
    local label="$1" command="$2"
    if command -v "$command" >/dev/null 2>&1; then
        pass "$label" "$(command -v "$command")"
    elif package_bootstrap_pending; then
        ready_check "$label" 'owned package bootstrap will install this prerequisite'
    else
        fail_check "$label" 'missing after package bootstrap'
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --audio)
            [[ $# -ge 2 ]] || { error '--audio requires a profile.'; exit 64; }
            AUDIO_PROFILE="$2"
            shift 2
            ;;
        --weather-observations)
            [[ $# -ge 2 ]] || { error '--weather-observations requires a provider.'; exit 64; }
            WEATHER_PROVIDER="$2"
            shift 2
            ;;
        --project-user)
            [[ $# -ge 2 ]] || { error '--project-user requires a user.'; exit 64; }
            PROJECT_USER="$2"
            shift 2
            ;;
        --binary)
            [[ $# -ge 2 ]] || { error '--binary requires a path.'; exit 64; }
            CAMILLA_BINARY="$2"
            shift 2
            ;;
        --weather-api-key-env)
            [[ $# -ge 2 ]] || { error '--weather-api-key-env requires a name.'; exit 64; }
            WU_KEY_ENV="$2"
            shift 2
            ;;
        --weather-api-key-file)
            [[ $# -ge 2 ]] || { error '--weather-api-key-file requires a path.'; exit 64; }
            WU_KEY_FILE="$2"
            shift 2
            ;;
        --bootstrap-pending)
            BOOTSTRAP_PENDING=true
            shift
            ;;
        --fresh-bootstrap-pending)
            FRESH_BOOTSTRAP_PENDING=true
            shift
            ;;
        --player-pending)
            PLAYER_PENDING=true
            shift
            ;;
        --source-only)
            MODE=source
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            usage >&2
            exit 64
            ;;
    esac
done

case "$AUDIO_PROFILE" in
    direct|eq) ;;
    *) error "Unsupported audio profile: $AUDIO_PROFILE"; exit 64 ;;
esac
case "$WEATHER_PROVIDER" in
    ecowitt-push|weather-underground) ;;
    *) error "Unsupported weather observation provider: $WEATHER_PROVIDER"; exit 64 ;;
esac
[[ "$PROJECT_USER" =~ ^[A-Za-z_][A-Za-z0-9_.-]*$ ]] || {
    error "Invalid project user: $PROJECT_USER"
    exit 64
}
[[ "$WU_KEY_ENV" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || {
    error "Invalid Weather Underground API-key environment name: $WU_KEY_ENV"
    exit 64
}
case "$PRESERVE_WEATHER_OBSERVATIONS" in
    true|false) ;;
    *) error 'ACP_PRESERVE_WEATHER_OBSERVATIONS must be true or false.'; exit 64 ;;
esac
if [[ "$PRESERVE_WEATHER_OBSERVATIONS" == true && -n "$WU_KEY_FILE" ]]; then
    error '--weather-api-key-file cannot be combined with commissioned Weather preservation.'
    exit 64
fi
if [[ "$WEATHER_PROVIDER" != weather-underground && -n "$WU_KEY_FILE" ]]; then
    error '--weather-api-key-file is only valid with --weather-observations weather-underground.'
    exit 64
fi

stage_count=0
[[ "$BOOTSTRAP_PENDING" == true ]] && stage_count=$((stage_count + 1))
[[ "$FRESH_BOOTSTRAP_PENDING" == true ]] && stage_count=$((stage_count + 1))
[[ "$PLAYER_PENDING" == true ]] && stage_count=$((stage_count + 1))
if [[ "$stage_count" -gt 1 ]]; then
    error 'Choose only one staged host mode: --bootstrap-pending, --fresh-bootstrap-pending or --player-pending.'
    exit 64
fi
if [[ "$MODE" == source && "$stage_count" -gt 0 ]]; then
    error 'Staged pending modes are host-preflight modes and cannot be combined with --source-only.'
    exit 64
fi

acp_verify_component_sources || exit 1
acp_verify_direct_audio_sources || exit 1
[[ -f "$REPO_ROOT/requirements.txt" && ! -L "$REPO_ROOT/requirements.txt" ]] || {
    error 'requirements.txt is missing or unsafe.'
    exit 1
}

if [[ "$MODE" == source ]]; then
    DISPLAY_MODE=source
elif [[ "$BOOTSTRAP_PENDING" == true ]]; then
    DISPLAY_MODE=pre-bootstrap-compatibility
elif [[ "$FRESH_BOOTSTRAP_PENDING" == true ]]; then
    DISPLAY_MODE=fresh-bootstrap-stage-zero
elif [[ "$PLAYER_PENDING" == true ]]; then
    DISPLAY_MODE=post-hardware-player-pending
else
    DISPLAY_MODE=host
fi

cat <<EOF
A Clockwork Plex fresh-Pi prerequisite report

Mode:                 $DISPLAY_MODE
Audio profile:        $AUDIO_PROFILE
Weather observations: $WEATHER_PROVIDER
Project user:         $PROJECT_USER
EOF

echo
acp_prerequisite_plan "$AUDIO_PROFILE" "$WEATHER_PROVIDER" "$PROJECT_USER"

if [[ "$MODE" == source ]]; then
    cat <<'EOF'

Repository/component source validation passed.
No host prerequisite was probed in source-only mode.
No production file, package, service, route, mixer, PCM or configuration was changed.
APPLIANCE_PREFLIGHT=SOURCE-PASS
EOF
    exit 0
fi

echo
echo 'Host checks:'

if [[ "$(uname -s)" == Linux ]]; then
    pass host-os 'Linux'
else
    fail_check host-os "expected Linux; found $(uname -s)"
fi
if [[ "$(uname -m)" == aarch64 ]]; then
    pass architecture 'aarch64'
else
    fail_check architecture "expected aarch64; found $(uname -m)"
fi

if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    source /etc/os-release
    os_family="${ID:-unknown} ${ID_LIKE:-}"
    if [[ "$os_family" == *debian* || "$os_family" == *raspbian* ]]; then
        pass os-family "$os_family"
    else
        fail_check os-family "expected Raspberry Pi OS/Debian family; found $os_family"
    fi
else
    fail_check os-family '/etc/os-release is unavailable'
fi

if [[ "$EUID" -eq 0 ]]; then
    fail_check execution-user 'run preflight as the normal project user, not root'
else
    pass execution-user "uid=$EUID"
fi

if id "$PROJECT_USER" >/dev/null 2>&1; then
    home="$(getent passwd "$PROJECT_USER" | cut -d: -f6)"
    if [[ -n "$home" && -d "$home" ]]; then
        pass project-user "$PROJECT_USER home=$home"
    else
        fail_check project-user "$PROJECT_USER has no usable home directory"
    fi
else
    fail_check project-user "$PROJECT_USER does not exist"
fi

# Platform commands are not owned by the package bootstrap and must already exist.
# visudo is pinned here because restricted helper policies are validated before install.
for command in bash systemctl sudo visudo install sha256sum stat awk sed grep getent; do
    if command -v "$command" >/dev/null 2>&1; then
        pass "command:$command" "$(command -v "$command")"
    else
        fail_check "command:$command" 'missing platform prerequisite'
    fi
done

# These commands are explicitly owned by scripts/install-appliance-packages.sh.
for command in git curl python3 i2cdetect; do
    owned_command_check "command:$command" "$command"
done

if command -v python3 >/dev/null 2>&1 && python3 -c 'import venv' >/dev/null 2>&1; then
    pass python-venv 'python3 venv module available'
elif package_bootstrap_pending; then
    ready_check python-venv 'python3-venv is owned by package bootstrap'
else
    fail_check python-venv 'python3 venv module unavailable after package bootstrap'
fi

for command in aplay amixer shairport-sync; do
    owned_command_check "audio:$command" "$command"
done

browser=
for candidate in chromium-browser chromium google-chrome-stable google-chrome; do
    if command -v "$candidate" >/dev/null 2>&1; then
        browser="$(command -v "$candidate")"
        break
    fi
done
if [[ -n "$browser" ]]; then
    pass browser "$browser"
elif package_bootstrap_pending; then
    ready_check browser 'Chromium is owned by package bootstrap'
else
    fail_check browser 'Chromium-compatible browser not found after package bootstrap'
fi

if systemctl cat plexamp.service >/dev/null 2>&1; then
    pass plexamp-service 'plexamp.service is installed'
elif [[ "$FRESH_BOOTSTRAP_PENDING" == true || "$PLAYER_PENDING" == true ]]; then
    ready_check plexamp-service 'guarded Plexamp compatibility-runtime owner has not run yet'
else
    fail_check plexamp-service 'plexamp.service is not installed; current compatibility/full gate still requires Plexamp'
fi

if systemctl cat shairport-sync.service >/dev/null 2>&1; then
    pass shairport-service 'shairport-sync.service is installed'
elif package_bootstrap_pending; then
    ready_check shairport-service 'shairport-sync package/service is owned by package bootstrap'
else
    fail_check shairport-service 'shairport-sync.service is not installed after package bootstrap'
fi

if [[ -r /proc/asound/cards ]] && grep -Eq '^\s*[0-9]+\s+\[Pro\s*\]' /proc/asound/cards; then
    pass dac-card 'ALSA card id Pro found'
elif [[ "$FRESH_BOOTSTRAP_PENDING" == true ]]; then
    ready_check dac-card 'guarded platform-hardware owner has not commissioned the accepted DAC yet'
else
    fail_check dac-card 'ALSA card id Pro not found'
fi

if [[ "$FRESH_BOOTSTRAP_PENDING" == true ]]; then
    ready_check pn532-i2c 'guarded platform-hardware owner will require bus 1 address 0x24'
elif [[ "$PLAYER_PENDING" == true ]]; then
    if ! command -v i2cdetect >/dev/null 2>&1; then
        fail_check pn532-i2c 'i2cdetect missing after package bootstrap'
    else
        pn532_probe="$(sudo -- i2cdetect -y 1 0x24 0x24 2>/dev/null || true)"
        if printf '%s\n' "$pn532_probe" | grep -Eq '(^|[[:space:]])24([[:space:]]|$)'; then
            pass pn532-i2c 'PN532 found on I2C bus 1 address 0x24'
        else
            fail_check pn532-i2c 'PN532 not found on I2C bus 1 address 0x24 after hardware bootstrap'
        fi
    fi
fi

if [[ "$AUDIO_PROFILE" == eq ]]; then
    if [[ -z "$CAMILLA_BINARY" ]]; then
        fail_check camilladsp 'EQ host preflight requires --binary PATH'
    elif [[ ! -f "$CAMILLA_BINARY" || ! -x "$CAMILLA_BINARY" || -L "$CAMILLA_BINARY" ]]; then
        fail_check camilladsp 'binary is not an executable regular file'
    else
        observed="$(sha256sum "$CAMILLA_BINARY" | awk '{print $1}')"
        expected=e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa
        version="$("$CAMILLA_BINARY" --version 2>&1 | head -n 1 || true)"
        if [[ "$observed" == "$expected" && "$version" == *'4.1.3'* ]]; then
            pass camilladsp "4.1.3 sha256=$observed"
        else
            fail_check camilladsp "expected CamillaDSP 4.1.3 sha256=$expected"
        fi
    fi

    if command -v modinfo >/dev/null 2>&1 && modinfo snd_aloop >/dev/null 2>&1; then
        pass snd-aloop 'kernel module is available (not loaded by preflight)'
    else
        fail_check snd-aloop 'snd_aloop module is unavailable'
    fi
else
    pass camilladsp 'not required by Direct profile'
    pass snd-aloop 'not required by Direct profile'
fi

if [[ "$WEATHER_PROVIDER" == weather-underground ]]; then
    if [[ "$PRESERVE_WEATHER_OBSERVATIONS" == true ]]; then
        if [[ ! -x "$WEATHER_SECRET_HELPER" || -L "$WEATHER_SECRET_HELPER" ]]; then
            fail_check weather-credential "managed Weather credential helper is unavailable or unsafe: $WEATHER_SECRET_HELPER"
        elif managed_weather_status="$(sudo -n -- "$WEATHER_SECRET_HELPER" status 2>/dev/null)" && \
            [[ "$managed_weather_status" == 'WEATHER_SECRET_CONFIGURED=1' ]]; then
            pass weather-credential 'managed WU credential is present; commissioned profile will be preserved'
        else
            fail_check weather-credential 'managed WU credential is unavailable or invalid for commissioned profile preservation'
        fi
    elif [[ -n "$WU_KEY_FILE" ]]; then
        if [[ ! -f "$WU_KEY_FILE" || -L "$WU_KEY_FILE" || ! -r "$WU_KEY_FILE" ]]; then
            fail_check weather-credential 'candidate API-key file must be a readable regular file, not a symlink'
        elif command -v python3 >/dev/null 2>&1; then
            if python3 - "$WU_KEY_FILE" <<'PY'
import sys
from pathlib import Path

raw = Path(sys.argv[1]).read_bytes().rstrip(b"\r\n")
if not raw or b"\x00" in raw or b"\n" in raw or b"\r" in raw:
    raise SystemExit(1)
try:
    value = raw.decode("utf-8")
except UnicodeDecodeError:
    raise SystemExit(1)
raise SystemExit(0 if value.strip() else 1)
PY
            then
                pass weather-credential 'fresh-install API-key file is readable and structurally valid (value not displayed)'
            else
                fail_check weather-credential 'candidate API-key file is empty, multiline or invalid UTF-8'
            fi
        elif package_bootstrap_pending; then
            ready_check weather-credential 'key file is readable; structural validation follows Python package bootstrap'
        else
            fail_check weather-credential 'python3 unavailable for credential validation after package bootstrap'
        fi
    elif [[ -n "${!WU_KEY_ENV:-}" ]]; then
        pass weather-credential "$WU_KEY_ENV is set for an existing installation (value not displayed)"
    else
        fail_check weather-credential "provide --weather-api-key-file PATH for fresh install or set $WU_KEY_ENV for an existing installation"
    fi
else
    warn_check weather-ingress 'Ecowitt custom-push network reachability requires physical/site acceptance'
fi

echo
printf 'Failures: %d\nWarnings: %d\n' "$FAILURES" "$WARNINGS"
cat <<'EOF'
No production file, package, service, route, mixer, PCM or configuration was changed.
EOF

if [[ "$FAILURES" -eq 0 ]]; then
    if [[ "$BOOTSTRAP_PENDING" == true ]]; then
        echo 'APPLIANCE_PREFLIGHT=PLATFORM-PASS'
    elif [[ "$FRESH_BOOTSTRAP_PENDING" == true ]]; then
        echo 'APPLIANCE_PREFLIGHT=FRESH-STAGE-ZERO-PASS'
    elif [[ "$PLAYER_PENDING" == true ]]; then
        echo 'APPLIANCE_PREFLIGHT=HARDWARE-PASS-PLAYER-PENDING'
    else
        echo 'APPLIANCE_PREFLIGHT=PASS'
    fi
    exit 0
fi

echo 'APPLIANCE_PREFLIGHT=FAIL'
exit 1
