#!/bin/bash

if [[ -z "${ACP_REPO_ROOT:-}" ]]; then
    ACP_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi

ACP_AUDIO_PROFILE="$ACP_REPO_ROOT/installer/profiles/eq-split-bus"
ACP_AUDIO_TEMPLATES="$ACP_REPO_ROOT/installer/templates"
ACP_CAMILLADSP_VERSION=4.1.3
ACP_CAMILLADSP_SHA256=e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa
ACP_ACCEPTED_DIRECT_SHA256=08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9

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
