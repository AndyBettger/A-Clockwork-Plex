#!/usr/bin/env bash
# Manual Phase-B launcher for the separately installed Plexamp desktop Flatpak.
# Does not manage Headless, audio routing, or kiosk autostart.
set -euo pipefail

APP_ID="com.plexamp.Plexamp"
APP_BRANCH="beta"

usage() {
  cat <<'HELP'
Usage: bash scripts/launch-native-plexamp.sh [--fullscreen]

Launch the already-installed Plexamp desktop Flatpak in the active labwc/Wayland
session, including when invoked from SSH. The application runs in the background
and writes output to ~/.cache/a-clockwork-plex/native-plexamp.log.

--fullscreen  Ask labwc to put native Plexamp into genuine fullscreen using
              wlrctl. Identifies the actual Wayland window; refuses ambiguous
              matches or Chromium windows. Fullscreen currently hides the Pi OS
              Squeekboard keyboard, so default remains windowed until touch-only
              text entry is solved.

This is a Phase-B manual discovery helper. It does not change ACP, Headless,
autostart, Flatpak permissions, or audio settings.

Close the native player separately with: flatpak kill com.plexamp.Plexamp
HELP
}

fail() {
  printf 'ACP native Plexamp: %s\n' "$*" >&2
  exit 1
}

fullscreen=false
if (( $# > 1 )); then
  usage >&2
  exit 2
fi
case "${1:-}" in
  -h|--help) usage; exit 0 ;;
  --fullscreen) fullscreen=true ;;
  "") ;;
  *) usage >&2; exit 2 ;;
esac

if (( EUID == 0 )); then
  fail "Run as your normal desktop user, not root (no sudo)."
fi
command -v flatpak >/dev/null 2>&1 || fail "Flatpak is not installed."
# Unlike flatpak run, flatpak info accepts BRANCH as a positional argument.
# Both per-user and system-wide installations are searched by default.
flatpak info "$APP_ID" "$APP_BRANCH" >/dev/null 2>&1 || \
  fail "Plexamp $APP_BRANCH Flatpak is not installed for this user/system."

# Do not launch another native player if one is already running. This check
# deliberately does not match or affect the separate Headless Node service.
already_running=false
if flatpak ps --columns=application 2>/dev/null | grep -Fxq "$APP_ID"; then
  already_running=true
  if [[ "$fullscreen" == false ]]; then
    printf 'ACP native Plexamp: already running; not starting another instance.\n'
    exit 0
  fi
fi

if [[ "$fullscreen" == true ]]; then
  command -v wlrctl >/dev/null 2>&1 || \
    fail "--fullscreen requires wlrctl (install with: sudo apt install wlrctl). No changes made."
  # Polling is bounded by the shell, so the launcher needs no timeout binary.
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

if [[ "$already_running" == false ]]; then
  printf 'ACP native Plexamp: requesting launch on %s (Flatpak %s).\n' "$WAYLAND_DISPLAY" "$APP_BRANCH"
  nohup flatpak run --branch="$APP_BRANCH" "$APP_ID" >>"$log_file" 2>&1 </dev/null &
  printf 'ACP native Plexamp: launch requested; output: %s\n' "$log_file"
else
  printf 'ACP native Plexamp: already running; using existing instance.\n'
fi

if [[ "$fullscreen" == true ]]; then
  # Flatpak's installation ID and the application's Wayland app_id can differ.
  # Find a real toplevel before altering anything. wlrctl 0.2.2 implements
  # "toplevel list" even though its Debian man page does not list the action.
  match=""
  last_listing=""
  deadline=$((SECONDS + 20))
  while (( SECONDS < deadline )); do
    if wlrctl toplevel find "app_id:$APP_ID" >/dev/null 2>&1; then
      match="app_id:$APP_ID"
      break
    fi

    if listing="$(wlrctl toplevel list 2>/dev/null)"; then
      last_listing="$listing"
      candidate=""
      count=0
      while IFS= read -r line; do
        [[ "$line" == *": Plexamp" ]] || continue
        window_id="${line%: Plexamp}"
        [[ -n "$window_id" && "$window_id" != "$line" ]] || continue
        # An exact Plexamp title alone is not enough to target a browser.
        case "${window_id,,}" in
          *chromium*|*chrome*|*firefox*) continue ;;
        esac
        count=$((count + 1))
        candidate="$window_id"
      done <<< "$listing"

      if (( count > 1 )); then
        fail "Multiple windows titled Plexamp; refusing an ambiguous fullscreen request. Run: wlrctl toplevel list"
      fi
      if (( count == 1 )) && \
        wlrctl toplevel find "app_id:$candidate" "title:Plexamp" >/dev/null 2>&1; then
        match="app_id:$candidate"
        title_match="title:Plexamp"
        break
      fi
    fi
    sleep 0.25
  done

  if [[ -z "$match" ]]; then
    printf 'ACP native Plexamp: available Wayland windows:\n%s\n' "$last_listing" >&2
    fail "Couldn't identify a unique native Plexamp window within 20 seconds; no window was changed."
  fi

  if [[ -n "${title_match:-}" ]]; then
    if ! wlrctl toplevel fullscreen "$match" "$title_match"; then
      fail "Could not request fullscreen for $match ($title_match); native Plexamp remains running."
    fi
  elif ! wlrctl toplevel fullscreen "$match"; then
    fail "Could not request fullscreen for $match; native Plexamp remains running."
  fi
  printf 'ACP native Plexamp: fullscreen requested for %s.\n' "$match"
  printf 'Note: Squeekboard is currently hidden in true fullscreen; touch Search is not yet accepted.\n'
fi
