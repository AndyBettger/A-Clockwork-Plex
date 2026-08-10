#!/bin/bash

# Package/artifact ownership for the future whole-appliance installer.
# This file is descriptive/read-only until top-level guarded activation exists.

ACP_APT_PACKAGES=(
    git
    curl
    python3
    python3-venv
    alsa-utils
    shairport-sync
    chromium
)

acp_package_plan() {
    local audio_profile="$1" weather_provider="$2"

    cat <<'EOF'
Package and artifact ownership:
  Debian/Raspberry Pi OS packages (future root-installer ownership):
    git curl python3 python3-venv alsa-utils shairport-sync chromium

  Python application environment (future root-installer ownership):
    create/reuse repository venv, then install requirements.txt into that venv

  Platform baseline (checked, not claimed as application packages):
    systemd, sudo, a normal desktop/session environment, kernel/ALSA support

  External prerequisite (verified but not installed by this repository):
    Plexamp Headless distribution and plexamp.service on local port 32500
EOF

    if [[ "$audio_profile" == eq ]]; then
        cat <<'EOF'

  Supplied EQ artifact (verified, never silently downloaded):
    CamillaDSP 4.1.3 aarch64 executable
    sha256 e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa
EOF
    else
        cat <<'EOF'

  EQ artifact:
    not required by the Direct profile
EOF
    fi

    if [[ "$weather_provider" == weather-underground ]]; then
        cat <<'EOF'

  External secret/configuration:
    Weather Underground station ID plus API key in a server environment variable;
    the key is not a package/artifact and must never enter config.json/browser state
EOF
    else
        cat <<'EOF'

  External site configuration:
    Ecowitt custom-push destination/reachability is commissioned at the station/network
EOF
    fi

    cat <<'EOF'

The eventual package apply path must query package availability first, use the
host package manager rather than downloading .deb files directly, and retain the
same specialist ownership boundaries used by the plan/preflight stages.
EOF
}

acp_required_apt_packages() {
    printf '%s\n' "${ACP_APT_PACKAGES[@]}"
}
