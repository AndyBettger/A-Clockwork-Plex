#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ACP_REPO_ROOT="$REPO_ROOT"

source "$REPO_ROOT/installer/lib/common.sh"
source "$REPO_ROOT/installer/lib/services.sh"
source "$REPO_ROOT/installer/lib/audio.sh"

REQUESTED_ROOT=/

usage() {
    cat <<'EOF_USAGE'
Usage: scripts/audio/verify-audio.sh [options]

Options:
  --root PATH    Alternate filesystem root for non-production tests.
  -h, --help     Show this help.

Verification is read-only. Under the production root it checks the installed
manifest, fixed helpers, ALSA routes, CamillaDSP binary/configuration, loopback
contract, route state and managed service status. Under an alternate root it
checks only the installed filesystem contract and never calls systemd.
EOF_USAGE
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --root)
                [[ $# -ge 2 ]] || { acp_error '--root requires a path.'; return 64; }
                REQUESTED_ROOT="$2"
                shift 2
                ;;
            -h|--help)
                usage
                return 2
                ;;
            *)
                acp_error "Unknown option: $1"
                usage >&2
                return 64
                ;;
        esac
    done
}

check_python_source() {
    local source="$1"
    python3 - "$source" <<'PY_CHECK'
from pathlib import Path
import sys
path = Path(sys.argv[1])
compile(path.read_text(encoding='utf-8'), str(path), 'exec')
PY_CHECK
}

verify_filesystem() {
    local failures=0 marker state module source
    marker="$(acp_path '/var/lib/a-clockwork-plex/split-bus/installed')" || return 1
    state="$(acp_path '/var/lib/a-clockwork-plex/split-bus/master-eq.json')" || return 1

    [[ -f "$marker" && "$(cat "$marker")" == eq-split-bus ]] || {
        acp_error 'The EQ-capable installed marker is missing or invalid.'
        failures=$((failures + 1))
    }
    acp_verify_install_manifest || {
        acp_error 'The installed file manifest does not match the filesystem.'
        failures=$((failures + 1))
    }
    python3 - "$state" <<'PY_STATE' || failures=$((failures + 1))
from pathlib import Path
import json
import sys
path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding='utf-8'))
assert payload.get('schema_version') == 2
assert isinstance(payload.get('bypassed'), bool)
bands = payload.get('bands')
assert isinstance(bands, dict)
assert set(bands) == {'bass', 'mid', 'treble'}
for value in bands.values():
    number = float(value)
    assert -6.0 <= number <= 6.0
    assert round(number * 2) == number * 2
PY_STATE

    for source in \
        "$(acp_path '/usr/local/bin/a-clockwork-plex-audio-route')" \
        "$(acp_path '/usr/local/bin/a-clockwork-plex-audio-eq')"; do
        check_python_source "$source" || failures=$((failures + 1))
    done
    for module in __init__.py model.py runtime.py cli.py; do
        source="$(acp_path "/usr/local/lib/a-clockwork-plex/audio-eq/audio_eq_camilladsp/$module")" || \
            { failures=$((failures + 1)); continue; }
        check_python_source "$source" || failures=$((failures + 1))
    done
    [[ "$failures" -eq 0 ]]
}

verify_production_runtime() {
    local route_helper=/usr/local/bin/a-clockwork-plex-audio-route
    local eq_helper=/usr/local/bin/a-clockwork-plex-audio-eq
    local failures=0

    "$route_helper" validate || failures=$((failures + 1))
    "$route_helper" status || failures=$((failures + 1))
    "$eq_helper" status || failures=$((failures + 1))
    systemctl is-enabled --quiet a-clockwork-plex-audio-route.service || \
        failures=$((failures + 1))
    systemctl is-enabled --quiet a-clockwork-plex-camilladsp.service || \
        failures=$((failures + 1))
    [[ "$failures" -eq 0 ]]
}

main() {
    parse_args "$@"
    local parsed=$?
    [[ "$parsed" -eq 2 ]] && return 0
    [[ "$parsed" -eq 0 ]] || return "$parsed"

    ACP_ROOT="$(acp_normalise_root "$REQUESTED_ROOT")" || return 1
    export ACP_ROOT ACP_REPO_ROOT
    for command in sha256sum stat python3; do
        acp_require_command "$command" || return 1
    done

    verify_filesystem || return 1
    if acp_is_production_root; then
        acp_require_command systemctl || return 1
        verify_production_runtime || return 1
    fi
    acp_log 'EQ-capable audio verification passed.'
}

main "$@"
