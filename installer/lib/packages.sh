#!/bin/bash

# Package/artifact ownership for the whole-appliance installer.
# Read-only planning/checking lives here; guarded mutation is owned by
# scripts/install-appliance-packages.sh and is invoked by root install.sh only
# after the pre-bootstrap platform/external gate has passed.

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
  Debian/Raspberry Pi OS packages (guarded bootstrap ownership):
    git curl python3 python3-venv alsa-utils shairport-sync chromium

  Python application environment (guarded bootstrap ownership):
    build a complete staged repository venv, install requirements.txt, run
    pip check/import verification, then atomically swap it into repository/venv

  Explicit rollback boundary:
    APT packages are additive shared-host prerequisites and are never automatically
    removed/purged/autoremoved on rollback. A failed venv activation restores the
    exact previous venv directory (or previous absence) by same-filesystem rename.
    A successful package/venv bootstrap becomes the prerequisite baseline for the
    later exact application-managed whole-appliance transaction.

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
    Weather Underground station ID plus API key supplied through a host secret file;
    the key is not a package/artifact and must never enter config.json/browser state
EOF
    else
        cat <<'EOF'

  External site configuration:
    Ecowitt custom-push destination/reachability is commissioned at the station/network
EOF
    fi

    cat <<'EOF'

The guarded package owner queries package availability first, uses the host package
manager rather than downloading .deb files directly, and retains the same specialist
ownership boundaries used by the plan/preflight stages.
EOF
}

acp_required_apt_packages() {
    printf '%s\n' "${ACP_APT_PACKAGES[@]}"
}
