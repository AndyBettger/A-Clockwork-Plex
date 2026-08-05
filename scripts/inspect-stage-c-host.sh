#!/bin/bash
set -euo pipefail

# Read-only Stage C host discovery. This script changes nothing: it uses no sudo,
# does not load or unload modules, does not touch services, and opens no PCM.

CAMILLADSP_BINARY="${CAMILLADSP_BINARY:-}"
ALSA_CONFIG="${ALSA_CONFIG:-/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf}"
DAC_CARD="${DAC_CARD:-Pro}"
DAC_DEVICE="${DAC_DEVICE:-0}"
SERVICES=(plexamp.service shairport-sync.service a-clockwork-plex.service)

usage() {
    cat <<'EOF'
Usage: bash scripts/inspect-stage-c-host.sh [--binary PATH]

Collects the read-only Pi facts needed before generating the persistent Stage C
installer: snd_aloop parameters and persistence, ALSA card identity, current
route shape/checksum, service states, DAC state and an optional CamillaDSP binary
version/checksum.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --binary)
            [[ $# -ge 2 ]] || { echo "--binary requires a path." >&2; exit 64; }
            CAMILLADSP_BINARY="$2"
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

section() {
    printf '\n=== %s ===\n' "$1"
}

print_file_if_present() {
    local path="$1"
    if [[ -r "$path" ]]; then
        printf '%s\n' "--- $path"
        sed -n '1,160p' "$path"
    fi
}

section "Host"
printf 'timestamp=%s\n' "$(date --iso-8601=seconds)"
printf 'hostname=%s\n' "$(hostname)"
printf 'architecture=%s\n' "$(uname -m)"
printf 'kernel=%s\n' "$(uname -r)"
printf 'user=%s\n' "$(id -un)"

section "snd_aloop module"
if command -v modinfo >/dev/null 2>&1; then
    modinfo -F filename snd_aloop 2>&1 | sed 's/^/module_file=/'
    modinfo -p snd_aloop 2>&1 || true
else
    echo "modinfo=unavailable"
fi
if command -v lsmod >/dev/null 2>&1; then
    lsmod | awk 'NR == 1 || $1 == "snd_aloop"'
fi
if [[ -d /sys/module/snd_aloop/parameters ]]; then
    for parameter in /sys/module/snd_aloop/parameters/*; do
        [[ -r "$parameter" ]] || continue
        printf '%s=' "$(basename "$parameter")"
        cat "$parameter"
    done
else
    echo "loaded=false"
fi

section "snd_aloop persistence files"
print_file_if_present /etc/modules
for path in \
    /etc/modules-load.d/*aloop*.conf \
    /etc/modprobe.d/*aloop*.conf \
    /etc/modprobe.d/*loopback*.conf; do
    [[ -e "$path" ]] || continue
    print_file_if_present "$path"
done

section "ALSA cards"
cat /proc/asound/cards 2>/dev/null || echo "/proc/asound/cards unavailable"
printf '\nPlayback devices:\n'
aplay -l 2>&1 || true
printf '\nA Clockwork Plex PCMs:\n'
aplay -L 2>/dev/null | grep -E '^acp_(dmix|master|plexamp|airplay|alarm)$' || true

section "Current production route"
printf 'path=%s\n' "$ALSA_CONFIG"
if [[ -r "$ALSA_CONFIG" ]]; then
    printf 'sha256=%s\n' "$(sha256sum "$ALSA_CONFIG" | awk '{print $1}')"
    printf 'mode=%s owner=%s:%s\n' \
        "$(stat -c '%a' "$ALSA_CONFIG")" \
        "$(stat -c '%U' "$ALSA_CONFIG")" \
        "$(stat -c '%G' "$ALSA_CONFIG")"
    printf '\nAlarm softvol block:\n'
    awk '
        /^pcm\.acp_alarm_volume[[:space:]]*\{/ {printing=1}
        printing {print}
        printing && /^}/ {exit}
    ' "$ALSA_CONFIG"
else
    echo "readable=false"
fi

section "Service states"
for service in "${SERVICES[@]}"; do
    active="$(systemctl is-active "$service" 2>/dev/null || true)"
    enabled="$(systemctl is-enabled "$service" 2>/dev/null || true)"
    printf '%s active=%s enabled=%s\n' "$service" "${active:-unknown}" "${enabled:-unknown}"
done
for service in \
    a-clockwork-plex-audio-route.service \
    a-clockwork-plex-camilladsp.service \
    a-clockwork-plex-audio-failback.service; do
    active="$(systemctl is-active "$service" 2>/dev/null || true)"
    enabled="$(systemctl is-enabled "$service" 2>/dev/null || true)"
    printf '%s active=%s enabled=%s\n' "$service" "${active:-unknown}" "${enabled:-unknown}"
done

section "Running CamillaDSP"
if pgrep -a -x camilladsp >/dev/null 2>&1; then
    pgrep -a -x camilladsp
else
    echo "running=false"
fi

section "CamillaDSP candidate binary"
if [[ -n "$CAMILLADSP_BINARY" ]]; then
    printf 'requested_path=%s\n' "$CAMILLADSP_BINARY"
    if [[ -x "$CAMILLADSP_BINARY" ]]; then
        printf 'resolved_path=%s\n' "$(realpath "$CAMILLADSP_BINARY")"
        printf 'sha256=%s\n' "$(sha256sum "$CAMILLADSP_BINARY" | awk '{print $1}')"
        "$CAMILLADSP_BINARY" --version 2>&1 | head -n 3
    else
        echo "executable=false"
    fi
else
    echo "not supplied; rerun with --binary PATH"
fi

section "DAC state"
printf 'requested=hw:CARD=%s,DEV=%s\n' "$DAC_CARD" "$DAC_DEVICE"
dac_index="$(awk -v wanted="$DAC_CARD" '$0 ~ "\\[" wanted "[[:space:]]*\\]" {print $1; exit}' /proc/asound/cards 2>/dev/null || true)"
printf 'card_index=%s\n' "${dac_index:-unresolved}"
if [[ "$dac_index" =~ ^[0-9]+$ ]]; then
    device="/dev/snd/pcmC${dac_index}D${DAC_DEVICE}p"
    printf 'device=%s exists=%s\n' "$device" "$([[ -e "$device" ]] && echo true || echo false)"
    if command -v fuser >/dev/null 2>&1; then
        fuser -v "$device" 2>&1 || true
    fi
fi
hw_params="/proc/asound/Pro/pcm0p/sub0/hw_params"
print_file_if_present "$hw_params"

section "Stage C discovery complete"
echo "No file, service, module, mixer level or audio route was changed."
