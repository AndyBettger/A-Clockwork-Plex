#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_UNIT="$ROOT_DIR/systemd/a-clockwork-plex.service"
TARGET_UNIT="${TARGET_UNIT:-/etc/systemd/system/a-clockwork-plex.service}"
SERVICE_NAME="${SERVICE_NAME:-a-clockwork-plex.service}"
DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:8088}"
PROJECT_USER="${PROJECT_USER:-${SUDO_USER:-${USER:-$(id -un)}}}"
CONFIRM_TOKEN="INSTALL-DASHBOARD-RUNNER"
MODE="check"
CONFIRM=""

usage() {
  cat <<EOF
Usage:
  bash scripts/install-dashboard-service.sh [--project-user USER]
  bash scripts/install-dashboard-service.sh --apply --confirm $CONFIRM_TOKEN [--project-user USER]

The default mode is read-only. It renders the repository service definition for
the selected project user/current repository path, compares that candidate with
the installed unit and changes nothing.

--apply installs the rendered unit, reloads systemd, restarts only
$SERVICE_NAME, and verifies $DASHBOARD_URL/api/state. The prior unit is
restored automatically if activation or verification fails.
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
    --project-user)
      [[ $# -ge 2 ]] || { echo "--project-user requires a value" >&2; exit 2; }
      PROJECT_USER="$2"
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

[[ "$PROJECT_USER" =~ ^[A-Za-z_][A-Za-z0-9_.-]*$ ]] || {
  echo "Invalid project user: $PROJECT_USER" >&2
  exit 2
}
[[ -f "$SOURCE_UNIT" && ! -L "$SOURCE_UNIT" ]] || {
  echo "Missing or unsafe repository unit: $SOURCE_UNIT" >&2
  exit 1
}

EXPECTED_UNIT="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-dashboard-unit.XXXXXX")"
trap 'rm -f "$EXPECTED_UNIT"' EXIT
sed \
  -e "s/^User=.*/User=$PROJECT_USER/" \
  -e "s/^Group=.*/Group=$PROJECT_USER/" \
  -e "s|^WorkingDirectory=.*|WorkingDirectory=$ROOT_DIR|" \
  -e "s|^ExecStart=.*|ExecStart=$ROOT_DIR/venv/bin/python $ROOT_DIR/app/runner.py|" \
  "$SOURCE_UNIT" >"$EXPECTED_UNIT"

if ! grep -Fxq "User=$PROJECT_USER" "$EXPECTED_UNIT" || \
   ! grep -Fxq "Group=$PROJECT_USER" "$EXPECTED_UNIT" || \
   ! grep -Fxq "WorkingDirectory=$ROOT_DIR" "$EXPECTED_UNIT" || \
   ! grep -Fxq "ExecStart=$ROOT_DIR/venv/bin/python $ROOT_DIR/app/runner.py" "$EXPECTED_UNIT"; then
  echo "Rendered dashboard service did not contain the expected project identity/path." >&2
  exit 1
fi

echo "===== EXPECTED UNIT ====="
grep -E '^(User|Group|WorkingDirectory|ExecStart)=' "$EXPECTED_UNIT" || true

echo
echo "===== INSTALLED UNIT ====="
if sudo test -f "$TARGET_UNIT"; then
  sudo grep -E '^(User|Group|WorkingDirectory|ExecStart)=' "$TARGET_UNIT" || true
else
  echo "Not installed: $TARGET_UNIT"
fi

echo
echo "===== COMPARISON ====="
if sudo test -f "$TARGET_UNIT" && sudo cmp -s "$EXPECTED_UNIT" "$TARGET_UNIT"; then
  echo "CURRENT: installed unit matches the rendered repository unit."
  units_match=true
else
  echo "STALE OR MISSING: installed unit differs from the rendered repository unit."
  units_match=false
fi

if [[ "$MODE" == "check" ]]; then
  echo
  echo "Check-only mode: no file, service or route was changed."
  if [[ "$units_match" == false ]]; then
    echo "Apply with:"
    echo "  bash scripts/install-dashboard-service.sh --apply --confirm $CONFIRM_TOKEN --project-user $PROJECT_USER"
  fi
  exit 0
fi

if [[ "$CONFIRM" != "$CONFIRM_TOKEN" ]]; then
  echo "Activation blocked: use --confirm $CONFIRM_TOKEN" >&2
  exit 2
fi

for command in sudo systemctl install cmp curl; do
  command -v "$command" >/dev/null 2>&1 || { echo "Required command not found: $command" >&2; exit 1; }
done

if command -v systemd-analyze >/dev/null 2>&1; then
  systemd-analyze verify "$EXPECTED_UNIT"
fi

BACKUP_DIR="$(mktemp -d /var/tmp/a-clockwork-plex-dashboard-service.XXXXXX)"
BACKUP_UNIT="$BACKUP_DIR/a-clockwork-plex.service"
OLD_UNIT_PRESENT=false
if sudo test -f "$TARGET_UNIT"; then
  sudo cp -a "$TARGET_UNIT" "$BACKUP_UNIT"
  OLD_UNIT_PRESENT=true
fi

rollback() {
  local exit_status=$?
  trap - ERR INT TERM
  set +e
  echo >&2
  echo "Dashboard service activation failed; restoring the previous unit..." >&2
  if [[ "$OLD_UNIT_PRESENT" == true ]]; then
    sudo install -o root -g root -m 0644 "$BACKUP_UNIT" "$TARGET_UNIT"
  else
    sudo rm -f "$TARGET_UNIT"
  fi
  sudo systemctl daemon-reload
  if [[ "$OLD_UNIT_PRESENT" == true ]]; then
    sudo systemctl restart "$SERVICE_NAME"
  fi
  echo "Rollback copy: $BACKUP_DIR" >&2
  exit "$exit_status"
}
trap rollback ERR INT TERM

sudo install -o root -g root -m 0644 "$EXPECTED_UNIT" "$TARGET_UNIT"
sudo systemctl daemon-reload
sudo systemctl restart "$SERVICE_NAME"

for _ in {1..20}; do
  if systemctl is-active --quiet "$SERVICE_NAME"; then
    status="$(curl -sS -o "$BACKUP_DIR/api-state.json" -w '%{http_code}' "$DASHBOARD_URL/api/state" || true)"
    if [[ "$status" == "200" ]]; then
      trap - ERR INT TERM
      echo
      echo "PASS: dashboard service now uses the rendered repository unit."
      systemctl show -p ExecStart --value "$SERVICE_NAME"
      echo "PASS: $DASHBOARD_URL/api/state returned HTTP 200."
      echo "Rollback copy retained at: $BACKUP_DIR"
      exit 0
    fi
  fi
  sleep 0.5
done

echo "The service did not expose /api/state successfully." >&2
false
