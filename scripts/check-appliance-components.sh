#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ACP_REPO_ROOT="$REPO_ROOT"
# shellcheck source=installer/lib/components.sh
source "$REPO_ROOT/installer/lib/components.sh"

ROOT=/
REQUESTED_COMPONENT=all

usage() {
    cat <<'EOF'
Usage: bash scripts/check-appliance-components.sh [options]

Read-only adapter for appliance components that do not own a native check mode.
It inspects source and installed-path state but never installs, removes, chmods,
chowns, restarts or reloads anything.

Options:
  --component NAME   airplay-hooks, airplay-metadata, alarm-audio-helper,
                     shairport-name-helper, or all (default)
  --root PATH        alternate filesystem root for non-production checks
  -h, --help         show this help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --component)
            [[ $# -ge 2 ]] || { echo '--component requires a value.' >&2; exit 64; }
            REQUESTED_COMPONENT="$2"
            shift 2
            ;;
        --root)
            [[ $# -ge 2 ]] || { echo '--root requires a path.' >&2; exit 64; }
            ROOT="$2"
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

if [[ "$ROOT" != / ]]; then
    ROOT="${ROOT%/}"
    [[ -d "$ROOT" ]] || { echo "Alternate root does not exist: $ROOT" >&2; exit 1; }
fi

root_path() {
    local path="$1"
    if [[ "$ROOT" == / ]]; then
        printf '%s\n' "$path"
    else
        printf '%s%s\n' "$ROOT" "$path"
    fi
}

copy_state() {
    local source="$1" target="$2"
    if [[ ! -e "$target" ]]; then
        printf 'missing'
    elif [[ ! -f "$target" || -L "$target" ]]; then
        printf 'unexpected-type'
    elif cmp -s "$source" "$target"; then
        printf 'current'
    elif [[ -r "$target" ]]; then
        printf 'different'
    else
        printf 'present-protected'
    fi
}

present_state() {
    local target="$1"
    if [[ ! -e "$target" ]]; then
        printf 'missing'
    elif [[ -L "$target" ]]; then
        printf 'unexpected-symlink'
    else
        printf 'present'
    fi
}

check_airplay_hooks() {
    local installer="$REPO_ROOT/scripts/install-airplay-integration.sh"
    local renderer="$REPO_ROOT/scripts/a-clockwork-plex-airplay-wrappers.py"
    local start end
    start="$(root_path '/usr/local/bin/a-clockwork-plex-airplay-start')"
    end="$(root_path '/usr/local/bin/a-clockwork-plex-airplay-end')"
    bash -n "$installer"
    [[ -f "$renderer" && ! -L "$renderer" ]] || { echo "Missing wrapper renderer: $renderer" >&2; return 1; }
    echo 'airplay-hooks:'
    printf '  guarded owner:     valid shell\n'
    printf '  wrapper renderer:  present\n'
    printf '  start wrapper:     %s\n' "$(present_state "$start")"
    printf '  end wrapper:       %s\n' "$(present_state "$end")"
    printf '  apply ownership:   scripts/install-airplay-integration.sh (shared guarded owner)\n'
}

check_airplay_metadata() {
    local installer="$REPO_ROOT/scripts/install-airplay-integration.sh"
    local listener="$REPO_ROOT/scripts/airplay-metadata-listener.py"
    local renderer="$REPO_ROOT/scripts/a-clockwork-plex-shairport-integration.py"
    local unit fifo
    unit="$(root_path '/etc/systemd/system/a-clockwork-plex-airplay-metadata.service')"
    fifo="$(root_path '/tmp/shairport-sync-metadata')"
    bash -n "$installer"
    [[ -f "$listener" && ! -L "$listener" ]] || { echo "Missing listener source: $listener" >&2; return 1; }
    [[ -f "$renderer" && ! -L "$renderer" ]] || { echo "Missing Shairport renderer: $renderer" >&2; return 1; }
    echo 'airplay-metadata:'
    printf '  guarded owner:     valid shell\n'
    printf '  listener source:   present\n'
    printf '  config renderer:   present\n'
    printf '  service unit:      %s\n' "$(present_state "$unit")"
    if [[ -p "$fifo" ]]; then
        printf '  metadata FIFO:     fifo\n'
    else
        printf '  metadata FIFO:     %s\n' "$(present_state "$fifo")"
    fi
    printf '  apply ownership:   scripts/install-airplay-integration.sh (shared guarded owner)\n'
}

check_alarm_audio_helper() {
    local installer="$REPO_ROOT/scripts/install-appliance-helpers.sh"
    local source="$REPO_ROOT/scripts/a-clockwork-plex-alarm-audio-helper.sh"
    local target sudoers
    target="$(root_path '/usr/local/bin/a-clockwork-plex-alarm-audio')"
    sudoers="$(root_path '/etc/sudoers.d/a-clockwork-plex-alarm-audio')"
    bash -n "$installer"
    [[ -f "$source" && ! -L "$source" ]] || { echo "Missing helper source: $source" >&2; return 1; }
    echo 'alarm-audio-helper:'
    printf '  guarded packager: valid shell\n'
    printf '  helper target:    %s\n' "$(copy_state "$source" "$target")"
    printf '  sudoers policy:   %s\n' "$(present_state "$sudoers")"
    printf '  apply ownership:  scripts/install-appliance-helpers.sh (guarded)\n'
}

check_shairport_name_helper() {
    local installer="$REPO_ROOT/scripts/install-appliance-helpers.sh"
    local source="$REPO_ROOT/scripts/a-clockwork-plex-shairport-name.py"
    local target sudoers
    target="$(root_path '/usr/local/bin/a-clockwork-plex-shairport-name')"
    sudoers="$(root_path '/etc/sudoers.d/a-clockwork-plex-shairport-name')"
    bash -n "$installer"
    [[ -f "$source" && ! -L "$source" ]] || { echo "Missing helper source: $source" >&2; return 1; }
    echo 'shairport-name-helper:'
    printf '  guarded packager: valid shell\n'
    printf '  helper target:    %s\n' "$(copy_state "$source" "$target")"
    printf '  sudoers policy:   %s\n' "$(present_state "$sudoers")"
    printf '  apply ownership:  scripts/install-appliance-helpers.sh (guarded)\n'
}

check_one() {
    case "$1" in
        airplay-hooks) check_airplay_hooks ;;
        airplay-metadata) check_airplay_metadata ;;
        alarm-audio-helper) check_alarm_audio_helper ;;
        shairport-name-helper) check_shairport_name_helper ;;
        dashboard-service|dashboard-kiosk)
            echo "$1 has a native read-only check mode; use the command reported by install.sh."
            ;;
        *)
            echo "Unsupported component: $1" >&2
            return 64
            ;;
    esac
}

acp_verify_component_sources

echo 'A Clockwork Plex appliance component adapter check'
echo "Filesystem root: $ROOT"
echo

if [[ "$REQUESTED_COMPONENT" == all ]]; then
    for component in airplay-hooks airplay-metadata alarm-audio-helper shairport-name-helper; do
        check_one "$component"
        echo
    done
else
    check_one "$REQUESTED_COMPONENT"
    echo
fi

cat <<'EOF'
This adapter is informational: missing/stale targets are expected on a fresh Pi
and are not repaired here. AirPlay integration and restricted helper packaging
now each have guarded specialist owners; root Phase 7 orchestration still does
not invoke those mutating entrypoints until the whole-appliance boundary exists.

No production file, package, service, route, mixer, PCM or configuration was changed.
COMPONENT_ADAPTER_CHECK=PASS
EOF
