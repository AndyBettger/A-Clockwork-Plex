#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
  PYTHON="${VIRTUAL_ENV}/bin/python"
elif [[ -x "$ROOT_DIR/venv/bin/python" ]]; then
  PYTHON="$ROOT_DIR/venv/bin/python"
elif [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON="$ROOT_DIR/.venv/bin/python"
else
  cat >&2 <<'EOF'
A Clockwork Plex test runner could not find a project virtual environment.

Create it with:
  python3 -m venv venv
  venv/bin/python -m pip install -r requirements.txt

Then run:
  bash scripts/run-tests.sh
EOF
  exit 1
fi

if ! "$PYTHON" -c 'import flask' >/dev/null 2>&1; then
  cat >&2 <<EOF
Flask is not installed in the selected Python environment:
  $PYTHON

Install the project dependencies with:
  "$PYTHON" -m pip install -r requirements.txt
EOF
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  cat >&2 <<'EOF'
Node.js is required for the JavaScript syntax pass.
Install Node.js, then rerun:
  bash scripts/run-tests.sh
EOF
  exit 1
fi

PYCACHE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/a-clockwork-plex-pycache.XXXXXX")"
cleanup() {
  rm -rf "$PYCACHE_ROOT"
}
trap cleanup EXIT
export PYTHONPYCACHEPREFIX="$PYCACHE_ROOT"

echo "Using Python: $PYTHON"
echo "Using Node:   $(command -v node)"

echo
echo "== Python syntax: app/ + scripts/ =="
while IFS= read -r -d '' file; do
  "$PYTHON" -m py_compile "$file"
done < <(find app scripts -type f -name '*.py' -print0 | sort -z)

echo
echo "== Shell syntax: repository installer + scripts/ =="
bash -n setup.sh
bash -n appliance-installer.sh
while IFS= read -r -d '' file; do
  bash -n "$file"
done < <(find scripts -type f -name '*.sh' -print0 | sort -z)

echo
echo "== JavaScript syntax: app/static/js/ =="
while IFS= read -r -d '' file; do
  node --check "$file"
done < <(find app/static/js -type f -name '*.js' -print0 | sort -z)

echo
echo "== Unit tests =="
if [[ -n "${CI:-}" ]]; then
  "$PYTHON" -m unittest discover -s tests
else
  "$PYTHON" -m unittest discover -s tests -v
fi

echo
echo "PASS: Python, shell and JavaScript syntax plus the complete unit suite are green."
