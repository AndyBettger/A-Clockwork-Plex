#!/bin/bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_HELPER="$SOURCE_DIR/a-clockwork-plex-shairport-name.py"
TARGET_HELPER="/usr/local/bin/a-clockwork-plex-shairport-name"
SUDOERS_FILE="/etc/sudoers.d/a-clockwork-plex-shairport-name"
TARGET_USER="${TARGET_USER:-${SUDO_USER:-andy}}"

if [[ ! -f "$SOURCE_HELPER" ]]; then
  echo "Missing helper source: $SOURCE_HELPER" >&2
  exit 1
fi

if [[ ! "$TARGET_USER" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
  echo "Invalid TARGET_USER: $TARGET_USER" >&2
  exit 1
fi

if ! command -v visudo >/dev/null 2>&1; then
  echo "visudo is required." >&2
  exit 1
fi

sudo install -o root -g root -m 0755 "$SOURCE_HELPER" "$TARGET_HELPER"

TEMP_SUDOERS="$(mktemp)"
trap 'rm -f "$TEMP_SUDOERS"' EXIT
cat > "$TEMP_SUDOERS" <<EOF
$TARGET_USER ALL=(root) NOPASSWD: $TARGET_HELPER status
$TARGET_USER ALL=(root) NOPASSWD: $TARGET_HELPER set *
EOF
sudo visudo -cf "$TEMP_SUDOERS" >/dev/null
sudo install -o root -g root -m 0440 "$TEMP_SUDOERS" "$SUDOERS_FILE"

sudo "$TARGET_HELPER" status

echo
echo "Installed managed Shairport receiver-name helper:"
echo "  $TARGET_HELPER"
echo "Installed restricted sudo policy:"
echo "  $SUDOERS_FILE"
echo
echo "The helper may only inspect the fixed Shairport configuration, change general.name,"
echo "validate the candidate configuration, restart shairport-sync.service and roll back on failure."
