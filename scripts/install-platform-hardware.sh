#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

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
  75  I2C was enabled/configured but a reboot is required before bus acceptance
  78  I2C/PN532 passed but CARD=$ACP_DAC_CARD_ID is absent; exact DAC overlay
      commissioning is intentionally blocked until its physical identity is pinned
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

for command in sudo raspi-config i2cdetect aplay id getent grep tr; do
    command -v "$command" >/dev/null 2>&1 || fail "Required command not found after package bootstrap: $command"
done
[[ -x "$USERMOD_BIN" ]] || fail "Required system command is missing: $USERMOD_BIN"

id "$PROJECT_USER" >/dev/null 2>&1 || fail "Project user does not exist: $PROJECT_USER"

# Raspberry Pi OS owns the exact boot-file mechanics. Do not reproduce or guess
# them here; use its constrained non-interactive I2C action only.
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
I2C_OUTPUT="$(i2cdetect -y "$ACP_PN532_I2C_BUS" "$ACP_PN532_I2C_ADDRESS" "$ACP_PN532_I2C_ADDRESS" 2>&1)" || {
    printf '%s\n' "$I2C_OUTPUT" >&2
    fail 'PN532 I2C probe failed.'
}
if ! printf '%s\n' "$I2C_OUTPUT" | grep -Eq '(^|[[:space:]])24([[:space:]]|$)'; then
    printf '%s\n' "$I2C_OUTPUT" >&2
    fail 'PN532 was not detected at the accepted I2C address 0x24.'
fi

echo 'PN532_I2C=PASS'

if ! aplay -l 2>/dev/null | grep -Eq 'card [0-9]+: Pro[[:space:]]+\['; then
    cat <<'EOF'
PLATFORM_HARDWARE=DAC-COMMISSIONING-REQUIRED
DAC_REQUIRED_CARD=Pro
DAC_POLICY=NO-GUESSED-OVERLAY
EOF
    exit 78
fi

cat <<'EOF'
PLATFORM_HARDWARE=PASS
PN532_I2C=PASS
DAC_PRO=PASS
FIRMWARE_UPDATE=NOT-PERFORMED
EOF
