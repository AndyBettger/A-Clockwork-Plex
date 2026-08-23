#!/usr/bin/env python3
"""Read-only inventory of Plexamp preference storage names and approved values.

Default mode is intentionally content-blind: it never opens Plexamp or Chromium
storage files. ``--show-safe-values`` opens only an explicit allow-list of
ordinary Plexamp preference files whose names were first observed by the
content-blind audit. Unknown, identity, capability, authentication and browser
storage remain unread.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import unquote


PLEXAMP_SETTINGS_PREFIX = "@Plexamp:settings:"
SAFE_KEY = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
SAFE_SCALAR = re.compile(r"^[A-Za-z0-9_.+ -]{1,48}$")
SENSITIVE_KEY_TERMS = {
    "account",
    "auth",
    "claim",
    "clientid",
    "cookie",
    "credential",
    "identity",
    "machine",
    "password",
    "secret",
    "session",
    "token",
}
BROWSER_STORAGE_AREAS = (
    "Local Storage",
    "IndexedDB",
    "Session Storage",
)

# These keys were observed on the commissioned Plexamp 4.13.2 development Pi
# and are ordinary preference candidates. Value mode may open only these files.
SAFE_VALUE_KEYS = frozenset(
    {
        "audioConversionBitrate",
        "autoPlayEnabled",
        "cacheSize",
        "cachingWiFi",
        "loudnessLeveling",
        "precacheNetworkSpeed",
        "sampleRateConversionQuality",
        "sampleRateMatching",
    }
)

# These names are useful to classify, but their values are deliberately never
# opened by this helper.
KNOWN_NON_PORTABLE_KEYS = {
    "audioDeviceUuid": "device-specific output binding; recommission on the target",
    "playerName": "device label/identity; keep outside the ordinary portable preference bundle",
    "premium": "derived account/capability state; do not restore",
}


def candidate_key(filename: str) -> str | None:
    """Return a safe preference-key suffix, never a file value."""

    decoded = unquote(filename)
    if not decoded.startswith(PLEXAMP_SETTINGS_PREFIX):
        return None
    key = decoded[len(PLEXAMP_SETTINGS_PREFIX) :]
    lowered = key.lower()
    if not SAFE_KEY.fullmatch(key):
        return None
    if any(term in lowered for term in SENSITIVE_KEY_TERMS):
        return None
    return key


def _safe_scalar(path: Path) -> str:
    """Read one explicitly allow-listed small scalar and return safe display text."""

    try:
        if path.stat().st_size > 64:
            return "<not shown: value exceeds 64-byte audit limit>"
        raw = path.read_bytes()
    except OSError:
        return "<not shown: unreadable>"

    try:
        text = raw.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError:
        return "<not shown: non-UTF-8 value>"

    # Prefer JSON primitive interpretation when Plexamp stores JSON-ish values.
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        parsed = text

    if isinstance(parsed, bool):
        return "true" if parsed else "false"
    if isinstance(parsed, int) and not isinstance(parsed, bool):
        return str(parsed)
    if isinstance(parsed, float):
        return repr(parsed)
    if isinstance(parsed, str) and SAFE_SCALAR.fullmatch(parsed):
        return json.dumps(parsed)
    return "<not shown: unexpected scalar format>"


def audit(home: Path, *, show_safe_values: bool = False) -> int:
    settings_dir = home / ".local" / "share" / "Plexamp" / "Settings"
    browser_default = home / ".config" / "a-clockwork-plex" / "chromium-profile" / "Default"

    print("A Clockwork Plex — Plexamp preference inventory")
    if show_safe_values:
        print("READ-ONLY AUDIT: ONLY EXPLICITLY ALLOW-LISTED ORDINARY PREFERENCE VALUES ARE READ")
    else:
        print("READ-ONLY AUDIT: NO FILE CONTENTS ARE READ")
    print(f"Plexamp Settings path: {settings_dir}")

    total_files = 0
    safe_candidates: list[tuple[str, int, Path]] = []
    excluded = 0

    if settings_dir.is_dir():
        for entry in settings_dir.iterdir():
            if not entry.is_file():
                continue
            total_files += 1
            key = candidate_key(entry.name)
            if key is None:
                excluded += 1
                continue
            try:
                size = entry.stat().st_size
            except OSError:
                excluded += 1
                continue
            safe_candidates.append((key, size, entry))

        safe_candidates.sort(key=lambda item: item[0].casefold())
        print(f"Plexamp Settings files: {total_files}")
        print(f"Candidate non-sensitive preference keys: {len(safe_candidates)}")
        print(f"Excluded/unclassified files: {excluded}")
        if safe_candidates:
            print("Candidate keys (name and file size only):")
            for key, size, _path in safe_candidates:
                print(f"  {key}\t{size} bytes")
        else:
            print("Candidate keys: none")

        if show_safe_values:
            by_key = {key: path for key, _size, path in safe_candidates}
            print("Explicit portable-preference value audit:")
            found_safe = False
            for key in sorted(SAFE_VALUE_KEYS, key=str.casefold):
                path = by_key.get(key)
                if path is None:
                    continue
                found_safe = True
                print(f"  {key} = {_safe_scalar(path)}")
            if not found_safe:
                print("  none of the explicit allow-listed keys are present")

            present_non_portable = [
                key for key in KNOWN_NON_PORTABLE_KEYS if key in by_key
            ]
            if present_non_portable:
                print("Known non-portable/ separately-owned keys (values NOT read):")
                for key in sorted(present_non_portable, key=str.casefold):
                    print(f"  {key}: {KNOWN_NON_PORTABLE_KEYS[key]}")
    else:
        print("Plexamp Settings: NOT FOUND")

    print(f"Chromium profile path: {browser_default}")
    if browser_default.is_dir():
        print("Chromium storage areas present (directory presence only):")
        found = False
        for area in BROWSER_STORAGE_AREAS:
            if (browser_default / area).is_dir():
                found = True
                print(f"  {area}")
        if not found:
            print("  none of the inspected storage areas")
    else:
        print("Chromium profile: NOT FOUND")

    if show_safe_values:
        print("No unknown Plexamp values and no Chromium storage values were opened or printed.")
    else:
        print("No Plexamp/Chromium storage values were opened or printed.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inventory Plexamp preference keys; optionally show only explicit safe scalar values."
    )
    parser.add_argument(
        "--home",
        type=Path,
        default=Path.home(),
        help="Home directory to inspect (default: current user's home).",
    )
    parser.add_argument(
        "--show-safe-values",
        action="store_true",
        help="Read/show only the explicit ordinary preference allow-list; never unknown/identity/browser values.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return audit(args.home.expanduser(), show_safe_values=args.show_safe_values)


if __name__ == "__main__":
    raise SystemExit(main())
