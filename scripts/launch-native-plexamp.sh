#!/usr/bin/env bash
# Manual Phase-B launcher for the separately installed Plexamp desktop Flatpak.
# Does not manage Headless, audio routing, or kiosk autostart.
set -euo pipefail

APP_ID="com.plexamp.Plexamp"
APP_BRANCH="beta"

usage() {
  cat <<'HELP'
Usage: bash scripts/launch-native-plexamp.sh

Launch the already-installed Plexamp desktop Flatpak in the active labwc/Wayland
session, including when invoked from SSH. The application runs in the background
and writes output to ~/.cache/a-clockwork-plex/native-plexamp.log.

This is a Phase-B manual discovery helper. It does not change ACP, Headless,
autostart, Flatpak permissions, or audio settings.

Close the native player separately with: flatpak kill com.plexamp.Plexamp
HELP
}

fail() {
  printf 'ACP native Plexamp: %s\n' "$*" >&2
  exit 1
}

case "${1:-}" in
  -h|--help) usage; exit 0 ;;
  "") ;;
  *) usage >&2; exit 2 ;;
esac
if (( $# > 1 )); then
  usage >&2
  exit 2
fi

if (( EUID == 0 )); then
  fail "Run as your normal desktop user, not root (no sudo)."
fi
command -v flatpak >/dev/null 2>&1 || fail "Flatpak is not installed."
flatpak info --branch="$APP_BRANCH" "$APP_ID" >/dev/null 2>&1 || \
  fail "Plexamp $APP_BRANCH Flatpak is not installed for this user/system."

# Do not launch another native player if one is already running. This check
# deliberately does not match or affect the separate Headless Node service.
if flatpak ps --columns=application 2>/dev/null | grep -Fxq "$APP_ID"; then
  printf 'ACP native Plexamp: already running; not starting another instance.\n'
  exit 0
fi

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
[[ -d "$XDG_RUNTIME_DIR" ]] || fail "No user runtime directory: $XDG_RUNTIME_DIR"

# SSH usually has no WAYLAND_DISPLAY. Prefer an existing valid value, then the
# commissioned Pi's wayland-0; never start another compositor or X server.
wayland="${WAYLAND_DISPLAY:-}"
if [[ -n "$wayland" ]]; then
  if [[ "$wayland" == /* ]]; then
    [[ -S "$wayland" ]] || wayland=""
  else
    [[ -S "$XDG_RUNTIME_DIR/$wayland" ]] || wayland=""
  fi
fi
if [[ -z "$wayland" ]]; then
  if [[ -S "$XDG_RUNTIME_DIR/wayland-0" ]]; then
    wayland="wayland-0"
  else
    for candidate in "$XDG_RUNTIME_DIR"/wayland-*; do
      if [[ -S "$candidate" ]]; then
        wayland="${candidate##*/}"
        break
      fi
    done
  fi
fi
[[ -n "$wayland" ]] || fail "No running Wayland session socket found. Log into labwc first."
export WAYLAND_DISPLAY="$wayland"

if [[ -S "$XDG_RUNTIME_DIR/bus" ]]; then
  export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
elif [[ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]]; then
  fail "No desktop session D-Bus bus available at $XDG_RUNTIME_DIR/bus"
fi

umask 077
log_dir="${XDG_CACHE_HOME:-$HOME/.cache}/a-clockwork-plex"
mkdir -p -- "$log_dir"
log_file="$log_dir/native-plexamp.log"

printf 'ACP native Plexamp: requesting launch on %s (Flatpak %s).\n' "$WAYLAND_DISPLAY" "$APP_BRANCH"
nohup flatpak run --branch="$APP_BRANCH" "$APP_ID" >>"$log_file" 2>&1 </dev/null &
printf 'ACP native Plexamp: launch requested; output: %s\n' "$log_file"
