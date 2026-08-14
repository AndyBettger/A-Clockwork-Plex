#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export ACP_REPO_ROOT="$REPO_ROOT"

# shellcheck source=installer/lib/common.sh
source "$REPO_ROOT/installer/lib/common.sh"
# shellcheck source=installer/lib/transaction.sh
source "$REPO_ROOT/installer/lib/transaction.sh"
# shellcheck source=installer/lib/platform_hardware.sh
source "$REPO_ROOT/installer/lib/platform_hardware.sh"

MODE=prepare-only
CONFIRM=
PROJECT_USER="${ACP_PROJECT_USER:-${SUDO_USER:-${USER:-andy}}}"
USERMOD_BIN=/usr/sbin/usermod

usage() {
    cat <<EOF
Usage: bash scripts/install-platform-hardware.sh [options]

Guarded Raspberry Pi hardware commissioning owner. Prepare-only is the default.
This owner is intended to run after the additive package bootstrap has installed
raspi-config, i2c-tools and python3-lgpio.

Options:
  --prepare-only
  --activate --confirm $ACP_PLATFORM_HARDWARE_CONFIRMATION
  --project-user USER
  -h, --help

Exit contracts during activation:
  0   I2C/PN532 and accepted CARD=$ACP_DAC_CARD_ID are ready
  75  an I2C or DAC Pro boot configuration change requires an operator reboot;
      rerun the root installer after reboot
  78  hardware identity/configuration is inconsistent and later bootstrap must stop
EOF
}

fail() {
    printf '[A Clockwork Plex] ERROR: %s\n' "$*" >&2
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prepare-only) MODE=prepare-only; shift ;;
        --activate) MODE=activate; shift ;;
        --confirm)
            [[ $# -ge 2 ]] || { echo '--confirm requires a token.' >&2; exit 64; }
            CONFIRM="$2"; shift 2 ;;
        --project-user)
            [[ $# -ge 2 ]] || { echo '--project-user requires a user.' >&2; exit 64; }
            PROJECT_USER="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 64 ;;
    esac
done

[[ "$PROJECT_USER" =~ ^[A-Za-z_][A-Za-z0-9_.-]*$ ]] || {
    echo "Invalid project user: $PROJECT_USER" >&2
    exit 64
}

if [[ "$MODE" == activate ]]; then
    [[ "$CONFIRM" == "$ACP_PLATFORM_HARDWARE_CONFIRMATION" ]] || {
        echo "Activation requires --confirm $ACP_PLATFORM_HARDWARE_CONFIRMATION." >&2
        exit 64
    }
elif [[ -n "$CONFIRM" ]]; then
    echo '--confirm is only valid with --activate.' >&2
    exit 64
fi

acp_platform_hardware_plan "$PROJECT_USER"

if [[ "$MODE" == prepare-only ]]; then
    cat <<'EOF'

Prepare-only complete. No package, boot configuration, user/group, service,
firmware, audio route, mixer, PCM or hardware state was changed.
EOF
    exit 0
fi

[[ "$MODE" == activate ]] || { echo "Unsupported mode: $MODE" >&2; exit 64; }
[[ "$EUID" -ne 0 ]] || fail 'Run activation as the normal project user, not as root.'

for command in sudo raspi-config i2cdetect aplay id getent grep tr awk mktemp stat cmp install; do
    command -v "$command" >/dev/null 2>&1 || fail "Required command not found after package bootstrap: $command"
done
[[ -x "$USERMOD_BIN" ]] || fail "Required system command is missing: $USERMOD_BIN"

id "$PROJECT_USER" >/dev/null 2>&1 || fail "Project user does not exist: $PROJECT_USER"
[[ "$(id -un)" == "$PROJECT_USER" ]] || fail "Activation must be run by project user $PROJECT_USER."

# Raspberry Pi OS owns the exact boot-file mechanics. Use its constrained
# non-interactive I2C action rather than reproducing interface configuration.
echo
echo 'Ensuring Raspberry Pi I2C is enabled...'
sudo -- raspi-config nonint do_i2c 0

for group in $(acp_platform_hardware_groups); do
    if ! getent group "$group" >/dev/null 2>&1; then
        fail "Required Raspberry Pi hardware group is missing: $group"
    fi
    if ! id -nG "$PROJECT_USER" | tr ' ' '\n' | grep -Fqx "$group"; then
        echo "Adding $PROJECT_USER to hardware group $group..."
        sudo -- "$USERMOD_BIN" -aG "$group" "$PROJECT_USER"
    fi
done

if [[ ! -e "/dev/i2c-$ACP_PN532_I2C_BUS" ]]; then
    cat <<EOF
PLATFORM_HARDWARE=REBOOT-REQUIRED
REBOOT_REASON=I2C-BUS-NOT-LIVE
RESUME_COMMAND=bash scripts/install-platform-hardware.sh --activate --confirm $ACP_PLATFORM_HARDWARE_CONFIRMATION --project-user $PROJECT_USER
EOF
    exit 75
fi

echo
echo "Checking PN532 at I2C bus $ACP_PN532_I2C_BUS address $ACP_PN532_I2C_ADDRESS..."
# Group changes made above do not affect the already-running login shell. Use
# sudo for this read-only immediate probe so commissioning does not falsely fail
# solely because the new i2c supplementary group is not live until next login.
I2C_OUTPUT="$(sudo -- i2cdetect -y "$ACP_PN532_I2C_BUS" "$ACP_PN532_I2C_ADDRESS" "$ACP_PN532_I2C_ADDRESS" 2>&1)" || {
    printf '%s\n' "$I2C_OUTPUT" >&2
    fail 'PN532 I2C probe failed.'
}
if ! printf '%s\n' "$I2C_OUTPUT" | grep -Eq '(^|[[:space:]])24([[:space:]]|$)'; then
    printf '%s\n' "$I2C_OUTPUT" >&2
    fail 'PN532 was not detected at the accepted I2C address 0x24.'
fi

echo 'PN532_I2C=PASS'

if aplay -l 2>/dev/null | grep -Eq 'card [0-9]+: Pro[[:space:]]+\['; then
    cat <<'EOF'
DAC_PRO=PASS
DAC_BOOT_CONFIG=EEPROM-OR-EXISTING-CONFIG
PLATFORM_HARDWARE=PASS
PN532_I2C=PASS
FIRMWARE_UPDATE=NOT-PERFORMED
EOF
    exit 0
fi

# CARD=Pro is absent. Determine whether this exact appliance's DAC Pro needs
# the documented compatibility overlay, rather than applying a generic audio HAT.
BOOT_CONFIG=
for candidate in /boot/firmware/config.txt /boot/config.txt; do
    if sudo test -f "$candidate" && ! sudo test -L "$candidate"; then
        BOOT_CONFIG="$candidate"
        break
    fi
done
if [[ -z "$BOOT_CONFIG" ]]; then
    echo 'PLATFORM_HARDWARE=DAC-COMMISSIONING-FAILED'
    echo 'DAC_REASON=BOOT-CONFIG-NOT-FOUND'
    exit 78
fi

if sudo grep -Eq '^[[:space:]]*dtoverlay=rpi-dacpro([,[:space:]]|$)' "$BOOT_CONFIG"; then
    cat <<EOF
PLATFORM_HARDWARE=DAC-COMMISSIONING-FAILED
DAC_REQUIRED_CARD=$ACP_DAC_CARD_ID
DAC_CONFIG=$BOOT_CONFIG
DAC_REASON=RPI-DACPRO-CONFIG-PRESENT-BUT-CARD-MISSING
EOF
    exit 78
fi

read_dt_property() {
    local path="$1"
    if [[ -r "$path" ]]; then
        tr -d '\000' <"$path" 2>/dev/null || true
    fi
}
HAT_VENDOR="$(read_dt_property /proc/device-tree/hat/vendor)"
HAT_PRODUCT="$(read_dt_property /proc/device-tree/hat/product)"

if [[ -n "$HAT_PRODUCT" ]] && ! printf '%s\n' "$HAT_PRODUCT" | grep -Eiq "$ACP_DAC_PRODUCT_PATTERN"; then
    cat <<EOF
PLATFORM_HARDWARE=DAC-COMMISSIONING-FAILED
DAC_REASON=IDENTIFIED-HAT-IS-NOT-DAC-PRO
HAT_VENDOR=$HAT_VENDOR
HAT_PRODUCT=$HAT_PRODUCT
EOF
    exit 78
fi

DAC_CONFIG_MODE=
case "$HAT_VENDOR" in
    *'Raspberry Pi Ltd.'*)
        cat <<EOF
PLATFORM_HARDWARE=DAC-COMMISSIONING-FAILED
DAC_REASON=RASPBERRY-PI-DAC-PRO-EEPROM-DETECTED-BUT-CARD-MISSING
HAT_VENDOR=$HAT_VENDOR
HAT_PRODUCT=$HAT_PRODUCT
EOF
        exit 78
        ;;
    *IQaudIO*|*IQAUDIO*|*iqaudio*)
        DAC_CONFIG_MODE=iqaudio
        ;;
    '')
        DAC_CONFIG_MODE=explicit
        ;;
    *)
        cat <<EOF
PLATFORM_HARDWARE=DAC-COMMISSIONING-FAILED
DAC_REASON=UNRECOGNISED-HAT-VENDOR
HAT_VENDOR=$HAT_VENDOR
HAT_PRODUCT=$HAT_PRODUCT
EOF
        exit 78
        ;;
esac

CURRENT_MODE="$(sudo stat -c '%a' "$BOOT_CONFIG")"
CANDIDATE="$(mktemp "${TMPDIR:-/tmp}/a-clockwork-plex-dac-config.XXXXXX")"
TRANSACTION_PARENT="$(mktemp -d "${TMPDIR:-/tmp}/a-clockwork-plex-dac-boot.XXXXXX")"
TRANSACTION="$TRANSACTION_PARENT/transaction"
cleanup() { rm -f -- "$CANDIDATE"; rm -rf -- "$TRANSACTION_PARENT"; }
trap cleanup EXIT

sudo cat "$BOOT_CONFIG" >"$CANDIDATE.source"
trap 'rm -f -- "$CANDIDATE" "$CANDIDATE.source"; rm -rf -- "$TRANSACTION_PARENT"' EXIT
acp_render_dac_pro_config "$CANDIDATE.source" "$CANDIDATE" "$DAC_CONFIG_MODE" || fail 'Could not render DAC Pro boot configuration.'
[[ "$(grep -Fxc "$ACP_DAC_CONFIG_BEGIN" "$CANDIDATE")" -eq 1 ]] || fail 'Rendered DAC config has an invalid begin marker count.'
[[ "$(grep -Fxc "$ACP_DAC_CONFIG_END" "$CANDIDATE")" -eq 1 ]] || fail 'Rendered DAC config has an invalid end marker count.'
grep -Fxq "dtoverlay=$ACP_DAC_OVERLAY" "$CANDIDATE" || fail 'Rendered DAC config does not select rpi-dacpro.'
if [[ "$DAC_CONFIG_MODE" == iqaudio ]]; then
    grep -Fxq 'dtoverlay=' "$CANDIDATE" || fail 'IQaudIO compatibility config does not suppress the legacy HAT overlay.'
fi

acp_transaction_begin "$TRANSACTION"
acp_transaction_capture_path "$TRANSACTION" "$BOOT_CONFIG"
if ! sudo -- install -m "$CURRENT_MODE" "$CANDIDATE" "$BOOT_CONFIG" || ! sudo -- cmp -s "$CANDIDATE" "$BOOT_CONFIG"; then
    echo 'DAC boot configuration activation failed; restoring captured state.' >&2
    acp_transaction_restore_paths "$TRANSACTION" || true
    exit 1
fi
acp_transaction_mark_complete "$TRANSACTION"

cat <<EOF
PLATFORM_HARDWARE=REBOOT-REQUIRED
REBOOT_REASON=DAC-PRO-BOOT-CONFIG-INSTALLED
DAC_CONFIG=$BOOT_CONFIG
DAC_CONFIG_MODE=$DAC_CONFIG_MODE
DAC_OVERLAY=$ACP_DAC_OVERLAY
FIRMWARE_UPDATE=NOT-PERFORMED
RESUME_COMMAND=bash scripts/install-platform-hardware.sh --activate --confirm $ACP_PLATFORM_HARDWARE_CONFIRMATION --project-user $PROJECT_USER
EOF
exit 75
