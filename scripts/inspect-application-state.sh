#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/venv/bin/python}"
DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:8088}"
REPOSITORY_UNIT="$ROOT_DIR/systemd/a-clockwork-plex.service"
INSTALLED_UNIT="${INSTALLED_UNIT:-/etc/systemd/system/a-clockwork-plex.service}"

if [[ ! -x "$PYTHON_BIN" ]]; then
    PYTHON_BIN="$(command -v python3)"
fi

echo "===== SYSTEMD ENTRYPOINT ====="
if command -v systemctl >/dev/null 2>&1; then
    systemctl show -p ExecStart --value a-clockwork-plex.service 2>/dev/null || true
else
    echo "systemctl is unavailable"
fi

echo
echo "===== UNIT SYNCHRONISATION ====="
if [[ -f "$REPOSITORY_UNIT" ]] && sudo test -f "$INSTALLED_UNIT" && sudo cmp -s "$REPOSITORY_UNIT" "$INSTALLED_UNIT"; then
    echo "CURRENT: installed unit matches the repository unit."
else
    echo "STALE OR MISSING: installed unit differs from the repository unit."
    echo "Repository entrypoint:"
    grep -E '^ExecStart=' "$REPOSITORY_UNIT" 2>/dev/null || true
    echo "Installed entrypoint:"
    sudo grep -E '^ExecStart=' "$INSTALLED_UNIT" 2>/dev/null || echo "not installed"
    echo "Guarded repair:"
    echo "  bash scripts/install-dashboard-service.sh --apply --confirm INSTALL-DASHBOARD-RUNNER"
fi

echo
echo "===== ROUTES IN REPOSITORY ENTRYPOINT ====="
cd "$ROOT_DIR"
"$PYTHON_BIN" - <<'PY'
from app.runner import app
for rule in sorted(app.url_map.iter_rules(), key=lambda item: item.rule):
    if rule.rule in {"/api/state", "/api/status", "/api/airplay/state"}:
        print(f"{rule.rule:24} endpoint={rule.endpoint}")
PY

echo
echo "===== RUNNING /api/state ====="
response_file="$(mktemp)"
trap 'rm -f "$response_file"' EXIT
status="$({ curl -sS -o "$response_file" -w '%{http_code}' "$DASHBOARD_URL/api/state" || true; })"
echo "HTTP $status"
if [[ -s "$response_file" ]]; then
    "$PYTHON_BIN" -m json.tool "$response_file" 2>/dev/null || cat "$response_file"
fi

echo
if [[ "$status" == "200" ]]; then
    echo "PASS: the running service exposes the ApplicationStateHub."
else
    echo "FAIL: the running service does not expose /api/state."
fi

echo "This inspection is read-only. It changes no service, route, state or audio setting."
