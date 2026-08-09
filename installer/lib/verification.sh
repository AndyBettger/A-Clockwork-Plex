#!/bin/bash

# Manifest creation and verification live here because installed files may sit
# beneath protected directories such as /etc/sudoers.d. Production inspection
# must therefore use the same fixed sudo boundary as installation.

ACP_RUNTIME_MANIFEST_HASH='runtime-generated'

acp_manifest_destination_is_runtime_mutable() {
    [[ "$1" == '/etc/a-clockwork-plex/camilladsp-split-bus.yml' ]]
}

acp_write_install_manifest() {
    local manifest temporary destination path hash mode
    manifest="$(acp_path '/var/lib/a-clockwork-plex/split-bus/install-manifest.tsv')" || return 1
    temporary="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-install-manifest.XXXXXX")" || return 1
    printf 'destination\tsha256\tmode\n' >"$temporary"
    while IFS= read -r destination; do
        path="$(acp_path "$destination")" || { rm -f "$temporary"; return 1; }
        if ! acp_run_root test -f "$path"; then
            acp_error "Installed file is missing: $path"
            rm -f "$temporary"
            return 1
        fi
        if acp_manifest_destination_is_runtime_mutable "$destination"; then
            hash="$ACP_RUNTIME_MANIFEST_HASH"
        else
            hash="$(acp_run_root sha256sum "$path" | awk '{print $1}')" || { rm -f "$temporary"; return 1; }
        fi
        mode="$(acp_run_root stat -c '%a' "$path")" || { rm -f "$temporary"; return 1; }
        printf '%s\t%s\t%s\n' "$destination" "$hash" "$mode" >>"$temporary"
    done < <(acp_managed_file_destinations)
    if ! acp_run_root install -D -m 0600 "$temporary" "$manifest"; then
        rm -f "$temporary"
        return 1
    fi
    rm -f "$temporary"
}

acp_copy_root_file_to_temporary() {
    local source="$1" temporary="$2"
    acp_run_root test -f "$source" || return 1
    acp_run_root cat -- "$source" >"$temporary"
}

acp_verify_install_manifest() {
    acp_verify_installed_files
}

acp_verify_installed_files() {
    local manifest temporary destination expected mode path observed observed_mode failures=0
    local require_hash
    manifest="$(acp_path '/var/lib/a-clockwork-plex/split-bus/install-manifest.tsv')" || return 1
    temporary="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-manifest-read.XXXXXX")" || return 1
    if ! acp_copy_root_file_to_temporary "$manifest" "$temporary"; then
        acp_error "Installed manifest is missing or unreadable: $manifest"
        rm -f "$temporary"
        return 1
    fi

    while IFS=$'\t' read -r destination expected mode; do
        [[ "$destination" == destination ]] && continue
        path="$(acp_path "$destination")" || { failures=$((failures + 1)); continue; }
        if ! acp_run_root test -f "$path"; then
            acp_error "Installed managed file is missing: $path"
            failures=$((failures + 1))
            continue
        fi

        observed_mode="$(acp_run_root stat -c '%a' "$path")" || observed_mode=''
        if [[ "$observed_mode" != "$mode" ]]; then
            acp_error "Installed managed file mode mismatch: $path (expected $mode, observed ${observed_mode:-unreadable})"
            failures=$((failures + 1))
        fi

        require_hash=true
        if acp_manifest_destination_is_runtime_mutable "$destination"; then
            # The live CamillaDSP configuration is rendered from master-eq.json
            # whenever the saved EQ/bypass state changes. New manifests mark that
            # row explicitly as runtime-generated. On production systems, accept
            # older manifests that still contain the install-time concrete hash so
            # a legitimate runtime EQ change does not masquerade as file damage.
            if [[ "$expected" == "$ACP_RUNTIME_MANIFEST_HASH" ]] || acp_is_production_root; then
                require_hash=false
            fi
        fi

        if [[ "$require_hash" == true ]]; then
            observed="$(acp_run_root sha256sum "$path" | awk '{print $1}')" || observed=''
            if [[ "$observed" != "$expected" ]]; then
                acp_error "Installed managed file hash mismatch: $path (expected $expected, observed ${observed:-unreadable})"
                failures=$((failures + 1))
            fi
        fi
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
