#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

MODE=prepare-only
CONFIRM=
CONFIRM_TOKEN=INSTALL-WEATHER-CONFIG
ROOT="${ACP_ROOT:-/}"
PROVIDER="${ACP_WEATHER_OBSERVATIONS:-ecowitt-push}"
WU_STATION_ID="${ACP_WU_STATION_ID:-}"
WU_API_KEY_FILE="${ACP_WU_API_KEY_FILE:-}"
WEATHER_ENV_NAME=WEATHER_UNDERGROUND_API_KEY

usage() {
    cat <<EOF
Usage: bash scripts/install-weather-config.sh [options]

Guarded weather observation-provider configuration owner. Prepare-only is the default.
Open-Meteo forecast configuration is preserved and this owner never restarts services.

Options:
  --prepare-only
  --activate --confirm $CONFIRM_TOKEN
  --provider ecowitt-push|weather-underground
  --wu-station-id ID       required when selecting Weather Underground
  --wu-api-key-file PATH   secret file; required for Weather Underground activation
  --root PATH              alternate filesystem root for non-production transaction tests
  -h, --help

Secrets:
  Weather Underground API keys are never accepted as literal command-line values and
  are never written to config.json. Production storage is:
    /etc/default/a-clockwork-plex-weather
  exported as $WEATHER_ENV_NAME with mode 0600.

Rollback:
  config.json and the managed weather environment file are restored to their exact
  previous bytes/existence if activation fails. No service state is owned here.
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
        --provider)
            [[ $# -ge 2 ]] || { error '--provider requires a provider.'; exit 64; }
            PROVIDER="$2"; shift 2 ;;
        --wu-station-id)
            [[ $# -ge 2 ]] || { error '--wu-station-id requires a station ID.'; exit 64; }
            WU_STATION_ID="$2"; shift 2 ;;
        --wu-api-key-file)
            [[ $# -ge 2 ]] || { error '--wu-api-key-file requires a path.'; exit 64; }
            WU_API_KEY_FILE="$2"; shift 2 ;;
        --root)
            [[ $# -ge 2 ]] || { error '--root requires a path.'; exit 64; }
            ROOT="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) error "Unknown option: $1"; usage >&2; exit 64 ;;
    esac
done

case "$PROVIDER" in
    ecowitt-push) RUNTIME_PROVIDER=ecowitt_push ;;
    weather-underground) RUNTIME_PROVIDER=weather_underground ;;
    *) error "Unsupported weather provider: $PROVIDER"; exit 64 ;;
esac

if [[ "$MODE" == activate ]]; then
    [[ "$CONFIRM" == "$CONFIRM_TOKEN" ]] || {
        error "Activation requires --confirm $CONFIRM_TOKEN."
        exit 64
    }
elif [[ -n "$CONFIRM" ]]; then
    error '--confirm is only valid with --activate.'
    exit 64
fi

if [[ "$PROVIDER" == weather-underground ]]; then
    [[ "$WU_STATION_ID" =~ ^[A-Za-z0-9_-]+$ ]] || {
        error 'Weather Underground requires --wu-station-id using letters, digits, underscore or hyphen.'
        exit 64
    }
    if [[ "$MODE" == activate ]]; then
        [[ -n "$WU_API_KEY_FILE" ]] || {
            error 'Weather Underground activation requires --wu-api-key-file PATH.'
            exit 64
        }
    fi
elif [[ -n "$WU_STATION_ID" || -n "$WU_API_KEY_FILE" ]]; then
    error 'Weather Underground station/key options are only valid with --provider weather-underground.'
    exit 64
fi

if [[ "$ROOT" != / ]]; then
    ROOT="${ROOT%/}"
    [[ -d "$ROOT" && ! -L "$ROOT" ]] || { error "Alternate root is unavailable or unsafe: $ROOT"; exit 1; }
    PROJECT_ROOT="$ROOT/project"
    WEATHER_ENV_FILE="$ROOT/etc/default/a-clockwork-plex-weather"
else
    PROJECT_ROOT="$REPO_ROOT"
    WEATHER_ENV_FILE=/etc/default/a-clockwork-plex-weather
fi
CONFIG_FILE="$PROJECT_ROOT/config.json"
CONFIG_TEMPLATE="$REPO_ROOT/config.example.json"

[[ -d "$PROJECT_ROOT" && ! -L "$PROJECT_ROOT" ]] || {
    error "Project root is unavailable or unsafe: $PROJECT_ROOT"
    exit 1
}
[[ -f "$CONFIG_TEMPLATE" && ! -L "$CONFIG_TEMPLATE" ]] || {
    error "config.example.json is unavailable or unsafe: $CONFIG_TEMPLATE"
    exit 1
}
if [[ -e "$CONFIG_FILE" || -L "$CONFIG_FILE" ]]; then
    [[ -f "$CONFIG_FILE" && ! -L "$CONFIG_FILE" ]] || {
        error "config.json is unavailable or unsafe: $CONFIG_FILE"
        exit 1
    }
fi
if [[ -e "$WEATHER_ENV_FILE" || -L "$WEATHER_ENV_FILE" ]]; then
    [[ -f "$WEATHER_ENV_FILE" && ! -L "$WEATHER_ENV_FILE" ]] || {
        error "Managed weather environment path is unavailable or unsafe: $WEATHER_ENV_FILE"
        exit 1
    }
fi

for command in python3 mktemp cp mv rm mkdir chmod; do
    command -v "$command" >/dev/null 2>&1 || { error "Required command not found: $command"; exit 1; }
done

if [[ "$MODE" == activate && "$ROOT" == / ]]; then
    [[ "$EUID" -eq 0 ]] || {
        error 'Production activation must run as root because the managed secret lives under /etc/default.'
        exit 1
    }
    if [[ "${ACP_WEATHER_TEST_FAIL_AFTER_CONFIG:-0}" != 0 || "${ACP_WEATHER_TEST_FAIL_AFTER_SECRET:-0}" != 0 ]]; then
        error 'Weather failure-injection controls are forbidden on the production root.'
        exit 1
    fi
fi

if [[ "$PROVIDER" == weather-underground && -n "$WU_API_KEY_FILE" ]]; then
    [[ -f "$WU_API_KEY_FILE" && ! -L "$WU_API_KEY_FILE" && -r "$WU_API_KEY_FILE" ]] || {
        error 'Weather Underground API-key file must be a readable regular file, not a symlink.'
        exit 1
    }
fi

SOURCE_CONFIG="$CONFIG_FILE"
if [[ ! -e "$SOURCE_CONFIG" ]]; then
    SOURCE_CONFIG="$CONFIG_TEMPLATE"
fi

STAGE_PARENT="$(mktemp -d "$PROJECT_ROOT/.acp-weather-stage.XXXXXX")"
CANDIDATE_CONFIG="$STAGE_PARENT/config.json.candidate"
CANDIDATE_ENV="$STAGE_PARENT/weather.env.candidate"
CONFIG_BACKUP="$STAGE_PARENT/config.json.previous"
ENV_BACKUP="$STAGE_PARENT/weather.env.previous"
CONFIG_PRESENT=false
ENV_PRESENT=false
MUTATION_STARTED=false
SUCCESS=false

cleanup() {
    rm -rf -- "$STAGE_PARENT"
}

restore_prestate() {
    set +e
    if [[ "$MUTATION_STARTED" != true ]]; then
        return
    fi
    if [[ "$CONFIG_PRESENT" == true ]]; then
        cp -a -- "$CONFIG_BACKUP" "$CONFIG_FILE"
    else
        rm -f -- "$CONFIG_FILE"
    fi
    if [[ "$ENV_PRESENT" == true ]]; then
        mkdir -p -- "$(dirname "$WEATHER_ENV_FILE")"
        cp -a -- "$ENV_BACKUP" "$WEATHER_ENV_FILE"
    else
        rm -f -- "$WEATHER_ENV_FILE"
    fi
}

on_exit() {
    local rc=$?
    if [[ "$SUCCESS" != true && "$MUTATION_STARTED" == true ]]; then
        restore_prestate
        error 'Weather configuration activation failed; exact managed pre-state was restored.'
    fi
    cleanup
    exit "$rc"
}
trap on_exit EXIT

python3 - "$SOURCE_CONFIG" "$CANDIDATE_CONFIG" "$RUNTIME_PROVIDER" "$WU_STATION_ID" <<'PY'
import json
import os
import sys

source, destination, provider, station_id = sys.argv[1:]
with open(source, "r", encoding="utf-8") as handle:
    config = json.load(handle)
if not isinstance(config, dict):
    raise SystemExit("config root must be a JSON object")

weather = config.setdefault("weather", {})
if not isinstance(weather, dict):
    raise SystemExit("weather configuration must be a JSON object")
weather["provider"] = provider

# Remove historical inline-secret shapes even when they are not selected. The
# application runtime accepts only an environment-variable reference.
for section_name in ("weather_underground", "wunderground"):
    section = weather.get(section_name)
    if isinstance(section, dict):
        section.pop("api_key", None)

if provider == "weather_underground":
    section = weather.setdefault("weather_underground", {})
    if not isinstance(section, dict):
        raise SystemExit("weather.weather_underground must be a JSON object")
    section["station_id"] = station_id.strip().upper()
    section["api_key_env"] = "WEATHER_UNDERGROUND_API_KEY"

with open(destination, "w", encoding="utf-8") as handle:
    json.dump(config, handle, indent=2, ensure_ascii=False)
    handle.write("\n")
PY

if [[ "$PROVIDER" == weather-underground && -n "$WU_API_KEY_FILE" ]]; then
    python3 - "$WU_API_KEY_FILE" "$CANDIDATE_ENV" <<'PY'
import os
import sys

source, destination = sys.argv[1:]
with open(source, "rb") as handle:
    raw = handle.read()
raw = raw.rstrip(b"\r\n")
if not raw:
    raise SystemExit("Weather Underground API key is empty")
if b"\x00" in raw or b"\n" in raw or b"\r" in raw:
    raise SystemExit("Weather Underground API key must be a single line without NUL bytes")
try:
    key = raw.decode("utf-8")
except UnicodeDecodeError as exc:
    raise SystemExit("Weather Underground API key must be UTF-8 text") from exc
if not key.strip():
    raise SystemExit("Weather Underground API key is blank")
escaped = key.replace("\\", "\\\\").replace('"', '\\"')
with open(destination, "w", encoding="utf-8") as handle:
    handle.write(f'WEATHER_UNDERGROUND_API_KEY="{escaped}"\n')
os.chmod(destination, 0o600)
PY
fi

cat <<EOF
A Clockwork Plex weather configuration plan

Mode:                  $MODE
Filesystem root:       $ROOT
Project configuration: $CONFIG_FILE
Observation provider:  $RUNTIME_PROVIDER
Forecast configuration: preserved unchanged
Managed secret file:   $WEATHER_ENV_FILE
Service restart:       not owned by this component
EOF
if [[ "$PROVIDER" == weather-underground ]]; then
    echo "Weather Underground station: ${WU_STATION_ID^^}"
    if [[ -n "$WU_API_KEY_FILE" ]]; then
        echo 'Weather Underground secret: validated from file; value not displayed'
    else
        echo 'Weather Underground secret: required for activation; no value supplied in prepare-only mode'
    fi
else
    echo 'Weather Underground secret: managed file will be absent after successful activation'
fi

if [[ "$MODE" == prepare-only ]]; then
    echo
    echo 'Prepare-only complete. No configuration, secret, service, route, mixer or PCM was changed.'
    SUCCESS=true
    exit 0
fi
[[ "$MODE" == activate ]] || { error "Unsupported mode: $MODE"; exit 64; }

if [[ -e "$CONFIG_FILE" ]]; then
    cp -a -- "$CONFIG_FILE" "$CONFIG_BACKUP"
    CONFIG_PRESENT=true
fi
if [[ -e "$WEATHER_ENV_FILE" ]]; then
    cp -a -- "$WEATHER_ENV_FILE" "$ENV_BACKUP"
    ENV_PRESENT=true
fi

MUTATION_STARTED=true
mkdir -p -- "$(dirname "$CONFIG_FILE")"
cp -- "$CANDIDATE_CONFIG" "$CONFIG_FILE.new"
if [[ "$CONFIG_PRESENT" == true ]]; then
    chmod --reference="$CONFIG_BACKUP" "$CONFIG_FILE.new"
    if [[ "$ROOT" == / ]]; then
        chown --reference="$CONFIG_BACKUP" "$CONFIG_FILE.new"
    fi
else
    chmod 0644 "$CONFIG_FILE.new"
    if [[ "$ROOT" == / ]]; then
        chown --reference="$PROJECT_ROOT" "$CONFIG_FILE.new"
    fi
fi
mv -f -- "$CONFIG_FILE.new" "$CONFIG_FILE"

if [[ "$ROOT" != / && "${ACP_WEATHER_TEST_FAIL_AFTER_CONFIG:-0}" == 1 ]]; then
    error 'Injected non-production failure after config.json mutation.'
    exit 1
fi

if [[ "$PROVIDER" == weather-underground ]]; then
    mkdir -p -- "$(dirname "$WEATHER_ENV_FILE")"
    cp -- "$CANDIDATE_ENV" "$WEATHER_ENV_FILE.new"
    chmod 0600 "$WEATHER_ENV_FILE.new"
    if [[ "$ROOT" == / ]]; then
        chown root:root "$WEATHER_ENV_FILE.new"
    fi
    mv -f -- "$WEATHER_ENV_FILE.new" "$WEATHER_ENV_FILE"
else
    rm -f -- "$WEATHER_ENV_FILE"
fi

if [[ "$ROOT" != / && "${ACP_WEATHER_TEST_FAIL_AFTER_SECRET:-0}" == 1 ]]; then
    error 'Injected non-production failure after managed-secret mutation.'
    exit 1
fi

python3 - "$CONFIG_FILE" "$RUNTIME_PROVIDER" "$WU_STATION_ID" "$WEATHER_ENV_FILE" <<'PY'
import json
import os
import stat
import sys

config_path, provider, station_id, env_path = sys.argv[1:]
with open(config_path, "r", encoding="utf-8") as handle:
    config = json.load(handle)
weather = config.get("weather")
if not isinstance(weather, dict) or weather.get("provider") != provider:
    raise SystemExit("activated weather provider verification failed")
for section_name in ("weather_underground", "wunderground"):
    section = weather.get(section_name)
    if isinstance(section, dict) and "api_key" in section:
        raise SystemExit("inline Weather Underground API key survived activation")
if provider == "weather_underground":
    section = weather.get("weather_underground")
    if not isinstance(section, dict):
        raise SystemExit("Weather Underground configuration missing after activation")
    if section.get("station_id") != station_id.strip().upper():
        raise SystemExit("Weather Underground station verification failed")
    if section.get("api_key_env") != "WEATHER_UNDERGROUND_API_KEY":
        raise SystemExit("Weather Underground environment-variable reference verification failed")
    if not os.path.isfile(env_path) or os.path.islink(env_path):
        raise SystemExit("managed Weather Underground secret file is unavailable")
    if stat.S_IMODE(os.stat(env_path).st_mode) != 0o600:
        raise SystemExit("managed Weather Underground secret file mode is not 0600")
else:
    if os.path.exists(env_path) or os.path.islink(env_path):
        raise SystemExit("managed Weather Underground secret survived Ecowitt activation")
PY

SUCCESS=true
echo
echo '[A Clockwork Plex] Weather observation-provider configuration completed successfully.'
echo "WEATHER_PROVIDER=$RUNTIME_PROVIDER"
echo 'WEATHER_FORECAST=OPEN-METEO-PRESERVED'
echo 'WEATHER_SECRET_POLICY=ENV-FILE-ONLY'
echo 'WEATHER_ROLLBACK_POLICY=EXACT-MANAGED-PRESTATE-ON-FAILURE'
