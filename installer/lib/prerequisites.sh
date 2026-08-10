#!/bin/bash

# Shared read-only prerequisite contract for the Phase 7 appliance installer.
# It describes what a fresh Pi must provide before guarded activation exists.

acp_prerequisite_plan() {
    local audio_profile="$1" weather_provider="$2" project_user="$3"

    cat <<EOF
Fresh-Pi prerequisite contract:
  host OS:             Raspberry Pi OS / Debian-family Linux, 64-bit aarch64
  project user:        $project_user (normal non-root account with sudo access)
  application runtime: python3, python3-venv/pip capability, requirements.txt
  base tools:          bash, git, curl, systemctl, sudo, install, sha256sum
  audio tools:         aplay/amixer (alsa-utils), Shairport Sync service
  external player:     Plexamp Headless exposed as plexamp.service on port 32500
  physical audio:      ALSA DAC card id Pro available as hw:CARD=Pro,DEV=0
  display:             Chromium-compatible browser and desktop autostart session
EOF

    if [[ "$audio_profile" == eq ]]; then
        cat <<'EOF'
  EQ artifact:         verified CamillaDSP 4.1.3 aarch64 executable
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
  weather credential:  Weather Underground API key supplied through the selected
                       server environment variable, never config.json/browser
EOF
    else
        cat <<'EOF'
  weather ingress:     Ecowitt station/custom upload must be able to reach this Pi
EOF
    fi

    cat <<'EOF'

Plexamp Headless is currently treated as an external appliance prerequisite:
this repository verifies its service/API contract but does not yet claim an
installation/update authority for the Plexamp distribution itself.
EOF
}
