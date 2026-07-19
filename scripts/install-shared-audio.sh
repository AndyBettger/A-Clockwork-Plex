#!/bin/bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this installer with sudo." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_USER="${PROJECT_USER:-andy}"
PROJECT_HOME="${PROJECT_HOME:-/home/$PROJECT_USER}"
ALSA_CARD="${ALSA_CARD:-Pro}"
ALSA_DEVICE="${ALSA_DEVICE:-0}"
SHAIRPORT_CONFIG="${SHAIRPORT_CONFIG:-/etc/shairport-sync.conf}"
ALSA_CONFIG="${ALSA_CONFIG:-/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf}"
MIXER_DEFAULTS="${MIXER_DEFAULTS:-/etc/default/a-clockwork-plex-audio}"
MIXER_HELPER="${MIXER_HELPER:-/usr/local/bin/a-clockwork-plex-audio-mixer}"
MIXER_SUDOERS="${MIXER_SUDOERS:-/etc/sudoers.d/a-clockwork-plex-audio-mixer}"
ASOUNDRC="$PROJECT_HOME/.asoundrc"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

validate_simple() {
    local label="$1"
    local value="$2"
    if [[ ! "$value" =~ ^[A-Za-z0-9_.@-]+$ ]]; then
        echo "Invalid $label: $value" >&2
        exit 64
    fi
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Required command not found: $1" >&2
        exit 1
    }
}

validate_simple "PROJECT_USER" "$PROJECT_USER"
validate_simple "ALSA_CARD" "$ALSA_CARD"
[[ "$ALSA_DEVICE" =~ ^[0-9]+$ ]] || { echo "ALSA_DEVICE must be numeric." >&2; exit 64; }

for command in aplay amixer alsactl python3 install visudo timeout; do
    require_command "$command"
done

if ! id "$PROJECT_USER" >/dev/null 2>&1; then
    echo "Project user does not exist: $PROJECT_USER" >&2
    exit 1
fi

install -d -m 0755 "$(dirname "$ALSA_CONFIG")" "$(dirname "$MIXER_DEFAULTS")"

if [[ -e "$ALSA_CONFIG" ]]; then
    cp -a "$ALSA_CONFIG" "$ALSA_CONFIG.$TIMESTAMP.bak"
fi

cat > "$ALSA_CONFIG" <<EOF
# Managed by A Clockwork Plex.
# Three source-specific softvol controls feed one master softvol and dmix PCM.

pcm.acp_dmix {
    type dmix
    ipc_key 1094931536
    ipc_key_add_uid false
    ipc_perm 0666
    slave {
        pcm "hw:CARD=$ALSA_CARD,DEV=$ALSA_DEVICE"
        format S16_LE
        rate 44100
        channels 2
        period_size 1024
        buffer_size 8192
    }
    bindings {
        0 0
        1 1
    }
}

pcm.acp_master_volume {
    type softvol
    slave.pcm "acp_dmix"
    control {
        name "A Clockwork Master"
        card "$ALSA_CARD"
    }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}

pcm.acp_master {
    type plug
    slave.pcm "acp_master_volume"
    hint {
        show on
        description "A Clockwork Plex - Shared master"
    }
}

pcm.acp_plexamp_volume {
    type softvol
    slave.pcm "acp_master"
    control {
        name "A Clockwork Plexamp"
        card "$ALSA_CARD"
    }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}

pcm.acp_plexamp {
    type plug
    slave.pcm "acp_plexamp_volume"
    hint {
        show on
        description "A Clockwork Plex - Plexamp"
    }
}

pcm.acp_airplay_volume {
    type softvol
    slave.pcm "acp_master"
    control {
        name "A Clockwork AirPlay"
        card "$ALSA_CARD"
    }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}

pcm.acp_airplay {
    type plug
    slave.pcm "acp_airplay_volume"
    hint {
        show on
        description "A Clockwork Plex - AirPlay"
    }
}

pcm.acp_alarm_volume {
    type softvol
    slave.pcm "acp_master"
    control {
        name "A Clockwork Alarm"
        card "$ALSA_CARD"
    }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}

pcm.acp_alarm {
    type plug
    slave.pcm "acp_alarm_volume"
    hint {
        show on
        description "A Clockwork Plex - Alarm"
    }
}
EOF
chmod 0644 "$ALSA_CONFIG"

cat > "$MIXER_DEFAULTS" <<EOF
# Managed by A Clockwork Plex.
ALSA_CARD=$ALSA_CARD
ALSA_DEVICE=$ALSA_DEVICE
SAMPLE_RATE=44100
CHANNELS=2
EOF
chmod 0644 "$MIXER_DEFAULTS"

install -o root -g root -m 0755 "$SCRIPT_DIR/a-clockwork-plex-audio-mixer.py" "$MIXER_HELPER"

cat > "$MIXER_SUDOERS" <<EOF
# Managed by A Clockwork Plex. The helper validates channel names and 0-100 levels.
$PROJECT_USER ALL=(root) NOPASSWD: $MIXER_HELPER status
$PROJECT_USER ALL=(root) NOPASSWD: $MIXER_HELPER set *
EOF
chmod 0440 "$MIXER_SUDOERS"
visudo -cf "$MIXER_SUDOERS" >/dev/null

# Route applications running as the project user through the Plexamp source PCM
# whenever they ask ALSA for the default output. Existing unmanaged default PCM
# definitions are preserved and reported instead of being silently overwritten.
python3 - "$ASOUNDRC" "$ALSA_CARD" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
card = sys.argv[2]
begin = "# BEGIN A CLOCKWORK PLEX SHARED AUDIO"
end = "# END A CLOCKWORK PLEX SHARED AUDIO"
text = path.read_text(encoding="utf-8") if path.exists() else ""
managed = re.compile(re.escape(begin) + r".*?" + re.escape(end) + r"\n?", re.S)
text_without_managed = managed.sub("", text).rstrip()
if re.search(r"(?m)^\s*pcm\.!default\b", text_without_managed):
    print(f"WARNING: {path} already has an unmanaged pcm.!default; Plexamp may need acp_plexamp selected manually.")
else:
    block = f'''{begin}
pcm.!default {{
    type plug
    slave.pcm "acp_plexamp"
}}
ctl.!default {{
    type hw
    card "{card}"
}}
{end}
'''
    output = (text_without_managed + "\n\n" + block).lstrip() if text_without_managed else block
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(output, encoding="utf-8")
PY
chown "$PROJECT_USER:$PROJECT_USER" "$ASOUNDRC" 2>/dev/null || true
chmod 0644 "$ASOUNDRC" 2>/dev/null || true

# Point Shairport Sync at its own source PCM and bind sender volume to the same
# softvol control shown by the dashboard mixer.
if [[ -f "$SHAIRPORT_CONFIG" ]]; then
    cp -a "$SHAIRPORT_CONFIG" "$SHAIRPORT_CONFIG.$TIMESTAMP.bak"
    python3 - "$SHAIRPORT_CONFIG" "$ALSA_CARD" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
card = sys.argv[2]
text = path.read_text(encoding="utf-8")

block_match = re.search(r"(?ms)^\s*alsa\s*=\s*\{.*?^\s*\};", text)
values = {
    "output_device": "acp_airplay",
    "mixer_control_name": "A Clockwork AirPlay",
    "mixer_device": f"hw:CARD={card}",
}

if block_match:
    block = block_match.group(0)
    for key, value in values.items():
        pattern = re.compile(rf'(?m)^(\s*)#?\s*{re.escape(key)}\s*=\s*"[^"]*"\s*;')
        if pattern.search(block):
            block = pattern.sub(lambda match: f'{match.group(1)}{key} = "{value}";', block, count=1)
        else:
            opening = re.search(r"\{\s*\n", block)
            insertion = f'    {key} = "{value}";\n'
            block = block[:opening.end()] + insertion + block[opening.end():] if opening else block
    text = text[:block_match.start()] + block + text[block_match.end():]
else:
    text = text.rstrip() + "\n\nalsa =\n{\n" + "".join(
        f'    {key} = "{value}";\n' for key, value in values.items()
    ) + "};\n"

path.write_text(text, encoding="utf-8")
PY
else
    echo "WARNING: $SHAIRPORT_CONFIG was not found; configure Shairport output_device = \"acp_airplay\" manually." >&2
fi

# Activate the new lightweight AirPlay hooks, which pause Plexamp but never stop
# its service now that both programs can share the DAC.
bash "$SCRIPT_DIR/install-airplay-hooks.sh"

# Open each PCM with silence so ALSA creates its softvol control before the web
# UI tries to read it. timeout returning 124 is expected and harmless.
for pcm in acp_master acp_plexamp acp_airplay acp_alarm; do
    timeout 0.35 /usr/bin/aplay -q -D "$pcm" -f S16_LE -r 44100 -c 2 /dev/zero >/dev/null 2>&1 || true
done

"$MIXER_HELPER" set master 80 >/dev/null
"$MIXER_HELPER" set plexamp 100 >/dev/null
"$MIXER_HELPER" set airplay 100 >/dev/null
"$MIXER_HELPER" set alarm 100 >/dev/null

# Migrate this checkout to shared mode without enabling scheduled alarm audio.
if [[ -f "$PROJECT_DIR/config.json" ]]; then
    python3 - "$PROJECT_DIR/config.json" "$ALSA_CARD" "$ALSA_DEVICE" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
card = sys.argv[2]
device = sys.argv[3]
try:
    config = json.loads(path.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"WARNING: could not migrate {path}: {exc}")
    raise SystemExit(0)

audio = config.get("alarm_audio") if isinstance(config.get("alarm_audio"), dict) else {}
audio.update(
    {
        "shared_mixer_enabled": True,
        "hardware_device": f"hw:CARD={card},DEV={device}",
        "alsa_device": "acp_alarm",
        "release_services": False,
        "restore_services": False,
        "mixer_helper_path": "/usr/local/bin/a-clockwork-plex-audio-mixer",
        "scheduled_enabled": False,
    }
)
config["alarm_audio"] = audio
temporary = path.with_suffix(path.suffix + ".tmp")
temporary.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
temporary.replace(path)
PY
fi

echo
echo "Shared ALSA mixer installed."
echo "  Physical DAC: hw:CARD=$ALSA_CARD,DEV=$ALSA_DEVICE"
echo "  Plexamp PCM:   acp_plexamp"
echo "  AirPlay PCM:   acp_airplay"
echo "  Alarm PCM:     acp_alarm"
echo "  Master PCM:    acp_master"
echo
echo "Mixer status:"
"$MIXER_HELPER" status | python3 -m json.tool || true
echo
echo "Restart the audio services and dashboard:"
echo "  sudo systemctl restart plexamp.service"
echo "  sudo systemctl restart shairport-sync.service"
echo "  sudo systemctl restart a-clockwork-plex.service"
echo
echo "Plexamp should use its default output or the ALSA PCM named acp_plexamp."
