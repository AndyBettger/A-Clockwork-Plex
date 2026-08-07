#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ACP_REPO_ROOT="$REPO_ROOT"

source "$REPO_ROOT/installer/lib/common.sh"
source "$REPO_ROOT/installer/lib/services.sh"
source "$REPO_ROOT/installer/lib/audio.sh"
source "$REPO_ROOT/installer/lib/verification.sh"

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

check_root_text_equals() {
    local source="$1" expected="$2" temporary observed result=0
    temporary="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-text-read.XXXXXX")" || return 1
    if ! acp_copy_root_file_to_temporary "$source" "$temporary"; then
        rm -f "$temporary"
        return 1
    fi
    observed="$(cat "$temporary")" || result=1
    rm -f "$temporary"
    [[ "$result" -eq 0 && "$observed" == "$expected" ]]
}

check_python_source() {
    local source="$1" temporary result
    temporary="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-python-read.XXXXXX")" || return 1
    if ! acp_copy_root_file_to_temporary "$source" "$temporary"; then
        rm -f "$temporary"
        return 1
    fi
    python3 - "$temporary" <<'PY_CHECK'
from pathlib import Path
import sys
path = Path(sys.argv[1])
compile(path.read_text(encoding='utf-8'), str(path), 'exec')
PY_CHECK
    result=$?
    rm -f "$temporary"
    return "$result"
}

validate_route_payload() {
    local source="$1" payload_kind="$2"
    python3 - "$source" "$payload_kind" <<'PY_ROUTE'
from pathlib import Path
import json
import sys

source = Path(sys.argv[1])
kind = sys.argv[2]
payload = json.loads(source.read_text(encoding='utf-8'))
assert isinstance(payload, dict)
assert payload.get('ok') is True

if kind == 'validate':
    assert isinstance(payload.get('checks'), dict)
    assert payload.get('errors') == []
    loopback = payload['checks'].get('loopback')
    assert isinstance(loopback, dict)
    assert loopback.get('ok') is True
elif kind == 'status':
    assert payload.get('mode') == 'split-bus-active'
    assert payload.get('selected_mode') in {'split-bus-selected', 'split-bus-active'}
    assert payload.get('active_matches_split') is True
    assert payload.get('installed_marker') is True
    loopback = payload.get('loopback')
    assert isinstance(loopback, dict)
    assert loopback.get('ok') is True
    assert isinstance(payload.get('services'), dict)
else:
    raise AssertionError(f'unknown route payload kind: {kind}')
PY_ROUTE
}

validate_eq_payload() {
    local source="$1"
    python3 - "$source" <<'PY_EQ'
from pathlib import Path
import json
import sys

source = Path(sys.argv[1])
payload = json.loads(source.read_text(encoding='utf-8'))
assert isinstance(payload, dict)
assert payload.get('ok') is True
assert payload.get('available') is True
assert payload.get('installed') is True
assert payload.get('configured') is True
assert payload.get('mode') == 'master-three-band'
assert payload.get('backend') == 'camilladsp'
assert payload.get('backend_state') == 'split-bus-active'
assert isinstance(payload.get('bypassed'), bool)
bands = payload.get('bands')
assert isinstance(bands, dict)
assert set(bands) == {'bass', 'mid', 'treble'}
for band in bands.values():
    assert isinstance(band, dict)
    assert band.get('available') is True
    stored = float(band['stored_db'])
    applied = float(band['applied_db'])
    assert -6.0 <= stored <= 6.0
    assert -6.0 <= applied <= 6.0
PY_EQ
}

verify_filesystem() {
    local failures=0 marker module source
    marker="$(acp_path '/var/lib/a-clockwork-plex/split-bus/installed')" || return 1

    check_root_text_equals "$marker" eq-split-bus || {
        acp_error 'The EQ-capable installed marker is missing or invalid.'
        failures=$((failures + 1))
    }
    acp_verify_installed_files || {
        acp_error 'The installed file manifest does not match the filesystem.'
        failures=$((failures + 1))
    }
    acp_validate_eq_state_file || {
        acp_error 'The saved EQ state is missing or invalid.'
        failures=$((failures + 1))
    }

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
    local route_validation route_status eq_status failures=0

    route_validation="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-route-validate.XXXXXX")" || return 1
    route_status="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-route-status.XXXXXX")" || {
        rm -f "$route_validation"
        return 1
    }
    eq_status="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-eq-status.XXXXXX")" || {
        rm -f "$route_validation" "$route_status"
        return 1
    }

    if ! "$route_helper" validate >"$route_validation"; then
        failures=$((failures + 1))
    elif ! validate_route_payload "$route_validation" validate; then
        failures=$((failures + 1))
    fi
    if ! "$route_helper" status >"$route_status"; then
        failures=$((failures + 1))
    elif ! validate_route_payload "$route_status" status; then
        failures=$((failures + 1))
    fi
    if ! "$eq_helper" status >"$eq_status"; then
        failures=$((failures + 1))
    elif ! validate_eq_payload "$eq_status"; then
        failures=$((failures + 1))
    fi

    systemctl is-enabled --quiet a-clockwork-plex-audio-route.service || \
        failures=$((failures + 1))
    systemctl is-enabled --quiet a-clockwork-plex-camilladsp.service || \
        failures=$((failures + 1))

    rm -f "$route_validation" "$route_status" "$eq_status"
    [[ "$failures" -eq 0 ]]
}

main() {
    parse_args "$@"
    local parsed=$?
    [[ "$parsed" -eq 2 ]] && return 0
    [[ "$parsed" -eq 0 ]] || return "$parsed"

    ACP_ROOT="$(acp_normalise_root "$REQUESTED_ROOT")" || return 1
    export ACP_ROOT ACP_REPO_ROOT
    for command in cat mktemp sha256sum stat python3; do
        acp_require_command "$command" || return 1
    done

    verify_filesystem || return 1
    if acp_is_production_root; then
        for command in sudo systemctl; do
            acp_require_command "$command" || return 1
        done
        verify_production_runtime || return 1
    fi
    acp_log 'EQ-capable audio verification passed.'
}

main "$@"
