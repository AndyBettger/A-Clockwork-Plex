#!/bin/bash
set -euo pipefail

# Stage C1 prepares the deterministic persistent-route package inside a private
# laboratory directory. It has no activation mode and performs no privileged,
# service, module, mixer or PCM operation.

CAMILLADSP_BINARY=""
LAB_ROOT="${LAB_ROOT:-}"
EXPECTED_CAMILLADSP_VERSION="4.1.3"
EXPECTED_CAMILLADSP_SHA256="e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa"
EXPECTED_CURRENT_ALSA_SHA256="08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9"
CURRENT_ALSA_CONFIG="${CURRENT_ALSA_CONFIG:-/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf}"
PROJECT_USER="${PROJECT_USER:-$(id -un)}"
DAC_CARD="${DAC_CARD:-Pro}"
DAC_DEVICE="${DAC_DEVICE:-0}"
LOOPBACK_INDEX="${LOOPBACK_INDEX:-7}"
LOOPBACK_ID="${LOOPBACK_ID:-ACP_Loopback}"
SAMPLE_RATE=44100
FORMAT=S16_LE
PERIOD_SIZE=1024
BUFFER_SIZE=8192
CHUNKSIZE=1024
TARGET_LEVEL=2048
LIMIT_DB=-1.0
PACKAGE_VERSION=1

usage() {
    cat <<'EOF'
Usage:
  bash scripts/prepare-stage-c-route-package.sh --binary PATH [--lab-root PATH]

Generates and validates the Stage C1 persistent route package. This script has
no activation mode. It never invokes sudo, writes a production path, loads a
module, changes a service, opens a PCM or changes a mixer value.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --binary)
            [[ $# -ge 2 ]] || { echo "--binary requires a path." >&2; exit 64; }
            CAMILLADSP_BINARY="$2"
            shift 2
            ;;
        --lab-root)
            [[ $# -ge 2 ]] || { echo "--lab-root requires a path." >&2; exit 64; }
            LAB_ROOT="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 64
            ;;
    esac
done

[[ -n "$CAMILLADSP_BINARY" ]] || { echo "--binary PATH is required." >&2; exit 64; }
[[ "$EUID" -ne 0 ]] || { echo "Run as $PROJECT_USER, not as root." >&2; exit 1; }
[[ "$(uname -m)" == "aarch64" ]] || { echo "Expected aarch64; found $(uname -m)." >&2; exit 1; }
[[ "$PROJECT_USER" =~ ^[A-Za-z0-9_.@-]+$ ]] || { echo "Invalid project user: $PROJECT_USER" >&2; exit 64; }
[[ "$DAC_CARD" =~ ^[A-Za-z0-9_.@-]+$ ]] || { echo "Invalid DAC card: $DAC_CARD" >&2; exit 64; }
[[ "$DAC_DEVICE" =~ ^[0-9]+$ ]] || { echo "Invalid DAC device: $DAC_DEVICE" >&2; exit 64; }
[[ "$LOOPBACK_INDEX" =~ ^[0-9]+$ ]] || { echo "Invalid loopback index: $LOOPBACK_INDEX" >&2; exit 64; }
[[ "$LOOPBACK_ID" =~ ^[A-Za-z0-9_.@-]+$ ]] || { echo "Invalid loopback ID: $LOOPBACK_ID" >&2; exit 64; }

require_command() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Required command not found: $1" >&2
        exit 1
    }
}

for command in aplay awk chmod cp grep mkdir mktemp python3 sed sha256sum stat; do
    require_command "$command"
done

[[ -x "$CAMILLADSP_BINARY" ]] || { echo "CamillaDSP binary is not executable: $CAMILLADSP_BINARY" >&2; exit 1; }
binary_version="$("$CAMILLADSP_BINARY" --version 2>&1 | head -n1)"
grep -Fq "$EXPECTED_CAMILLADSP_VERSION" <<<"$binary_version" || {
    echo "Unexpected CamillaDSP version: $binary_version" >&2
    exit 1
}
binary_sha="$(sha256sum "$CAMILLADSP_BINARY" | awk '{print $1}')"
[[ "$binary_sha" == "$EXPECTED_CAMILLADSP_SHA256" ]] || {
    echo "Unexpected CamillaDSP SHA-256: $binary_sha" >&2
    exit 1
}

[[ -r "$CURRENT_ALSA_CONFIG" ]] || { echo "Current ALSA route is unreadable: $CURRENT_ALSA_CONFIG" >&2; exit 1; }
current_alsa_sha="$(sha256sum "$CURRENT_ALSA_CONFIG" | awk '{print $1}')"
[[ "$current_alsa_sha" == "$EXPECTED_CURRENT_ALSA_SHA256" ]] || {
    echo "Current ALSA checksum differs from the physically validated pre-Stage-C route." >&2
    echo "Expected: $EXPECTED_CURRENT_ALSA_SHA256" >&2
    echo "Observed: $current_alsa_sha" >&2
    exit 1
}
python3 - "$CURRENT_ALSA_CONFIG" <<'PY_CURRENT_ROUTE'
from pathlib import Path
import sys

text = Path(sys.argv[1]).read_text(encoding="utf-8")
start = text.index("pcm.acp_alarm_volume")
end = text.index("pcm.acp_alarm {", start)
block = text[start:end]
if 'slave.pcm "acp_master"' not in block:
    raise SystemExit("current route is not the expected pre-Stage-C alarm-under-Master graph")
PY_CURRENT_ROUTE

[[ -d /sys/module/snd_aloop/parameters ]] || { echo "snd_aloop is not loaded." >&2; exit 1; }
parameter_starts_with() {
    local name="$1"
    local expected="$2"
    local value
    value="$(cat "/sys/module/snd_aloop/parameters/$name")"
    [[ "${value%%,*}" == "$expected" ]] || {
        echo "Unexpected snd_aloop $name: $value" >&2
        exit 1
    }
}
parameter_starts_with index "$LOOPBACK_INDEX"
parameter_starts_with id "$LOOPBACK_ID"
parameter_starts_with pcm_substreams 2
parameter_starts_with pcm_notify 1

grep -Eq "^[[:space:]]*$LOOPBACK_INDEX[[:space:]]+\[ACPLoopback[[:space:]]*\]" /proc/asound/cards || {
    echo "Loopback card $LOOPBACK_INDEX / ACPLoopback was not found." >&2
    exit 1
}
grep -Eq '^[[:space:]]*[0-9]+[[:space:]]+\[Pro[[:space:]]*\]' /proc/asound/cards || {
    echo "Physical DAC card Pro was not found." >&2
    exit 1
}

if [[ -z "$LAB_ROOT" ]]; then
    LAB_ROOT="$(mktemp -d /var/tmp/a-clockwork-plex-stage-c1-package.XXXXXX)"
else
    mkdir -p "$LAB_ROOT"
    LAB_ROOT="$(cd "$LAB_ROOT" && pwd)"
fi
chmod 0700 "$LAB_ROOT"

ROOTFS="$LAB_ROOT/rootfs"
MANIFEST="$LAB_ROOT/manifest.tsv"
REPORT="$LAB_ROOT/report.txt"
RESULTS="$LAB_ROOT/results.tsv"
mkdir -p \
    "$ROOTFS/etc/a-clockwork-plex/audio-routes" \
    "$ROOTFS/etc/default" \
    "$ROOTFS/etc/modules-load.d" \
    "$ROOTFS/etc/modprobe.d" \
    "$ROOTFS/etc/sudoers.d" \
    "$ROOTFS/etc/systemd/system" \
    "$ROOTFS/usr/local/bin" \
    "$ROOTFS/usr/local/lib/a-clockwork-plex/camilladsp-$EXPECTED_CAMILLADSP_VERSION" \
    "$ROOTFS/var/lib/a-clockwork-plex/split-bus"

SPLIT_ROUTE="$ROOTFS/etc/a-clockwork-plex/audio-routes/split-bus.conf"
DIRECT_ROUTE="$ROOTFS/etc/a-clockwork-plex/audio-routes/direct-alarm-bypass.conf"
CAMILLA_CONFIG="$ROOTFS/etc/a-clockwork-plex/camilladsp-split-bus.yml"
DEFAULTS="$ROOTFS/etc/default/a-clockwork-plex-split-bus"
MODULE_LOAD="$ROOTFS/etc/modules-load.d/a-clockwork-plex-aloop.conf"
MODULE_OPTIONS="$ROOTFS/etc/modprobe.d/a-clockwork-plex-aloop.conf"
ROUTE_HELPER="$ROOTFS/usr/local/bin/a-clockwork-plex-audio-route"
ROUTE_SUDOERS="$ROOTFS/etc/sudoers.d/a-clockwork-plex-audio-route"
ROUTE_UNIT="$ROOTFS/etc/systemd/system/a-clockwork-plex-audio-route.service"
CAMILLA_UNIT="$ROOTFS/etc/systemd/system/a-clockwork-plex-camilladsp.service"
FAILBACK_UNIT="$ROOTFS/etc/systemd/system/a-clockwork-plex-audio-failback.service"
STAGED_BINARY="$ROOTFS/usr/local/lib/a-clockwork-plex/camilladsp-$EXPECTED_CAMILLADSP_VERSION/camilladsp"

cat >"$MODULE_LOAD" <<EOF_MODULE_LOAD
# Managed candidate generated by A Clockwork Plex Stage C1.
snd_aloop
EOF_MODULE_LOAD

cat >"$MODULE_OPTIONS" <<EOF_MODULE_OPTIONS
# Managed candidate generated by A Clockwork Plex Stage C1.
options snd_aloop index=$LOOPBACK_INDEX id=$LOOPBACK_ID pcm_substreams=2 pcm_notify=1
EOF_MODULE_OPTIONS

cat >"$DEFAULTS" <<EOF_DEFAULTS
# Managed candidate generated by A Clockwork Plex Stage C1.
PROJECT_USER=$PROJECT_USER
DAC_CARD=$DAC_CARD
DAC_DEVICE=$DAC_DEVICE
LOOPBACK_INDEX=$LOOPBACK_INDEX
LOOPBACK_ID=$LOOPBACK_ID
SAMPLE_RATE=$SAMPLE_RATE
FORMAT=$FORMAT
PERIOD_SIZE=$PERIOD_SIZE
BUFFER_SIZE=$BUFFER_SIZE
CAMILLADSP_VERSION=$EXPECTED_CAMILLADSP_VERSION
CAMILLADSP_SHA256=$EXPECTED_CAMILLADSP_SHA256
PRE_STAGE_C_ALSA_SHA256=$EXPECTED_CURRENT_ALSA_SHA256
ACTIVE_ALSA_CONFIG=/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf
SPLIT_ROUTE=/etc/a-clockwork-plex/audio-routes/split-bus.conf
DIRECT_FAILBACK_ROUTE=/etc/a-clockwork-plex/audio-routes/direct-alarm-bypass.conf
CAMILLADSP_BINARY=/usr/local/lib/a-clockwork-plex/camilladsp-$EXPECTED_CAMILLADSP_VERSION/camilladsp
CAMILLADSP_CONFIG=/etc/a-clockwork-plex/camilladsp-split-bus.yml
STATE_DIR=/var/lib/a-clockwork-plex/split-bus
EOF_DEFAULTS

cat >"$SPLIT_ROUTE" <<EOF_SPLIT
# A Clockwork Plex Stage C split-bus candidate.
# Music occupies loopback channels 0/1; alarm occupies 2/3.
pcm.acp_dmix {
    type dmix
    ipc_key 1094934536
    ipc_key_add_uid false
    ipc_perm 0666
    slave {
        pcm "hw:$LOOPBACK_INDEX,0,0"
        format $FORMAT
        rate $SAMPLE_RATE
        channels 4
        period_size $PERIOD_SIZE
        buffer_size $BUFFER_SIZE
    }
    bindings { 0 0 1 1 2 2 3 3 }
}
pcm.acp_music_route {
    type route
    slave { pcm "acp_dmix" channels 4 }
    ttable { 0.0 1 1.1 1 }
}
pcm.acp_alarm_route {
    type route
    slave { pcm "acp_dmix" channels 4 }
    ttable { 0.2 1 1.3 1 }
}
pcm.acp_master_volume {
    type softvol
    slave.pcm "acp_music_route"
    control { name "A Clockwork Master" card "$DAC_CARD" }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}
pcm.acp_master { type plug slave.pcm "acp_master_volume" hint { show on description "A Clockwork Plex - Music master" } }
pcm.acp_plexamp_volume {
    type softvol
    slave.pcm "acp_master"
    control { name "A Clockwork Plexamp" card "$DAC_CARD" }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}
pcm.acp_plexamp { type plug slave.pcm "acp_plexamp_volume" hint { show on description "A Clockwork Plex - Plexamp" } }
pcm.acp_airplay_volume {
    type softvol
    slave.pcm "acp_master"
    control { name "A Clockwork AirPlay" card "$DAC_CARD" }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}
pcm.acp_airplay { type plug slave.pcm "acp_airplay_volume" hint { show on description "A Clockwork Plex - AirPlay" } }
pcm.acp_alarm_volume {
    type softvol
    slave.pcm "acp_alarm_route"
    control { name "A Clockwork Alarm" card "$DAC_CARD" }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}
pcm.acp_alarm { type plug slave.pcm "acp_alarm_volume" hint { show on description "A Clockwork Plex - Independent alarm ceiling" } }
EOF_SPLIT

cat >"$DIRECT_ROUTE" <<EOF_DIRECT
# A Clockwork Plex Stage C direct alarm-bypass failback candidate.
pcm.acp_dmix {
    type dmix
    ipc_key 1094931536
    ipc_key_add_uid false
    ipc_perm 0666
    slave {
        pcm "hw:CARD=$DAC_CARD,DEV=$DAC_DEVICE"
        format $FORMAT
        rate $SAMPLE_RATE
        channels 2
        period_size $PERIOD_SIZE
        buffer_size $BUFFER_SIZE
    }
    bindings { 0 0 1 1 }
}
pcm.acp_master_volume {
    type softvol
    slave.pcm "acp_dmix"
    control { name "A Clockwork Master" card "$DAC_CARD" }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}
pcm.acp_master { type plug slave.pcm "acp_master_volume" hint { show on description "A Clockwork Plex - Music master direct failback" } }
pcm.acp_plexamp_volume {
    type softvol
    slave.pcm "acp_master"
    control { name "A Clockwork Plexamp" card "$DAC_CARD" }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}
pcm.acp_plexamp { type plug slave.pcm "acp_plexamp_volume" hint { show on description "A Clockwork Plex - Plexamp" } }
pcm.acp_airplay_volume {
    type softvol
    slave.pcm "acp_master"
    control { name "A Clockwork AirPlay" card "$DAC_CARD" }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}
pcm.acp_airplay { type plug slave.pcm "acp_airplay_volume" hint { show on description "A Clockwork Plex - AirPlay" } }
pcm.acp_alarm_volume {
    type softvol
    slave.pcm "acp_dmix"
    control { name "A Clockwork Alarm" card "$DAC_CARD" }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}
pcm.acp_alarm { type plug slave.pcm "acp_alarm_volume" hint { show on description "A Clockwork Plex - Independent alarm direct failback" } }
EOF_DIRECT

cat >"$CAMILLA_CONFIG" <<EOF_CAMILLA
---
title: "A Clockwork Plex Stage C split bus"
description: "Music-only EQ and headroom, independent alarm, final limiter"
devices:
  samplerate: $SAMPLE_RATE
  chunksize: $CHUNKSIZE
  queuelimit: 4
  silence_timeout: 0
  target_level: $TARGET_LEVEL
  adjust_period: 1
  enable_rate_adjust: true
  resampler: null
  volume_ramp_time: 100
  volume_limit: 0.0
  capture:
    type: Alsa
    channels: 4
    device: "hw:$LOOPBACK_INDEX,1,0"
    format: $FORMAT
  playback:
    type: Alsa
    channels: 2
    device: "hw:CARD=$DAC_CARD,DEV=$DAC_DEVICE"
    format: $FORMAT
filters:
  bass: {type: Biquad, parameters: {type: Lowshelf, freq: 125, gain: 0.0, slope: 6}}
  mid: {type: Biquad, parameters: {type: Peaking, freq: 1000, gain: 0.0, q: 0.7}}
  treble: {type: Biquad, parameters: {type: Highshelf, freq: 4000, gain: 0.0, slope: 6}}
  headroom: {type: Gain, parameters: {gain: 0.0, scale: dB, inverted: false, mute: false}}
  final_safety_limiter: {type: Limiter, parameters: {soft_clip: false, clip_limit: $LIMIT_DB}}
mixers:
  combine_music_and_alarm:
    channels: {in: 4, out: 2}
    mapping:
      - dest: 0
        sources:
          - {channel: 0, gain: 0, scale: dB, inverted: false}
          - {channel: 2, gain: 0, scale: dB, inverted: false}
      - dest: 1
        sources:
          - {channel: 1, gain: 0, scale: dB, inverted: false}
          - {channel: 3, gain: 0, scale: dB, inverted: false}
pipeline:
  - {type: Filter, channels: [0, 1], names: [bass, mid, treble, headroom]}
  - {type: Mixer, name: combine_music_and_alarm}
  - {type: Filter, channels: [0, 1], names: [final_safety_limiter]}
EOF_CAMILLA

cat >"$ROUTE_HELPER" <<'PY_ROUTE_HELPER'
#!/usr/bin/python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

DEFAULTS = Path('/etc/default/a-clockwork-plex-split-bus')
STATE = Path('/var/lib/a-clockwork-plex/split-bus/route-state.json')
ACTIVE = Path('/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf')
BLOCKED = {'boot-select', 'activate-split-bus', 'activate-direct-failback', 'restore-backup'}


def digest(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def status() -> dict[str, object]:
    try:
        state = json.loads(STATE.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        state = {'mode': 'offline', 'reason': 'no committed Stage C state'}
    return {
        'ok': True,
        'package_phase': 'stage-c1-candidate-only',
        'activation_approved': False,
        'active_alsa_sha256': digest(ACTIVE),
        'defaults_present': DEFAULTS.exists(),
        'state': state,
    }


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if action == 'status' and len(sys.argv) == 2:
        print(json.dumps(status(), sort_keys=True))
        return 0
    if action == 'validate-package' and len(sys.argv) == 2:
        payload = status()
        payload['validated'] = DEFAULTS.exists()
        print(json.dumps(payload, sort_keys=True))
        return 0 if payload['validated'] else 1
    if action in BLOCKED:
        print(json.dumps({'ok': False, 'error': 'Stage C1 is prepare-only; mutation is deliberately blocked.'}), file=sys.stderr)
        return 78
    print(json.dumps({'ok': False, 'error': f'Unsupported action: {action}'}), file=sys.stderr)
    return 64


if __name__ == '__main__':
    raise SystemExit(main())
PY_ROUTE_HELPER

cat >"$ROUTE_SUDOERS" <<EOF_SUDOERS
# Stage C1 candidate only. Mutation actions are not authorised.
$PROJECT_USER ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-audio-route status
$PROJECT_USER ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-audio-route validate-package
EOF_SUDOERS

cat >"$CAMILLA_UNIT" <<EOF_CAMILLA_UNIT
[Unit]
Description=A Clockwork Plex split-bus CamillaDSP
After=sound.target systemd-modules-load.service
Requires=sound.target
OnFailure=a-clockwork-plex-audio-failback.service
ConditionPathExists=/var/lib/a-clockwork-plex/split-bus/activation-approved
StartLimitIntervalSec=60
StartLimitBurst=3

[Service]
Type=simple
User=$PROJECT_USER
Group=audio
ExecStart=/usr/local/lib/a-clockwork-plex/camilladsp-$EXPECTED_CAMILLADSP_VERSION/camilladsp /etc/a-clockwork-plex/camilladsp-split-bus.yml
Restart=on-failure
RestartSec=2
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF_CAMILLA_UNIT

cat >"$ROUTE_UNIT" <<EOF_ROUTE_UNIT
[Unit]
Description=A Clockwork Plex guarded audio-route authority
After=systemd-modules-load.service sound.target
Before=plexamp.service shairport-sync.service a-clockwork-plex.service
Wants=sound.target
ConditionPathExists=/var/lib/a-clockwork-plex/split-bus/activation-approved

[Service]
Type=oneshot
ExecStart=/usr/local/bin/a-clockwork-plex-audio-route boot-select
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF_ROUTE_UNIT

cat >"$FAILBACK_UNIT" <<EOF_FAILBACK_UNIT
[Unit]
Description=A Clockwork Plex direct alarm-bypass failback
After=sound.target
ConditionPathExists=/var/lib/a-clockwork-plex/split-bus/activation-approved

[Service]
Type=oneshot
ExecStart=/usr/local/bin/a-clockwork-plex-audio-route activate-direct-failback
EOF_FAILBACK_UNIT

cp "$CAMILLADSP_BINARY" "$STAGED_BINARY"
chmod 0755 "$STAGED_BINARY" "$ROUTE_HELPER"
chmod 0644 "$SPLIT_ROUTE" "$DIRECT_ROUTE" "$CAMILLA_CONFIG" "$DEFAULTS" "$MODULE_LOAD" "$MODULE_OPTIONS" "$ROUTE_UNIT" "$CAMILLA_UNIT" "$FAILBACK_UNIT"
chmod 0440 "$ROUTE_SUDOERS"

build_alsa_validation_root() {
    local fragment="$1"
    local output="$2"
    python3 - /usr/share/alsa/alsa.conf "$fragment" "$output" <<'PY_ALSA_ROOT'
from pathlib import Path
import sys

base = Path(sys.argv[1]).read_text(encoding='utf-8').splitlines()
fragment = Path(sys.argv[2]).read_text(encoding='utf-8')
out: list[str] = []
skipping = False
depth = 0
removed = False
for line in base:
    stripped = line.strip()
    if not removed and not skipping and stripped.startswith('@hooks') and '[' in stripped:
        skipping = True
        depth = line.count('[') - line.count(']')
        if depth == 0:
            skipping = False
            removed = True
        continue
    if skipping:
        depth += line.count('[') - line.count(']')
        if depth == 0:
            skipping = False
            removed = True
        continue
    out.append(line)
if not removed:
    raise SystemExit('could not remove global ALSA preload hook')
out.extend(('', fragment))
Path(sys.argv[3]).write_text('\n'.join(out).rstrip() + '\n', encoding='utf-8')
PY_ALSA_ROOT
}

printf 'check\tresult\tdetail\n' >"$RESULTS"
for route in split direct; do
    if [[ "$route" == split ]]; then fragment="$SPLIT_ROUTE"; else fragment="$DIRECT_ROUTE"; fi
    validation="$LAB_ROOT/alsa-$route-validation.conf"
    build_alsa_validation_root "$fragment" "$validation"
    if ALSA_CONFIG_PATH="$validation" aplay -L >"$LAB_ROOT/aplay-$route.txt" 2>"$LAB_ROOT/aplay-$route.err"; then
        printf 'alsa-%s-parse\tPASS\tcandidate parsed\n' "$route" | tee -a "$RESULTS"
    else
        printf 'alsa-%s-parse\tFAIL\tsee aplay-%s.err\n' "$route" "$route" | tee -a "$RESULTS"
        exit 1
    fi
done

for pcm in acp_dmix acp_master acp_plexamp acp_airplay acp_alarm; do
    grep -q "^$pcm$" "$LAB_ROOT/aplay-split.txt" || { echo "Split route missing $pcm" >&2; exit 1; }
    grep -q "^$pcm$" "$LAB_ROOT/aplay-direct.txt" || { echo "Direct route missing $pcm" >&2; exit 1; }
done
printf 'public-pcm-contract\tPASS\tall five public PCMs exist in both routes\n' | tee -a "$RESULTS"

if "$CAMILLADSP_BINARY" --check "$CAMILLA_CONFIG" >"$LAB_ROOT/camilladsp-check.txt" 2>&1; then
    printf 'camilladsp-config\tPASS\t%s\n' "$binary_version" | tee -a "$RESULTS"
else
    printf 'camilladsp-config\tFAIL\tsee camilladsp-check.txt\n' | tee -a "$RESULTS"
    exit 1
fi

python3 -m py_compile "$ROUTE_HELPER"
printf 'route-helper-syntax\tPASS\tPython candidate compiled\n' | tee -a "$RESULTS"

if command -v visudo >/dev/null 2>&1; then
    if visudo -cf "$ROUTE_SUDOERS" >"$LAB_ROOT/visudo.txt" 2>&1; then
        printf 'sudoers-candidate\tPASS\tvisudo accepted read-only rules\n' | tee -a "$RESULTS"
    else
        printf 'sudoers-candidate\tFAIL\tsee visudo.txt\n' | tee -a "$RESULTS"
        exit 1
    fi
else
    printf 'sudoers-candidate\tSKIP\tvisudo unavailable\n' | tee -a "$RESULTS"
fi

printf 'destination\tmode\towner\tsha256\n' >"$MANIFEST"
manifest_item() {
    local file="$1"
    local destination="/${file#"$ROOTFS/"}"
    local mode
    mode="$(stat -c '%a' "$file")"
    printf '%s\t%s\troot:root\t%s\n' "$destination" "$mode" "$(sha256sum "$file" | awk '{print $1}')" >>"$MANIFEST"
}
while IFS= read -r -d '' file; do manifest_item "$file"; done < <(find "$ROOTFS" -type f -print0 | sort -z)

cat >"$REPORT" <<EOF_REPORT
A Clockwork Plex Stage C1 prepare-only route package
Generated: $(date --iso-8601=seconds)
Package version: $PACKAGE_VERSION
Host: $(hostname)
Architecture: $(uname -m)
Laboratory: $LAB_ROOT
Rootfs candidate: $ROOTFS
Verified CamillaDSP: $binary_version
Verified binary SHA-256: $binary_sha
Verified pre-Stage-C ALSA SHA-256: $current_alsa_sha
Loopback: index $LOOPBACK_INDEX, ID $LOOPBACK_ID, substreams 2, pcm_notify 1
DAC: hw:CARD=$DAC_CARD,DEV=$DAC_DEVICE
Format: $SAMPLE_RATE Hz / $FORMAT / period $PERIOD_SIZE / buffer $BUFFER_SIZE

Safety state:
- no activation option exists
- no sudo command was invoked
- no production path was written
- no module was loaded or unloaded
- no service was started, stopped, restarted, enabled or disabled
- no PCM was opened
- no mixer value was changed
- generated route mutation actions return exit 78
- generated units require an absent activation-approved marker
EOF_REPORT

cat <<EOF_DONE

A Clockwork Plex Stage C1 route package prepared and validated.

  Directory:  $LAB_ROOT
  Rootfs:     $ROOTFS
  Manifest:   $MANIFEST
  Results:    $RESULTS
  Report:     $REPORT

The package contains candidate split-bus and direct-failback ALSA routes,
CamillaDSP configuration, deterministic snd_aloop persistence, staged verified
binary, read-only route helper, restricted sudoers and three guarded systemd
units.

No activation path exists in this script. Generated mutation actions remain
blocked, and every generated unit requires an approval marker that is absent.
Review the manifest and generated files before transaction code is added.
EOF_DONE