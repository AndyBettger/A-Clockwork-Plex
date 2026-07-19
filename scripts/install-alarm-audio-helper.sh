#!/bin/bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this installer with sudo." >&2
    exit 1
fi

PROJECT_USER="${PROJECT_USER:-andy}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_HELPER="$SCRIPT_DIR/a-clockwork-plex-alarm-audio-helper.sh"
TARGET_HELPER="/usr/local/bin/a-clockwork-plex-alarm-audio"
SUDOERS_FILE="/etc/sudoers.d/a-clockwork-plex-alarm-audio"

if [[ ! -f "$SOURCE_HELPER" ]]; then
    echo "Helper source not found: $SOURCE_HELPER" >&2
    exit 1
fi

/usr/bin/install -o root -g root -m 0755 "$SOURCE_HELPER" "$TARGET_HELPER"

cat > "$SUDOERS_FILE" <<EOF
# Managed by A Clockwork Plex. The helper validates every action and argument.
$PROJECT_USER ALL=(root) NOPASSWD: $TARGET_HELPER release
$PROJECT_USER ALL=(root) NOPASSWD: $TARGET_HELPER restore *
EOF
/usr/bin/chmod 0440 "$SUDOERS_FILE"
/usr/sbin/visudo -cf "$SUDOERS_FILE"

echo "Installed alarm audio helper: $TARGET_HELPER"
echo "Installed restricted sudo policy: $SUDOERS_FILE"
"$TARGET_HELPER" status
