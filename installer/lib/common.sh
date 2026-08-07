#!/bin/bash

# Shared filesystem and reporting helpers for the supported installer path.
# Callers decide whether failures are fatal; these helpers do not enable shell
# errexit or execute caller-provided command strings.

acp_log() {
    printf '[A Clockwork Plex] %s\n' "$*"
}

acp_error() {
    printf '[A Clockwork Plex] ERROR: %s\n' "$*" >&2
}

acp_require_command() {
    command -v "$1" >/dev/null 2>&1 || {
        acp_error "Required command not found: $1"
        return 1
    }
}

acp_normalise_root() {
    local requested="${1:-/}"
    case "$requested" in
        /*) ;;
        *)
            acp_error "Installer root must be an absolute path: $requested"
            return 1
            ;;
    esac
    if [[ "$requested" != "/" ]]; then
        requested="${requested%/}"
        [[ -n "$requested" ]] || requested="/"
    fi
    printf '%s\n' "$requested"
}

acp_path() {
    local destination="$1"
    [[ "$destination" == /* ]] || {
        acp_error "Managed destination must be absolute: $destination"
        return 1
    }
    if [[ "${ACP_ROOT:-/}" == "/" ]]; then
        printf '%s\n' "$destination"
    else
        printf '%s%s\n' "${ACP_ROOT%/}" "$destination"
    fi
}

acp_is_production_root() {
    [[ "${ACP_ROOT:-/}" == "/" ]]
}

acp_run_root() {
    if acp_is_production_root; then
        sudo -- "$@"
    else
        "$@"
    fi
}

acp_make_directory() {
    local destination mode
    destination="$(acp_path "$1")" || return 1
    mode="$2"
    acp_run_root install -d -m "$mode" "$destination"
}

acp_install_file() {
    local source="$1" destination mode
    destination="$(acp_path "$2")" || return 1
    mode="$3"
    [[ -f "$source" && ! -L "$source" ]] || {
        acp_error "Install source is not a regular file: $source"
        return 1
    }
    acp_run_root install -D -m "$mode" "$source" "$destination"
}

acp_install_text() {
    local content="$1" destination="$2" mode="$3" temporary
    temporary="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-install-text.XXXXXX")" || return 1
    printf '%s' "$content" >"$temporary"
    if ! acp_install_file "$temporary" "$destination" "$mode"; then
        rm -f "$temporary"
        return 1
    fi
    rm -f "$temporary"
}

acp_remove_file() {
    local destination
    destination="$(acp_path "$1")" || return 1
    if [[ -e "$destination" || -L "$destination" ]]; then
        acp_run_root rm -f -- "$destination"
    fi
}

acp_copy_preserving() {
    local source destination
    source="$(acp_path "$1")" || return 1
    destination="$(acp_path "$2")" || return 1
    [[ -f "$source" && ! -L "$source" ]] || {
        acp_error "Backup source is not a regular file: $source"
        return 1
    }
    acp_run_root install -d -m 0755 "$(dirname "$destination")" || return 1
    acp_run_root cp -p -- "$source" "$destination"
}

acp_sha256() {
    local path
    path="$(acp_path "$1")" || return 1
    [[ -f "$path" ]] || return 1
    sha256sum "$path" | awk '{print $1}'
}

acp_write_operation_log() {
    local message="$1" destination
    destination="$(acp_path '/var/lib/a-clockwork-plex/split-bus/last-operation.log')" || return 1
    acp_run_root install -d -m 0755 "$(dirname "$destination")" || return 1
    acp_install_text "$(date --iso-8601=seconds) $message\n" \
        '/var/lib/a-clockwork-plex/split-bus/last-operation.log' 0644
}
