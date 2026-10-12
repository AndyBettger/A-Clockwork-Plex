#!/usr/bin/env bash
# Disposable ARM64 Debian CI builder for the *test-only* Squeekboard OVERLAY candidate.
# NEVER invoke on the commissioned Pi. Container + GitHub Actions guards fail closed.
set -euo pipefail

if [[ "${GITHUB_ACTIONS:-}" != "true" || ! -f /.dockerenv ]]; then
  echo "Refusing: builder must run inside a disposable GitHub Actions container." >&2
  exit 2
fi
if [[ "$(id -u)" != "0" || "$(dpkg --print-architecture)" != "arm64" || "$(uname -m)" != "aarch64" ]]; then
  echo "Refusing: requires root inside disposable Debian arm64 container (not host)." >&2
  exit 2
fi

REPO="${GITHUB_WORKSPACE:?No checked-out repository specified}"
ROOT="$(mktemp -d /tmp/acp-squeekboard-arm64-XXXXXXXX)"
ARTIFACTS="$REPO/artifacts/squeekboard-overlay"
mkdir -p "$ARTIFACTS"
printf 'Build root: %s\n' "$ROOT"

# Package mutations below are confined to the disposable CI container.
# Use APT's pinned distro crate packages and do not fetch Rust crates from crates.io.
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates python3 dpkg-dev build-essential passwd file binutils
python3 "$REPO/scripts/ci/prepare-squeekboard-overlay-source.py" \
    --destination "$ROOT/vendor"
SOURCE="$ROOT/vendor/squeekboard-source"
cp "$ROOT/vendor/PROVENANCE.txt" "$ARTIFACTS/PROVENANCE.txt"

# Parse ONLY the pinned, already verified Raspberry Pi source package's
# Build-Depends using the same parser as the commissioned Pi simulation.
export ACP_SQUEEKBOARD_CONTROL="$SOURCE/debian/control"
export ACP_ACP_DEP_PLAN_SCRIPT="$REPO/scripts/plan-squeekboard-build-deps.py"
DEPENDS="$(python3 - <<'PY'
import importlib.util
import os
from pathlib import Path

spec = importlib.util.spec_from_file_location("squeekboard_build_deps", os.environ["ACP_ACP_DEP_PLAN_SCRIPT"])
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(module.build_depends(Path(os.environ["ACP_SQUEEKBOARD_CONTROL"]).read_text(encoding="utf-8")))
PY
)"
printf '%s\n' "$DEPENDS" > "$ARTIFACTS/build-depends.txt"
DEBIAN_FRONTEND=noninteractive apt-get -y -o APT::Install-Recommends=false satisfy "$DEPENDS"

# Build as an unprivileged user; package installation of the resulting .deb
# is explicitly prohibited. Avoid network Cargo registry access.
useradd --create-home --shell /bin/bash acp-builder
chown -R acp-builder:acp-builder "$ROOT"
echo "Building tested vendor source as unprivileged acp-builder."
runuser -u acp-builder -- bash -c '
  set -euo pipefail
  cd "$1"
  export CARGO_NET_OFFLINE=true CARGO_BUILD_JOBS=2 DEB_BUILD_OPTIONS=parallel=2
  dpkg-checkbuilddeps
  dpkg-buildpackage --build=binary -us -uc -j2
' _ "$SOURCE" >"$ARTIFACTS/build.log" 2>&1 || {
  echo "Build failed; last 120 lines follow. The Pi is unchanged." >&2
  tail -n 120 "$ARTIFACTS/build.log" >&2
  exit 1
}

mapfile -t PKGS < <(find "$ROOT/vendor" -maxdepth 1 -type f -name 'squeekboard_*_arm64.deb' -print)
if (( ${#PKGS[@]} != 1 )); then
  echo "Expected exactly one arm64 squeekboard package; found ${#PKGS[@]}" >&2
  exit 1
fi
PKG="${PKGS[0]}"
cp "$PKG" "$ARTIFACTS/"
mkdir "$ROOT/extracted"
dpkg-deb --extract "$PKG" "$ROOT/extracted"
EXE="$ROOT/extracted/usr/bin/squeekboard"
[[ -f "$EXE" ]] || { echo "Missing packaged keyboard executable" >&2; exit 1; }
cp "$EXE" "$ARTIFACTS/squeekboard-overlay-arm64"

{
  printf 'Build context: disposable GitHub Actions debian:trixie ARM64 container\n'
  printf 'Test-only artifact. NEVER install this .deb on the commissioned Pi.\n'
  printf 'Architecture: '; dpkg --print-architecture
  printf 'Package metadata:\n'; dpkg-deb --field "$PKG"
  printf '\nELF inspection:\n'; file "$EXE"
  printf '\nNEEDED shared libraries (ELF metadata only; binary is not executed):\n'
  readelf -d "$EXE" | grep -E 'NEEDED|RUNPATH|RPATH' || true
  printf '\nRequired symbol versions:\n'
  readelf --version-info "$EXE" || true
  printf '\nHashes:\n'
  sha256sum "$PKG" "$EXE"
} > "$ARTIFACTS/ABI-AND-PACKAGE-REPORT.txt"
echo "Finished producing test-only ARM64 artifact; original Pi and keyboard were untouched."
ls -lh "$ARTIFACTS"
