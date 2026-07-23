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

echo "Using Python: $PYTHON"
"$PYTHON" -m py_compile app/main.py app/dashboard_core.py app/alarm_config.py app/alarm_scheduler.py app/alarm_runtime.py app/alarm_audio.py app/alarm_audio_core.py
"$PYTHON" -m unittest discover -s tests -v

if command -v node >/dev/null 2>&1; then
  node --check app/static/js/settings-alarms.js
  node --check app/static/js/settings-alarm-scheduler.js
  node --check app/static/js/settings-alarm-audio.js
  node --check app/static/js/settings-keyboard.js
  node --check app/static/js/settings-tabs.js
  node --check app/static/js/settings-about.js
  node --check app/static/js/mode-watch.js
  node --check app/static/js/alarm-active.js
else
  echo "Node.js not found; skipping JavaScript syntax checks."
fi

bash -n scripts/a-clockwork-plex-alarm-audio-helper.sh
bash -n scripts/install-alarm-audio-helper.sh
