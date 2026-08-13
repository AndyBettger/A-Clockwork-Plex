#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=installer/lib/packages.sh
source "$REPO_ROOT/installer/lib/packages.sh"

MODE=prepare-only
CONFIRM=
ROOT="${ACP_ROOT:-/}"
AUDIO_PROFILE="${ACP_AUDIO_PROFILE:-eq}"
WEATHER_PROVIDER="${ACP_WEATHER_OBSERVATIONS:-ecowitt-push}"
CONFIRM_TOKEN=INSTALL-APPLIANCE-PACKAGES

usage() {
    cat <<EOF
Usage: bash scripts/install-appliance-packages.sh [options]

Guarded package/Python-environment bootstrap owner. Prepare-only is the default.

Options:
  --prepare-only
  --activate --confirm $CONFIRM_TOKEN
  --audio direct|eq
  --weather-observations ecowitt-push|weather-underground
  --root PATH       alternate filesystem root for non-production venv tests;
                    APT mutation is never performed for an alternate root
  -h, --help

Rollback policy:
  * Debian/Raspberry Pi OS packages are additive bootstrap prerequisites. Packages
    installed successfully by this owner are NOT automatically removed/purged or
    autoremoved on a later failure because that could damage shared host state.
  * The main repository venv and NFC system-site-packages venv are both staged and
    verified completely before either live directory is replaced.
  * If either venv activation/verification fails, both exact previous directories
    are restored (or both new directories are removed where previously absent).
  * After this bootstrap owner succeeds, package and both venv states form the
    prerequisite baseline for the later whole-appliance application transaction.
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
        --audio)
            [[ $# -ge 2 ]] || { error '--audio requires a profile.'; exit 64; }
            AUDIO_PROFILE="$2"; shift 2 ;;
        --weather-observations)
            [[ $# -ge 2 ]] || { error '--weather-observations requires a provider.'; exit 64; }
            WEATHER_PROVIDER="$2"; shift 2 ;;
        --root)
            [[ $# -ge 2 ]] || { error '--root requires a path.'; exit 64; }
            ROOT="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) error "Unknown option: $1"; usage >&2; exit 64 ;;
    esac
done

case "$AUDIO_PROFILE" in direct|eq) ;; *) error "Unsupported audio profile: $AUDIO_PROFILE"; exit 64 ;; esac
case "$WEATHER_PROVIDER" in ecowitt-push|weather-underground) ;; *) error "Unsupported weather provider: $WEATHER_PROVIDER"; exit 64 ;; esac

if [[ "$ROOT" != / ]]; then
    ROOT="${ROOT%/}"
    [[ -d "$ROOT" ]] || { error "Alternate root does not exist: $ROOT"; exit 1; }
    PROJECT_ROOT="$ROOT/project"
else
    PROJECT_ROOT="$REPO_ROOT"
fi
VENV_TARGET="$PROJECT_ROOT/venv"
NFC_VENV_TARGET="$PROJECT_ROOT/nfc-venv"
REQUIREMENTS="$REPO_ROOT/requirements.txt"
NFC_REQUIREMENTS="$REPO_ROOT/vendor/plexamp-nfc-listener/requirements.txt"

[[ -d "$PROJECT_ROOT" && ! -L "$PROJECT_ROOT" ]] || {
    error "Project root is unavailable or unsafe: $PROJECT_ROOT"
    exit 1
}
for requirements_file in "$REQUIREMENTS" "$NFC_REQUIREMENTS"; do
    [[ -f "$requirements_file" && ! -L "$requirements_file" ]] || {
        error "Requirements file is unavailable or unsafe: $requirements_file"
        exit 1
    }
done

if [[ "$MODE" == activate ]]; then
    [[ "$CONFIRM" == "$CONFIRM_TOKEN" ]] || {
        error "Activation requires --confirm $CONFIRM_TOKEN."
        exit 64
    }
elif [[ -n "$CONFIRM" ]]; then
    error '--confirm is only valid with --activate.'
    exit 64
fi

run_package_gate() {
    local args=(
        --audio "$AUDIO_PROFILE"
        --weather-observations "$WEATHER_PROVIDER"
    )
    if [[ "$ROOT" != / ]]; then
        args+=(--source-only)
    fi
    bash "$REPO_ROOT/scripts/check-appliance-packages.sh" "${args[@]}"
}

cat <<EOF
A Clockwork Plex package + venv bootstrap plan

Mode:                 $MODE
Filesystem root:      $ROOT
Project root:         $PROJECT_ROOT
Main venv target:     $VENV_TARGET
NFC venv target:      $NFC_VENV_TARGET
Audio profile:        $AUDIO_PROFILE
Weather observations: $WEATHER_PROVIDER

APT policy:
  package installation is additive prerequisite bootstrap;
  rollback never runs apt remove, purge or autoremove.

Venv policy:
  build complete main and NFC candidates first; the NFC candidate uses
  --system-site-packages so Raspberry Pi OS python3-lgpio is visible. Verify both
  candidates before a paired live swap. A later failure restores both exact
  previous venv directories or their exact previous absence.
EOF

echo
run_package_gate

if [[ "$MODE" == prepare-only ]]; then
    echo
    echo 'Prepare-only complete. No package, venv, service, route, mixer, PCM or configuration was changed.'
    exit 0
fi
[[ "$MODE" == activate ]] || { error "Unsupported mode: $MODE"; exit 64; }

if [[ "$ROOT" == / ]]; then
    [[ "$EUID" -ne 0 ]] || {
        error 'Run this installer as the normal project user, not as root.'
        exit 1
    }
    for command in sudo apt-get dpkg-query python3 mktemp mv rm; do
        command -v "$command" >/dev/null 2>&1 || { error "Required command not found: $command"; exit 1; }
    done
    if [[ -n "${ACP_PACKAGES_TEST_PYTHON:-}" ]]; then
        error 'ACP_PACKAGES_TEST_PYTHON is forbidden on the production root.'
        exit 1
    fi
    PYTHON_BIN=python3

    missing_packages=()
    while IFS= read -r package; do
        if ! dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -Fqx 'install ok installed'; then
            missing_packages+=("$package")
        fi
    done < <(acp_required_apt_packages)

    if [[ "${#missing_packages[@]}" -gt 0 ]]; then
        echo
        printf 'Installing missing additive prerequisites:'
        printf ' %s' "${missing_packages[@]}"
        echo
        sudo -- apt-get update
        sudo -- apt-get install -y --no-install-recommends "${missing_packages[@]}"
    else
        echo
        echo 'All owned APT prerequisites are already installed; no APT mutation required.'
    fi

    echo
    run_package_gate
else
    [[ -n "${ACP_PACKAGES_TEST_PYTHON:-}" ]] || {
        error 'Alternate-root activation requires ACP_PACKAGES_TEST_PYTHON; APT is never simulated implicitly.'
        exit 1
    }
    [[ -x "$ACP_PACKAGES_TEST_PYTHON" && ! -L "$ACP_PACKAGES_TEST_PYTHON" ]] || {
        error 'ACP_PACKAGES_TEST_PYTHON must be an executable regular file.'
        exit 1
    }
    PYTHON_BIN="$ACP_PACKAGES_TEST_PYTHON"
    echo
    echo 'Alternate-root activation: APT mutation skipped by design; testing paired venv transaction only.'
fi

for target in "$VENV_TARGET" "$NFC_VENV_TARGET"; do
    if [[ -e "$target" || -L "$target" ]]; then
        [[ -d "$target" && ! -L "$target" ]] || {
            error "Existing venv target is not a safe directory: $target"
            exit 1
        }
    fi
done

STAGE_PARENT="$(mktemp -d "$PROJECT_ROOT/.acp-package-stage.XXXXXX")"
APP_CANDIDATE="$STAGE_PARENT/venv.candidate"
NFC_CANDIDATE="$STAGE_PARENT/nfc-venv.candidate"
APP_PREVIOUS="$STAGE_PARENT/venv.previous"
NFC_PREVIOUS="$STAGE_PARENT/nfc-venv.previous"
APP_PREVIOUS_PRESENT=false
NFC_PREVIOUS_PRESENT=false
APP_SWAPPED=false
NFC_SWAPPED=false

cleanup() {
    rm -rf -- "$STAGE_PARENT"
}
trap cleanup EXIT

restore_previous_venvs() {
    set +e
    if [[ "$APP_SWAPPED" == true && -d "$VENV_TARGET" ]]; then
        rm -rf -- "$VENV_TARGET"
    fi
    if [[ "$NFC_SWAPPED" == true && -d "$NFC_VENV_TARGET" ]]; then
        rm -rf -- "$NFC_VENV_TARGET"
    fi
    if [[ "$APP_PREVIOUS_PRESENT" == true && -d "$APP_PREVIOUS" ]]; then
        [[ ! -e "$VENV_TARGET" ]] || rm -rf -- "$VENV_TARGET"
        mv -- "$APP_PREVIOUS" "$VENV_TARGET"
    fi
    if [[ "$NFC_PREVIOUS_PRESENT" == true && -d "$NFC_PREVIOUS" ]]; then
        [[ ! -e "$NFC_VENV_TARGET" ]] || rm -rf -- "$NFC_VENV_TARGET"
        mv -- "$NFC_PREVIOUS" "$NFC_VENV_TARGET"
    fi
}

fail_venvs() {
    local message="$1"
    error "$message"
    restore_previous_venvs
    error 'Main/NFC venv prestates restored; additive APT prerequisites, if installed, are intentionally retained.'
    exit 1
}

echo
echo 'Building staged main Python environment...'
"$PYTHON_BIN" -m venv "$APP_CANDIDATE" || fail_venvs 'Failed to create staged main venv.'
[[ -x "$APP_CANDIDATE/bin/python" ]] || fail_venvs 'Staged main venv did not provide executable bin/python.'
"$APP_CANDIDATE/bin/python" -m pip install --disable-pip-version-check -r "$REQUIREMENTS" || fail_venvs 'Main requirements.txt installation failed in staged venv.'
"$APP_CANDIDATE/bin/python" -m pip check || fail_venvs 'pip check failed in staged main venv.'
"$APP_CANDIDATE/bin/python" -c 'import flask; print("Flask", flask.__version__ if hasattr(flask, "__version__") else "import-ok")' || fail_venvs 'Flask import verification failed in staged main venv.'

echo
echo 'Building staged NFC Python environment with system site packages...'
"$PYTHON_BIN" -m venv --system-site-packages "$NFC_CANDIDATE" || fail_venvs 'Failed to create staged NFC venv.'
[[ -x "$NFC_CANDIDATE/bin/python" ]] || fail_venvs 'Staged NFC venv did not provide executable bin/python.'
"$NFC_CANDIDATE/bin/python" -m pip install --disable-pip-version-check -r "$NFC_REQUIREMENTS" || fail_venvs 'NFC requirements installation failed in staged venv.'
"$NFC_CANDIDATE/bin/python" -m pip check || fail_venvs 'pip check failed in staged NFC venv.'
if [[ "$ROOT" == / ]]; then
    "$NFC_CANDIDATE/bin/python" -c 'import lgpio, board, busio, requests; from adafruit_pn532.i2c import PN532_I2C' || fail_venvs 'NFC hardware-library import verification failed in staged venv.'
else
    "$NFC_CANDIDATE/bin/python" -c 'import requests' || fail_venvs 'Alternate-root NFC candidate verification failed.'
fi

# Both candidates are complete before any live venv moves.
if [[ -d "$VENV_TARGET" ]]; then
    mv -- "$VENV_TARGET" "$APP_PREVIOUS" || fail_venvs 'Could not preserve the previous main venv.'
    APP_PREVIOUS_PRESENT=true
fi
if [[ -d "$NFC_VENV_TARGET" ]]; then
    mv -- "$NFC_VENV_TARGET" "$NFC_PREVIOUS" || fail_venvs 'Could not preserve the previous NFC venv.'
    NFC_PREVIOUS_PRESENT=true
fi
mv -- "$APP_CANDIDATE" "$VENV_TARGET" || fail_venvs 'Could not activate the staged main venv.'
APP_SWAPPED=true
mv -- "$NFC_CANDIDATE" "$NFC_VENV_TARGET" || fail_venvs 'Could not activate the staged NFC venv.'
NFC_SWAPPED=true

if [[ "$ROOT" != / && "${ACP_PACKAGES_TEST_FAIL_AFTER_SWAP:-0}" == 1 ]]; then
    fail_venvs 'Injected non-production failure after paired venv swap.'
fi

"$VENV_TARGET/bin/python" -m pip check || fail_venvs 'Activated main venv failed pip check.'
"$VENV_TARGET/bin/python" -c 'import flask' || fail_venvs 'Activated main venv failed Flask import verification.'
"$NFC_VENV_TARGET/bin/python" -m pip check || fail_venvs 'Activated NFC venv failed pip check.'
if [[ "$ROOT" == / ]]; then
    "$NFC_VENV_TARGET/bin/python" -c 'import lgpio, board, busio, requests; from adafruit_pn532.i2c import PN532_I2C' || fail_venvs 'Activated NFC venv failed hardware-library import verification.'
else
    "$NFC_VENV_TARGET/bin/python" -c 'import requests' || fail_venvs 'Activated alternate-root NFC venv failed verification.'
fi

APP_SWAPPED=false
NFC_SWAPPED=false
rm -rf -- "$APP_PREVIOUS" "$NFC_PREVIOUS"

echo
echo '[A Clockwork Plex] Package/main/NFC venv bootstrap completed successfully.'
echo 'APT_ROLLBACK_POLICY=RETAIN-ADDITIVE-PREREQUISITES'
echo 'VENV_ROLLBACK_POLICY=EXACT-PAIRED-PRESTATE-ON-STAGE-FAILURE'
echo 'NFC_VENV_SYSTEM_SITE_PACKAGES=REQUIRED'
