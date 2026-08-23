#!/bin/bash
set -euo pipefail

VERSION=4.1.3
ARCHIVE=camilladsp-linux-aarch64.tar.gz
URL="https://github.com/HEnquist/camilladsp/releases/download/v${VERSION}/${ARCHIVE}"
ARCHIVE_SHA256=d9a17092923ebfe5d20a770c6b6a7eb2268f9700f999bf604b9db09f518aca5a
BINARY_SHA256=e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa
CONFIRM_TOKEN=FETCH-CAMILLADSP-4.1.3
MODE=prepare-only
CONFIRM=
DESTINATION="${ACP_CAMILLA_ARTIFACT_DIR:-$HOME/.cache/a-clockwork-plex/artifacts/camilladsp-$VERSION}"
ARCHIVE_INPUT=

usage() {
    cat <<EOF
Usage: bash scripts/fetch-camilladsp-4.1.3.sh [options]

Guarded user-owned acquisition of the exact CamillaDSP binary already accepted
for the A Clockwork Plex EQ profile. Prepare-only is the default.

Options:
  --prepare-only
  --activate --confirm $CONFIRM_TOKEN
  --destination DIR   default: $DESTINATION
  --archive PATH      verify/extract a pre-downloaded archive instead of downloading
  -h, --help

Pinned identities:
  release:            v$VERSION
  official archive:   $URL
  archive SHA-256:    $ARCHIVE_SHA256
  executable SHA-256: $BINARY_SHA256

This helper never installs into /usr/local, starts services or changes audio.
It only produces a verified user-owned artifact that can be passed to:
  install.sh --camilladsp-binary PATH
EOF
}

error() { printf '[A Clockwork Plex] ERROR: %s\n' "$*" >&2; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prepare-only) MODE=prepare-only; shift ;;
        --activate) MODE=activate; shift ;;
        --confirm)
            [[ $# -ge 2 ]] || { error '--confirm requires a token.'; exit 64; }
            CONFIRM="$2"; shift 2 ;;
        --destination)
            [[ $# -ge 2 ]] || { error '--destination requires a directory.'; exit 64; }
            DESTINATION="$2"; shift 2 ;;
        --archive)
            [[ $# -ge 2 ]] || { error '--archive requires a path.'; exit 64; }
            ARCHIVE_INPUT="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) error "Unknown option: $1"; usage >&2; exit 64 ;;
    esac
done

[[ "$DESTINATION" == /* ]] || { error '--destination must be absolute.'; exit 64; }
if [[ "$MODE" == activate ]]; then
    [[ "$CONFIRM" == "$CONFIRM_TOKEN" ]] || { error "Activation requires --confirm $CONFIRM_TOKEN."; exit 64; }
elif [[ -n "$CONFIRM" ]]; then
    error '--confirm is only valid with --activate.'
    exit 64
fi

TARGET="$DESTINATION/camilladsp"
MANIFEST="$DESTINATION/.a-clockwork-plex-artifact"

cat <<EOF
A Clockwork Plex CamillaDSP artifact plan

Mode:              $MODE
Destination:       $DESTINATION
Executable:        $TARGET
Version:           $VERSION
Archive SHA-256:   $ARCHIVE_SHA256
Executable SHA-256:$BINARY_SHA256
Source:            ${ARCHIVE_INPUT:-$URL}
EOF

if [[ "$MODE" == prepare-only ]]; then
    echo
    echo 'Prepare-only complete. No download, file, package, service or audio state was changed.'
    exit 0
fi

[[ "$EUID" -ne 0 ]] || { error 'Run this helper as the normal project user, not root.'; exit 1; }
for command in curl tar sha256sum mktemp stat mv rm grep; do
    command -v "$command" >/dev/null 2>&1 || { error "Required command not found: $command"; exit 1; }
done
if [[ -n "$ARCHIVE_INPUT" ]]; then
    [[ -f "$ARCHIVE_INPUT" && ! -L "$ARCHIVE_INPUT" && -r "$ARCHIVE_INPUT" ]] || {
        error 'Archive input must be a readable regular file, not a symlink.'
        exit 1
    }
fi
if [[ -e "$DESTINATION" || -L "$DESTINATION" ]]; then
    [[ -d "$DESTINATION" && ! -L "$DESTINATION" ]] || { error 'Destination exists but is not a safe directory.'; exit 1; }
fi

# Fast idempotent path: accept only the exact executable plus ownership manifest.
if [[ -x "$TARGET" && ! -L "$TARGET" && -f "$MANIFEST" && ! -L "$MANIFEST" ]]; then
    observed="$(sha256sum "$TARGET" | awk '{print $1}')"
    version_line="$("$TARGET" --version 2>&1 | head -n1 || true)"
    if [[ "$observed" == "$BINARY_SHA256" ]] && [[ "$version_line" == *"$VERSION"* ]] && \
       grep -Fxq "archive_sha256=$ARCHIVE_SHA256" "$MANIFEST" && \
       grep -Fxq "binary_sha256=$BINARY_SHA256" "$MANIFEST"; then
        echo
        echo 'CAMILLA_ARTIFACT=PASS-EXISTING'
        printf 'CAMILLA_BINARY=%s\n' "$TARGET"
        exit 0
    fi
fi

PARENT="$(dirname "$DESTINATION")"
mkdir -p "$PARENT"
STAGE="$(mktemp -d "$PARENT/.acp-camilladsp-stage.XXXXXX")"
DOWNLOAD="$STAGE/$ARCHIVE"
EXTRACT="$STAGE/extract"
PREVIOUS="$STAGE/previous"
PREVIOUS_PRESENT=false
SWAPPED=false
cleanup() { rm -rf -- "$STAGE"; }
trap cleanup EXIT
mkdir -p "$EXTRACT"

if [[ -n "$ARCHIVE_INPUT" ]]; then
    cp -- "$ARCHIVE_INPUT" "$DOWNLOAD"
else
    echo 'Downloading pinned CamillaDSP release archive...'
    curl --fail --show-error --silent --location --proto '=https' --tlsv1.2 \
        --output "$DOWNLOAD" "$URL"
fi

observed_archive="$(sha256sum "$DOWNLOAD" | awk '{print $1}')"
[[ "$observed_archive" == "$ARCHIVE_SHA256" ]] || {
    error "CamillaDSP archive SHA-256 mismatch: $observed_archive"
    exit 1
}
echo "Archive SHA-256 verified: $observed_archive"

tar -xzf "$DOWNLOAD" -C "$EXTRACT"
CANDIDATE="$EXTRACT/camilladsp"
[[ -f "$CANDIDATE" && ! -L "$CANDIDATE" ]] || { error 'Archive did not contain camilladsp executable.'; exit 1; }
chmod 0755 "$CANDIDATE"
observed_binary="$(sha256sum "$CANDIDATE" | awk '{print $1}')"
[[ "$observed_binary" == "$BINARY_SHA256" ]] || {
    error "CamillaDSP executable SHA-256 mismatch: $observed_binary"
    exit 1
}
version_line="$("$CANDIDATE" --version 2>&1 | head -n1 || true)"
[[ "$version_line" == *"$VERSION"* ]] || { error "CamillaDSP executable did not report version $VERSION."; exit 1; }

cat >"$EXTRACT/.a-clockwork-plex-artifact" <<EOF
kind=camilladsp
version=$VERSION
archive=$ARCHIVE
archive_sha256=$ARCHIVE_SHA256
binary_sha256=$BINARY_SHA256
EOF

# Promote only after both archive and executable identities pass. A failed swap
# restores exact previous directory or exact previous absence.
restore_previous() {
    set +e
    if [[ "$SWAPPED" == true && -d "$DESTINATION" ]]; then rm -rf -- "$DESTINATION"; fi
    if [[ "$PREVIOUS_PRESENT" == true && -d "$PREVIOUS" ]]; then mv -- "$PREVIOUS" "$DESTINATION"; fi
}

if [[ -d "$DESTINATION" ]]; then
    mv -- "$DESTINATION" "$PREVIOUS" || { error 'Could not preserve previous artifact directory.'; exit 1; }
    PREVIOUS_PRESENT=true
fi
mv -- "$EXTRACT" "$DESTINATION" || {
    error 'Could not promote verified CamillaDSP artifact.'
    restore_previous
    exit 1
}
SWAPPED=true

if [[ "${ACP_CAMILLA_FETCH_TEST_FAIL_AFTER_SWAP:-0}" == 1 ]]; then
    error 'Injected non-production failure after artifact swap.'
    restore_previous
    exit 1
fi

observed_binary="$(sha256sum "$TARGET" | awk '{print $1}')"
[[ "$observed_binary" == "$BINARY_SHA256" ]] || {
    error 'Promoted CamillaDSP artifact failed final digest verification.'
    restore_previous
    exit 1
}
SWAPPED=false
rm -rf -- "$PREVIOUS"

echo
echo 'CAMILLA_ARTIFACT=PASS'
printf 'CAMILLA_BINARY=%s\n' "$TARGET"
