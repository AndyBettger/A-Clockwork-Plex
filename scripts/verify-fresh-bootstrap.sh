#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=installer/lib/platform_hardware.sh
source "$REPO_ROOT/installer/lib/platform_hardware.sh"
# shellcheck source=installer/lib/plexamp_runtime.sh
source "$REPO_ROOT/installer/lib/plexamp_runtime.sh"

ROOT=/
PROJECT_USER="${SUDO_USER:-${USER:-andy}}"
PROJECT_DIR=
FAILURES=0
WARNINGS=0
NFC_BLOB=5f87b477bfdac27a34373cb7708af8236c33c2ab

usage() {
    cat <<'EOF'
Usage: bash scripts/verify-fresh-bootstrap.sh [options]

Read-only verifier for installer-owned fresh-Pi substrate: DAC/PN532 hardware,
pinned Node/Plexamp runtime and the pinned NFC listener runtime/service.
It complements scripts/verify-appliance.sh; it does not replace the existing
application/audio/weather verifier.

Options:
  --project-user USER
  --project-dir PATH
  --root PATH          alternate filesystem root; live hardware/service probes skipped
  -h, --help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project-user)
            [[ $# -ge 2 ]] || { echo '--project-user requires a user.' >&2; exit 64; }
            PROJECT_USER="$2"; shift 2 ;;
        --project-dir)
            [[ $# -ge 2 ]] || { echo '--project-dir requires a path.' >&2; exit 64; }
            PROJECT_DIR="$2"; shift 2 ;;
        --root)
            [[ $# -ge 2 ]] || { echo '--root requires a path.' >&2; exit 64; }
            ROOT="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 64 ;;
    esac
done

[[ "$PROJECT_USER" =~ ^[A-Za-z_][A-Za-z0-9_.-]*$ ]] || { echo "Invalid project user: $PROJECT_USER" >&2; exit 64; }
if [[ "$ROOT" != / ]]; then
    ROOT="${ROOT%/}"
    [[ -d "$ROOT" ]] || { echo "Alternate root does not exist: $ROOT" >&2; exit 1; }
fi
if [[ -z "$PROJECT_DIR" ]]; then
    if [[ "$ROOT" == / ]]; then PROJECT_DIR="$REPO_ROOT"; else PROJECT_DIR="/home/$PROJECT_USER/A-Clockwork-Plex"; fi
fi
[[ "$PROJECT_DIR" == /* ]] || { echo '--project-dir must be absolute.' >&2; exit 64; }

root_path() {
    if [[ "$ROOT" == / ]]; then printf '%s\n' "$1"; else printf '%s%s\n' "$ROOT" "$1"; fi
}

if [[ "$ROOT" == / ]]; then
    PROJECT_HOME="$(getent passwd "$PROJECT_USER" | cut -d: -f6)"
    [[ -n "$PROJECT_HOME" && "$PROJECT_HOME" == /* ]] || { echo "Cannot resolve home for $PROJECT_USER" >&2; exit 1; }
else
    PROJECT_HOME="/home/$PROJECT_USER"
fi

NODE_TARGET="/opt/a-clockwork-plex/node-v${ACP_NODE_VERSION}-${ACP_NODE_PLATFORM}"
PLEXAMP_TARGET="$PROJECT_HOME/plexamp"
PLEXAMP_SETTINGS="$PROJECT_HOME/.local/share/Plexamp/Settings"
NFC_RUNTIME="$PROJECT_DIR/vendor/plexamp-nfc-listener/nfc_listener.py"
NFC_VENV="$PROJECT_DIR/nfc-venv"

EXPECTED_NODE_SHA="$ACP_NODE_ARCHIVE_SHA256"
EXPECTED_PLEXAMP_SHA="$ACP_PLEXAMP_ARCHIVE_SHA256"
if [[ "$ROOT" != / ]]; then
    EXPECTED_NODE_SHA="${ACP_PLEXAMP_TEST_NODE_SHA256:-$EXPECTED_NODE_SHA}"
    EXPECTED_PLEXAMP_SHA="${ACP_PLEXAMP_TEST_ARCHIVE_SHA256:-$EXPECTED_PLEXAMP_SHA}"
fi

pass() { printf 'PASS  %-24s %s\n' "$1" "$2"; }
fail_check() { printf 'FAIL  %-24s %s\n' "$1" "$2"; FAILURES=$((FAILURES + 1)); }
warn_check() { printf 'WARN  %-24s %s\n' "$1" "$2"; WARNINGS=$((WARNINGS + 1)); }

require_file() {
    local label="$1" logical="$2" path
    path="$(root_path "$logical")"
    if [[ -f "$path" && ! -L "$path" ]]; then pass "$label" "$logical"; else fail_check "$label" "missing/unsafe: $logical"; fi
}

require_contains() {
    local label="$1" logical="$2" needle="$3" path
    path="$(root_path "$logical")"
    if [[ -f "$path" && ! -L "$path" ]] && grep -Fq "$needle" "$path"; then pass "$label" "$needle"; else fail_check "$label" "$logical missing: $needle"; fi
}

manifest_ok() {
    local logical="$1" kind="$2" version="$3" digest="$4" path
    path="$(root_path "$logical")/.a-clockwork-plex-runtime"
    [[ -f "$path" && ! -L "$path" ]] && \
        grep -Fxq "kind=$kind" "$path" && \
        grep -Fxq "version=$version" "$path" && \
        grep -Fxq "archive_sha256=$digest" "$path"
}

cat <<EOF
A Clockwork Plex fresh-bootstrap verification

Filesystem root: $ROOT
Project user:    $PROJECT_USER
Project dir:     $PROJECT_DIR
Plexamp:         $ACP_PLEXAMP_VERSION / sha256 $ACP_PLEXAMP_ARCHIVE_SHA256
Node:            $ACP_NODE_VERSION / sha256 $ACP_NODE_ARCHIVE_SHA256
PN532:           I2C bus $ACP_PN532_I2C_BUS address $ACP_PN532_I2C_ADDRESS
DAC:             CARD=$ACP_DAC_CARD_ID / overlay $ACP_DAC_OVERLAY when required
EOF

echo
echo 'Pinned player runtime:'
require_file node-runtime "$NODE_TARGET/bin/node"
if manifest_ok "$NODE_TARGET" node "$ACP_NODE_VERSION" "$EXPECTED_NODE_SHA"; then pass node-manifest "$ACP_NODE_VERSION / $EXPECTED_NODE_SHA"; else fail_check node-manifest 'runtime ownership manifest mismatch'; fi
require_file plexamp-runtime "$PLEXAMP_TARGET/js/index.js"
if manifest_ok "$PLEXAMP_TARGET" plexamp "$ACP_PLEXAMP_VERSION" "$EXPECTED_PLEXAMP_SHA"; then pass plexamp-manifest "$ACP_PLEXAMP_VERSION / $EXPECTED_PLEXAMP_SHA"; else fail_check plexamp-manifest 'runtime ownership manifest mismatch'; fi
require_contains plexamp-unit '/etc/systemd/system/plexamp.service' "User=$PROJECT_USER"
require_contains plexamp-unit '/etc/systemd/system/plexamp.service' "WorkingDirectory=$PLEXAMP_TARGET"
require_contains plexamp-unit '/etc/systemd/system/plexamp.service' "ExecStart=$NODE_TARGET/bin/node $PLEXAMP_TARGET/js/index.js"
settings_path="$(root_path "$PLEXAMP_SETTINGS")"
if [[ -d "$settings_path" ]] && find "$settings_path" -maxdepth 1 -type f -print -quit 2>/dev/null | grep -q .; then pass plexamp-claim 'persistent Settings state present'; else fail_check plexamp-claim 'no persistent Plexamp Settings state; interactive claim is incomplete'; fi

node_path="$(root_path "$NODE_TARGET/bin/node")"
if [[ -x "$node_path" ]]; then
    version="$($node_path --version 2>/dev/null || true)"
    if [[ "$version" == "v$ACP_NODE_VERSION" ]]; then pass node-version "$version"; else fail_check node-version "expected v$ACP_NODE_VERSION observed ${version:-none}"; fi
fi

echo
echo 'Pinned NFC runtime:'
require_file nfc-runtime "$NFC_RUNTIME"
nfc_path="$(root_path "$NFC_RUNTIME")"
if [[ -f "$nfc_path" ]] && command -v git >/dev/null 2>&1; then
    observed_blob="$(git hash-object "$nfc_path")"
    if [[ "$observed_blob" == "$NFC_BLOB" ]]; then pass nfc-source "git-blob=$observed_blob"; else fail_check nfc-source "expected blob $NFC_BLOB observed $observed_blob"; fi
else
    fail_check nfc-source 'git or pinned listener source unavailable'
fi
require_file nfc-python "$NFC_VENV/bin/python"
require_contains nfc-unit '/etc/systemd/system/nfc-listener.service' "User=$PROJECT_USER"
require_contains nfc-unit '/etc/systemd/system/nfc-listener.service' 'SupplementaryGroups=i2c gpio spi'
require_contains nfc-unit '/etc/systemd/system/nfc-listener.service' "ExecStart=$NFC_VENV/bin/python $NFC_RUNTIME"

if [[ "$ROOT" == / ]]; then
    echo
echo 'Live hardware and services:'
    if [[ -e "/dev/i2c-$ACP_PN532_I2C_BUS" ]]; then pass i2c-bus "/dev/i2c-$ACP_PN532_I2C_BUS"; else fail_check i2c-bus 'I2C bus missing'; fi
    i2c_output="$(sudo -- i2cdetect -y "$ACP_PN532_I2C_BUS" "$ACP_PN532_I2C_ADDRESS" "$ACP_PN532_I2C_ADDRESS" 2>/dev/null || true)"
    if printf '%s\n' "$i2c_output" | grep -Eq '(^|[[:space:]])24([[:space:]]|$)'; then pass pn532-i2c 'bus 1 address 0x24'; else fail_check pn532-i2c 'PN532 not visible at accepted address'; fi

    if aplay -l 2>/dev/null | grep -Eq 'card [0-9]+: Pro[[:space:]]+\['; then pass dac-card 'CARD=Pro'; else fail_check dac-card 'CARD=Pro missing'; fi

    for unit in plexamp.service nfc-listener.service; do
        if systemctl is-active --quiet "$unit"; then pass "service:$unit" active; else fail_check "service:$unit" inactive; fi
        enabled="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
        if [[ "$enabled" == enabled || "$enabled" == static ]]; then pass "enable:$unit" "$enabled"; else fail_check "enable:$unit" "${enabled:-unknown}"; fi
    done

    if curl -fsS "http://127.0.0.1:$ACP_PLEXAMP_PORT/" >/dev/null; then pass plexamp-api "localhost:$ACP_PLEXAMP_PORT"; else fail_check plexamp-api "localhost:$ACP_PLEXAMP_PORT unavailable"; fi

    nfc_python="$(root_path "$NFC_VENV/bin/python")"
    if "$nfc_python" -c 'import lgpio, board, busio, requests; from adafruit_pn532.i2c import PN532_I2C' >/dev/null 2>&1; then
        pass nfc-imports 'lgpio/Blinka/PN532/requests'
    else
        fail_check nfc-imports 'NFC hardware-library import failed'
    fi

    config=
    for candidate in /boot/firmware/config.txt /boot/config.txt; do [[ -f "$candidate" && ! -L "$candidate" ]] && { config="$candidate"; break; }; done
    if [[ -n "$config" ]] && grep -Fq "$ACP_DAC_CONFIG_BEGIN" "$config"; then
        if grep -Fxq "dtoverlay=$ACP_DAC_OVERLAY" "$config" && grep -Fq "$ACP_DAC_CONFIG_END" "$config"; then pass dac-managed-config "$config"; else fail_check dac-managed-config 'managed DAC marker is incomplete'; fi
    else
        pass dac-managed-config 'not required; accepted CARD=Pro supplied by EEPROM/existing configuration'
    fi
else
    echo
    warn_check live-hardware 'skipped for alternate-root verification'
fi

echo
printf 'Failures: %d\nWarnings: %d\n' "$FAILURES" "$WARNINGS"
echo 'No production file, package, service, boot setting, route, mixer, PCM or configuration was changed.'
if [[ "$FAILURES" -eq 0 ]]; then echo 'FRESH_BOOTSTRAP_VERIFY=PASS'; exit 0; fi
echo 'FRESH_BOOTSTRAP_VERIFY=FAIL'
exit 1
