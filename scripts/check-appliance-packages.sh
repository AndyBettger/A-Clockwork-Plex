#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=installer/lib/packages.sh
source "$REPO_ROOT/installer/lib/packages.sh"

MODE=host
AUDIO_PROFILE=eq
WEATHER_PROVIDER=ecowitt-push
FAILURES=0

usage() {
    cat <<'EOF'
Usage: bash scripts/check-appliance-packages.sh [options]

Read-only package/artifact ownership check. It never runs apt update/install,
pip install, downloads artifacts or changes services/configuration.

Options:
  --audio direct|eq
  --weather-observations ecowitt-push|weather-underground
  --source-only    print the package/artifact contract without probing this host
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
        --source-only)
            MODE=source
            shift
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

case "$AUDIO_PROFILE" in direct|eq) ;; *) echo "Unsupported audio profile: $AUDIO_PROFILE" >&2; exit 64 ;; esac
case "$WEATHER_PROVIDER" in ecowitt-push|weather-underground) ;; *) echo "Unsupported weather provider: $WEATHER_PROVIDER" >&2; exit 64 ;; esac

cat <<EOF
A Clockwork Plex package/artifact report

Mode:                 $MODE
Audio profile:        $AUDIO_PROFILE
Weather observations: $WEATHER_PROVIDER
EOF

echo
acp_package_plan "$AUDIO_PROFILE" "$WEATHER_PROVIDER"

if [[ "$MODE" == source ]]; then
    cat <<'EOF'

No host package state was probed in source-only mode.
No package, Python environment, artifact, service or configuration was changed.
APPLIANCE_PACKAGE_CHECK=SOURCE-PASS
EOF
    exit 0
fi

for command in dpkg-query apt-cache; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "FAIL: required read-only package query command is missing: $command"
        FAILURES=$((FAILURES + 1))
    fi
done

if [[ "$FAILURES" -ne 0 ]]; then
    echo "APPLIANCE_PACKAGE_CHECK=FAIL"
    exit 1
fi

echo
echo 'Package state:'
while IFS= read -r package; do
    if dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -Fqx 'install ok installed'; then
        version="$(dpkg-query -W -f='${Version}' "$package" 2>/dev/null || true)"
        printf 'PASS  %-18s installed %s\n' "$package" "$version"
    elif apt-cache show "$package" >/dev/null 2>&1; then
        printf 'READY %-18s available but not installed\n' "$package"
    else
        printf 'FAIL  %-18s unavailable from current APT metadata\n' "$package"
        FAILURES=$((FAILURES + 1))
    fi
done < <(acp_required_apt_packages)

echo
if [[ -f "$REPO_ROOT/requirements.txt" && ! -L "$REPO_ROOT/requirements.txt" ]]; then
    echo 'PASS  requirements.txt   repository Python dependency manifest present'
else
    echo 'FAIL  requirements.txt   missing or unsafe'
    FAILURES=$((FAILURES + 1))
fi

if [[ "$AUDIO_PROFILE" == eq ]]; then
    echo 'INFO  CamillaDSP          supplied/verified artifact; not downloaded by this check'
else
    echo 'INFO  CamillaDSP          not required for Direct audio'
fi

echo 'INFO  Plexamp Headless    external prerequisite; not installed by this repository'

cat <<'EOF'

No package, Python environment, artifact, service or configuration was changed.
EOF
if [[ "$FAILURES" -eq 0 ]]; then
    echo 'APPLIANCE_PACKAGE_CHECK=PASS'
    exit 0
fi
echo 'APPLIANCE_PACKAGE_CHECK=FAIL'
exit 1
