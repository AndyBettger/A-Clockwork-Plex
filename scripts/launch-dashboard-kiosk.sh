#!/usr/bin/env bash
set -euo pipefail

DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:8088/}"
DASHBOARD_HEALTH_URL="${DASHBOARD_HEALTH_URL:-http://localhost:8088/api/state}"
WAIT_SECONDS="${WAIT_SECONDS:-60}"
PROFILE_DIR="${DASHBOARD_CHROMIUM_PROFILE:-$HOME/.config/a-clockwork-plex/chromium-profile}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BRIDGE_DIR="${DASHBOARD_PLEXAMP_BRIDGE_DIR:-$REPO_ROOT/browser/plexamp-bridge}"
SEARCH_BRIDGE_DIR="${DASHBOARD_PLEXAMP_SEARCH_BRIDGE_DIR:-$REPO_ROOT/browser/plexamp-search-bridge}"

find_browser() {
  if [[ -n "${DASHBOARD_BROWSER:-}" ]]; then
    command -v "$DASHBOARD_BROWSER" 2>/dev/null || true
    return
  fi
  for candidate in chromium-browser chromium google-chrome-stable google-chrome; do
    if command -v "$candidate" >/dev/null 2>&1; then
      command -v "$candidate"
      return
    fi
  done
}

browser="$(find_browser)"
if [[ -z "$browser" ]]; then
  echo "A Clockwork Plex kiosk: Chromium-compatible browser not found." >&2
  exit 1
fi

if command -v curl >/dev/null 2>&1; then
  deadline=$((SECONDS + WAIT_SECONDS))
  until curl --fail --silent --show-error --max-time 2 "$DASHBOARD_HEALTH_URL" >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then
      echo "A Clockwork Plex kiosk: dashboard did not become ready at $DASHBOARD_HEALTH_URL." >&2
      exit 1
    fi
    sleep 1
  done
else
  # Raspberry Pi OS normally includes curl. A short fallback delay prevents an
  # immediate browser error page on unusually minimal installations.
  sleep 5
fi

mkdir -p "$PROFILE_DIR"

browser_args=(
  --kiosk
  --noerrdialogs
  --disable-infobars
  --disable-session-crashed-bubble
  --no-first-run
  --user-data-dir="$PROFILE_DIR"
)

# Both optional bridges are unpacked, permission-free content extensions scoped
# only to Plexamp's loopback web UI. The Home-preference bridge owns the accepted
# allow-listed backup/restore path; the separate Search bridge owns only focused
# Search text editing. If either source tree is incomplete, the other feature and
# normal kiosk launch remain available. No remote-debugging interface is exposed.
extension_dirs=()
if [[ -f "$BRIDGE_DIR/manifest.json" && -f "$BRIDGE_DIR/content.js" ]]; then
  extension_dirs+=("$BRIDGE_DIR")
fi
if [[ -f "$SEARCH_BRIDGE_DIR/manifest.json" && -f "$SEARCH_BRIDGE_DIR/content.js" ]]; then
  extension_dirs+=("$SEARCH_BRIDGE_DIR")
fi
if (( ${#extension_dirs[@]} > 0 )); then
  extension_arg="$(IFS=,; printf '%s' "${extension_dirs[*]}")"
  browser_args+=(--load-extension="$extension_arg")
fi

exec "$browser" "${browser_args[@]}" "$DASHBOARD_URL"
