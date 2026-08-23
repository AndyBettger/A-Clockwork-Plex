#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAUNCHER="$ROOT_DIR/scripts/launch-dashboard-kiosk.sh"
MODE="check"
CONFIRM=""
CONFIRM_TOKEN="INSTALL-DASHBOARD-KIOSK"
TARGET_USER="${TARGET_USER:-${SUDO_USER:-$(id -un)}}"
TARGET_HOME="${TARGET_HOME:-}"
DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:8088/}"

usage() {
  cat <<EOF
Usage:
  bash scripts/install-dashboard-kiosk.sh
  bash scripts/install-dashboard-kiosk.sh --apply --confirm $CONFIRM_TOKEN

The default mode is read-only. It reports the dashboard autostart entry and any
older Chromium launch aimed at Plexamp on port 32500.

Apply mode backs up every touched desktop file, disables only matching old
Plexamp browser launches, and installs the A Clockwork Plex dashboard as the
logged-in desktop user's kiosk target.

Run this script as the desktop user, not with sudo.
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

if [[ "$(id -un)" != "$TARGET_USER" ]]; then
  echo "Run this as desktop user '$TARGET_USER', without sudo." >&2
  exit 2
fi

if [[ -z "$TARGET_HOME" ]]; then
  TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
fi
[[ -n "$TARGET_HOME" && -d "$TARGET_HOME" ]] || {
  echo "Could not resolve a home directory for $TARGET_USER." >&2
  exit 1
}
[[ -f "$LAUNCHER" ]] || { echo "Missing kiosk launcher: $LAUNCHER" >&2; exit 1; }

AUTOSTART_DIR="$TARGET_HOME/.config/autostart"
TARGET_DESKTOP="$AUTOSTART_DIR/a-clockwork-plex-dashboard.desktop"
LINE_AUTOSTART_FILES=(
  "$TARGET_HOME/.config/lxsession/LXDE-pi/autostart"
  "$TARGET_HOME/.config/lxsession/LXDE/autostart"
  "$TARGET_HOME/.config/labwc/autostart"
  "$TARGET_HOME/.config/openbox/autostart"
  "$TARGET_HOME/.config/wayfire.ini"
)

is_old_plexamp_desktop() {
  local path="$1"
  [[ "$path" != "$TARGET_DESKTOP" ]] || return 1
  grep -Eiq '(chromium|google-chrome)' "$path" || return 1
  grep -Eiq '((localhost|127\.0\.0\.1):32500|plexamp)' "$path"
}

line_file_has_old_plexamp_kiosk() {
  local path="$1"
  [[ -f "$path" ]] || return 1
  python3 - "$path" <<'PY'
from __future__ import annotations
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
pattern = re.compile(
    r"(?:chromium(?:-browser)?|google-chrome(?:-stable)?).*"
    r"(?:(?:localhost|127\.0\.0\.1):32500|plexamp)|"
    r"(?:(?:localhost|127\.0\.0\.1):32500|plexamp).*"
    r"(?:chromium(?:-browser)?|google-chrome(?:-stable)?)",
    re.IGNORECASE,
)
for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
    stripped = line.lstrip()
    if stripped.startswith(("#", ";")):
        continue
    if pattern.search(line):
        raise SystemExit(0)
raise SystemExit(1)
PY
}

shopt -s nullglob
OLD_DESKTOPS=()
for path in "$AUTOSTART_DIR"/*.desktop; do
  if is_old_plexamp_desktop "$path"; then
    OLD_DESKTOPS+=("$path")
  fi
done

OLD_LINE_FILES=()
for path in "${LINE_AUTOSTART_FILES[@]}"; do
  if line_file_has_old_plexamp_kiosk "$path"; then
    OLD_LINE_FILES+=("$path")
  fi
done

printf 'Dashboard URL: %s\n' "$DASHBOARD_URL"
printf 'Desktop user: %s\n' "$TARGET_USER"
printf 'Autostart target: %s\n' "$TARGET_DESKTOP"

if [[ -f "$TARGET_DESKTOP" ]] && grep -Fq "$LAUNCHER" "$TARGET_DESKTOP"; then
  echo "CURRENT: dashboard kiosk autostart is installed."
else
  echo "STALE OR MISSING: dashboard kiosk autostart is not installed."
fi

if (( ${#OLD_DESKTOPS[@]} == 0 && ${#OLD_LINE_FILES[@]} == 0 )); then
  echo "No active legacy Plexamp browser autostart was detected."
else
  echo "Legacy Plexamp browser autostart detected:"
  for path in "${OLD_DESKTOPS[@]}" "${OLD_LINE_FILES[@]}"; do
    printf '  %s\n' "$path"
  done
fi

if [[ "$MODE" == "check" ]]; then
  echo
  echo "Check-only mode: no browser or autostart file was changed."
  echo "Apply with:"
  echo "  bash scripts/install-dashboard-kiosk.sh --apply --confirm $CONFIRM_TOKEN"
  exit 0
fi

if [[ "$CONFIRM" != "$CONFIRM_TOKEN" ]]; then
  echo "Activation blocked: use --confirm $CONFIRM_TOKEN" >&2
  exit 2
fi

for command in python3 mkdir cp mv rm date; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Required command not found: $command" >&2
    exit 1
  }
done
bash -n "$LAUNCHER"

BACKUP_DIR="$TARGET_HOME/.local/state/a-clockwork-plex/kiosk-backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
declare -a BACKUP_PATHS=()
declare -a BACKUP_FILES=()
declare -a BACKUP_PRESENT=()
declare -a CREATED_PATHS=()

backup_path() {
  local path="$1"
  local index="${#BACKUP_PATHS[@]}"
  local copy="$BACKUP_DIR/item-$index"
  BACKUP_PATHS+=("$path")
  BACKUP_FILES+=("$copy")
  if [[ -e "$path" ]]; then
    cp -a "$path" "$copy"
    BACKUP_PRESENT+=("yes")
  else
    BACKUP_PRESENT+=("no")
  fi
}

rollback() {
  local exit_status=$?
  trap - ERR INT TERM
  set +e
  echo "Dashboard kiosk installation failed; restoring touched files..." >&2
  for path in "${CREATED_PATHS[@]}"; do
    rm -f "$path"
  done
  for ((index=${#BACKUP_PATHS[@]}-1; index>=0; index--)); do
    path="${BACKUP_PATHS[$index]}"
    if [[ "${BACKUP_PRESENT[$index]}" == "yes" ]]; then
      mkdir -p "$(dirname "$path")"
      cp -a "${BACKUP_FILES[$index]}" "$path"
    else
      rm -f "$path"
    fi
  done
  echo "Rollback snapshot retained at: $BACKUP_DIR" >&2
  exit "$exit_status"
}
trap rollback ERR INT TERM

backup_path "$TARGET_DESKTOP"
mkdir -p "$AUTOSTART_DIR"

for path in "${OLD_DESKTOPS[@]}"; do
  backup_path "$path"
  disabled_path="$path.disabled-by-a-clockwork-plex"
  suffix=1
  while [[ -e "$disabled_path" ]]; do
    disabled_path="$path.disabled-by-a-clockwork-plex-$suffix"
    suffix=$((suffix + 1))
  done
  mv "$path" "$disabled_path"
  CREATED_PATHS+=("$disabled_path")
done

for path in "${OLD_LINE_FILES[@]}"; do
  backup_path "$path"
  python3 - "$path" <<'PY'
from __future__ import annotations
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
pattern = re.compile(
    r"(?:chromium(?:-browser)?|google-chrome(?:-stable)?).*"
    r"(?:(?:localhost|127\.0\.0\.1):32500|plexamp)|"
    r"(?:(?:localhost|127\.0\.0\.1):32500|plexamp).*"
    r"(?:chromium(?:-browser)?|google-chrome(?:-stable)?)",
    re.IGNORECASE,
)
lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
updated: list[str] = []
for line in lines:
    stripped = line.lstrip()
    if not stripped.startswith(("#", ";")) and pattern.search(line):
        newline = "\n" if line.endswith("\n") else ""
        body = line[:-1] if newline else line
        updated.append(f"# Disabled by A Clockwork Plex dashboard kiosk: {body}{newline}")
    else:
        updated.append(line)
path.write_text("".join(updated), encoding="utf-8")
PY
done

cat >"$TARGET_DESKTOP.tmp" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=A Clockwork Plex Dashboard
Comment=Start the bedside dashboard after the desktop session opens
Exec=/usr/bin/env bash "$LAUNCHER"
Terminal=false
StartupNotify=false
X-GNOME-Autostart-enabled=true
Hidden=false
EOF
mv "$TARGET_DESKTOP.tmp" "$TARGET_DESKTOP"
chmod 0755 "$LAUNCHER"
chmod 0644 "$TARGET_DESKTOP"

if command -v desktop-file-validate >/dev/null 2>&1; then
  desktop-file-validate "$TARGET_DESKTOP"
fi

grep -Fq "$LAUNCHER" "$TARGET_DESKTOP"
grep -Fq 'X-GNOME-Autostart-enabled=true' "$TARGET_DESKTOP"

trap - ERR INT TERM

echo
echo "PASS: dashboard kiosk autostart installed."
echo "PASS: matching old Plexamp browser launchers were disabled."
echo "Chromium will use its own dashboard profile and open: $DASHBOARD_URL"
echo "Backup snapshot retained at: $BACKUP_DIR"
echo "Log out and back in, or reboot, to validate desktop autostart."
