#!/bin/bash

acp_copy_root_file_to_temporary() {
    local source="$1" temporary="$2"
    [[ -f "$source" ]] || return 1
    acp_run_root cat -- "$source" >"$temporary"
}

acp_verify_installed_files() {
    local manifest temporary destination expected mode path observed observed_mode failures=0
    manifest="$(acp_path '/var/lib/a-clockwork-plex/split-bus/install-manifest.tsv')" || return 1
    temporary="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-manifest-read.XXXXXX")" || return 1
    if ! acp_copy_root_file_to_temporary "$manifest" "$temporary"; then
        rm -f "$temporary"
        return 1
    fi

    while IFS=$'\t' read -r destination expected mode; do
        [[ "$destination" == destination ]] && continue
        path="$(acp_path "$destination")" || { failures=$((failures + 1)); continue; }
        if [[ ! -f "$path" ]]; then
            failures=$((failures + 1))
            continue
        fi
        observed="$(acp_run_root sha256sum "$path" | awk '{print $1}')" || observed=''
        observed_mode="$(acp_run_root stat -c '%a' "$path")" || observed_mode=''
        [[ "$observed" == "$expected" && "$observed_mode" == "$mode" ]] || \
            failures=$((failures + 1))
    done <"$temporary"
    rm -f "$temporary"
    [[ "$failures" -eq 0 ]]
}

acp_validate_eq_state_file() {
    local state temporary
    state="$(acp_path '/var/lib/a-clockwork-plex/split-bus/master-eq.json')" || return 1
    temporary="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-eq-state-read.XXXXXX")" || return 1
    if ! acp_copy_root_file_to_temporary "$state" "$temporary"; then
        rm -f "$temporary"
        return 1
    fi
    python3 - "$temporary" <<'PY_STATE'
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
    local result=$?
    rm -f "$temporary"
    return "$result"
}
