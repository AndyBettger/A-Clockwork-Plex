#!/bin/bash
set -euo pipefail

PLEXAMP_DIR="${PLEXAMP_DIR:-$HOME/plexamp}"
LAB_ROOT="${LAB_ROOT:-}"

usage() {
    cat <<'EOF'
Usage: bash scripts/prepare-plexamp-upgrade-rehearsal.sh [--plexamp-dir PATH] [--lab-root PATH]

Read-only preparation for a guarded Plexamp Headless upgrade. This script does
not stop services, download files, change Plexamp settings, or run upgrade.sh.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --plexamp-dir) PLEXAMP_DIR="$2"; shift 2 ;;
        --lab-root) LAB_ROOT="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 64 ;;
    esac
done

[[ "$EUID" -ne 0 ]] || { echo "Run as the project user, not root." >&2; exit 1; }

for command in systemctl journalctl sha256sum find grep sed aplay; do
    command -v "$command" >/dev/null 2>&1 || { echo "Required command not found: $command" >&2; exit 1; }
done

if [[ -z "$LAB_ROOT" ]]; then
    LAB_ROOT="$(mktemp -d /var/tmp/a-clockwork-plex-plexamp-upgrade.XXXXXX)"
else
    mkdir -p "$LAB_ROOT"
    LAB_ROOT="$(cd "$LAB_ROOT" && pwd)"
fi
chmod 0700 "$LAB_ROOT"

REPORT="$LAB_ROOT/report.txt"
RESULTS="$LAB_ROOT/results.tsv"
SETTINGS_ROOT="$HOME/.local/share/Plexamp/Settings"
AUDIO_UUID="$SETTINGS_ROOT/%40Plexamp%3Asettings%3AaudioDeviceUuid"
ALIAS_FILE="/etc/alsa/conf.d/98-a-clockwork-plex-control-aliases.conf"

printf 'check\tresult\tdetail\n' >"$RESULTS"

record() {
    printf '%s\t%s\t%s\n' "$1" "$2" "$3" | tee -a "$RESULTS"
}

{
    echo "A Clockwork Plex Plexamp upgrade preparation"
    echo "Generated: $(date --iso-8601=seconds)"
    echo "Plexamp directory: $PLEXAMP_DIR"
    echo "Laboratory: $LAB_ROOT"
    echo "Changes made: none"
} >"$REPORT"

if [[ -d "$PLEXAMP_DIR" ]]; then
    record plexamp-directory PASS "$PLEXAMP_DIR exists"
else
    record plexamp-directory FAIL "$PLEXAMP_DIR is missing"
fi

if [[ -f "$PLEXAMP_DIR/package.json" ]]; then
    grep -E '"version"' "$PLEXAMP_DIR/package.json" | head -n1 >"$LAB_ROOT/package-version.txt" || true
    record package-json PASS "captured package version"
else
    record package-json INFO "package.json not found"
fi

if [[ -x "$PLEXAMP_DIR/upgrade.sh" || -f "$PLEXAMP_DIR/upgrade.sh" ]]; then
    sha256sum "$PLEXAMP_DIR/upgrade.sh" >"$LAB_ROOT/upgrade-sh.sha256"
    sed -n '1,220p' "$PLEXAMP_DIR/upgrade.sh" >"$LAB_ROOT/upgrade-sh.txt"
    record upgrade-script PASS "captured upgrade.sh and SHA256"
else
    record upgrade-script INFO "upgrade.sh not found"
fi

systemctl cat plexamp.service >"$LAB_ROOT/plexamp.service.txt" 2>&1 || true
systemctl show plexamp.service \
    -p ActiveState -p SubState -p User -p Group -p WorkingDirectory -p ExecStart \
    >"$LAB_ROOT/plexamp-service-properties.txt" 2>&1 || true
journalctl -u plexamp.service -n 120 --no-pager >"$LAB_ROOT/plexamp-journal.txt" 2>&1 || true

if [[ -f "$AUDIO_UUID" ]]; then
    cp -a "$AUDIO_UUID" "$LAB_ROOT/audioDeviceUuid.txt"
    record audio-device-setting PASS "captured audioDeviceUuid"
else
    record audio-device-setting INFO "audioDeviceUuid file not found"
fi

if [[ -e "$ALIAS_FILE" ]]; then
    record control-alias-state WARN "$ALIAS_FILE is still present"
else
    record control-alias-state PASS "temporary alias file is absent"
fi

aplay -l >"$LAB_ROOT/aplay-l.txt" 2>&1 || true
aplay -L >"$LAB_ROOT/aplay-L.txt" 2>&1 || true
find "$SETTINGS_ROOT" -maxdepth 1 -type f -printf '%f\n' 2>/dev/null | sort >"$LAB_ROOT/settings-files.txt" || true

cat >>"$REPORT" <<EOF

Results:
$(cat "$RESULTS")

Captured files:
- plexamp.service.txt
- plexamp-service-properties.txt
- plexamp-journal.txt
- package-version.txt (when available)
- upgrade-sh.txt and upgrade-sh.sha256 (when available)
- audioDeviceUuid.txt (when available)
- aplay-l.txt and aplay-L.txt
- settings-files.txt
EOF

cat <<EOF

Plexamp upgrade preparation complete.

  Directory: $LAB_ROOT
  Report:    $REPORT
  Results:   $RESULTS

No service, setting, package, ALSA file or audio route was changed.
EOF
