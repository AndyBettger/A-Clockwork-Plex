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
  * The repository venv is staged completely before replacement. If venv activation
    fails, its exact previous directory is restored by same-filesystem rename (or
    the new venv is removed when none existed before).
  * After this bootstrap owner succeeds, package and venv state form the prerequisite
    baseline for the later whole-appliance application transaction.
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
REQUIREMENTS="$REPO_ROOT/requirements.txt"

[[ -d "$PROJECT_ROOT" && ! -L "$PROJECT_ROOT" ]] || {
    error "Project root is unavailable or unsafe: $PROJECT_ROOT"
    exit 1
}
[[ -f "$REQUIREMENTS" && ! -L "$REQUIREMENTS" ]] || {
    error "requirements.txt is unavailable or unsafe: $REQUIREMENTS"
    exit 1
}

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
Venv target:          $VENV_TARGET
Audio profile:        $AUDIO_PROFILE
Weather observations: $WEATHER_PROVIDER

APT policy:
  package installation is additive prerequisite bootstrap;
  rollback never runs apt remove, purge or autoremove.

Venv policy:
  build a complete candidate first, run pip check/import verification, then use
  a same-filesystem rename swap so a failed activation can restore the exact
  prior venv directory (or exact prior absence).
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
    echo 'Alternate-root activation: APT mutation skipped by design; testing venv transaction only.'
fi

if [[ -e "$VENV_TARGET" || -L "$VENV_TARGET" ]]; then
    [[ -d "$VENV_TARGET" && ! -L "$VENV_TARGET" ]] || {
        error "Existing venv target is not a safe directory: $VENV_TARGET"
        exit 1
    }
fi

STAGE_PARENT="$(mktemp -d "$PROJECT_ROOT/.acp-package-stage.XXXXXX")"
CANDIDATE="$STAGE_PARENT/venv.candidate"
PREVIOUS="$STAGE_PARENT/venv.previous"
PREVIOUS_PRESENT=false
SWAPPED=false

cleanup() {
    rm -rf -- "$STAGE_PARENT"
}
trap cleanup EXIT

restore_previous_venv() {
    set +e
    if [[ "$SWAPPED" == true && -e "$VENV_TARGET" ]]; then
        rm -rf -- "$VENV_TARGET"
    fi
    if [[ "$PREVIOUS_PRESENT" == true && -d "$PREVIOUS" ]]; then
        mv -- "$PREVIOUS" "$VENV_TARGET"
    fi
}

fail_venv() {
    local message="$1"
    error "$message"
    restore_previous_venv
    error 'Venv pre-state restored; additive APT prerequisites, if installed, are intentionally retained.'
    exit 1
}

echo
echo 'Building staged Python environment...'
"$PYTHON_BIN" -m venv "$CANDIDATE" || fail_venv 'Failed to create staged venv.'
[[ -x "$CANDIDATE/bin/python" ]] || fail_venv 'Staged venv did not provide executable bin/python.'
"$CANDIDATE/bin/python" -m pip install --disable-pip-version-check -r "$REQUIREMENTS" || fail_venv 'requirements.txt installation failed in staged venv.'
"$CANDIDATE/bin/python" -m pip check || fail_venv 'pip check failed in staged venv.'
"$CANDIDATE/bin/python" -c 'import flask; print("Flask", flask.__version__ if hasattr(flask, "__version__") else "import-ok")' || fail_venv 'Flask import verification failed in staged venv.'

if [[ -d "$VENV_TARGET" ]]; then
    mv -- "$VENV_TARGET" "$PREVIOUS" || fail_venv 'Could not preserve the previous venv.'
    PREVIOUS_PRESENT=true
fi
mv -- "$CANDIDATE" "$VENV_TARGET" || fail_venv 'Could not activate the staged venv.'
SWAPPED=true

if [[ "$ROOT" != / && "${ACP_PACKAGES_TEST_FAIL_AFTER_SWAP:-0}" == 1 ]]; then
    fail_venv 'Injected non-production failure after venv swap.'
fi

"$VENV_TARGET/bin/python" -m pip check || fail_venv 'Activated venv failed pip check.'
"$VENV_TARGET/bin/python" -c 'import flask' || fail_venv 'Activated venv failed Flask import verification.'

SWAPPED=false
rm -rf -- "$PREVIOUS"

echo
echo '[A Clockwork Plex] Package/venv bootstrap completed successfully.'
echo 'APT_ROLLBACK_POLICY=RETAIN-ADDITIVE-PREREQUISITES'
echo 'VENV_ROLLBACK_POLICY=EXACT-PRESTATE-ON-STAGE-FAILURE'
