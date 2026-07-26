#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/venv/bin/python}"
DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:8088}"

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
echo "This inspection is read-only. It changes no service, route, state or audio setting."
