#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ROOT=/
AUDIO_PROFILE=eq
WEATHER_PROVIDER=ecowitt-push
PROJECT_USER="${SUDO_USER:-${USER:-andy}}"
PROJECT_DIR=
CONFIG_PATH=
DASHBOARD_URL=http://localhost:8088
WU_KEY_FILE=
FAILURES=0
WARNINGS=0
DIRECT_SHA256=654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9
MIXER_HELPER=/usr/local/bin/a-clockwork-plex-audio-mixer
WEATHER_SECRET_HELPER="${WEATHER_SECRET_HELPER:-/usr/local/bin/a-clockwork-plex-weather-secret}"

usage() {
    cat <<'EOF'
Usage: bash scripts/verify-appliance.sh [options]

Read-only post-install verification for one selected appliance profile.
Production mode also verifies service/API health. An alternate --root performs
filesystem/config verification only for non-production integration tests.

Options:
  --audio direct|eq
  --weather-observations ecowitt-push|weather-underground
  --weather-api-key-file PATH
                          Optional WU credential-file override; the secret
                          value is validated but never displayed. Normal
                          commissioned appliances use the restricted
                          managed-credential status helper instead
  --project-user USER
  --project-dir PATH     logical installed repository path
  --config PATH          logical config.json path
  --root PATH            alternate filesystem root; disables live service/API probes
  --dashboard-url URL    production dashboard base URL (default http://localhost:8088)
  -h, --help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --audio)
            [[ $# -ge 2 ]] || { echo '--audio requires a profile.' >&2; exit 64; }
            AUDIO_PROFILE="$2"
            shift 2
            ;;
        --weather-observations)
            [[ $# -ge 2 ]] || { echo '--weather-observations requires a provider.' >&2; exit 64; }
            WEATHER_PROVIDER="$2"
            shift 2
            ;;
        --weather-api-key-file)
            [[ $# -ge 2 ]] || { echo '--weather-api-key-file requires a path.' >&2; exit 64; }
            WU_KEY_FILE="$2"
            shift 2
            ;;
        --project-user)
            [[ $# -ge 2 ]] || { echo '--project-user requires a user.' >&2; exit 64; }
            PROJECT_USER="$2"
            shift 2
            ;;
        --project-dir)
            [[ $# -ge 2 ]] || { echo '--project-dir requires a path.' >&2; exit 64; }
            PROJECT_DIR="$2"
            shift 2
            ;;
        --config)
            [[ $# -ge 2 ]] || { echo '--config requires a path.' >&2; exit 64; }
            CONFIG_PATH="$2"
            shift 2
            ;;
        --root)
            [[ $# -ge 2 ]] || { echo '--root requires a path.' >&2; exit 64; }
            ROOT="$2"
            shift 2
            ;;
        --dashboard-url)
            [[ $# -ge 2 ]] || { echo '--dashboard-url requires a URL.' >&2; exit 64; }
            DASHBOARD_URL="${2%/}"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 64
            ;;
    esac
done

case "$AUDIO_PROFILE" in
    direct|eq) ;;
    *) echo "Unsupported audio profile: $AUDIO_PROFILE" >&2; exit 64 ;;
esac
case "$WEATHER_PROVIDER" in
    ecowitt-push|weather-underground) ;;
    *) echo "Unsupported weather provider: $WEATHER_PROVIDER" >&2; exit 64 ;;
esac
if [[ "$WEATHER_PROVIDER" != weather-underground && -n "$WU_KEY_FILE" ]]; then
    echo '--weather-api-key-file is only valid with --weather-observations weather-underground.' >&2
    exit 64
fi
[[ "$PROJECT_USER" =~ ^[A-Za-z_][A-Za-z0-9_.-]*$ ]] || { echo "Invalid project user: $PROJECT_USER" >&2; exit 64; }
[[ "$PROJECT_DIR" == /* || -z "$PROJECT_DIR" ]] || { echo '--project-dir must be absolute.' >&2; exit 64; }
[[ "$CONFIG_PATH" == /* || -z "$CONFIG_PATH" ]] || { echo '--config must be absolute.' >&2; exit 64; }
[[ "$WEATHER_SECRET_HELPER" == /* ]] || { echo 'WEATHER_SECRET_HELPER must be an absolute path.' >&2; exit 64; }

if [[ "$ROOT" != / ]]; then
    ROOT="${ROOT%/}"
    [[ -d "$ROOT" ]] || { echo "Alternate root does not exist: $ROOT" >&2; exit 1; }
fi

if [[ -z "$PROJECT_DIR" ]]; then
    if [[ "$ROOT" == / ]]; then
        PROJECT_DIR="$REPO_ROOT"
    else
        PROJECT_DIR="/home/$PROJECT_USER/A-Clockwork-Plex"
    fi
fi
if [[ -z "$CONFIG_PATH" ]]; then
    CONFIG_PATH="$PROJECT_DIR/config.json"
fi

root_path() {
    local path="$1"
    if [[ "$ROOT" == / ]]; then
        printf '%s\n' "$path"
    else
        printf '%s%s\n' "$ROOT" "$path"
    fi
}

pass() { printf 'PASS  %-24s %s\n' "$1" "$2"; }
fail_check() { printf 'FAIL  %-24s %s\n' "$1" "$2"; FAILURES=$((FAILURES + 1)); }
warn_check() { printf 'WARN  %-24s %s\n' "$1" "$2"; WARNINGS=$((WARNINGS + 1)); }

require_file() {
    local label="$1" logical="$2" path
    path="$(root_path "$logical")"
    if [[ -f "$path" && ! -L "$path" ]]; then
        pass "$label" "$logical"
    else
        fail_check "$label" "missing/unsafe: $logical"
    fi
}

require_protected_file() {
    local label="$1" logical="$2" path
    path="$(root_path "$logical")"
    if [[ "$ROOT" == / ]]; then
        if sudo -n test -f "$path" 2>/dev/null && ! sudo -n test -L "$path" 2>/dev/null; then
            pass "$label" "$logical"
        else
            fail_check "$label" "missing/unsafe or protected inspection unavailable: $logical"
        fi
    else
        require_file "$label" "$logical"
    fi
}

require_contains() {
    local label="$1" logical="$2" needle="$3" path
    path="$(root_path "$logical")"
    if [[ -f "$path" && ! -L "$path" ]] && grep -Fq "$needle" "$path"; then
        pass "$label" "$needle"
    else
        fail_check "$label" "$logical does not contain: $needle"
    fi
}

valid_wu_key_file() {
    local path="$1"
    [[ -f "$path" && ! -L "$path" && -r "$path" ]] || return 1
    python3 - "$path" <<'PY'
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
}

managed_wu_credential_configured() {
    local output
    if ! output="$(sudo -n "$WEATHER_SECRET_HELPER" status 2>/dev/null)"; then
        return 1
    fi
    [[ "$output" == 'WEATHER_SECRET_CONFIGURED=1' ]]
}

validate_mixer_payload() {
    local source="$1"
    python3 - "$source" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if isinstance(payload, dict) and isinstance(payload.get("mixer"), dict):
    payload = payload["mixer"]
channels = payload.get("channels") if isinstance(payload, dict) else None
required = {"master", "plexamp", "airplay", "alarm"}
ok = (
    isinstance(payload, dict)
    and payload.get("available") is True
    and payload.get("configured") is True
    and isinstance(channels, dict)
    and required.issubset(channels)
    and all(channels[name].get("available") is True and channels[name].get("pcm_available") is True for name in required)
)
raise SystemExit(0 if ok else 1)
PY
}

cat <<EOF
A Clockwork Plex appliance post-install verification

Filesystem root:      $ROOT
Project directory:    $PROJECT_DIR
Project user:         $PROJECT_USER
Audio profile:        $AUDIO_PROFILE
Weather observations: $WEATHER_PROVIDER
EOF

echo
echo 'Application/integration files:'
require_contains dashboard-unit '/etc/systemd/system/a-clockwork-plex.service' "User=$PROJECT_USER"
require_contains dashboard-unit '/etc/systemd/system/a-clockwork-plex.service' "Group=$PROJECT_USER"
require_contains dashboard-unit '/etc/systemd/system/a-clockwork-plex.service' "WorkingDirectory=$PROJECT_DIR"
require_contains dashboard-unit '/etc/systemd/system/a-clockwork-plex.service' "ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/app/runner.py"
require_file airplay-start '/usr/local/bin/a-clockwork-plex-airplay-start'
require_file airplay-end '/usr/local/bin/a-clockwork-plex-airplay-end'
require_contains airplay-start '/usr/local/bin/a-clockwork-plex-airplay-start' '/api/airplay/start'
require_contains airplay-start '/usr/local/bin/a-clockwork-plex-airplay-start' 'PlaybackCoordinator owns Plexamp pause'
require_contains airplay-end '/usr/local/bin/a-clockwork-plex-airplay-end' '/api/airplay/end'
require_contains airplay-end '/usr/local/bin/a-clockwork-plex-airplay-end' '/api/playback/events'
require_contains airplay-end '/usr/local/bin/a-clockwork-plex-airplay-end' 'org.gnome.ShairportSync.RemoteControl'
require_file metadata-unit '/etc/systemd/system/a-clockwork-plex-airplay-metadata.service'
require_contains metadata-unit '/etc/systemd/system/a-clockwork-plex-airplay-metadata.service' "User=$PROJECT_USER"
require_contains metadata-unit '/etc/systemd/system/a-clockwork-plex-airplay-metadata.service' 'Environment=SHAIRPORT_METADATA_PIPE=/tmp/shairport-sync-metadata'
require_contains metadata-unit '/etc/systemd/system/a-clockwork-plex-airplay-metadata.service' 'scripts/airplay-metadata-listener.py'
require_file alarm-helper '/usr/local/bin/a-clockwork-plex-alarm-audio'
require_protected_file alarm-sudoers '/etc/sudoers.d/a-clockwork-plex-alarm-audio'
require_file shairport-name-helper '/usr/local/bin/a-clockwork-plex-shairport-name'
require_protected_file shairport-name-sudoers '/etc/sudoers.d/a-clockwork-plex-shairport-name'
if [[ "$ROOT" == / ]]; then
    require_file weather-secret-helper "$WEATHER_SECRET_HELPER"
    require_protected_file weather-secret-sudoers '/etc/sudoers.d/a-clockwork-plex-weather-secret'
else
    weather_helper_fixture="$(root_path "$WEATHER_SECRET_HELPER")"
    weather_sudoers_fixture="$(root_path '/etc/sudoers.d/a-clockwork-plex-weather-secret')"
    if [[ -e "$weather_helper_fixture" || -L "$weather_helper_fixture" || -e "$weather_sudoers_fixture" || -L "$weather_sudoers_fixture" ]]; then
        require_file weather-secret-helper "$WEATHER_SECRET_HELPER"
        require_protected_file weather-secret-sudoers '/etc/sudoers.d/a-clockwork-plex-weather-secret'
    else
        warn_check weather-secret-helper 'managed credential helper not staged in alternate-root application fixture'
    fi
fi
require_file mixer-helper "$MIXER_HELPER"
require_protected_file mixer-sudoers '/etc/sudoers.d/a-clockwork-plex-audio-mixer'
require_file mixer-defaults '/etc/default/a-clockwork-plex-audio'
require_contains mixer-defaults '/etc/default/a-clockwork-plex-audio' 'ALSA_CARD=Pro'
require_contains mixer-defaults '/etc/default/a-clockwork-plex-audio' 'ALSA_DEVICE=0'
require_contains shairport-config '/etc/shairport-sync.conf' '/usr/local/bin/a-clockwork-plex-airplay-start'
require_contains shairport-config '/etc/shairport-sync.conf' '/usr/local/bin/a-clockwork-plex-airplay-end'
require_contains shairport-config '/etc/shairport-sync.conf' '/tmp/shairport-sync-metadata'
require_contains shairport-config '/etc/shairport-sync.conf' 'acp_airplay'
require_contains kiosk-autostart "/home/$PROJECT_USER/.config/autostart/a-clockwork-plex-dashboard.desktop" "$PROJECT_DIR/scripts/launch-dashboard-kiosk.sh"

echo
echo 'Audio profile:'
if [[ "$AUDIO_PROFILE" == direct ]]; then
    route="$(root_path '/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf')"
    if [[ -f "$route" && ! -L "$route" ]]; then
        observed="$(sha256sum "$route" | awk '{print $1}')"
        if [[ "$observed" == "$DIRECT_SHA256" ]]; then
            pass direct-route "sha256=$observed"
        else
            fail_check direct-route "expected $DIRECT_SHA256 observed $observed"
        fi
    else
        fail_check direct-route 'active direct ALSA route missing/unsafe'
    fi
    marker="$(root_path '/var/lib/a-clockwork-plex/split-bus/installed')"
    if [[ ! -e "$marker" ]]; then
        pass eq-marker 'absent as required for Direct profile'
    else
        fail_check eq-marker 'EQ installed marker exists on Direct profile'
    fi
else
    verify_command=(bash "$REPO_ROOT/scripts/audio/verify-audio.sh")
    if [[ "$ROOT" != / ]]; then
        verify_command+=(--root "$ROOT")
    fi
    verify_output="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-appliance-audio-verify.XXXXXX")"
    if "${verify_command[@]}" >"$verify_output" 2>&1; then
        pass eq-audio 'standalone EQ verifier passed'
    else
        fail_check eq-audio "standalone verifier failed: $(tr '\n' ' ' <"$verify_output" | tail -c 300)"
    fi
    rm -f "$verify_output"
fi

echo
echo 'Weather/configuration:'
config_file="$(root_path "$CONFIG_PATH")"
if [[ ! -f "$config_file" || -L "$config_file" ]]; then
    fail_check config "missing/unsafe: $CONFIG_PATH"
else
    mapfile -t weather_values < <(python3 - "$config_file" <<'PY'
import json
import sys
from pathlib import Path

config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
weather = config.get("weather") if isinstance(config.get("weather"), dict) else {}
wu = weather.get("weather_underground") if isinstance(weather.get("weather_underground"), dict) else {}
ecowitt = weather.get("ecowitt_push") if isinstance(weather.get("ecowitt_push"), dict) else {}
forecast = weather.get("forecast") if isinstance(weather.get("forecast"), dict) else {}
secret_keys = {"api_key", "apikey", "password", "secret", "token"}
secret_present = any(str(key).lower() in secret_keys for key in wu)
provider = str(weather.get("provider") or "ecowitt_push").strip().lower()
provider = {"ecowitt_push": "ecowitt-push", "weather_underground": "weather-underground"}.get(provider, provider)
print(provider)
print(str(forecast.get("provider") or "open_meteo"))
print(str(wu.get("station_id") or ""))
print(str(wu.get("api_key_env") or "WEATHER_UNDERGROUND_API_KEY"))
print(str(ecowitt.get("path") or "/ecowitt"))
print("true" if secret_present else "false")
PY
)
    configured_provider="${weather_values[0]:-}"
    forecast_provider="${weather_values[1]:-}"
    wu_station="${weather_values[2]:-}"
    wu_key_env="${weather_values[3]:-}"
    ecowitt_path="${weather_values[4]:-}"
    secret_present="${weather_values[5]:-true}"

    if [[ "$configured_provider" == "$WEATHER_PROVIDER" ]]; then
        pass weather-provider "$configured_provider"
    else
        fail_check weather-provider "expected $WEATHER_PROVIDER configured $configured_provider"
    fi
    if [[ "$forecast_provider" == open_meteo ]]; then
        pass forecast-provider 'open_meteo'
    else
        fail_check forecast-provider "expected open_meteo configured $forecast_provider"
    fi
    if [[ "$secret_present" == false ]]; then
        pass weather-secret 'no API secret stored in config.json'
    else
        fail_check weather-secret 'Weather Underground secret-like field exists in config.json'
    fi

    if [[ "$WEATHER_PROVIDER" == weather-underground ]]; then
        if [[ -n "$wu_station" ]]; then
            pass wu-station "$wu_station"
        else
            fail_check wu-station 'station_id is empty'
        fi
        if [[ "$wu_key_env" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
            pass wu-key-env "$wu_key_env (name only)"
        else
            fail_check wu-key-env "invalid environment variable name: $wu_key_env"
        fi
        if [[ "$ROOT" == / ]]; then
            if [[ -n "$WU_KEY_FILE" ]] && valid_wu_key_file "$WU_KEY_FILE"; then
                pass wu-credential 'credential file is readable and structurally valid (value hidden)'
            elif [[ -n "${!wu_key_env:-}" ]]; then
                pass wu-credential "$wu_key_env is set in verifier environment (value hidden)"
            elif managed_wu_credential_configured; then
                pass wu-credential 'managed root-owned credential is configured (value hidden)'
            else
                fail_check wu-credential 'managed Weather Underground credential is not configured or its restricted status helper is unavailable'
            fi
        fi
    else
        if [[ "$ecowitt_path" == /* && "$ecowitt_path" != *'?'* && "$ecowitt_path" != *'#'* ]]; then
            pass ecowitt-path "$ecowitt_path"
        else
            fail_check ecowitt-path "invalid path: $ecowitt_path"
        fi
    fi
fi

if [[ "$ROOT" == / ]]; then
    echo
echo 'Live runtime/API:'
    for unit in plexamp.service shairport-sync.service a-clockwork-plex.service a-clockwork-plex-airplay-metadata.service; do
        if systemctl is-active --quiet "$unit"; then
            pass "service:$unit" active
        else
            fail_check "service:$unit" inactive
        fi
        enabled="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
        if [[ "$enabled" == enabled || "$enabled" == static ]]; then
            pass "enable:$unit" "$enabled"
        else
            fail_check "enable:$unit" "${enabled:-unknown}"
        fi
    done

    mixer_helper_json="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-mixer-helper.XXXXXX")"
    state_json="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-api-state.XXXXXX")"
    weather_json="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-weather-state.XXXXXX")"
    eq_json="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-eq-state.XXXXXX")"
    mixer_api_json="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-mixer-api.XXXXXX")"
    trap 'rm -f "$mixer_helper_json" "$state_json" "$weather_json" "$eq_json" "$mixer_api_json"' EXIT

    if sudo -n "$MIXER_HELPER" status >"$mixer_helper_json" 2>/dev/null && validate_mixer_payload "$mixer_helper_json"; then
        pass mixer-runtime 'helper reports master/Plexamp/AirPlay/alarm controls ready'
    else
        fail_check mixer-runtime 'restricted mixer helper is unavailable or reports incomplete controls/PCMs'
    fi

    if curl -fsS "$DASHBOARD_URL/api/state" -o "$state_json"; then
        pass dashboard-api '/api/state HTTP success'
    else
        fail_check dashboard-api '/api/state unavailable'
    fi

    if curl -fsS "$DASHBOARD_URL/api/weather/observations" -o "$weather_json"; then
        if python3 - "$weather_json" "$WEATHER_PROVIDER" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
expected = sys.argv[2]
actual = payload.get("provider") if isinstance(payload, dict) else None
actual = {"ecowitt_push": "ecowitt-push", "weather_underground": "weather-underground"}.get(actual, actual)
state = payload.get("status") if isinstance(payload, dict) else None
allowed = {"ecowitt-push": {"push"}, "weather-underground": {"ready", "pending", "degraded"}}
raise SystemExit(0 if actual == expected and state in allowed[expected] else 1)
PY
        then
            pass weather-api "provider=$WEATHER_PROVIDER status acceptable"
        else
            fail_check weather-api 'provider/status does not match selected observation profile'
        fi
    else
        fail_check weather-api '/api/weather/observations unavailable'
    fi

    if curl -fsS "$DASHBOARD_URL/api/audio/eq" -o "$eq_json"; then
        if python3 - "$eq_json" "$AUDIO_PROFILE" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
profile = sys.argv[2]
eq = payload.get("eq") if isinstance(payload, dict) else None
if not isinstance(eq, dict):
    eq = payload if isinstance(payload, dict) else {}
installed = eq.get("installed") is True
if profile == "direct":
    raise SystemExit(0 if not installed else 1)
raise SystemExit(0 if installed and eq.get("configured") is True else 1)
PY
        then
            pass eq-api "truthful for $AUDIO_PROFILE profile"
        else
            fail_check eq-api "does not match $AUDIO_PROFILE installation"
        fi
    else
        fail_check eq-api '/api/audio/eq unavailable'
    fi

    if curl -fsS "$DASHBOARD_URL/api/audio/mixer" -o "$mixer_api_json"; then
        if validate_mixer_payload "$mixer_api_json"; then
            pass mixer-api 'master/Plexamp/AirPlay/alarm controls available'
        else
            fail_check mixer-api '/api/audio/mixer reports incomplete controls/PCMs'
        fi
    else
        fail_check mixer-api '/api/audio/mixer unavailable'
    fi

    rm -f "$mixer_helper_json" "$state_json" "$weather_json" "$eq_json" "$mixer_api_json"
    trap - EXIT
else
    echo
    warn_check live-runtime 'skipped for alternate-root non-production verification'
fi

echo
printf 'Failures: %d\nWarnings: %d\n' "$FAILURES" "$WARNINGS"
echo 'No production file, package, service, route, mixer, PCM or configuration was changed.'
if [[ "$FAILURES" -eq 0 ]]; then
    echo 'APPLIANCE_VERIFY=PASS'
    exit 0
fi
echo 'APPLIANCE_VERIFY=FAIL'
exit 1
