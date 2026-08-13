#!/bin/bash

# Pinned compatibility-runtime contract for Phase 7.
#
# Plexamp Headless is retained for this release because A Clockwork Plex depends
# on its local browsing surface and port-32500 API. This contract intentionally
# fails closed until the exact 4.13.2 archive SHA-256 has been captured from the
# official artifact and reviewed into source.

ACP_PLEXAMP_VERSION=4.13.2
ACP_PLEXAMP_ARCHIVE="Plexamp-Linux-headless-v${ACP_PLEXAMP_VERSION}.tar.bz2"
ACP_PLEXAMP_ARCHIVE_URL="https://plexamp.plex.tv/headless/${ACP_PLEXAMP_ARCHIVE}"
ACP_PLEXAMP_ARCHIVE_SHA256=""

ACP_NODE_VERSION=20.20.2
ACP_NODE_PLATFORM=linux-arm64
ACP_NODE_ARCHIVE="node-v${ACP_NODE_VERSION}-${ACP_NODE_PLATFORM}.tar.xz"
ACP_NODE_ARCHIVE_URL="https://nodejs.org/dist/v${ACP_NODE_VERSION}/${ACP_NODE_ARCHIVE}"
ACP_NODE_ARCHIVE_SHA256="73093db209e4e9e09dd7d15a47aeaab1b74833830df03efa5f942a1122c5fa71"

ACP_PLEXAMP_RUNTIME_CONFIRMATION=INSTALL-PLEXAMP-RUNTIME
ACP_PLEXAMP_SERVICE=plexamp.service
ACP_PLEXAMP_PORT=32500

acp_plexamp_runtime_artifact_pinned() {
    [[ "$ACP_PLEXAMP_ARCHIVE_SHA256" =~ ^[0-9a-f]{64}$ ]]
}

acp_plexamp_runtime_plan() {
    local project_user="$1"

    cat <<EOF
Plexamp compatibility-runtime ownership:
  project user:      $project_user
  Plexamp version:   $ACP_PLEXAMP_VERSION
  Plexamp archive:   $ACP_PLEXAMP_ARCHIVE
  Plexamp URL:       $ACP_PLEXAMP_ARCHIVE_URL
  Plexamp SHA-256:   ${ACP_PLEXAMP_ARCHIVE_SHA256:-NOT-PINNED — activation blocked}

  Node version:      $ACP_NODE_VERSION
  Node platform:     $ACP_NODE_PLATFORM
  Node archive:      $ACP_NODE_ARCHIVE
  Node URL:          $ACP_NODE_ARCHIVE_URL
  Node SHA-256:      $ACP_NODE_ARCHIVE_SHA256

Target runtime contract:
  * Node is installed under an A Clockwork Plex-owned versioned /opt path rather
    than replacing the distribution /usr/bin/node or using NodeSource/nvm.
  * Plexamp is installed for the selected normal project user and exposed as
    $ACP_PLEXAMP_SERVICE on local port $ACP_PLEXAMP_PORT.
  * First account claim remains an explicit interactive authentication boundary;
    claim material is never accepted as a normal command-line argument or log field.
  * The installed service uses the pinned Node executable directly.
  * No mutable community curl|bash installer, 'latest' archive or unverified
    download may become production authority.
EOF

    if acp_plexamp_runtime_artifact_pinned; then
        cat <<'EOF'

Artifact gate: READY — both runtime archive identities are pinned in source.
EOF
    else
        cat <<'EOF'

Artifact gate: BLOCKED — Plexamp 4.13.2 SHA-256 is not yet pinned in source.
Prepare-only remains available; production activation must refuse before network
or filesystem mutation until that immutable artifact identity is reviewed.
EOF
    fi
}
