#!/bin/bash
set -euo pipefail

REPO_DIR="${ACP_REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ACP_USER="${ACP_USER:-$(id -un)}"
PIPE_PATH="${SHAIRPORT_METADATA_PIPE:-/tmp/shairport-sync-metadata}"
SERVICE_NAME="${ACP_METADATA_SERVICE_NAME:-a-clockwork-plex-airplay-metadata.service}"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"
STATE_PATH="${ACP_STATE_PATH:-$REPO_DIR/state.json}"
ARTWORK_DIR="${ACP_ARTWORK_DIR:-$REPO_DIR/app/static/generated}"
LISTENER_PATH="$REPO_DIR/scripts/airplay-metadata-listener.py"

if [[ ! -f "$LISTENER_PATH" ]]; then
  echo "Could not find metadata listener: $LISTENER_PATH" >&2
  exit 1
fi

sudo mkdir -p "$(dirname "$PIPE_PATH")" "$ARTWORK_DIR"

if [[ -e "$PIPE_PATH" && ! -p "$PIPE_PATH" ]]; then
  echo "Metadata path exists but is not a FIFO: $PIPE_PATH" >&2
  exit 1
fi

if [[ ! -e "$PIPE_PATH" ]]; then
  sudo mkfifo "$PIPE_PATH"
fi

sudo chmod 666 "$PIPE_PATH"
sudo chown "$ACP_USER:$ACP_USER" "$ARTWORK_DIR"
chmod +x "$LISTENER_PATH"

cat <<SERVICE_EOF | sudo tee "$SERVICE_PATH" >/dev/null
[Unit]
Description=A Clockwork Plex AirPlay Metadata Listener
After=a-clockwork-plex.service shairport-sync.service
Wants=a-clockwork-plex.service

[Service]
Type=simple
User=$ACP_USER
WorkingDirectory=$REPO_DIR
Environment=PYTHONUNBUFFERED=1
Environment=SHAIRPORT_METADATA_PIPE=$PIPE_PATH
Environment=ACP_BASE_DIR=$REPO_DIR
Environment=ACP_STATE_PATH=$STATE_PATH
Environment=ACP_ARTWORK_DIR=$ARTWORK_DIR
ExecStart=/usr/bin/python3 $LISTENER_PATH
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SERVICE_EOF

sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"

echo "Installed AirPlay metadata listener service:"
echo "  $SERVICE_NAME"
echo
echo "Metadata FIFO:"
echo "  $PIPE_PATH"
echo
echo "Add or update this block in /etc/shairport-sync.conf:"
echo "metadata ="
echo "{"
echo "    enabled = \"yes\";"
echo "    include_cover_art = \"yes\";"
echo "    pipe_name = \"$PIPE_PATH\";"
echo "    pipe_timeout = 5000;"
echo "};"
echo
echo "Then run:"
echo "  shairport-sync -t"
echo "  sudo systemctl restart shairport-sync"
echo
echo "Watch metadata logs with:"
echo "  journalctl -u $SERVICE_NAME -f"
