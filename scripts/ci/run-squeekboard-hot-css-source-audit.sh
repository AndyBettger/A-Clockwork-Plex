#!/usr/bin/env bash
# Source-only audit of the exact Pi Debian Squeekboard fork in disposable ARM64 CI.
# NEVER run this on the commissioned Pi. NO dpkg package is built or installed.
set -euo pipefail

if [[ "${GITHUB_ACTIONS:-}" != "true" || ! -f /.dockerenv ]]; then
  echo "Refusing: source audit must run inside disposable GitHub Actions container." >&2
  exit 2
fi
if [[ "$(id -u)" != "0" || "$(dpkg --print-architecture)" != "arm64" || "$(uname -m)" != "aarch64" ]]; then
  echo "Refusing: requires root in an ARM64 Debian CI container, not the commissioned Pi." >&2
  exit 2
fi

REPO="${GITHUB_WORKSPACE:?Missing CI checkout}"
[[ -f "$REPO/scripts/ci/prepare-squeekboard-overlay-source.py" &&
   -f "$REPO/scripts/ci/audit-squeekboard-hot-css-source.py" &&
   -f "$REPO/scripts/ci/patch-squeekboard-hot-css.py" ]] || {
  echo "Missing exact CI audit scripts in checkout" >&2
  exit 2
}

ROOT="$(mktemp -d /tmp/acp-c3-squeekboard-source-audit-XXXXXXXX)"
ARTIFACTS="$REPO/artifacts/squeekboard-hot-css-source-audit"
mkdir -p "$ARTIFACTS"

# All APT activity is confined to this throwaway Debian container.
# dpkg-source must be available to apply the Raspberry Pi Debian source patches.
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates python3 dpkg-dev

# Original source stage checks official .dsc version, downloaded checksums,
# known vendor panel.c hash, TOP->OVERLAY patch, and test-only Rust fixture.
# This writes ONLY under the temporary container root.
python3 "$REPO/scripts/ci/prepare-squeekboard-overlay-source.py" \
    --destination "$ROOT/vendor"

SOURCE="$ROOT/vendor/squeekboard-source"
cp "$ROOT/vendor/PROVENANCE.txt" "$ARTIFACTS/PROVENANCE.txt"

# Read-only audit of extracted vendor eek/eek-gtk-keyboard.c:
# computes original/proposed hashes; the proposed patch exists IN MEMORY only.
python3 "$REPO/scripts/ci/audit-squeekboard-hot-css-source.py" \
    --source-tree "$SOURCE" --show-diff \
    > "$ARTIFACTS/SOURCE-ONLY-AUDIT.txt"

grep -Fq "SOURCE PATCH COMPATIBILITY: PASS" "$ARTIFACTS/SOURCE-ONLY-AUDIT.txt"

{
    printf 'ACP Stage C3 source-only audit: PASS\n'
    printf 'Raspberry Pi Debian source version: 1.43.1-1+rpt1\n'
    printf 'Runner architecture: '; dpkg --print-architecture
    printf 'Verified source staged only in disposable CI: YES\n'
    printf 'Experimental C code compiled: NO\n'
    printf 'Keyboard executable or .deb built/installed: NO\n'
    printf 'Commissioned Pi, original OSK, Headless, NFC, GTK: UNTOUCHED\n'
    printf 'Review SOURCE-ONLY-AUDIT.txt and PROVENANCE.txt before any build.\n'
} > "$ARTIFACTS/SUMMARY.txt"
cat "$ARTIFACTS/SUMMARY.txt"
echo "Audit files saved to separate CI artifacts directory."
