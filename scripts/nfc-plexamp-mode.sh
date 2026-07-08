#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

/usr/bin/logger -t a-clockwork-plex "NFC event - switching display to Plexamp"
"$SCRIPT_DIR/display-mode.sh" plexamp || true
