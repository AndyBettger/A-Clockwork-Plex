#!/usr/bin/env python3
"""Stage Raspberry Pi's exact Squeekboard source with one OVERLAY change.

Development-only: no package, service, audio, autostart, or runtime mutation.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request


VERSION = "1.43.1-1+rpt1"
UPSTREAM_VERSION = "1.43.1"
EXPECTED_VENDOR_BINARY_SHA256 = (
    "2ad3ef3750c26b94427deb7423041293c1ae658027261a38623373af1a243338"
)
BASE_URL = "https://archive.raspberrypi.org/debian/pool/main/s/squeekboard/"
DSC_NAME = f"squeekboard_{VERSION}.dsc"
SOURCE_NAMES = (
    f"squeekboard_{UPSTREAM_VERSION}.orig.tar.bz2",
    f"squeekboard_{VERSION}.debian.tar.xz",
)
OLD_LAYER = '"layer", ZWLR_LAYER_SHELL_V1_LAYER_TOP,'
NEW_LAYER = '"layer", ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY,'


class PreparationError(Exception):
    """Preflight/source verification failed; no installed software was changed."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(128 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_checksums(dsc_text: str) -> dict[str, tuple[str, int]]:
    """Read just the two expected files from the descriptor's SHA-256 section."""
    entries: dict[str, tuple[str, int]] = {}
    in_section = False
    for line in dsc_text.splitlines():
        if line == "Checksums-Sha256:":
            in_section = True
            continue
        if not in_section:
            continue
        if not line.startswith((" ", "\t")):
            break
        match = re.fullmatch(r"\s+([0-9a-f]{64})\s+(\d+)\s+(\S+)\s*", line)
        if not match:
            raise PreparationError("Unexpected Checksums-Sha256 entry in source descriptor")
        checksum, count, name = match.groups()
        if name in entries:
            raise PreparationError("Duplicate source descriptor entry")
        entries[name] = (checksum, int(count))
    if set(entries) != set(SOURCE_NAMES):
        raise PreparationError(
            f"Source descriptor does not describe exactly the expected files: {sorted(entries)}"
        )
    if any(size <= 0 or size > 10_000_000 for _, size in entries.values()):
        raise PreparationError("Unexpected source archive size")
    return entries


def patch_panel_text(source: str) -> str:
    if source.count(OLD_LAYER) != 1 or NEW_LAYER in source:
        raise PreparationError("Expected exactly one unpatched TOP layer in src/panel.c")
    return source.replace(OLD_LAYER, NEW_LAYER, 1)


def download(url: str, target: Path, *, size_limit: int = 1_000_000) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "ACP-PhaseB-Squeekboard-Source-Staging/1"})
    with urllib.request.urlopen(request, timeout=40) as response, target.open("wb") as out:
        if not response.geturl().startswith("https://"):
            raise PreparationError("Source download redirected to a non-HTTPS URL")
        size = 0
        while chunk := response.read(128 * 1024):
            size += len(chunk)
            if size > size_limit:
                raise PreparationError("Downloaded source file exceeds size limit")
            out.write(chunk)


def confirm_vendor() -> None:
    if os.geteuid() == 0:
        raise PreparationError("Run as the normal desktop user, never with sudo")
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=$" + "{Version}", "squeekboard"],
        text=True, capture_output=True, check=True,
    )
    if result.stdout != VERSION:
        raise PreparationError(f"Installed Squeekboard is {result.stdout}, expected {VERSION}")
    actual = sha256(Path("/usr/bin/squeekboard"))
    if actual != EXPECTED_VENDOR_BINARY_SHA256:
        raise PreparationError("Vendor keyboard SHA-256 differs from the physically recorded baseline")
    if shutil.which("dpkg-source") is None:
        raise PreparationError("dpkg-source is required for safe source extraction (no change made)")


def prepare(destination: Path) -> None:
    confirm_vendor()
    if destination.exists() or destination.is_symlink():
        raise PreparationError(f"Destination already exists; refusing to overwrite: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".squeekboard-stage-", dir=destination.parent))
    try:
        downloads = stage / "downloads"
        downloads.mkdir()
        dsc = downloads / DSC_NAME
        print(f"Fetching Raspberry Pi vendor descriptor: {DSC_NAME}", flush=True)
        download(BASE_URL + DSC_NAME, dsc)
        expected = source_checksums(dsc.read_text(encoding="utf-8"))
        for name in SOURCE_NAMES:
            checksum, size = expected[name]
            archive = downloads / name
            print(f"Fetching and verifying {name}", flush=True)
            download(BASE_URL + name, archive, size_limit=size)
            if archive.stat().st_size != size or sha256(archive) != checksum:
                raise PreparationError(f"Source descriptor checksum/size mismatch: {name}")
        source = stage / "squeekboard-source"
        # dpkg-source verifies the descriptor's checksums and applies the vendor
        # Debian quilt patches. It does not install any packages or binaries.
        subprocess.run(["dpkg-source", "-x", str(dsc), str(source)], check=True)
        panel = source / "src" / "panel.c"
        if not panel.is_file() or not panel.resolve().is_relative_to(source.resolve()):
            raise PreparationError("Missing or unsafe src/panel.c in extracted vendor source")
        before = sha256(panel)
        patched = patch_panel_text(panel.read_text(encoding="utf-8"))
        panel.write_text(patched, encoding="utf-8")
        after = sha256(panel)
        (stage / "PROVENANCE.txt").write_text(
            f"Source: Raspberry Pi Squeekboard {VERSION}\n"
            f"Descriptor: {BASE_URL}{DSC_NAME}\n"
            f"Installed vendor binary SHA-256: {EXPECTED_VENDOR_BINARY_SHA256}\n"
            f"src/panel.c before SHA-256: {before}\n"
            f"src/panel.c after SHA-256: {after}\n"
            "Only change after applying vendor source patches: one TOP -> OVERLAY substitution.\n"
            "Not built or installed. Do not execute alongside the stock keyboard.\n",
            encoding="utf-8",
        )
        stage.rename(destination)
        print(f"Prepared overlay source: {destination / 'squeekboard-source'}")
        print("No keyboard was stopped, built, installed or launched.")
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="Display the non-installing plan (default)")
    mode.add_argument("--prepare", action="store_true", help="Download, verify, extract and patch source only")
    args = parser.parse_args()
    destination = Path.home() / ".cache" / "a-clockwork-plex" / f"squeekboard-overlay-{VERSION}"
    if not args.prepare:
        print(f"Vendor target: squeekboard {VERSION}; original keyboard SHA-256: {EXPECTED_VENDOR_BINARY_SHA256}")
        print(f"Source: {BASE_URL}{DSC_NAME}")
        print(f"Staging destination: {destination}")
        print("--prepare: uses vendor source descriptor hashes and exactly one TOP -> OVERLAY patch.")
        print("Never stops/restarts Squeekboard, installs packages, changes autostart or builds code.")
        return 0
    try:
        prepare(destination)
    except (PreparationError, OSError, subprocess.CalledProcessError, urllib.error.URLError) as exc:
        print(f"ACP Squeekboard staging: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
