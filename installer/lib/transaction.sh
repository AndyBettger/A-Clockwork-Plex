#!/bin/bash

# Shared whole-appliance transaction primitives.
#
# This library deliberately contains no automatic component list and no root
# installer entrypoint. The orchestrator must explicitly name every path/service
# it owns before mutation. Filesystem capture/restore works under ACP_ROOT for
# non-production tests; live service capture/restore is production-root only.

if [[ -z "${ACP_REPO_ROOT:-}" ]]; then
    ACP_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi

# shellcheck source=installer/lib/common.sh
source "$ACP_REPO_ROOT/installer/lib/common.sh"

ACP_TRANSACTION_SCHEMA_VERSION=1

acp_transaction_validate_directory() {
    local directory="$1"
    [[ "$directory" == /* ]] || {
        acp_error "Transaction directory must be absolute: $directory"
        return 1
    }
    [[ "$directory" != / ]] || {
        acp_error 'Transaction directory must not be /.'
        return 1
    }
}

acp_transaction_begin() {
    local directory="$1"
    acp_transaction_validate_directory "$directory" || return 1
    [[ ! -e "$directory" ]] || {
        acp_error "Transaction directory already exists: $directory"
        return 1
    }
    mkdir -p "$directory/files" || return 1
    chmod 0700 "$directory" "$directory/files" || return 1
    printf 'schema_version=%s\n' "$ACP_TRANSACTION_SCHEMA_VERSION" >"$directory/meta"
    printf 'path\tstate\tsha256\tmode\tuid\tgid\tbackup_key\n' >"$directory/paths.tsv"
    printf 'unit\tactive\tenabled\n' >"$directory/services.tsv"
}

acp_transaction_path_key() {
    printf '%s' "$1" | sha256sum | awk '{print $1}'
}

acp_transaction_capture_path() {
    local directory="$1" logical="$2" path key hash mode uid gid
    acp_transaction_validate_directory "$directory" || return 1
    [[ -f "$directory/paths.tsv" ]] || {
        acp_error "Transaction has not been initialised: $directory"
        return 1
    }
    [[ "$logical" == /* ]] || {
        acp_error "Captured path must be absolute: $logical"
        return 1
    }
    if awk -F '\t' -v wanted="$logical" 'NR > 1 && $1 == wanted { found=1 } END { exit !found }' "$directory/paths.tsv"; then
        acp_error "Transaction path was captured twice: $logical"
        return 1
    fi

    path="$(acp_path "$logical")" || return 1
    key="$(acp_transaction_path_key "$logical")" || return 1

    if acp_run_root test -L "$path"; then
        acp_error "Symlink capture is intentionally unsupported: $logical"
        return 1
    elif acp_run_root test -f "$path"; then
        hash="$(acp_run_root sha256sum "$path" | awk '{print $1}')" || return 1
        mode="$(acp_run_root stat -c '%a' "$path")" || return 1
        uid="$(acp_run_root stat -c '%u' "$path")" || return 1
        gid="$(acp_run_root stat -c '%g' "$path")" || return 1
        acp_run_root cp -p -- "$path" "$directory/files/$key" || return 1
        printf '%s\tfile\t%s\t%s\t%s\t%s\t%s\n' \
            "$logical" "$hash" "$mode" "$uid" "$gid" "$key" >>"$directory/paths.tsv"
    elif acp_run_root test -e "$path"; then
        acp_error "Only regular files or absent paths may be captured: $logical"
        return 1
    else
        printf '%s\tabsent\t-\t-\t-\t-\t%s\n' "$logical" "$key" >>"$directory/paths.tsv"
    fi
}

acp_transaction_restore_paths() {
    local directory="$1" logical state hash mode uid gid key path observed failures=0
    acp_transaction_validate_directory "$directory" || return 1
    [[ -f "$directory/paths.tsv" ]] || return 1

    while IFS=$'\t' read -r logical state hash mode uid gid key; do
        [[ "$logical" == path ]] && continue
        path="$(acp_path "$logical")" || { failures=$((failures + 1)); continue; }
        case "$state" in
            file)
                if ! acp_run_root install -D -m "$mode" "$directory/files/$key" "$path"; then
                    failures=$((failures + 1))
                    continue
                fi
                if acp_is_production_root; then
                    acp_run_root chown "$uid:$gid" "$path" || failures=$((failures + 1))
                fi
                observed="$(acp_run_root sha256sum "$path" | awk '{print $1}')" || observed=''
                [[ "$observed" == "$hash" ]] || failures=$((failures + 1))
                ;;
            absent)
                acp_remove_file "$logical" || failures=$((failures + 1))
                ;;
            *)
                acp_error "Unknown transaction path state '$state' for $logical"
                failures=$((failures + 1))
                ;;
        esac
    done < <(tail -n +2 "$directory/paths.tsv" | tac)

    [[ "$failures" -eq 0 ]]
}

acp_transaction_capture_service() {
    local directory="$1" unit="$2" active enabled
    acp_transaction_validate_directory "$directory" || return 1
    acp_is_production_root || {
        acp_error 'Live service capture is only valid on the production root.'
        return 1
    }
    [[ "$unit" =~ ^[A-Za-z0-9_.@-]+\.service$ ]] || {
        acp_error "Invalid systemd unit name: $unit"
        return 1
    }
    if awk -F '\t' -v wanted="$unit" 'NR > 1 && $1 == wanted { found=1 } END { exit !found }' "$directory/services.tsv"; then
        acp_error "Transaction service was captured twice: $unit"
        return 1
    fi
    active=false
    systemctl is-active --quiet "$unit" && active=true
    enabled="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
    [[ -n "$enabled" ]] || enabled=unknown
    printf '%s\t%s\t%s\n' "$unit" "$active" "$enabled" >>"$directory/services.tsv"
}

acp_transaction_restore_services() {
    local directory="$1" unit active enabled failures=0
    acp_transaction_validate_directory "$directory" || return 1
    acp_is_production_root || {
        acp_error 'Live service restoration is only valid on the production root.'
        return 1
    }
    [[ -f "$directory/services.tsv" ]] || return 1

    while IFS=$'\t' read -r unit active enabled; do
        [[ "$unit" == unit ]] && continue
        case "$enabled" in
            enabled)
                sudo -- systemctl enable "$unit" >/dev/null || failures=$((failures + 1))
                ;;
            disabled)
                sudo -- systemctl disable "$unit" >/dev/null || failures=$((failures + 1))
                ;;
            static|indirect|generated|alias|masked|masked-runtime|transient|unknown|not-found)
                ;;
            *)
                acp_error "Unrecognised saved enablement '$enabled' for $unit"
                failures=$((failures + 1))
                ;;
        esac
        if [[ "$active" == true ]]; then
            sudo -- systemctl start "$unit" || failures=$((failures + 1))
        elif [[ "$active" == false ]]; then
            sudo -- systemctl stop "$unit" || failures=$((failures + 1))
        else
            acp_error "Unrecognised saved activity '$active' for $unit"
            failures=$((failures + 1))
        fi
    done < <(tail -n +2 "$directory/services.tsv" | tac)

    [[ "$failures" -eq 0 ]]
}

acp_transaction_mark_complete() {
    local directory="$1"
    acp_transaction_validate_directory "$directory" || return 1
    [[ -f "$directory/meta" ]] || return 1
    printf 'complete\n' >"$directory/complete"
}
