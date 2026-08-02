#!/usr/bin/env bash
set -euo pipefail

MODE="check"
CONFIRM=""
CONFIRM_TOKEN="IMPORT-PLEXAMP-BROWSER-AUTH"
TARGET_ROOT="${DASHBOARD_CHROMIUM_PROFILE:-$HOME/.config/a-clockwork-plex/chromium-profile}"
SOURCE_ROOT="${SOURCE_CHROMIUM_USER_DATA:-}"
SOURCE_PROFILE="${SOURCE_CHROMIUM_PROFILE:-Default}"

usage() {
  cat <<EOF
Usage:
  bash scripts/migrate-dashboard-browser-auth.sh
  bash scripts/migrate-dashboard-browser-auth.sh --apply --confirm $CONFIRM_TOKEN

The default mode is read-only. It locates the previous Chromium profile and
reports which authentication/storage areas can be copied into the dedicated
A Clockwork Plex kiosk profile.

Apply mode must run as the desktop user with Chromium fully closed. It backs up
the dedicated kiosk profile, then copies browser authentication and origin
storage without copying session/tab restore files.

Optional overrides:
  SOURCE_CHROMIUM_USER_DATA=/path/to/user-data
  SOURCE_CHROMIUM_PROFILE=Default
  DASHBOARD_CHROMIUM_PROFILE=/path/to/kiosk-user-data
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)
      MODE="check"
      shift
      ;;
    --apply)
      MODE="apply"
      shift
      ;;
    --confirm)
      [[ $# -ge 2 ]] || { echo "--confirm requires a value" >&2; exit 2; }
      CONFIRM="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

find_source_root() {
  if [[ -n "$SOURCE_ROOT" ]]; then
    printf '%s\n' "$SOURCE_ROOT"
    return
  fi
  local candidate
  for candidate in \
    "$HOME/.config/chromium" \
    "$HOME/.config/chromium-browser" \
    "$HOME/.config/google-chrome"; do
    if [[ -d "$candidate/$SOURCE_PROFILE" && "$candidate" != "$TARGET_ROOT" ]]; then
      printf '%s\n' "$candidate"
      return
    fi
  done
}

SOURCE_ROOT="$(find_source_root || true)"
if [[ -z "$SOURCE_ROOT" || ! -d "$SOURCE_ROOT/$SOURCE_PROFILE" ]]; then
  echo "No previous Chromium profile was found." >&2
  echo "Set SOURCE_CHROMIUM_USER_DATA and optionally SOURCE_CHROMIUM_PROFILE." >&2
  exit 1
fi

SOURCE_PROFILE_ROOT="$SOURCE_ROOT/$SOURCE_PROFILE"
TARGET_PROFILE_ROOT="$TARGET_ROOT/Default"

COPY_PATHS=(
  "Local State"
  "$SOURCE_PROFILE/Local Storage"
  "$SOURCE_PROFILE/IndexedDB"
  "$SOURCE_PROFILE/Session Storage"
  "$SOURCE_PROFILE/WebStorage"
  "$SOURCE_PROFILE/Cookies"
  "$SOURCE_PROFILE/Cookies-journal"
  "$SOURCE_PROFILE/Network/Cookies"
  "$SOURCE_PROFILE/Network/Cookies-journal"
)

printf 'Source user data: %s\n' "$SOURCE_ROOT"
printf 'Source profile: %s\n' "$SOURCE_PROFILE"
printf 'Target kiosk profile: %s\n' "$TARGET_ROOT"
printf '\nAvailable authentication/storage areas:\n'
found=0
for relative in "${COPY_PATHS[@]}"; do
  if [[ -e "$SOURCE_ROOT/$relative" ]]; then
    printf '  %s\n' "$relative"
    found=$((found + 1))
  fi
done

if (( found == 0 )); then
  echo "No transferable browser authentication/storage was found." >&2
  exit 1
fi

echo
echo "Session and tab restore data will not be copied."
echo "The dashboard will continue using its dedicated kiosk profile."

if [[ "$MODE" == "check" ]]; then
  echo
  echo "Check-only mode: no browser data was changed."
  echo "Close Chromium, then apply with:"
  echo "  bash scripts/migrate-dashboard-browser-auth.sh --apply --confirm $CONFIRM_TOKEN"
  exit 0
fi

if [[ "$CONFIRM" != "$CONFIRM_TOKEN" ]]; then
  echo "Migration blocked: use --confirm $CONFIRM_TOKEN" >&2
  exit 2
fi

if pgrep -u "$(id -u)" -f '(chromium|chrome)' >/dev/null 2>&1; then
  echo "Chromium is still running. Close the kiosk browser before applying." >&2
  exit 2
fi

for command in cp mkdir rm date; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Required command not found: $command" >&2
    exit 1
  }
done

BACKUP_ROOT="$HOME/.local/state/a-clockwork-plex/browser-profile-backups"
BACKUP_DIR="$BACKUP_ROOT/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

if [[ -e "$TARGET_ROOT" ]]; then
  cp -a "$TARGET_ROOT" "$BACKUP_DIR/chromium-profile"
fi

rollback() {
  local exit_status=$?
  trap - ERR INT TERM
  set +e
  echo "Browser auth migration failed; restoring the kiosk profile backup..." >&2
  rm -rf "$TARGET_ROOT"
  if [[ -d "$BACKUP_DIR/chromium-profile" ]]; then
    mkdir -p "$(dirname "$TARGET_ROOT")"
    cp -a "$BACKUP_DIR/chromium-profile" "$TARGET_ROOT"
  fi
  echo "Backup retained at: $BACKUP_DIR" >&2
  exit "$exit_status"
}
trap rollback ERR INT TERM

mkdir -p "$TARGET_PROFILE_ROOT"

copy_item() {
  local relative="$1"
  local source="$SOURCE_ROOT/$relative"
  [[ -e "$source" ]] || return 0

  local target_relative="$relative"
  if [[ "$relative" == "$SOURCE_PROFILE/"* ]]; then
    target_relative="Default/${relative#"$SOURCE_PROFILE/"}"
  fi
  local target="$TARGET_ROOT/$target_relative"
  mkdir -p "$(dirname "$target")"
  rm -rf "$target"
  cp -a "$source" "$target"
}

for relative in "${COPY_PATHS[@]}"; do
  copy_item "$relative"
done

# Explicitly remove any restore artefacts should a source path ever contain one.
rm -rf \
  "$TARGET_PROFILE_ROOT/Sessions" \
  "$TARGET_PROFILE_ROOT/Current Session" \
  "$TARGET_PROFILE_ROOT/Current Tabs" \
  "$TARGET_PROFILE_ROOT/Last Session" \
  "$TARGET_PROFILE_ROOT/Last Tabs"

marker="$TARGET_ROOT/.acp-auth-imported"
printf 'source=%s/%s\nimported_at=%s\n' \
  "$SOURCE_ROOT" "$SOURCE_PROFILE" "$(date --iso-8601=seconds)" > "$marker"

trap - ERR INT TERM

echo
echo "PASS: browser authentication/storage copied into the kiosk profile."
echo "PASS: session and tab restore files were not copied."
echo "Backup retained at: $BACKUP_DIR"
echo "Start Chromium or reboot, then open Plexamp from the dashboard."
