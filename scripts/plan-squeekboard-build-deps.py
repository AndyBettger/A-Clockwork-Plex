#!/usr/bin/env python3
"""Preview APT build dependencies for an isolated Raspberry Pi Squeekboard overlay build.

Read-only: no apt update/install, no compiler execution, no Squeekboard process changes.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys

VERSION = "1.43.1-1+rpt1"
STAGED_DIRECTORY = "squeekboard-overlay-" + VERSION
EXPECTED_PANEL_SHA256 = "61d977ba7d7805f58dc57126b2fa410c6115af172889724f3e55cd444d9df916"
EXPECTED_VENDOR_BINARY_SHA256 = "2ad3ef3750c26b94427deb7423041293c1ae658027261a38623373af1a243338"
LAYER = '"layer", ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY,'
UNPATCHED_LAYER = '"layer", ZWLR_LAYER_SHELL_V1_LAYER_TOP,'


class PlanError(Exception):
    """No changes have been made; diagnostic preflight failed."""


def sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(128 * 1024), b""):
            hasher.update(part)
    return hasher.hexdigest()


def build_depends(control: str) -> str:
    """Return only the Source stanza's Build-Depends, preserving alternatives."""
    stanza = control.split("\n\n", 1)[0]
    if not re.search(r"^Source:\s+squeekboard\s*$", stanza, flags=re.MULTILINE):
        raise PlanError("Staged control is not the expected Squeekboard source package")
    found = False
    entries: list[str] = []
    for line in stanza.splitlines():
        if line.startswith("Build-Depends:"):
            if found:
                raise PlanError("Duplicate Build-Depends field")
            found = True
            entries.append(line.partition(":")[2].strip())
        elif found and line.startswith((" ", "\t")):
            entries.append(line.strip())
        elif found:
            break
    result = " ".join(entries).strip().rstrip(",")
    if not found or not result or len(result) > 16_000:
        raise PlanError("Cannot read a bounded Build-Depends list")
    return result


def validate_stage(stage: Path) -> tuple[Path, str]:
    source = stage / "squeekboard-source"
    provenance = stage / "PROVENANCE.txt"
    panel = source / "src" / "panel.c"
    control = source / "debian" / "control"
    if not all(path.is_file() and not path.is_symlink() for path in (provenance, panel, control)):
        raise PlanError("Staged source, provenance or control file absent/invalid; run --prepare first")
    recorded = provenance.read_text(encoding="utf-8")
    if (f"Source: Raspberry Pi Squeekboard {VERSION}" not in recorded or
        f"Installed vendor binary SHA-256: {EXPECTED_VENDOR_BINARY_SHA256}" not in recorded or
        f"src/panel.c after SHA-256: {EXPECTED_PANEL_SHA256}" not in recorded):
        raise PlanError("Source provenance differs from accepted Pi staging baseline")
    contents = panel.read_text(encoding="utf-8")
    if (sha256(panel) != EXPECTED_PANEL_SHA256 or
        contents.count(LAYER) != 1 or UNPATCHED_LAYER in contents):
        raise PlanError("OVERLAY patch/hash changed; refusing to plan dependencies from this tree")
    return source, build_depends(control.read_text(encoding="utf-8"))


def preview(*, stage: Path, runner=subprocess.run) -> int:
    source, deps = validate_stage(stage)
    if not shutil.which("apt-get"):
        raise PlanError("apt-get is unavailable")
    print(f"Validated isolated source: {source}", flush=True)
    print("Validated exactly one OVERLAY layer and recorded source SHA-256.", flush=True)
    print("Build dependencies taken from staged Raspberry Pi debian/control.", flush=True)
    print("\n========== APT SIMULATION (NO CHANGES) ==========", flush=True)
    # -s ensures there are no dpkg operations; disabling Recommends limits the
    # preview to necessary dependencies. No sudo, apt update, upgrade or install.
    args = ["apt-get", "--simulate", "-o", "APT::Install-Recommends=false", "satisfy", deps]
    result = runner(args, check=False)
    if result.returncode:
        print("APT simulation could not resolve this dependency set. Do not install anything yet.", file=sys.stderr)
        return result.returncode
    print("\nReview any proposed removals/upgrades and the disk/download totals before installation.")
    print("This command made no package, keyboard, audio or desktop changes.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    stage = Path.home() / ".cache" / "a-clockwork-plex" / STAGED_DIRECTORY
    try:
        return preview(stage=stage)
    except (PlanError, OSError, UnicodeError) as exc:
        print(f"ACP Squeekboard build-dependency plan: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
