#!/usr/bin/env python3
"""Read-only target-Pi ABI and provenance check for *C3* hot CSS Squeekboard.

The C2 inspector remains pinned to the existing, physically accepted artifact.
This deliberately separate checker verifies the SHA-pinned C3 GitHub artifact,
source patch attestation, exact package/ELF bytes, dynamic library names, and
installed package version floors on the user's Pi WITHOUT executing the ELF,
installing a .deb, stopping/restarting Squeekboard, changing GTK, or writing
outside Python's automatically removed temporary extraction directory.

A PASS is *not* dynamic symbol resolution, a safe runtime handover, or proof
that a displayed keyboard retains focus when its CSS changes.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
from pathlib import Path
import os
import platform
import sys
import zipfile

ARTIFACT_ZIP_SHA256 = "a2f615d31f7006a71867a92553c2aca02ee58ef130867856aeefcff0e2a59274"
VENDOR_C_SHA256 = "bc1076aa72c9b56ab752bd84815593c1228f13e74033de87f231597b27e97353"
PATCHED_C_SHA256 = "f4f45a776e11cc3d1e35631e5f19451e7746a6e53173467bf46580c688759f40"
EXPECTED_FILES = {
    "squeekboard-c3-hot-css-arm64": (
        17109456,
        "fdd1da08861bbc45331e66a70996953ed6ebfb52915a0a5abeb21c585f40bfd5",
    ),
    "squeekboard-c3-hot-css-arm64.deb": (
        2465204,
        "4eaad98634a44dfdfe64c5038283688e34cf55ee1be59eb0cfff1724f4fb8e14",
    ),
}
REPORT_NAMES = (
    "ABI-AND-PACKAGE-REPORT.txt",
    "PATCH-ATTESTATION.txt",
    "PROVENANCE.txt",
    "build-depends.txt",
    "build.log",
)
ALL_NAMES = set(EXPECTED_FILES) | set(REPORT_NAMES)
RESOURCE_LIMIT = 4_000_000
BUILD_LOG_LIMIT = 2_000_000
EXPECTED_VERSION = "1.43.1-1+rpt1"


class PreflightError(Exception):
    pass


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def c2_inspector():
    """Reuse proven C2 checks in a fresh module instance; never edit C2 source."""
    path = Path(__file__).resolve().with_name("inspect-squeekboard-overlay-artifact.py")
    spec = importlib.util.spec_from_file_location("acp_c3_reuse_readonly_abi", path)
    if not spec or not spec.loader:
        raise PreflightError("Maintained ABI inspection helper is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def checked_archive(artifact: Path) -> dict[str, bytes]:
    if not artifact.is_file() or artifact.is_symlink():
        raise PreflightError("C3 ZIP absent or symlinked")
    if digest(artifact.read_bytes()) != ARTIFACT_ZIP_SHA256:
        raise PreflightError("C3 GitHub Actions ZIP SHA-256 mismatch")
    try:
        with zipfile.ZipFile(artifact) as source:
            entries = source.infolist()
            if {e.filename for e in entries} != ALL_NAMES or len(entries) != len(ALL_NAMES):
                raise PreflightError("Missing, duplicate or unexpected C3 artifact entry")
            extracted: dict[str, bytes] = {}
            for entry in entries:
                max_size = (
                    EXPECTED_FILES[entry.filename][0] if entry.filename in EXPECTED_FILES
                    else BUILD_LOG_LIMIT if entry.filename == "build.log" else RESOURCE_LIMIT
                )
                ftype = (entry.external_attr >> 16) & 0o170000
                if (entry.is_dir() or ftype == 0o120000 or
                        entry.file_size > max_size or entry.file_size <= 0):
                    raise PreflightError("Unsafe C3 artifact entry: " + entry.filename)
                data = source.read(entry)
                if len(data) != entry.file_size:
                    raise PreflightError("C3 artifact size mismatch")
                if entry.filename in EXPECTED_FILES:
                    size, sha = EXPECTED_FILES[entry.filename]
                    if entry.file_size != size or digest(data) != sha:
                        raise PreflightError("C3 candidate binary or Debian package SHA mismatch")
                extracted[entry.filename] = data
    except (zipfile.BadZipFile, RuntimeError, OSError, ValueError) as exc:
        raise PreflightError(f"Cannot verify C3 ZIP: {exc}") from exc
    manifest = extracted["PATCH-ATTESTATION.txt"].decode("utf-8")
    for line in (
        "HOT CSS SOURCE PATCH: APPLIED TO DISPOSABLE CI ONLY",
        "Vendor extracted C SHA-256: " + VENDOR_C_SHA256,
        "Patched compiler-input C SHA-256: " + PATCHED_C_SHA256,
        "Accepted C2 keyboard, Pi OSK, 23 immutable CSS palettes: UNCHANGED",
    ):
        if line not in manifest.splitlines():
            raise PreflightError("C3 source patch attestation mismatch")
    provenance = extracted["PROVENANCE.txt"].decode("utf-8")
    if "Vendor version: " + EXPECTED_VERSION not in provenance.splitlines():
        raise PreflightError("Unexpected upstream source provenance")
    report = extracted["ABI-AND-PACKAGE-REPORT.txt"].decode("utf-8")
    for term in (
        "C3 hot-CSS candidate only. NEVER install this .deb on the commissioned Pi.",
        "Architecture: arm64", "Version: " + EXPECTED_VERSION,
        "SHA-256",
        EXPECTED_FILES["squeekboard-c3-hot-css-arm64"][1],
        EXPECTED_FILES["squeekboard-c3-hot-css-arm64.deb"][1],
    ):
        if term not in report:
            raise PreflightError("C3 build ABI report missing expected evidence")
    return extracted


def inspect(artifact: Path) -> None:
    if os.geteuid() == 0 or platform.machine().lower() != "aarch64":
        raise PreflightError("Run as ordinary user on target ARM64 Pi, never sudo")
    checked_archive(artifact)
    inspector = c2_inspector()
    # The C2 inspector is proven on the same Pi for 17 dependencies/18 SONAMEs.
    # Its module object is local; the approved C2 script/constants stay unchanged.
    inspector.EXPECTED = dict(EXPECTED_FILES)
    try:
        inspector.inspect(artifact)
    except (inspector.InspectionError, OSError, zipfile.BadZipFile) as exc:
        raise PreflightError("C3 target Pi ABI preflight failed: " + str(exc)) from exc
    print("C3 SOURCE/PACKAGE/ELF PROVENANCE: VERIFIED (separate C3 artifact)")
    print("C3 TARGET LIBRARY/PACKAGE ABI PREFLIGHT: PASS")
    print("No C3 executable run, no packages installed, no OSK/GTK/ACP changes.")
    print("Actual symbol resolution, CSS repaint and focus continuity: NOT YET TESTED")
    print("DO NOT use the existing C2 --start trial with this C3 artifact.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path,
                        help="Exact C3 ZIP from GitHub Actions C3 run 38473691406")
    args = parser.parse_args()
    try:
        inspect(args.artifact)
        return 0
    except (PreflightError, OSError, UnicodeError) as exc:
        print("ACP C3 native hot-CSS ABI preflight: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
