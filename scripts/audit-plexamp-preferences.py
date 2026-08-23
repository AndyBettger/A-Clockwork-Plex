#!/usr/bin/env python3
"""Read-only inventory of Plexamp preference storage and safe browser metadata.

Default mode is content-blind for Plexamp values. ``--show-safe-values`` opens
only the explicit typed Headless preference allow-list established from the
commissioned Plexamp 4.13.2 appliance. ``--scan-browser-keys`` reads only
Chromium Local Storage LevelDB data files and emits structured loopback-origin
key names; it never decodes or prints Local Storage values and never opens
Session Storage values.

For React Native MMKV's web implementation, Local Storage keys are namespaced
as ``<instance-id>\\<preference-key>``. The scanner recognises the default
``mmkv.default\\`` namespace and emits only safe-looking suffix names. It still
never decodes or prints the corresponding values.

``--fingerprint-browser-records`` retains the earlier broad differential aid.
``--fingerprint-browser-customizations`` is narrower: it hashes only complete
``mmkv.default\\discovery:customizations:...`` record neighbourhoods so a
before/after Plexamp Home-layout experiment can identify the exact customization
record that changed without decoding or printing any browser value.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import re
from pathlib import Path
from urllib.parse import unquote


PLEXAMP_SETTINGS_PREFIX = "@Plexamp:settings:"
SAFE_KEY = re.compile(r"^[A-Za-z0-9_.:@/+ -]{1,120}$")
SAFE_MMKV_SUFFIX = re.compile(r"^[A-Za-z0-9_.:@/+ -]{1,120}$")
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
LEVELDB_DATA_SUFFIXES = {".ldb", ".log"}

LOOPBACK_STORAGE_KEY = re.compile(
    rb"_(https?://(?:localhost|127\.0\.0\.1|\[::1\])(?::[0-9]{1,5})?)"
    rb"\x00(?:\x00|\x01)?([A-Za-z@][A-Za-z0-9_.:@/+ -]{0,119})"
)

MMKV_WEB_PREFIX = "mmkv.default\\"
MMKV_LOOPBACK_STORAGE_KEY = re.compile(
    rb"_(https?://(?:localhost|127\.0\.0\.1|\[::1\])(?::[0-9]{1,5})?)"
    rb"\x00(?:\x00|\x01)?mmkv\.default\\"
    rb"([A-Za-z0-9_@][A-Za-z0-9_.:@/+ -]{0,119})"
)
MMKV_CUSTOMIZATION_PREFIX = "discovery:customizations:"

SAFE_VALUE_SPECS = {
    "audioConversionBitrate": "integer",
    "autoPlayEnabled": "boolean",
    "cacheSize": "integer",
    "cachingWiFi": "integer",
    "loudnessLeveling": "boolean",
    "precacheNetworkSpeed": "integer",
    "sampleRateConversionQuality": "integer",
    "sampleRateMatching": "integer",
}
SAFE_VALUE_KEYS = frozenset(SAFE_VALUE_SPECS)

KNOWN_NON_PORTABLE_KEYS = {
    "audioDeviceUuid": "device-specific output binding; recommission on the target",
    "playerName": "device label/identity; keep outside the ordinary portable preference bundle",
    "premium": "derived account/capability state; do not restore",
}

BROWSER_FINGERPRINT_KEYS = frozenset(
    {
        "@Plexamp:settings:activeTab",
        "@Plexamp:settings:radioIncludeExternal",
        "mmkv.default",
    }
)
BROWSER_FINGERPRINT_WINDOW_BEFORE = 32
BROWSER_FINGERPRINT_WINDOW_AFTER = 2048


def _has_sensitive_term(key: str) -> bool:
    lowered = key.lower()
    return any(term in lowered for term in SENSITIVE_KEY_TERMS)


def candidate_key(filename: str) -> str | None:
    """Return a safe Headless preference-key suffix, never a file value."""
    decoded = unquote(filename)
    if not decoded.startswith(PLEXAMP_SETTINGS_PREFIX):
        return None
    key = decoded[len(PLEXAMP_SETTINGS_PREFIX) :]
    if not SAFE_KEY.fullmatch(key):
        return None
    if _has_sensitive_term(key):
        return None
    return key


def _decode_plexamp_scalar(text: str, expected: str) -> object:
    """Decode one supported Plexamp typed scalar or raise ValueError."""
    text = text.strip()
    if expected == "boolean":
        if text == "Btrue":
            return True
        if text == "Bfalse":
            return False
        raise ValueError("unexpected Plexamp boolean encoding")

    if expected == "integer":
        if not text.startswith("N"):
            raise ValueError("unexpected Plexamp numeric encoding")
        number_text = text[1:]
        if not re.fullmatch(r"-?(?:0|[1-9][0-9]{0,15})", number_text):
            raise ValueError("unexpected Plexamp integer encoding")
        return int(number_text)

    raise ValueError("unsupported preference type")


def _safe_scalar(path: Path, expected: str) -> str:
    """Read one explicitly allow-listed typed scalar and return display text."""
    try:
        if path.stat().st_size > 64:
            return "<not shown: value exceeds 64-byte audit limit>"
        raw = path.read_bytes()
    except OSError:
        return "<not shown: unreadable>"

    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return "<not shown: non-UTF-8 value>"

    try:
        parsed = _decode_plexamp_scalar(text, expected)
    except ValueError:
        return "<not shown: unexpected typed scalar format>"

    if isinstance(parsed, bool):
        return "true" if parsed else "false"
    if isinstance(parsed, int) and not isinstance(parsed, bool):
        return str(parsed)
    if isinstance(parsed, float) and math.isfinite(parsed):
        return repr(parsed)
    return "<not shown: unexpected scalar type>"


def _safe_browser_key(raw_key: bytes) -> str | None:
    try:
        key = raw_key.decode("ascii", errors="strict").strip()
    except UnicodeDecodeError:
        return None
    if not SAFE_KEY.fullmatch(key):
        return None
    if _has_sensitive_term(key):
        return None
    return key


def _safe_mmkv_suffix(raw_suffix: bytes) -> str | None:
    try:
        suffix = raw_suffix.decode("ascii", errors="strict").strip()
    except UnicodeDecodeError:
        return None
    if not SAFE_MMKV_SUFFIX.fullmatch(suffix):
        return None
    if _has_sensitive_term(suffix):
        return None
    return suffix


def _browser_leveldb_payloads(browser_default: Path) -> list[tuple[Path, bytes]]:
    leveldb = browser_default / "Local Storage" / "leveldb"
    if not leveldb.is_dir():
        return []

    payloads: list[tuple[Path, bytes]] = []
    for path in sorted(leveldb.iterdir()):
        if not path.is_file() or path.suffix.lower() not in LEVELDB_DATA_SUFFIXES:
            continue
        try:
            payloads.append((path, path.read_bytes()))
        except OSError:
            continue
    return payloads


def _scan_browser_local_storage(browser_default: Path) -> None:
    """Print only structured loopback Local Storage key names, never values."""
    leveldb = browser_default / "Local Storage" / "leveldb"
    print("Chromium Local Storage structured key audit:")
    if not leveldb.is_dir():
        print("  LevelDB directory: NOT FOUND")
        return

    payloads = _browser_leveldb_payloads(browser_default)
    scanned_files = len(payloads)
    scanned_bytes = sum(len(payload) for _path, payload in payloads)
    origins: set[str] = set()
    keys_by_origin: dict[str, set[str]] = {}
    sensitive_records = 0
    mmkv_keys = 0

    for _path, payload in payloads:
        for match in MMKV_LOOPBACK_STORAGE_KEY.finditer(payload):
            origin = match.group(1).decode("ascii", errors="strict")
            raw_suffix = match.group(2)
            try:
                decoded_for_filter = raw_suffix.decode("ascii", errors="strict")
            except UnicodeDecodeError:
                continue
            if _has_sensitive_term(decoded_for_filter):
                sensitive_records += 1
                continue
            suffix = _safe_mmkv_suffix(raw_suffix)
            if suffix is None:
                continue
            origins.add(origin)
            keys_by_origin.setdefault(origin, set()).add(f"{MMKV_WEB_PREFIX}{suffix}")
            mmkv_keys += 1

        for match in LOOPBACK_STORAGE_KEY.finditer(payload):
            origin = match.group(1).decode("ascii", errors="strict")
            raw_key = match.group(2)
            try:
                decoded_for_filter = raw_key.decode("ascii", errors="strict")
            except UnicodeDecodeError:
                continue
            if _has_sensitive_term(decoded_for_filter):
                sensitive_records += 1
                continue
            key = _safe_browser_key(raw_key)
            if key is None or key == "mmkv.default":
                continue
            origins.add(origin)
            keys_by_origin.setdefault(origin, set()).add(key)

    print(f"  LevelDB data files scanned: {scanned_files}")
    print(f"  Bytes scanned: {scanned_bytes}")
    if not origins:
        print("  Structured loopback origins/keys: none detected")
        print("  No browser Local Storage values were decoded or printed.")
        return

    print("  Loopback origins and non-sensitive key names:")
    for origin in sorted(origins):
        print(f"    {origin}")
        for key in sorted(keys_by_origin.get(origin, ()), key=str.casefold):
            print(f"      {key}")
    if mmkv_keys:
        print(
            f"  MMKV web-key records recognised: {mmkv_keys} "
            "(mmkv.default\\<key> namespace; values not decoded)"
        )
    if sensitive_records:
        print(f"  Sensitive-looking key records suppressed: {sensitive_records}")
    print("  No browser Local Storage values were decoded or printed.")


def _record_fingerprint(payload: bytes, start_at: int, end_at: int) -> str:
    start = max(0, start_at - BROWSER_FINGERPRINT_WINDOW_BEFORE)
    end = min(len(payload), end_at + BROWSER_FINGERPRINT_WINDOW_AFTER)
    return hashlib.sha256(payload[start:end]).hexdigest()[:20]


def _print_fingerprint_records(
    heading: str,
    records: dict[tuple[str, str], set[str]],
    occurrences: dict[tuple[str, str], int],
) -> None:
    print(heading)
    if not records:
        print("  Approved candidate records: none detected")
        print("  No browser values were decoded or printed.")
        return

    print("  Approved candidate record-neighbourhood hashes:")
    for origin, key in sorted(records, key=lambda item: (item[0], item[1].casefold())):
        digests = ", ".join(sorted(records[(origin, key)]))
        count = occurrences[(origin, key)]
        print(f"    {origin} | {key} | occurrences={count} | fingerprints={digests}")


def _fingerprint_browser_records(browser_default: Path) -> None:
    """Hash bounded neighbourhoods for broad discovery keys; never decode values."""
    leveldb = browser_default / "Local Storage" / "leveldb"
    if not leveldb.is_dir():
        print("Chromium Local Storage differential fingerprints:")
        print("  LevelDB directory: NOT FOUND")
        return

    records: dict[tuple[str, str], set[str]] = {}
    occurrences: dict[tuple[str, str], int] = {}
    for _path, payload in _browser_leveldb_payloads(browser_default):
        for match in LOOPBACK_STORAGE_KEY.finditer(payload):
            origin = match.group(1).decode("ascii", errors="strict")
            key = _safe_browser_key(match.group(2))
            if key not in BROWSER_FINGERPRINT_KEYS:
                continue
            identity = (origin, key)
            occurrences[identity] = occurrences.get(identity, 0) + 1
            records.setdefault(identity, set()).add(
                _record_fingerprint(payload, match.start(), match.end())
            )

    _print_fingerprint_records(
        "Chromium Local Storage differential fingerprints:", records, occurrences
    )
    if records:
        print("  @Plexamp:resources is deliberately excluded from fingerprinting.")
        if any(key == "mmkv.default" for _origin, key in records):
            print(
                "  mmkv.default hashes are namespace-prefix neighbourhoods across "
                "individual MMKV web keys, not one packed value."
            )
        print(
            "  Hashes cover bounded record neighbourhoods, not decoded preference values."
        )
        print("  No browser values were decoded or printed.")


def _fingerprint_browser_customizations(browser_default: Path) -> None:
    """Fingerprint only complete Plexamp MMKV customization keys."""
    leveldb = browser_default / "Local Storage" / "leveldb"
    if not leveldb.is_dir():
        print("Chromium Plexamp Home-layout customization fingerprints:")
        print("  LevelDB directory: NOT FOUND")
        return

    records: dict[tuple[str, str], set[str]] = {}
    occurrences: dict[tuple[str, str], int] = {}

    for _path, payload in _browser_leveldb_payloads(browser_default):
        for match in MMKV_LOOPBACK_STORAGE_KEY.finditer(payload):
            origin = match.group(1).decode("ascii", errors="strict")
            suffix = _safe_mmkv_suffix(match.group(2))
            if suffix is None or not suffix.startswith(MMKV_CUSTOMIZATION_PREFIX):
                continue
            key = f"{MMKV_WEB_PREFIX}{suffix}"
            identity = (origin, key)
            occurrences[identity] = occurrences.get(identity, 0) + 1
            records.setdefault(identity, set()).add(
                _record_fingerprint(payload, match.start(), match.end())
            )

    _print_fingerprint_records(
        "Chromium Plexamp Home-layout customization fingerprints:",
        records,
        occurrences,
    )
    if records:
        print("  Only discovery:customizations:* MMKV records are fingerprinted.")
        print("  cachedItems, @Plexamp:resources and unrelated browser state are excluded.")
        print(
            "  Hashes cover bounded record neighbourhoods, not decoded customization values."
        )
        print("  No browser values were decoded or printed.")


def audit(
    home: Path,
    *,
    show_safe_values: bool = False,
    scan_browser_keys: bool = False,
    fingerprint_browser_records: bool = False,
    fingerprint_browser_customizations: bool = False,
) -> int:
    settings_dir = home / ".local" / "share" / "Plexamp" / "Settings"
    browser_default = home / ".config" / "a-clockwork-plex" / "chromium-profile" / "Default"

    print("A Clockwork Plex — Plexamp preference inventory")
    if show_safe_values:
        print("READ-ONLY AUDIT: ONLY EXPLICITLY ALLOW-LISTED ORDINARY PREFERENCE VALUES ARE READ")
    else:
        print("READ-ONLY AUDIT: NO PLEXAMP SETTING VALUES ARE READ")
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
                print(f"  {key} = {_safe_scalar(path, SAFE_VALUE_SPECS[key])}")
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

    if scan_browser_keys:
        _scan_browser_local_storage(browser_default)
    if fingerprint_browser_records:
        _fingerprint_browser_records(browser_default)
    if fingerprint_browser_customizations:
        _fingerprint_browser_customizations(browser_default)

    browser_audit = (
        scan_browser_keys
        or fingerprint_browser_records
        or fingerprint_browser_customizations
    )
    if show_safe_values and browser_audit:
        print(
            "Unknown Plexamp values and Chromium values remain excluded; "
            "browser audit emitted names/hashes only."
        )
    elif show_safe_values:
        print("No unknown Plexamp values and no Chromium storage values were opened or printed.")
    elif browser_audit:
        print("No Plexamp setting values or Chromium Local Storage values were decoded or printed.")
    else:
        print("No Plexamp/Chromium storage values were opened or printed.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inventory Plexamp preferences; optionally show approved Headless values or safe browser metadata."
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
        help="Read/show only the explicit typed Headless preference allow-list; never unknown/identity/browser values.",
    )
    parser.add_argument(
        "--scan-browser-keys",
        action="store_true",
        help=(
            "Scan Chromium Local Storage LevelDB data files for structured "
            "loopback-origin key names and safe mmkv.default\\<key> suffixes "
            "only; never decode values."
        ),
    )
    parser.add_argument(
        "--fingerprint-browser-records",
        action="store_true",
        help=(
            "Hash bounded LevelDB record neighbourhoods for the explicit "
            "non-sensitive broad discovery keys; never decode values."
        ),
    )
    parser.add_argument(
        "--fingerprint-browser-customizations",
        action="store_true",
        help=(
            "Hash only complete mmkv.default\\discovery:customizations:* "
            "record neighbourhoods to identify Home-layout changes; never decode values."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return audit(
        args.home.expanduser(),
        show_safe_values=args.show_safe_values,
        scan_browser_keys=args.scan_browser_keys,
        fingerprint_browser_records=args.fingerprint_browser_records,
        fingerprint_browser_customizations=args.fingerprint_browser_customizations,
    )


if __name__ == "__main__":
    raise SystemExit(main())
