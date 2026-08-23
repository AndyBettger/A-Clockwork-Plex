#!/usr/bin/env python3
"""Read-only inventory of Plexamp preference storage names.

This helper is intentionally conservative. It never opens Plexamp or Chromium
storage files and never prints non-preference filenames. It exists only to help
classify which non-authentication preferences may be safe to support in the
A Clockwork Plex backup/restore feature.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import unquote


PLEXAMP_SETTINGS_PREFIX = "@Plexamp:settings:"
SAFE_KEY = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
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


def audit(home: Path) -> int:
    settings_dir = home / ".local" / "share" / "Plexamp" / "Settings"
    browser_default = home / ".config" / "a-clockwork-plex" / "chromium-profile" / "Default"

    print("A Clockwork Plex — Plexamp preference inventory")
    print("READ-ONLY AUDIT: NO FILE CONTENTS ARE READ")
    print(f"Plexamp Settings path: {settings_dir}")

    total_files = 0
    safe_candidates: list[tuple[str, int]] = []
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
            safe_candidates.append((key, size))

        safe_candidates.sort(key=lambda item: item[0].casefold())
        print(f"Plexamp Settings files: {total_files}")
        print(f"Candidate non-sensitive preference keys: {len(safe_candidates)}")
        print(f"Excluded/unclassified files: {excluded}")
        if safe_candidates:
            print("Candidate keys (name and file size only):")
            for key, size in safe_candidates:
                print(f"  {key}\t{size} bytes")
        else:
            print("Candidate keys: none")
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

    print("No Plexamp/Chromium storage values were opened or printed.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List safe Plexamp preference-key filenames without reading their contents."
    )
    parser.add_argument(
        "--home",
        type=Path,
        default=Path.home(),
        help="Home directory to inspect (default: current user's home).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return audit(args.home.expanduser())


if __name__ == "__main__":
    raise SystemExit(main())
