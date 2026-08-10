#!/bin/bash

# Read-only Direct-audio component contract for the Phase 7 appliance installer.
# This library deliberately exposes no activation function yet.

if [[ -z "${ACP_REPO_ROOT:-}" ]]; then
    ACP_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi

ACP_DIRECT_AUDIO_PROFILE="$ACP_REPO_ROOT/installer/profiles/direct"
ACP_DIRECT_AUDIO_ROUTE="$ACP_DIRECT_AUDIO_PROFILE/alarm-safe.conf"
ACP_DIRECT_AUDIO_ROUTE_SHA256=654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9
ACP_LEGACY_EQ_INSTALL_BASELINE_SHA256=08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9

acp_direct_audio_source_files() {
    cat <<EOF_PATHS
$ACP_DIRECT_AUDIO_ROUTE
$ACP_REPO_ROOT/scripts/a-clockwork-plex-audio-mixer.py
$ACP_REPO_ROOT/scripts/install-airplay-hooks.sh
EOF_PATHS
}

acp_verify_direct_audio_sources() {
    local source observed failures=0
    while IFS= read -r source; do
        [[ -f "$source" && ! -L "$source" ]] || {
            printf '[A Clockwork Plex] ERROR: Required Direct-audio source is unavailable: %s\n' "$source" >&2
            failures=$((failures + 1))
        }
    done < <(acp_direct_audio_source_files)

    if [[ -f "$ACP_DIRECT_AUDIO_ROUTE" ]]; then
        observed="$(sha256sum "$ACP_DIRECT_AUDIO_ROUTE" | awk '{print $1}')" || return 1
        if [[ "$observed" != "$ACP_DIRECT_AUDIO_ROUTE_SHA256" ]]; then
            printf '[A Clockwork Plex] ERROR: Direct alarm-safe route checksum mismatch. Expected %s, observed %s\n' \
                "$ACP_DIRECT_AUDIO_ROUTE_SHA256" "$observed" >&2
            failures=$((failures + 1))
        fi
    fi
    [[ "$failures" -eq 0 ]]
}

acp_direct_audio_plan() {
    cat <<EOF
Direct audio is a first-class profile.
Direct audio component boundary:
  route source:        installer/profiles/direct/alarm-safe.conf
  route SHA-256:       $ACP_DIRECT_AUDIO_ROUTE_SHA256
  music path:          Plexamp/AirPlay trims -> Music Master -> DAC
  alarm path:          Maximum Alarm Volume -> DAC (bypasses Music Master)
  public PCMs:         acp_plexamp, acp_airplay, acp_alarm, acp_master
  common integration:  mixer helper, Plexamp default PCM, Shairport acp_airplay output

The older scripts/install-shared-audio.sh is not an appliance-installer authority.
Its historical route SHA $ACP_LEGACY_EQ_INSTALL_BASELINE_SHA256 puts acp_alarm
under Music Master and is therefore not the final Direct-audio profile.

Fresh-EQ integration:
  scripts/audio/install-eq.sh keeps phase6-direct as its standalone default but
  now accepts --baseline alarm-safe-direct. The full appliance installer will
  use that explicit selector after this Direct profile is installed, allowing
  EQ first-install validation to recognise SHA $ACP_DIRECT_AUDIO_ROUTE_SHA256
  without changing the physically accepted Phase 6 default or exact uninstall
  backup semantics. No Direct activation is performed by this library yet.
EOF
}
