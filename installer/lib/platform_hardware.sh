#!/bin/bash

# Raspberry Pi board/HAT commissioning contract for fresh-appliance bootstrap.
# Known accepted hardware is pinned here so the installer can fail closed rather
# than infer arbitrary HATs from generic ALSA output.

ACP_PN532_I2C_BUS=1
ACP_PN532_I2C_ADDRESS=0x24
ACP_DAC_CARD_ID=Pro
ACP_DAC_PRODUCT_PATTERN='DAC.*Pro|DAC.*PRO|Pi-DAC.*PRO'
ACP_DAC_OVERLAY=rpi-dacpro
ACP_DAC_CONFIG_BEGIN='# BEGIN A CLOCKWORK PLEX DAC PRO'
ACP_DAC_CONFIG_END='# END A CLOCKWORK PLEX DAC PRO'
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
  accepted DAC result: ALSA card id $ACP_DAC_CARD_ID (RPi DAC Pro)
  DAC overlay:         dtoverlay=$ACP_DAC_OVERLAY when EEPROM auto-configuration
                       does not expose the accepted card

DAC policy:
  * Raspberry Pi-branded DAC Pro HATs are expected to auto-configure from EEPROM;
    if CARD=$ACP_DAC_CARD_ID already exists, boot configuration is left untouched.
  * Older IQaudIO DAC Pro hardware follows Raspberry Pi's documented compatibility
    block: suppress the old automatic HAT overlay, then load $ACP_DAC_OVERLAY.
  * If no HAT EEPROM identity is exposed but CARD=$ACP_DAC_CARD_ID is absent, the
    project-specific DAC Pro overlay may be installed explicitly.
  * An identified non-DAC-Pro HAT fails closed instead of receiving this overlay.

Guardrails:
  * no apt upgrade, rpi-update, bootloader update, audio-HAT EEPROM write or firmware update;
  * no boot mutation when the accepted DAC already works through EEPROM discovery;
  * boot config mutation is marker-bounded, idempotent and followed by an explicit
    operator-controlled REBOOT-REQUIRED checkpoint;
  * if enabling I2C cannot make /dev/i2c-$ACP_PN532_I2C_BUS live immediately,
    activation reports REBOOT-REQUIRED and stops before NFC/DAC acceptance;
  * if the PN532 is not visible at the accepted address, commissioning fails.
EOF
}

acp_platform_hardware_groups() {
    printf '%s\n' "${ACP_PLATFORM_HARDWARE_GROUPS[@]}"
}
