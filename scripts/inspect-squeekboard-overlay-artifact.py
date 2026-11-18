#!/usr/bin/env python3
"""Read-only ABI preflight of the experimental ARM64 Squeekboard ZIP on the Pi.

Never runs the candidate, installs packages, changes services or stops the OSK.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

EXPECTED = {
    "squeekboard-overlay-arm64": (17109456, "11e1c8ef40674503cb9a0b82a96086d8bbca319c99943b9061bc5629118166a6"),
    "squeekboard_1.43.1-1+rpt1_arm64.deb": (2468116, "f13e11f67b868d6f23beeeb607596fa99e05b5657c575526dcca43ca1ef1511e"),
}
SONAMES = {
    "libgio-2.0.so.0", "libgobject-2.0.so.0", "libglib-2.0.so.0",
    "libgnome-desktop-3.so.20", "libgtk-3.so.0", "libgdk-3.so.0",
    "libpangocairo-1.0.so.0", "libpango-1.0.so.0",
    "libcairo-gobject.so.2", "libcairo.so.2", "libgdk_pixbuf-2.0.so.0",
    "libbsd.so.0", "libfeedback-0.0.so.0", "libwayland-client.so.0",
    "libxkbcommon.so.0", "libgcc_s.so.1", "libc.so.6",
    "ld-linux-aarch64.so.1",
}


class InspectionError(Exception):
    pass


def checked_files(archive: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(archive) as source:
        entries = source.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)) or not set(EXPECTED).issubset(names) or len(entries) > 10:
            raise InspectionError("Unrecognised or duplicate artifact entries")
        result = {}
        for name, (size, digest) in EXPECTED.items():
            info = source.getinfo(name)
            if info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise InspectionError("Unexpected file type in artifact")
            if info.file_size != size:
                raise InspectionError(f"Unexpected artifact file size: {name}")
            data = source.read(name)
            if hashlib.sha256(data).hexdigest() != digest:
                raise InspectionError(f"Artifact SHA-256 mismatch: {name}")
            result[name] = data
    return result


def satisfied_dependency(expression: str) -> bool:
    match = re.fullmatch(r"([\w.+-]+)(?:\s+\(>=\s*([^) ]+)\))?", expression.strip())
    if not match:
        raise InspectionError(f"Unsupported dependency expression: {expression}")
    package, floor = match.groups()
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${db:Status-Status}\t${Version}", package],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0 or not result.stdout.startswith("installed\t"):
        return False
    if floor is None:
        return True
    return subprocess.run(
        ["dpkg", "--compare-versions", result.stdout.split("\t", 1)[1].strip(), "ge", floor],
        check=False,
    ).returncode == 0


def missing_dependencies(depends: str) -> list[str]:
    return [
        requirement.strip()
        for requirement in depends.split(",")
        if not any(satisfied_dependency(alt) for alt in requirement.split("|"))
    ]


def needed_sonames(dynamic_section: str) -> set[str]:
    return set(re.findall(r"\(NEEDED\)[^\n]*?\[([^\]]+)\]", dynamic_section))


def missing_sonames(needed: set[str], cache: str) -> list[str]:
    available = set(re.findall(r"(?m)^\s*(\S+)\s+\([^)]*\)\s+=>", cache))
    missing = needed - available
    if "ld-linux-aarch64.so.1" in missing and Path("/lib/ld-linux-aarch64.so.1").is_file():
        missing.remove("ld-linux-aarch64.so.1")
    return sorted(missing)


def inspect(archive: Path) -> None:
    if os.geteuid() == 0 or platform.machine().lower() != "aarch64":
        raise InspectionError("Run as the ordinary user on the ARM64 Raspberry Pi, without sudo")
    if not archive.is_file():
        raise InspectionError(f"Artifact ZIP not found: {archive}")
    files = checked_files(archive)
    required = ("readelf", "dpkg-deb", "dpkg-query", "dpkg")
    if any(shutil.which(command) is None for command in required):
        raise InspectionError("Missing a read-only Debian/ELF inspection command")
    loader = next((p for p in ("/sbin/ldconfig", "/usr/sbin/ldconfig") if Path(p).is_file()), None)
    if loader is None:
        raise InspectionError("ldconfig not available")
    with tempfile.TemporaryDirectory(prefix="acp-overlay-abi-") as temp:
        directory = Path(temp)
        binary, package = [directory / n for n in EXPECTED]
        for path in (binary, package):
            path.write_bytes(files[path.name])  # No execute bit, temporary files deleted.
        elf_header = subprocess.run(
            ["readelf", "-h", str(binary)], capture_output=True, text=True, check=True,
        ).stdout
        if "AArch64" not in elf_header:
            raise InspectionError("Unexpected ELF architecture")
        dynamic = subprocess.run(
            ["readelf", "-d", str(binary)], capture_output=True, text=True, check=True,
        ).stdout
        needed = needed_sonames(dynamic)
        if needed != SONAMES or "(RUNPATH)" in dynamic or "(RPATH)" in dynamic:
            raise InspectionError("Unexpected executable shared libraries or RPATH")
        fields = subprocess.run(
            ["dpkg-deb", "-f", str(package), "Package", "Version", "Architecture", "Depends"],
            capture_output=True, text=True, check=True,
        ).stdout
        metadata = dict(line.split(": ", 1) for line in fields.splitlines() if ": " in line)
        if any(metadata.get(field) != value for field, value in (
            ("Package", "squeekboard"), ("Version", "1.43.1-1+rpt1"), ("Architecture", "arm64"),
        )):
            raise InspectionError("Unexpected Debian package version or architecture")
        if not metadata.get("Depends"):
            raise InspectionError("Debian package dependencies missing")
        missing_packages = missing_dependencies(metadata["Depends"])
        cache = subprocess.run(
            [loader, "-p"], capture_output=True, text=True, check=True,
        ).stdout
        missing_libraries = missing_sonames(needed, cache)
    print("Artifact ELF and .deb SHA-256: PASS")
    print("Architecture and package metadata: PASS")
    print(f"Runtime dependency clauses checked: {len(metadata['Depends'].split(','))}")
    print(f"Direct ELF library names checked: {len(needed)}")
    if missing_packages:
        print("Unsatisfied package requirements: " + "; ".join(missing_packages))
    if missing_libraries:
        print("Missing shared libraries: " + "; ".join(missing_libraries))
    if missing_packages or missing_libraries:
        raise InspectionError("ABI preflight FAILED; do not start the candidate")
    print("ABI PACKAGE/LIBRARY PREFLIGHT PASSED")
    print("No program executed or system files, desktop or keyboard changed.")
    print("Actual dynamic symbol resolution and fullscreen touch behaviour remain untested.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path, help="ZIP downloaded from ARM64 run #5")
    args = parser.parse_args()
    try:
        inspect(args.artifact)
    except (InspectionError, OSError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        print(f"ACP Squeekboard ABI preflight: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
