#!/bin/bash
set -euo pipefail

# The first ALSA equalizer backend could make the otherwise healthy AirPlay PCM
# fail hardware-parameter negotiation. Keep rollback available, but do not let a
# bare installer command rewrite a working appliance. EQ experiments now run
# through the isolated laboratory harness and never edit /etc/alsa.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_USER="${PROJECT_USER:-andy}"
SHARED_CONFIG="${SHARED_CONFIG:-/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf}"
EQ_CONFIG="${EQ_CONFIG:-/etc/alsa/conf.d/98-a-clockwork-plex-master-eq.conf}"
EQ_DEFAULTS="${EQ_DEFAULTS:-/etc/default/a-clockwork-plex-eq}"
EQ_HELPER="${EQ_HELPER:-/usr/local/bin/a-clockwork-plex-audio-eq}"
EQ_SUDOERS="${EQ_SUDOERS:-/etc/sudoers.d/a-clockwork-plex-audio-eq}"
EQ_STATE_DIR="${EQ_STATE_DIR:-/var/lib/a-clockwork-plex}"
SERVICE_FILE="${SERVICE_FILE:-/etc/systemd/system/a-clockwork-plex.service}"
BACKUP_POINTER="$EQ_STATE_DIR/eq-last-backup"
LAB_SCRIPT="$SCRIPT_DIR/test-master-eq-lab.sh"

usage() {
    cat >&2 <<'EOF'
Usage:
  bash scripts/install-master-eq.sh --experimental-lab [lab options]
  sudo bash scripts/install-master-eq.sh --rollback

Production EQ installation is deliberately disabled while the ALSA backend is
being diagnosed. The EQ interface and API remain part of A Clockwork Plex.

Use --experimental-lab to create and optionally exercise temporary ALSA PCMs.
The laboratory harness does not edit /etc/alsa, Shairport, systemd or the live
A Clockwork Plex configuration.
EOF
}

require_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        echo "Rollback must be run with sudo." >&2
        exit 1
    fi
}

restore_item() {
    local target="$1"
    local name="$2"
    local backup="$3"
    if [[ -e "$backup/$name.present" ]]; then
        install -D -m "$(stat -c '%a' "$backup/$name")" "$backup/$name" "$target"
    elif [[ -e "$backup/$name.absent" ]]; then
        rm -f "$target"
    fi
}

rollback() {
    require_root
    command -v systemctl >/dev/null 2>&1 || {
        echo "Required command not found: systemctl" >&2
        exit 1
    }
    command -v install >/dev/null 2>&1 || {
        echo "Required command not found: install" >&2
        exit 1
    }
    command -v stat >/dev/null 2>&1 || {
        echo "Required command not found: stat" >&2
        exit 1
    }

    if [[ ! -s "$BACKUP_POINTER" ]]; then
        echo "No EQ backup pointer was found at $BACKUP_POINTER." >&2
        exit 1
    fi

    local backup
    backup="$(cat "$BACKUP_POINTER")"
    if [[ ! -d "$backup" ]]; then
        echo "EQ backup directory is missing: $backup" >&2
        exit 1
    fi

    restore_item "$SHARED_CONFIG" shared.conf "$backup"
    restore_item "$EQ_CONFIG" eq.conf "$backup"
    restore_item "$EQ_DEFAULTS" eq-defaults "$backup"
    restore_item "$EQ_HELPER" eq-helper "$backup"
    restore_item "$EQ_SUDOERS" eq-sudoers "$backup"
    restore_item "$SERVICE_FILE" dashboard.service "$backup"

    systemctl daemon-reload
    echo
    echo "Master EQ rollback restored from: $backup"
    echo "Restart the audio services and dashboard:"
    echo "  sudo systemctl restart plexamp.service"
    echo "  sudo systemctl restart shairport-sync.service"
    echo "  sudo systemctl restart a-clockwork-plex.service"
}

case "${1:-}" in
    --rollback)
        [[ $# -eq 1 ]] || { usage; exit 64; }
        rollback
        ;;
    --experimental-lab)
        shift
        if [[ ! -f "$LAB_SCRIPT" ]]; then
            echo "EQ laboratory harness not found: $LAB_SCRIPT" >&2
            exit 1
        fi
        if [[ "${EUID}" -eq 0 ]]; then
            echo "WARNING: the laboratory harness normally does not need sudo." >&2
        fi
        exec bash "$LAB_SCRIPT" "$@"
        ;;
    *)
        echo "Production EQ installation is disabled; the previous backend is not safe to reinstall." >&2
        usage
        exit 64
        ;;
esac
