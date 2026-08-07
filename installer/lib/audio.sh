#!/bin/bash

if [[ -z "${ACP_REPO_ROOT:-}" ]]; then
    ACP_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi

ACP_AUDIO_PROFILE="$ACP_REPO_ROOT/installer/profiles/eq-split-bus"
ACP_AUDIO_TEMPLATES="$ACP_REPO_ROOT/installer/templates"
ACP_CAMILLADSP_VERSION=4.1.3
ACP_CAMILLADSP_SHA256=e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa
ACP_ACCEPTED_DIRECT_SHA256=08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9
ACP_ACTIVE_ALSA_DESTINATION=/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf
ACP_BACKUP_DESTINATION=/var/lib/a-clockwork-plex/split-bus/pre-eq-backup

acp_audio_source_files() {
    cat <<EOF_PATHS
$ACP_AUDIO_PROFILE/split-bus.conf
$ACP_AUDIO_PROFILE/direct-alarm-bypass.conf
$ACP_AUDIO_PROFILE/camilladsp-split-bus.yml
$ACP_AUDIO_PROFILE/a-clockwork-plex-split-bus.defaults
$ACP_AUDIO_PROFILE/modules-load.d/a-clockwork-plex-aloop.conf
$ACP_AUDIO_PROFILE/modprobe.d/a-clockwork-plex-aloop.conf
$ACP_AUDIO_PROFILE/systemd/a-clockwork-plex-audio-route.service
$ACP_AUDIO_PROFILE/systemd/a-clockwork-plex-camilladsp.service
$ACP_AUDIO_PROFILE/systemd/a-clockwork-plex-audio-failback.service
$ACP_AUDIO_TEMPLATES/a-clockwork-plex-audio-route.sudoers.in
$ACP_AUDIO_TEMPLATES/a-clockwork-plex-audio-eq.sudoers.in
$ACP_REPO_ROOT/scripts/a-clockwork-plex-audio-route.py
$ACP_REPO_ROOT/scripts/a-clockwork-plex-audio-eq.py
$ACP_REPO_ROOT/scripts/audio_eq_camilladsp/__init__.py
$ACP_REPO_ROOT/scripts/audio_eq_camilladsp/model.py
$ACP_REPO_ROOT/scripts/audio_eq_camilladsp/runtime.py
$ACP_REPO_ROOT/scripts/audio_eq_camilladsp/cli.py
EOF_PATHS
}

acp_verify_audio_sources() {
    local source failures=0
    while IFS= read -r source; do
        [[ -f "$source" && ! -L "$source" ]] || {
            acp_error "Required audio source is unavailable: $source"
            failures=$((failures + 1))
        }
    done < <(acp_audio_source_files)
    [[ "$failures" -eq 0 ]]
}

acp_verify_camilladsp_binary() {
    local binary="$1" observed version
    [[ -f "$binary" && -x "$binary" && ! -L "$binary" ]] || {
        acp_error "CamillaDSP binary is not an executable regular file: $binary"
        return 1
    }
    observed="$(sha256sum "$binary" | awk '{print $1}')" || return 1
    [[ "$observed" == "$ACP_CAMILLADSP_SHA256" ]] || {
        acp_error "CamillaDSP checksum mismatch. Expected $ACP_CAMILLADSP_SHA256, observed $observed"
        return 1
    }
    version="$("$binary" --version 2>&1 | head -n 1)" || return 1
    [[ "$version" == *"$ACP_CAMILLADSP_VERSION"* ]] || {
        acp_error "Unexpected CamillaDSP version: ${version:-unknown}"
        return 1
    }
}

acp_managed_file_destinations() {
    cat <<'EOF_DESTINATIONS'
/etc/a-clockwork-plex/audio-routes/split-bus.conf
/etc/a-clockwork-plex/audio-routes/direct-alarm-bypass.conf
/etc/a-clockwork-plex/camilladsp-split-bus.yml
/etc/default/a-clockwork-plex-split-bus
/etc/modules-load.d/a-clockwork-plex-aloop.conf
/etc/modprobe.d/a-clockwork-plex-aloop.conf
/etc/sudoers.d/a-clockwork-plex-audio-route
/etc/sudoers.d/a-clockwork-plex-audio-eq
/etc/systemd/system/a-clockwork-plex-audio-route.service
/etc/systemd/system/a-clockwork-plex-camilladsp.service
/etc/systemd/system/a-clockwork-plex-audio-failback.service
/usr/local/bin/a-clockwork-plex-audio-route
/usr/local/bin/a-clockwork-plex-audio-eq
/usr/local/lib/a-clockwork-plex/audio-eq/audio_eq_camilladsp/__init__.py
/usr/local/lib/a-clockwork-plex/audio-eq/audio_eq_camilladsp/model.py
/usr/local/lib/a-clockwork-plex/audio-eq/audio_eq_camilladsp/runtime.py
/usr/local/lib/a-clockwork-plex/audio-eq/audio_eq_camilladsp/cli.py
/usr/local/lib/a-clockwork-plex/camilladsp-4.1.3/camilladsp
EOF_DESTINATIONS
}

acp_render_sudoers() {
    local template="$1" project_user="$2"
    [[ "$project_user" =~ ^[A-Za-z0-9_.@-]+$ ]] || {
        acp_error "Invalid project user: $project_user"
        return 1
    }
    sed "s/@PROJECT_USER@/$project_user/g" "$template"
}

acp_validate_sudoers_templates() {
    local project_user="$1" template temporary failures=0
    acp_require_command visudo || return 1
    for template in \
        "$ACP_AUDIO_TEMPLATES/a-clockwork-plex-audio-route.sudoers.in" \
        "$ACP_AUDIO_TEMPLATES/a-clockwork-plex-audio-eq.sudoers.in"; do
        temporary="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-sudoers.XXXXXX")" || return 1
        if ! acp_render_sudoers "$template" "$project_user" >"$temporary"; then
            rm -f "$temporary"
            return 1
        fi
        chmod 0440 "$temporary"
        visudo -cf "$temporary" >/dev/null || failures=$((failures + 1))
        rm -f "$temporary"
    done
    [[ "$failures" -eq 0 ]]
}

acp_install_sudoers() {
    local project_user="$1" rendered
    rendered="$(acp_render_sudoers \
        "$ACP_AUDIO_TEMPLATES/a-clockwork-plex-audio-route.sudoers.in" \
        "$project_user")" || return 1
    acp_install_text "$rendered\n" '/etc/sudoers.d/a-clockwork-plex-audio-route' 0440 || return 1
    rendered="$(acp_render_sudoers \
        "$ACP_AUDIO_TEMPLATES/a-clockwork-plex-audio-eq.sudoers.in" \
        "$project_user")" || return 1
    acp_install_text "$rendered\n" '/etc/sudoers.d/a-clockwork-plex-audio-eq' 0440
}

acp_install_audio_files() {
    local binary="$1" project_user="$2" module
    acp_verify_audio_sources || return 1

    acp_install_file "$ACP_AUDIO_PROFILE/split-bus.conf" \
        '/etc/a-clockwork-plex/audio-routes/split-bus.conf' 0644 || return 1
    acp_install_file "$ACP_AUDIO_PROFILE/direct-alarm-bypass.conf" \
        '/etc/a-clockwork-plex/audio-routes/direct-alarm-bypass.conf' 0644 || return 1
    acp_install_file "$ACP_AUDIO_PROFILE/camilladsp-split-bus.yml" \
        '/etc/a-clockwork-plex/camilladsp-split-bus.yml' 0644 || return 1
    acp_install_file "$ACP_AUDIO_PROFILE/a-clockwork-plex-split-bus.defaults" \
        '/etc/default/a-clockwork-plex-split-bus' 0644 || return 1
    acp_install_file "$ACP_AUDIO_PROFILE/modules-load.d/a-clockwork-plex-aloop.conf" \
        '/etc/modules-load.d/a-clockwork-plex-aloop.conf' 0644 || return 1
    acp_install_file "$ACP_AUDIO_PROFILE/modprobe.d/a-clockwork-plex-aloop.conf" \
        '/etc/modprobe.d/a-clockwork-plex-aloop.conf' 0644 || return 1

    acp_install_file "$ACP_REPO_ROOT/scripts/a-clockwork-plex-audio-route.py" \
        '/usr/local/bin/a-clockwork-plex-audio-route' 0755 || return 1
    acp_install_file "$ACP_REPO_ROOT/scripts/a-clockwork-plex-audio-eq.py" \
        '/usr/local/bin/a-clockwork-plex-audio-eq' 0755 || return 1
    for module in __init__.py model.py runtime.py cli.py; do
        acp_install_file "$ACP_REPO_ROOT/scripts/audio_eq_camilladsp/$module" \
            "/usr/local/lib/a-clockwork-plex/audio-eq/audio_eq_camilladsp/$module" 0644 || return 1
    done

    acp_install_file "$binary" \
        '/usr/local/lib/a-clockwork-plex/camilladsp-4.1.3/camilladsp' 0755 || return 1
    acp_install_sudoers "$project_user" || return 1

    for module in \
        a-clockwork-plex-audio-route.service \
        a-clockwork-plex-camilladsp.service \
        a-clockwork-plex-audio-failback.service; do
        acp_install_file "$ACP_AUDIO_PROFILE/systemd/$module" \
            "/etc/systemd/system/$module" 0644 || return 1
    done

    acp_make_directory '/var/lib/a-clockwork-plex/split-bus' 0755 || return 1
    if [[ ! -f "$(acp_path '/var/lib/a-clockwork-plex/split-bus/master-eq.json')" ]]; then
        acp_install_text '{"schema_version":2,"bypassed":false,"bands":{"bass":0.0,"mid":0.0,"treble":0.0}}\n' \
            '/var/lib/a-clockwork-plex/split-bus/master-eq.json' 0600 || return 1
    fi
}

acp_write_installed_marker() {
    acp_install_text 'eq-split-bus\n' \
        '/var/lib/a-clockwork-plex/split-bus/installed' 0644
}

acp_remove_managed_audio_files() {
    local destination failures=0
    while IFS= read -r destination; do
        acp_remove_file "$destination" || failures=$((failures + 1))
    done < <(acp_managed_file_destinations)
    acp_remove_file '/var/lib/a-clockwork-plex/split-bus/installed' || failures=$((failures + 1))
    [[ "$failures" -eq 0 ]]
}

acp_backup_key() {
    printf '%s' "$1" | sha256sum | awk '{print $1}'
}

acp_verify_initial_direct_route() {
    local active observed
    active="$(acp_path "$ACP_ACTIVE_ALSA_DESTINATION")" || return 1
    [[ -f "$active" && ! -L "$active" ]] || {
        acp_error "The current active ALSA route is not a regular file: $active"
        return 1
    }
    observed="$(sha256sum "$active" | awk '{print $1}')" || return 1
    [[ "$observed" == "$ACP_ACCEPTED_DIRECT_SHA256" ]] || {
        acp_error "Unexpected current ALSA route. Expected $ACP_ACCEPTED_DIRECT_SHA256, observed $observed"
        return 1
    }
}

acp_capture_preinstall_files() {
    local backup active destination path key present hash mode uid gid
    backup="$(acp_path "$ACP_BACKUP_DESTINATION")" || return 1
    active="$(acp_path "$ACP_ACTIVE_ALSA_DESTINATION")" || return 1
    [[ ! -e "$backup/complete" ]] || {
        acp_error "A complete pre-EQ backup already exists: $backup"
        return 1
    }
    acp_verify_initial_direct_route || return 1
    acp_run_root install -d -m 0700 "$backup/files" || return 1
    acp_run_root cp -p -- "$active" "$backup/pre-eq-active-route.conf" || return 1
    sha256sum "$active" | awk '{print $1}' | \
        acp_run_root tee "$backup/pre-eq-active-route.sha256" >/dev/null || return 1
    printf 'destination\tpresent\tsha256\tmode\tuid\tgid\tbackup_key\n' >"${TMPDIR:-/tmp}/a-clockwork-plex-managed-before.$$" || return 1
    local table="${TMPDIR:-/tmp}/a-clockwork-plex-managed-before.$$"
    while IFS= read -r destination; do
        path="$(acp_path "$destination")" || { rm -f "$table"; return 1; }
        key="$(acp_backup_key "$destination")" || { rm -f "$table"; return 1; }
        if [[ -f "$path" && ! -L "$path" ]]; then
            present=true
            hash="$(sha256sum "$path" | awk '{print $1}')" || { rm -f "$table"; return 1; }
            mode="$(stat -c '%a' "$path")" || { rm -f "$table"; return 1; }
            uid="$(stat -c '%u' "$path")" || { rm -f "$table"; return 1; }
            gid="$(stat -c '%g' "$path")" || { rm -f "$table"; return 1; }
            acp_run_root cp -p -- "$path" "$backup/files/$key" || { rm -f "$table"; return 1; }
        elif [[ ! -e "$path" && ! -L "$path" ]]; then
            present=false
            hash=-
            mode=-
            uid=-
            gid=-
        else
            acp_error "Managed path is neither absent nor a regular file: $path"
            rm -f "$table"
            return 1
        fi
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
            "$destination" "$present" "$hash" "$mode" "$uid" "$gid" "$key" >>"$table"
    done < <(acp_managed_file_destinations)
    acp_run_root install -m 0600 "$table" "$backup/managed-before.tsv" || { rm -f "$table"; return 1; }
    rm -f "$table"
    if acp_is_production_root && [[ -d /sys/module/snd_aloop ]]; then
        acp_install_text 'loaded\n' "$ACP_BACKUP_DESTINATION/loopback-before.txt" 0600 || return 1
    else
        acp_install_text 'absent\n' "$ACP_BACKUP_DESTINATION/loopback-before.txt" 0600 || return 1
    fi
    acp_install_text 'complete\n' "$ACP_BACKUP_DESTINATION/complete" 0600
}

acp_restore_preinstall_files() {
    local backup table destination present hash mode uid gid key path restored_hash expected_hash failures=0
    backup="$(acp_path "$ACP_BACKUP_DESTINATION")" || return 1
    table="$backup/managed-before.tsv"
    [[ -f "$backup/complete" && -f "$table" && -f "$backup/pre-eq-active-route.conf" ]] || {
        acp_error "The pre-EQ backup is incomplete: $backup"
        return 1
    }
    while IFS=$'\t' read -r destination present hash mode uid gid key; do
        [[ "$destination" == destination ]] && continue
        path="$(acp_path "$destination")" || { failures=$((failures + 1)); continue; }
        if [[ "$present" == true ]]; then
            if ! acp_run_root install -D -m "$mode" "$backup/files/$key" "$path"; then
                failures=$((failures + 1))
                continue
            fi
            acp_is_production_root && acp_run_root chown "$uid:$gid" "$path" || true
            restored_hash="$(sha256sum "$path" | awk '{print $1}')" || restored_hash=''
            [[ "$restored_hash" == "$hash" ]] || failures=$((failures + 1))
        else
            acp_remove_file "$destination" || failures=$((failures + 1))
        fi
    done <"$table"
    acp_run_root install -D -m "$(stat -c '%a' "$backup/pre-eq-active-route.conf")" \
        "$backup/pre-eq-active-route.conf" "$(acp_path "$ACP_ACTIVE_ALSA_DESTINATION")" || \
        failures=$((failures + 1))
    expected_hash="$(cat "$backup/pre-eq-active-route.sha256")"
    restored_hash="$(acp_sha256 "$ACP_ACTIVE_ALSA_DESTINATION" 2>/dev/null || true)"
    [[ "$restored_hash" == "$expected_hash" ]] || failures=$((failures + 1))
    [[ "$failures" -eq 0 ]]
}

acp_remove_preinstall_backup() {
    local backup
    backup="$(acp_path "$ACP_BACKUP_DESTINATION")" || return 1
    [[ -d "$backup" ]] && acp_run_root rm -rf -- "$backup"
}

acp_write_install_manifest() {
    local manifest temporary destination path hash mode
    manifest="$(acp_path '/var/lib/a-clockwork-plex/split-bus/install-manifest.tsv')" || return 1
    temporary="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-install-manifest.XXXXXX")" || return 1
    printf 'destination\tsha256\tmode\n' >"$temporary"
    while IFS= read -r destination; do
        path="$(acp_path "$destination")" || { rm -f "$temporary"; return 1; }
        [[ -f "$path" ]] || { acp_error "Installed file is missing: $path"; rm -f "$temporary"; return 1; }
        hash="$(sha256sum "$path" | awk '{print $1}')" || { rm -f "$temporary"; return 1; }
        mode="$(stat -c '%a' "$path")" || { rm -f "$temporary"; return 1; }
        printf '%s\t%s\t%s\n' "$destination" "$hash" "$mode" >>"$temporary"
    done < <(acp_managed_file_destinations)
    acp_run_root install -D -m 0600 "$temporary" "$manifest"
    rm -f "$temporary"
}
