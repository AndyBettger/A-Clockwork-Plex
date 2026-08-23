#!/bin/bash

# Pinned compatibility-runtime contract for Phase 7.
#
# Plexamp Headless is retained for this release because A Clockwork Plex depends
# on its local browsing surface and port-32500 API. Both the Plexamp and Node
# archives are pinned to immutable SHA-256 identities before production use.

ACP_PLEXAMP_VERSION=4.13.2
ACP_PLEXAMP_ARCHIVE="Plexamp-Linux-headless-v${ACP_PLEXAMP_VERSION}.tar.bz2"
ACP_PLEXAMP_ARCHIVE_URL="https://plexamp.plex.tv/headless/${ACP_PLEXAMP_ARCHIVE}"
ACP_PLEXAMP_ARCHIVE_SHA256="86e5ede3d852a87099a106f2cc6b83e4ec1350000176d83fbcedb83950c48041"
ACP_PLEXAMP_ARCHIVE_BYTES=14566439

ACP_NODE_VERSION=20.20.2
ACP_NODE_PLATFORM=linux-arm64
ACP_NODE_ARCHIVE="node-v${ACP_NODE_VERSION}-${ACP_NODE_PLATFORM}.tar.xz"
ACP_NODE_ARCHIVE_URL="https://nodejs.org/dist/v${ACP_NODE_VERSION}/${ACP_NODE_ARCHIVE}"
ACP_NODE_ARCHIVE_SHA256="73093db209e4e9e09dd7d15a47aeaab1b74833830df03efa5f942a1122c5fa71"

ACP_PLEXAMP_RUNTIME_CONFIRMATION=INSTALL-PLEXAMP-RUNTIME
ACP_PLEXAMP_SERVICE=plexamp.service
ACP_PLEXAMP_PORT=32500
ACP_PLEXAMP_CLAIM_EXIT=76

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
  Plexamp bytes:     $ACP_PLEXAMP_ARCHIVE_BYTES
  Plexamp SHA-256:   $ACP_PLEXAMP_ARCHIVE_SHA256

  Node version:      $ACP_NODE_VERSION
  Node platform:     $ACP_NODE_PLATFORM
  Node archive:      $ACP_NODE_ARCHIVE
  Node URL:          $ACP_NODE_ARCHIVE_URL
  Node SHA-256:      $ACP_NODE_ARCHIVE_SHA256

Runtime contract:
  * Node is installed under an A Clockwork Plex-owned versioned /opt path rather
    than replacing the distribution /usr/bin/node or using NodeSource/nvm.
  * Plexamp is installed as ~/plexamp for the selected normal project user and
    exposed as $ACP_PLEXAMP_SERVICE on local port $ACP_PLEXAMP_PORT.
  * Both downloads are SHA-256 verified before extraction or live-state mutation.
  * Fresh account claim is an explicit interactive boundary. If no Plexamp state
    exists, the owner installs the verified runtime then exits $ACP_PLEXAMP_CLAIM_EXIT
    with a foreground claim command; claim material is never accepted as a normal
    installer argument or log field. Re-running the root installer resumes.
  * The service uses the pinned Node executable directly.
  * No mutable community curl|bash installer, 'latest' archive or unverified
    download may become production authority.
EOF

    if acp_plexamp_runtime_artifact_pinned; then
        cat <<'EOF'

Artifact gate: READY — Plexamp and Node archive identities are pinned in source.
EOF
    else
        cat <<'EOF'

Artifact gate: BLOCKED — Plexamp SHA-256 is not pinned in source.
EOF
    fi
}
