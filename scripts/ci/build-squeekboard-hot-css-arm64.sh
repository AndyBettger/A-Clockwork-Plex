#!/usr/bin/env bash
# Disposable ARM64 Debian CI builder for the *separate* C3 hot-CSS test candidate.
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
ROOT="$(mktemp -d /tmp/acp-squeekboard-c3-arm64-XXXXXXXX)"
ARTIFACTS="$REPO/artifacts/squeekboard-c3-hot-css"
mkdir -p "$ARTIFACTS"
# The accepted C2 artifact location and existing C2 workflow are never reused.
[[ "$ARTIFACTS" != "$REPO/artifacts/squeekboard-overlay" ]] || exit 2
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

# EXACT fingerprint of the actual pinned Raspberry Pi Debian C file reviewed
# in the separate successful source-only audit, never of GitHub upstream.
# This Python helper refuses any non-container invocation and writes only
# to the expendable extracted vendor tree prepared above.
python3 "$REPO/scripts/ci/apply-squeekboard-hot-css-build-patch.py" \
    --source-tree "$SOURCE" \
    > "$ARTIFACTS/PATCH-ATTESTATION.txt"
grep -Fq 'HOT CSS SOURCE PATCH: APPLIED TO DISPOSABLE CI ONLY' \
    "$ARTIFACTS/PATCH-ATTESTATION.txt"


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
echo "Building SHA-locked C3 candidate as unprivileged acp-builder (off-device only)."
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
# Package remains temporarily local to the off-device build directory.
# The exported .deb is renamed explicitly below to prevent C2 confusion.
mkdir "$ROOT/extracted"
dpkg-deb --extract "$PKG" "$ROOT/extracted"
EXE="$ROOT/extracted/usr/bin/squeekboard"
[[ -f "$EXE" ]] || { echo "Missing packaged keyboard executable" >&2; exit 1; }
cp "$EXE" "$ARTIFACTS/squeekboard-c3-hot-css-arm64"
# Distinct package filename; do not ever ship the generic C2 artifact name.
cp "$PKG" "$ARTIFACTS/squeekboard-c3-hot-css-arm64.deb"

{
  printf 'Build context: separate C3 hot-CSS disposable GitHub Actions debian:trixie ARM64 container\n'
  printf 'C3 hot-CSS candidate only. NEVER install this .deb on the commissioned Pi.\n'
  printf 'Architecture: '; dpkg --print-architecture
  printf 'Package metadata:\n'; dpkg-deb --field "$PKG"
  printf '\nELF inspection:\n'; file "$EXE"
  printf '\nNEEDED shared libraries (ELF metadata only; binary is not executed):\n'
  readelf -d "$EXE" | grep -E 'NEEDED|RUNPATH|RPATH' || true
  printf '\nRequired symbol versions:\n'
  readelf --version-info "$EXE" || true
  printf '\nHash of new C3 candidate .deb and ELF:\n'
  sha256sum "$ARTIFACTS/squeekboard-c3-hot-css-arm64.deb" "$ARTIFACTS/squeekboard-c3-hot-css-arm64"
  printf '\nAccepted C2 artifact is not generated by this job.\n'
} > "$ARTIFACTS/ABI-AND-PACKAGE-REPORT.txt"
echo "Finished separate C3 hot-CSS ARM64 artifact; original Pi and accepted C2 keyboard unchanged."
ls -lh "$ARTIFACTS"
