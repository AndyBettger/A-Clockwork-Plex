#!/bin/bash

# Raspberry Pi board/HAT commissioning contract for fresh-appliance bootstrap.
# This layer deliberately owns only hardware facts that are already known and
# reviewable: I2C, the PN532 address and normal-user hardware groups. The
# accepted DAC endpoint is CARD=Pro, but its exact boot-overlay identity has not
# yet been captured from the physical appliance, so this code must not guess it.

ACP_PN532_I2C_BUS=1
ACP_PN532_I2C_ADDRESS=0x24
ACP_DAC_CARD_ID=Pro
ACP_PLATFORM_HARDWARE_CONFIRMATION=INSTALL-PLATFORM-HARDWARE
ACP_PLATFORM_HARDWARE_GROUPS=(i2c gpio spi)

acp_platform_hardware_plan() {
    local project_user="$1"

    cat <<EOF
Fresh-Pi hardware commissioning:
  project user:        $project_user
  I2C:                 enable through Raspberry Pi OS raspi-config
  PN532:               require I2C bus $ACP_PN532_I2C_BUS address $ACP_PN532_I2C_ADDRESS
  hardware groups:     ${ACP_PLATFORM_HARDWARE_GROUPS[*]}
  accepted DAC result: ALSA card id $ACP_DAC_CARD_ID

Guardrails:
  * no apt upgrade, rpi-update, bootloader update or firmware update;
  * no guessed dtoverlay or DAC boot configuration is written;
  * if enabling I2C cannot make /dev/i2c-$ACP_PN532_I2C_BUS live immediately,
    activation reports REBOOT-REQUIRED and stops before NFC/DAC acceptance;
  * if the PN532 is not visible at the accepted address, commissioning fails;
  * if CARD=$ACP_DAC_CARD_ID is absent, commissioning reports that the exact DAC
    overlay identity must be captured/pinned before the installer may own it.
EOF
}

acp_platform_hardware_groups() {
    printf '%s\n' "${ACP_PLATFORM_HARDWARE_GROUPS[@]}"
}
