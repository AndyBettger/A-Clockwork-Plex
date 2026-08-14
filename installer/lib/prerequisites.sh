#!/bin/bash

# Shared read-only prerequisite contract for the Phase 7 appliance installer.
# It distinguishes the tiny operator/OS baseline from components the guarded
# fresh-bootstrap route owns itself.

acp_prerequisite_plan() {
    local audio_profile="$1" weather_provider="$2" project_user="$3"

    cat <<EOF
Fresh-Pi prerequisite contract:
  host OS:             Raspberry Pi OS / Debian-family Linux, 64-bit aarch64
  project user:        $project_user (normal non-root account with sudo access)
  source bootstrap:    A Clockwork Plex source tree available to execute install.sh
  base platform:       bash, systemd, sudo and normal Raspberry Pi desktop/session
  hardware attached:  intended RPi DAC Pro, PN532 I2C HAT and appliance display

Guarded fresh-bootstrap ownership:
  application runtime: python3 + paired application/NFC venvs
  package tools:       git, curl, alsa-utils, Shairport Sync, Chromium, i2c-tools
  Pi interfaces:       I2C enablement, project-user hardware groups, PN532 0x24
  physical audio:      RPi DAC Pro -> accepted ALSA card id Pro; documented
                       rpi-dacpro boot overlay only when EEPROM/existing config
                       does not already expose the accepted card
  player runtime:      pinned Plexamp Headless 4.13.2 + pinned Node 20.20.2 ARM64,
                       local interactive Plex claim/name checkpoint, plexamp.service
  NFC runtime:         pinned vendored listener, NFC venv and nfc-listener.service
  display integration: Chromium kiosk/autostart and dashboard service

Compatibility-route note:
  install.sh without --fresh-bootstrap intentionally retains the older fail-closed
  contract and requires an already-working CARD=Pro and plexamp.service before its
  application transaction. The fresh route owns those stages instead of weakening
  that compatibility gate.
EOF

    if [[ "$audio_profile" == eq ]]; then
        cat <<'EOF'
  EQ artifact:         exact CamillaDSP 4.1.3 aarch64 executable; the repository
                       guarded fetcher can obtain/verify the official release asset
  EQ kernel support:   snd_aloop module available for the accepted split-bus path
EOF
    else
        cat <<'EOF'
  EQ artifact:         not required for Direct audio
  EQ kernel support:   snd_aloop not required for Direct audio
EOF
    fi

    if [[ "$weather_provider" == weather-underground ]]; then
        cat <<'EOF'
  weather commissioning: provider/station in Settings; WU API key entered locally
                         through the dedicated write-only credential boundary
EOF
    else
        cat <<'EOF'
  weather ingress:     Ecowitt station/custom upload reachability remains a site
                       commissioning item; Open-Meteo remains forecast provider
EOF
    fi
}
