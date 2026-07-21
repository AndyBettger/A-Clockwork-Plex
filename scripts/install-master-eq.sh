#!/bin/bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this installer with sudo." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_USER="${PROJECT_USER:-andy}"
SHARED_CONFIG="${SHARED_CONFIG:-/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf}"
EQ_CONFIG="${EQ_CONFIG:-/etc/alsa/conf.d/98-a-clockwork-plex-master-eq.conf}"
EQ_DEFAULTS="${EQ_DEFAULTS:-/etc/default/a-clockwork-plex-eq}"
EQ_HELPER="${EQ_HELPER:-/usr/local/bin/a-clockwork-plex-audio-eq}"
EQ_SUDOERS="${EQ_SUDOERS:-/etc/sudoers.d/a-clockwork-plex-audio-eq}"
EQ_STATE_DIR="${EQ_STATE_DIR:-/var/lib/a-clockwork-plex}"
EQ_CONTROL_FILE="${EQ_CONTROL_FILE:-$EQ_STATE_DIR/alsaequal.bin}"
EQ_STATE_FILE="${EQ_STATE_FILE:-$EQ_STATE_DIR/master-eq.json}"
SERVICE_FILE="${SERVICE_FILE:-/etc/systemd/system/a-clockwork-plex.service}"
BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/a-clockwork-plex-eq}"
BACKUP_POINTER="$EQ_STATE_DIR/eq-last-backup"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

require_command() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Required command not found: $1" >&2
        exit 1
    }
}

backup_item() {
    local source="$1"
    local name="$2"
    if [[ -e "$source" ]]; then
        cp -a "$source" "$BACKUP_DIR/$name"
        touch "$BACKUP_DIR/$name.present"
    else
        touch "$BACKUP_DIR/$name.absent"
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

if [[ "${1:-}" == "--rollback" ]]; then
    rollback
    exit 0
fi
if [[ $# -gt 0 ]]; then
    echo "Usage: sudo bash scripts/install-master-eq.sh [--rollback]" >&2
    exit 64
fi

for command in apt-get dpkg-query aplay amixer python3 install visudo timeout systemctl stat; do
    require_command "$command"
done

if ! id "$PROJECT_USER" >/dev/null 2>&1; then
    echo "Project user does not exist: $PROJECT_USER" >&2
    exit 1
fi
if [[ ! -f "$SHARED_CONFIG" ]]; then
    echo "Shared audio configuration was not found: $SHARED_CONFIG" >&2
    echo "Run sudo bash scripts/install-shared-audio.sh first." >&2
    exit 1
fi

if ! dpkg-query -W -f='${Status}' libasound2-plugin-equal 2>/dev/null | grep -q 'install ok installed'; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y libasound2-plugin-equal caps
elif ! dpkg-query -W -f='${Status}' caps 2>/dev/null | grep -q 'install ok installed'; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y caps
fi

BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"
install -d -m 0755 "$BACKUP_DIR" "$EQ_STATE_DIR" "$(dirname "$EQ_CONFIG")" "$(dirname "$EQ_DEFAULTS")"
backup_item "$SHARED_CONFIG" shared.conf
backup_item "$EQ_CONFIG" eq.conf
backup_item "$EQ_DEFAULTS" eq-defaults
backup_item "$EQ_HELPER" eq-helper
backup_item "$EQ_SUDOERS" eq-sudoers
backup_item "$SERVICE_FILE" dashboard.service
printf '%s\n' "$BACKUP_DIR" > "$BACKUP_POINTER"
chmod 0644 "$BACKUP_POINTER"

cat > "$EQ_CONFIG" <<EOF
# Managed by A Clockwork Plex.
# Eq10 is applied identically to Plexamp, AirPlay and alarm sources before
# the shared master soft-volume stage. Linear filtering before summing is
# equivalent to filtering the mixed signal, while retaining the existing dmix path.

ctl.acp_equal {
    type equal
    controls "$EQ_CONTROL_FILE"
    library "caps.so"
    module "Eq10"
    channels 2
}

pcm.acp_equal_engine {
    type equal
    slave.pcm "acp_master"
    controls "$EQ_CONTROL_FILE"
    library "caps.so"
    module "Eq10"
    channels 2
}

pcm.acp_equal {
    type plug
    slave.pcm "acp_equal_engine"
    hint {
        show on
        description "A Clockwork Plex - Master EQ"
    }
}
EOF
chmod 0644 "$EQ_CONFIG"

python3 - "$SHARED_CONFIG" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding='utf-8')


def replace_pcm_slave(source: str, pcm_name: str, slave_name: str) -> str:
    marker = f'pcm.{pcm_name}'
    start = source.find(marker)
    if start < 0:
        raise SystemExit(f'Missing {marker} in {path}.')
    brace = source.find('{', start)
    if brace < 0:
        raise SystemExit(f'Malformed {marker} block in {path}.')
    depth = 0
    end = None
    for index in range(brace, len(source)):
        char = source[index]
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    if end is None:
        raise SystemExit(f'Unterminated {marker} block in {path}.')
    block = source[start:end]
    updated, count = re.subn(
        r'(?m)^(\s*slave\.pcm\s+)"[^"]+"',
        rf'\1"{slave_name}"',
        block,
        count=1,
    )
    if count != 1:
        raise SystemExit(f'Missing slave.pcm in {marker}.')
    return source[:start] + updated + source[end:]

for pcm in ('acp_plexamp_volume', 'acp_airplay_volume', 'acp_alarm_volume'):
    text = replace_pcm_slave(text, pcm, 'acp_equal')

path.write_text(text, encoding='utf-8')
PY
chmod 0644 "$SHARED_CONFIG"

cat > "$EQ_DEFAULTS" <<EOF
# Managed by A Clockwork Plex.
ALSA_EQ_DEVICE=acp_equal
EQ_STATE_PATH=$EQ_STATE_FILE
EOF
chmod 0644 "$EQ_DEFAULTS"

install -o root -g root -m 0755 "$SCRIPT_DIR/a-clockwork-plex-audio-eq.py" "$EQ_HELPER"
cat > "$EQ_SUDOERS" <<EOF
# Managed by A Clockwork Plex. The helper accepts only three named bands and ±6 dB.
$PROJECT_USER ALL=(root) NOPASSWD: $EQ_HELPER status
$PROJECT_USER ALL=(root) NOPASSWD: $EQ_HELPER set *
$PROJECT_USER ALL=(root) NOPASSWD: $EQ_HELPER live *
$PROJECT_USER ALL=(root) NOPASSWD: $EQ_HELPER bypass *
$PROJECT_USER ALL=(root) NOPASSWD: $EQ_HELPER neutral
EOF
chmod 0440 "$EQ_SUDOERS"
visudo -cf "$EQ_SUDOERS" >/dev/null

touch "$EQ_CONTROL_FILE"
chown root:audio "$EQ_CONTROL_FILE" 2>/dev/null || chown root:root "$EQ_CONTROL_FILE"
chmod 0664 "$EQ_CONTROL_FILE"

timeout 0.8 /usr/bin/aplay -q -D acp_equal -f S16_LE -r 44100 -c 2 /dev/zero >/dev/null 2>&1 || true
"$EQ_HELPER" neutral >/dev/null
chown root:audio "$EQ_CONTROL_FILE" 2>/dev/null || true
chmod 0664 "$EQ_CONTROL_FILE" 2>/dev/null || true

install -o root -g root -m 0644 "$PROJECT_DIR/systemd/a-clockwork-plex.service" "$SERVICE_FILE"
systemctl daemon-reload

echo
echo "A Clockwork Plex master EQ installed."
echo "  Equalizer PCM: acp_equal"
echo "  Control device: acp_equal"
echo "  Range: Bass/Mid/Treble -6 dB to +6 dB"
echo "  Backup: $BACKUP_DIR"
echo
echo "EQ status:"
"$EQ_HELPER" status | python3 -m json.tool || true
echo
echo "Restart the audio services and dashboard:"
echo "  sudo systemctl restart plexamp.service"
echo "  sudo systemctl restart shairport-sync.service"
echo "  sudo systemctl restart a-clockwork-plex.service"
echo
echo "Rollback command:"
echo "  sudo bash scripts/install-master-eq.sh --rollback"
