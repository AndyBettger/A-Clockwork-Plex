#!/bin/bash

# Read-only host and parser validation for the supported EQ-capable audio
# installer. This command writes evidence only beneath a fresh /var/tmp
# directory. It does not use elevated privileges, open a PCM, load a module,
# change a route, write a mixer control, or alter a service.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PROFILE="$REPO_ROOT/installer/profiles/eq-split-bus"
TEMPLATES="$REPO_ROOT/installer/templates"
CAMILLA_MODULES="$REPO_ROOT/scripts"

CAMILLADSP_VERSION=4.1.3
CAMILLADSP_SHA256=e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa
DIRECT_ROUTE_SHA256=08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9
ACTIVE_ROUTE=/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf
ALSA_BASE=/usr/share/alsa/alsa.conf
DAC_HW_PARAMS=/proc/asound/Pro/pcm0p/sub0/hw_params
AUDIO_LOCK=/run/lock/a-clockwork-plex-audio-route.lock
APPROVAL_RECORD=/var/lib/a-clockwork-plex/split-bus/activation-approved
INSTALLED_MARKER=/var/lib/a-clockwork-plex/split-bus/installed
PRE_EQ_BACKUP=/var/lib/a-clockwork-plex/split-bus/pre-eq-backup

PUBLIC_PCMS=(acp_dmix acp_master acp_plexamp acp_airplay acp_alarm)
APPLICATION_SERVICES=(plexamp.service shairport-sync.service a-clockwork-plex.service)
MANAGED_SERVICES=(
    a-clockwork-plex-audio-route.service
    a-clockwork-plex-camilladsp.service
    a-clockwork-plex-audio-failback.service
)
MANAGED_FILES=(
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
)

CAMILLADSP_BINARY=
PROJECT_USER="${USER:-$(id -un)}"
EVIDENCE_ROOT=
RESULTS=

usage() {
    cat <<'EOF_USAGE'
Usage: bash scripts/audio/preflight-eq.sh --binary PATH [--project-user USER]

Runs the final read-only host/parser gate before the first supported EQ install.
Keep the current direct audio route active; ordinary Plexamp playback may remain
playing and audible throughout this command.

The command:
  - verifies the exact direct baseline and application-service state;
  - parses both candidate ALSA routes with aplay -L in isolated configs;
  - renders and checks a neutral CamillaDSP configuration;
  - verifies the three candidate units in a private systemd model;
  - validates rendered restricted rules with visudo;
  - compares production host state before and after;
  - retains evidence under /var/tmp/a-clockwork-plex-eq-preflight.*.

It does not install files, open a PCM, select a route, load a module, change a
mixer level, or start, stop, restart, enable or disable a service.
EOF_USAGE
}

error() {
    printf '[A Clockwork Plex] ERROR: %s\n' "$*" >&2
}

record() {
    local check="$1" status="$2" detail="$3"
    printf '%s\t%s\t%s\n' "$check" "$status" "$detail" | tee -a "$RESULTS"
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || {
        error "Required read-only validator is unavailable: $1"
        return 1
    }
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --binary)
                [[ $# -ge 2 ]] || { error '--binary requires a path.'; return 64; }
                CAMILLADSP_BINARY="$2"
                shift 2
                ;;
            --project-user)
                [[ $# -ge 2 ]] || { error '--project-user requires a user.'; return 64; }
                PROJECT_USER="$2"
                shift 2
                ;;
            -h|--help)
                usage
                return 2
                ;;
            *)
                error "Unknown option: $1"
                usage >&2
                return 64
                ;;
        esac
    done
}

service_state() {
    local unit="$1" active enabled
    active="$(systemctl is-active "$unit" 2>/dev/null || true)"
    enabled="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
    printf '%s\tactive=%s\tenabled=%s\n' \
        "$unit" "${active:-unknown}" "${enabled:-unknown}"
}

capture_host_state() {
    local output="$1" path parameter
    {
        printf 'architecture\t%s\n' "$(uname -m)"
        printf 'active-route\tsha256=%s\tmode=%s\tuid=%s\tgid=%s\n' \
            "$(sha256sum "$ACTIVE_ROUTE" | awk '{print $1}')" \
            "$(stat -c '%a' "$ACTIVE_ROUTE")" \
            "$(stat -c '%u' "$ACTIVE_ROUTE")" \
            "$(stat -c '%g' "$ACTIVE_ROUTE")"
        for path in "${APPLICATION_SERVICES[@]}" "${MANAGED_SERVICES[@]}"; do
            service_state "$path"
        done
        if [[ -d /sys/module/snd_aloop/parameters ]]; then
            printf 'snd_aloop\tloaded=true\n'
            for parameter in index id pcm_substreams pcm_notify enable; do
                if [[ -r "/sys/module/snd_aloop/parameters/$parameter" ]]; then
                    printf 'snd_aloop-%s\t%s\n' "$parameter" \
                        "$(cut -d, -f1 "/sys/module/snd_aloop/parameters/$parameter")"
                else
                    printf 'snd_aloop-%s\tunavailable\n' "$parameter"
                fi
            done
        else
            printf 'snd_aloop\tloaded=false\n'
        fi
        for path in "${MANAGED_FILES[@]}"; do
            if [[ -e "$path" || -L "$path" ]]; then
                printf 'managed-path\tpresent\t%s\n' "$path"
            else
                printf 'managed-path\tabsent\t%s\n' "$path"
            fi
        done
        for path in "$AUDIO_LOCK" "$APPROVAL_RECORD" "$INSTALLED_MARKER" "$PRE_EQ_BACKUP"; do
            if [[ -e "$path" || -L "$path" ]]; then
                printf 'guard-path\tpresent\t%s\n' "$path"
            else
                printf 'guard-path\tabsent\t%s\n' "$path"
            fi
        done
        if [[ -r "$DAC_HW_PARAMS" ]]; then
            while IFS= read -r path; do
                printf 'dac-hw-params\t%s\n' "$path"
            done <"$DAC_HW_PARAMS"
        else
            printf 'dac-hw-params\tunavailable\n'
        fi
    } >"$output"
}

validate_baseline() {
    local observed path state
    [[ "$EUID" -ne 0 ]] || {
        error 'Run this read-only preflight as the normal project user, not as root.'
        return 1
    }
    [[ "$(uname -m)" == aarch64 ]] || {
        error "Expected aarch64; found $(uname -m)."
        return 1
    }
    [[ -f "$ACTIVE_ROUTE" && ! -L "$ACTIVE_ROUTE" ]] || {
        error "The active route is not a regular file: $ACTIVE_ROUTE"
        return 1
    }
    observed="$(sha256sum "$ACTIVE_ROUTE" | awk '{print $1}')" || return 1
    [[ "$observed" == "$DIRECT_ROUTE_SHA256" ]] || {
        error "Unexpected active route checksum. Expected $DIRECT_ROUTE_SHA256, observed $observed"
        return 1
    }
    grep -Eq '^\s*[0-9]+\s+\[Pro\s*\]' /proc/asound/cards || {
        error 'Physical DAC card Pro was not found.'
        return 1
    }
    for path in "${APPLICATION_SERVICES[@]}"; do
        systemctl is-active --quiet "$path" || {
            error "Required application service is not active: $path"
            return 1
        }
        systemctl is-enabled --quiet "$path" || {
            error "Required application service is not enabled: $path"
            return 1
        }
    done
    for path in "${MANAGED_FILES[@]}"; do
        [[ ! -e "$path" && ! -L "$path" ]] || {
            error "EQ managed path already exists: $path"
            return 1
        }
    done
    for path in "$AUDIO_LOCK" "$APPROVAL_RECORD" "$INSTALLED_MARKER" "$PRE_EQ_BACKUP"; do
        [[ ! -e "$path" && ! -L "$path" ]] || {
            error "Preflight guard path is unexpectedly present: $path"
            return 1
        }
    done
    if [[ -d /sys/module/snd_aloop/parameters ]]; then
        for path in index id pcm_substreams pcm_notify; do
            state="$(cut -d, -f1 "/sys/module/snd_aloop/parameters/$path")" || return 1
            case "$path:$state" in
                index:7|id:ACP_Loopback|pcm_substreams:2|pcm_notify:1) ;;
                *)
                    error "Loaded snd_aloop parameter is unexpected: $path=$state"
                    return 1
                    ;;
            esac
        done
    fi
    record host-baseline PASS "direct route $observed; applications active and enabled"
}

validate_binary() {
    local observed version
    [[ -n "$CAMILLADSP_BINARY" ]] || {
        error '--binary PATH is required.'
        return 64
    }
    [[ -f "$CAMILLADSP_BINARY" && -x "$CAMILLADSP_BINARY" && ! -L "$CAMILLADSP_BINARY" ]] || {
        error "CamillaDSP binary is not an executable regular file: $CAMILLADSP_BINARY"
        return 1
    }
    observed="$(sha256sum "$CAMILLADSP_BINARY" | awk '{print $1}')" || return 1
    [[ "$observed" == "$CAMILLADSP_SHA256" ]] || {
        error "CamillaDSP checksum mismatch. Expected $CAMILLADSP_SHA256, observed $observed"
        return 1
    }
    version="$("$CAMILLADSP_BINARY" --version 2>&1 | head -n 1)" || return 1
    [[ "$version" == *"$CAMILLADSP_VERSION"* ]] || {
        error "Unexpected CamillaDSP version: ${version:-unknown}"
        return 1
    }
    printf '%s\n' "$version" >"$EVIDENCE_ROOT/camilladsp-version.txt"
    record camilladsp-binary PASS "$version; sha256=$observed"
}

build_alsa_validation() {
    local fragment="$1" output="$2"
    python3 - "$ALSA_BASE" "$fragment" "$output" <<'PY_ALSA'
from pathlib import Path
import sys

base = Path(sys.argv[1])
fragment = Path(sys.argv[2])
output = Path(sys.argv[3])
lines = base.read_text(encoding='utf-8').splitlines()
rendered: list[str] = []
skipping = False
depth = 0
removed = False
for line in lines:
    stripped = line.strip()
    if not removed and not skipping and stripped.startswith('@hooks') and '[' in stripped:
        skipping = True
        depth = line.count('[') - line.count(']')
        if depth == 0:
            skipping = False
            removed = True
        continue
    if skipping:
        depth += line.count('[') - line.count(']')
        if depth == 0:
            skipping = False
            removed = True
        continue
    rendered.append(line)
if not removed:
    raise SystemExit('Could not remove the global ALSA preload hook.')
rendered.extend(('', fragment.read_text(encoding='utf-8')))
output.write_text('\n'.join(rendered).rstrip() + '\n', encoding='utf-8')
PY_ALSA
}

validate_alsa() {
    local name fragment config output diagnostic pcm
    for name in split direct; do
        if [[ "$name" == split ]]; then
            fragment="$PROFILE/split-bus.conf"
        else
            fragment="$PROFILE/direct-alarm-bypass.conf"
        fi
        config="$EVIDENCE_ROOT/alsa-$name.conf"
        output="$EVIDENCE_ROOT/aplay-$name.txt"
        diagnostic="$EVIDENCE_ROOT/aplay-$name.err"
        build_alsa_validation "$fragment" "$config" || return 1
        if ! ALSA_CONFIG_PATH="$config" aplay -L >"$output" 2>"$diagnostic"; then
            error "ALSA $name candidate did not parse; see $diagnostic"
            return 1
        fi
        for pcm in "${PUBLIC_PCMS[@]}"; do
            grep -Fxq "$pcm" "$output" || {
                error "ALSA $name candidate omitted public PCM: $pcm"
                return 1
            }
        done
        record "alsa-$name" PASS "isolated aplay -L parse; five public PCMs present; no PCM opened"
    done
}

render_neutral_camilladsp() {
    local output="$1"
    PYTHONPATH="$CAMILLA_MODULES" python3 - "$output" <<'PY_RENDER'
from pathlib import Path
import sys
from audio_eq_camilladsp.model import Settings, default_state, render_config

output = Path(sys.argv[1])
output.write_text(render_config(Settings(), default_state()), encoding='utf-8')
PY_RENDER
}

validate_camilladsp() {
    local rendered static_log rendered_log
    rendered="$EVIDENCE_ROOT/camilladsp-rendered-neutral.yml"
    static_log="$EVIDENCE_ROOT/camilladsp-static-check.txt"
    rendered_log="$EVIDENCE_ROOT/camilladsp-rendered-check.txt"
    render_neutral_camilladsp "$rendered" || return 1
    if ! "$CAMILLADSP_BINARY" --check "$PROFILE/camilladsp-split-bus.yml" >"$static_log" 2>&1; then
        error "Reviewed CamillaDSP profile failed --check; see $static_log"
        return 1
    fi
    if ! "$CAMILLADSP_BINARY" --check "$rendered" >"$rendered_log" 2>&1; then
        error "Rendered neutral CamillaDSP profile failed --check; see $rendered_log"
        return 1
    fi
    record camilladsp-config PASS "reviewed and rendered neutral profiles accepted by CamillaDSP --check; no endpoint opened"
}

validate_sudoers() {
    local template rendered name
    [[ "$PROJECT_USER" =~ ^[A-Za-z0-9_.@-]+$ ]] || {
        error "Invalid project user: $PROJECT_USER"
        return 1
    }
    for name in route eq; do
        if [[ "$name" == route ]]; then
            template="$TEMPLATES/a-clockwork-plex-audio-route.sudoers.in"
        else
            template="$TEMPLATES/a-clockwork-plex-audio-eq.sudoers.in"
        fi
        rendered="$EVIDENCE_ROOT/sudoers-$name"
        sed "s/@PROJECT_USER@/$PROJECT_USER/g" "$template" >"$rendered" || return 1
        chmod 0440 "$rendered" || return 1
        if ! visudo -cf "$rendered" >"$EVIDENCE_ROOT/visudo-$name.txt" 2>&1; then
            error "Rendered $name rules failed visudo; see $EVIDENCE_ROOT/visudo-$name.txt"
            return 1
        fi
    done
    record sudoers PASS "both rendered restricted rule files accepted by visudo"
}

prepare_private_units() {
    local unit_dir="$1"
    python3 - "$PROFILE/systemd" "$unit_dir" <<'PY_UNITS'
from pathlib import Path
import sys

source = Path(sys.argv[1])
target = Path(sys.argv[2])
target.mkdir(mode=0o700)
unit_names = (
    'a-clockwork-plex-audio-route.service',
    'a-clockwork-plex-camilladsp.service',
    'a-clockwork-plex-audio-failback.service',
)
for name in unit_names:
    text = (source / name).read_text(encoding='utf-8')
    rewritten = '\n'.join(
        'ExecStart=/bin/true' if line.startswith('ExecStart=') else line
        for line in text.splitlines()
        if not line.startswith(('User=', 'Group='))
    ) + '\n'
    (target / name).write_text(rewritten, encoding='utf-8')
for name in (
    'plexamp.service',
    'shairport-sync.service',
    'a-clockwork-plex.service',
    'systemd-modules-load.service',
):
    (target / name).write_text(
        '[Unit]\nDescription=A Clockwork Plex private validation stub\n'
        '[Service]\nType=oneshot\nExecStart=/bin/true\n',
        encoding='utf-8',
    )
for name in ('sound.target', 'multi-user.target', 'sysinit.target', 'basic.target', 'shutdown.target'):
    (target / name).write_text(
        '[Unit]\nDescription=A Clockwork Plex private validation target\n',
        encoding='utf-8',
    )
PY_UNITS
}

validate_units() {
    local unit_dir log
    unit_dir="$EVIDENCE_ROOT/systemd-private"
    log="$EVIDENCE_ROOT/systemd-analyze.txt"
    prepare_private_units "$unit_dir" || return 1
    if ! SYSTEMD_UNIT_PATH="$unit_dir" systemd-analyze verify \
        "$unit_dir/a-clockwork-plex-audio-route.service" \
        "$unit_dir/a-clockwork-plex-camilladsp.service" \
        "$unit_dir/a-clockwork-plex-audio-failback.service" >"$log" 2>&1; then
        error "Candidate units failed private systemd verification; see $log"
        return 1
    fi
    record systemd-units PASS "three units accepted in private unit model; service manager not contacted"
}

run_validations() {
    validate_baseline || return $?
    validate_binary || return $?
    validate_alsa || return $?
    validate_camilladsp || return $?
    validate_sudoers || return $?
    validate_units || return $?
}

main() {
    local parsed status=0 after_status=0
    parse_args "$@"
    parsed=$?
    [[ "$parsed" -eq 2 ]] && return 0
    [[ "$parsed" -eq 0 ]] || return "$parsed"

    for command in aplay awk chmod cmp cut grep head mktemp python3 sed sha256sum stat systemctl systemd-analyze tee uname visudo; do
        require_command "$command" || return 1
    done
    [[ -f "$ALSA_BASE" ]] || { error "ALSA base configuration is unavailable: $ALSA_BASE"; return 1; }

    EVIDENCE_ROOT="$(mktemp -d /var/tmp/a-clockwork-plex-eq-preflight.XXXXXX)" || return 1
    RESULTS="$EVIDENCE_ROOT/results.tsv"
    printf 'check\tresult\tdetail\n' >"$RESULTS"
    printf 'timestamp=%s\nhostname=%s\nsource_root=%s\n' \
        "$(date --iso-8601=seconds)" "$(hostname)" "$REPO_ROOT" >"$EVIDENCE_ROOT/report.txt"

    if ! capture_host_state "$EVIDENCE_ROOT/host-before.tsv"; then
        error "Could not capture the initial host state; evidence retained at $EVIDENCE_ROOT"
        return 1
    fi

    run_validations || status=$?

    capture_host_state "$EVIDENCE_ROOT/host-after.tsv" || after_status=1
    if [[ "$after_status" -ne 0 ]]; then
        error 'Could not capture the final host state.'
        status=1
    elif ! cmp -s "$EVIDENCE_ROOT/host-before.tsv" "$EVIDENCE_ROOT/host-after.tsv"; then
        error "Production host state changed during read-only validation; inspect $EVIDENCE_ROOT"
        diff -u "$EVIDENCE_ROOT/host-before.tsv" "$EVIDENCE_ROOT/host-after.tsv" \
            >"$EVIDENCE_ROOT/host-state.diff" 2>&1 || true
        record production-state FAIL "before/after host snapshots differ"
        status=1
    else
        record production-state PASS "route, services, managed paths, loopback and DAC parameters unchanged"
    fi

    {
        printf 'evidence_root=%s\n' "$EVIDENCE_ROOT"
        printf 'active_route_sha256=%s\n' "$(sha256sum "$ACTIVE_ROUTE" | awk '{print $1}')"
        printf 'result=%s\n' "$([[ "$status" -eq 0 ]] && printf PASS || printf FAIL)"
    } >>"$EVIDENCE_ROOT/report.txt"

    printf '\nEVIDENCE_ROOT=%s\n' "$EVIDENCE_ROOT"
    printf 'ACTIVE_ROUTE_SHA256=%s\n' "$(sha256sum "$ACTIVE_ROUTE" | awk '{print $1}')"
    if [[ "$status" -eq 0 ]]; then
        printf 'EQ_AUDIO_READ_ONLY_PREFLIGHT=PASS\n'
        printf 'No production file, route, module, mixer control, PCM or service was changed.\n'
    else
        printf 'EQ_AUDIO_READ_ONLY_PREFLIGHT=FAIL\n' >&2
        printf 'Evidence was retained for inspection.\n' >&2
    fi
    return "$status"
}

main "$@"
