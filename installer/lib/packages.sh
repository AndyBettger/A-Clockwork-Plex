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
    i2c-tools
    python3-lgpio
    raspi-config
)

acp_package_plan() {
    local audio_profile="$1" weather_provider="$2"

    cat <<'EOF'
Package and artifact ownership:
  Debian/Raspberry Pi OS packages (guarded bootstrap ownership):
    git curl python3 python3-venv alsa-utils shairport-sync chromium
    i2c-tools python3-lgpio raspi-config

  Python environments (guarded paired bootstrap ownership):
    * main repository venv: install requirements.txt, pip check/import verify;
    * NFC venv: create with --system-site-packages, install the pinned vendored
      Plexamp NFC Listener requirements, pip check/import verify including lgpio.
    Both candidates are complete before either live venv is replaced. A failed
    activation restores both exact previous directories or previous absence.

  NFC/Pi hardware bootstrap support (guarded bootstrap ownership):
    i2c-tools provides read-only PN532 bus discovery, python3-lgpio supplies the
    Raspberry Pi GPIO backend required by Blinka, and raspi-config is used only
    by the dedicated guarded platform-hardware owner to enable I2C. The package
    owner does not itself edit boot configuration or probe NFC hardware.

  Explicit rollback boundary:
    APT packages are additive shared-host prerequisites and are never automatically
    removed/purged/autoremoved on rollback. The paired main/NFC venv transaction
    restores exact prestate on failure. A successful package/venv bootstrap becomes
    the prerequisite baseline for later bootstrap owners and the exact application
    transaction.

  Platform baseline (checked, not claimed as application packages):
    systemd, sudo, a normal desktop/session environment, kernel/ALSA support

  External prerequisite pending Phase 7 ownership promotion:
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
ownership boundaries used by the plan/preflight stages. It never runs apt upgrade,
rpi-update or firmware update as part of appliance bootstrap.
EOF
}

acp_required_apt_packages() {
    printf '%s\n' "${ACP_APT_PACKAGES[@]}"
}
