#!/usr/bin/env python3
"""Prepare a pinned ARM64 Squeekboard overlay source in disposable CI only.

Does not install the built program or change the commissioned Raspberry Pi.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


PI_VERSION = "1.43.1-1+rpt1"
BEFORE_SHA256 = "2983685254b5d5b81ce36d9277172a041502737450dee416a6f805b82d51c203"
AFTER_SHA256 = "61d977ba7d7805f58dc57126b2fa410c6115af172889724f3e55cd444d9df916"


def source_helper():
    script = Path(__file__).resolve().parents[1] / "prepare-squeekboard-overlay.py"
    spec = importlib.util.spec_from_file_location("squeekboard_source_staging", script)
    if not spec or not spec.loader:
        raise RuntimeError("Cannot load tested Squeekboard source helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def repair_scaling_test_fixture(source: str) -> tuple[str, int]:
    """Repair only the vendor Rust test fixtures missing OutputState.name.

    The packaged 1.43.1 source has an Option<String> name field but retains
    scaling-test initialisers without that field; normal lib compilation works,
    while cargo test --no-run fails with E0063. This never changes runtime logic.
    """
    anchor = "Application::get_preferred_height_and_arrangement(&OutputState {"
    old = "                    scale,\\n                }),".replace("\\\\n", "\\n")
    new = "                    scale,\\n                    name: None,\\n                }),".replace("\\\\n", "\\n")
    count = source.count(anchor)
    if count not in (1, 2) or source.count(old) != count or source.count(new) != 0:
        raise RuntimeError("Unexpected vendor scaling test fixture; refusing extra source changes")
    changed = source.replace(old, new)
    if changed.count("name: None,") - source.count("name: None,") != count:
        raise RuntimeError("Unexpected number of vendor test fixture repairs")
    return changed, count


def stage_source(destination: Path, *, helper=None) -> None:
    if destination.exists() or destination.is_symlink():
        raise RuntimeError(f"Destination exists: {destination}")
    helper = helper if helper is not None else source_helper()
    if helper.VERSION != PI_VERSION:
        raise RuntimeError("Source helper no longer targets commissioned Pi vendor version")
    destination.parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix=".acp-squeekboard-ci-", dir=destination.parent))
    try:
        downloads = scratch / "downloads"
        downloads.mkdir()
        descriptor = downloads / helper.DSC_NAME
        helper.download(helper.BASE_URL + helper.DSC_NAME, descriptor)
        raw = descriptor.read_text(encoding="utf-8")
        if f"Version: {PI_VERSION}" not in raw.splitlines():
            raise RuntimeError("Source descriptor has unexpected version")
        checks = helper.source_checksums(raw)
        for name in helper.SOURCE_NAMES:
            expected_hash, expected_size = checks[name]
            archive = downloads / name
            helper.download(helper.BASE_URL + name, archive, size_limit=expected_size)
            if archive.stat().st_size != expected_size or helper.sha256(archive) != expected_hash:
                raise RuntimeError(f"Vendor source archive mismatch: {name}")
        source = scratch / "squeekboard-source"
        subprocess.run(["dpkg-source", "-x", str(descriptor), str(source)], check=True)
        panel = source / "src/panel.c"
        if not panel.is_file() or panel.is_symlink():
            raise RuntimeError("Vendor src/panel.c missing or invalid")
        if helper.sha256(panel) != BEFORE_SHA256:
            raise RuntimeError("Vendor panel.c hash differs from physically approved source")
        panel.write_text(helper.patch_panel_text(panel.read_text(encoding="utf-8")), encoding="utf-8")
        if helper.sha256(panel) != AFTER_SHA256:
            raise RuntimeError("Patched panel.c hash differs from commissioned Pi result")
        # Only affects #[cfg(test)] scaling fixtures, not the keyboard itself.
        state = source / "src/state.rs"
        original_state = state.read_text(encoding="utf-8")
        repaired_state, repaired_count = repair_scaling_test_fixture(original_state)
        state.write_text(repaired_state, encoding="utf-8")
        (scratch / "PROVENANCE.txt").write_text(
            f"Source descriptor: {helper.BASE_URL}{helper.DSC_NAME}\n"
            f"Vendor version: {PI_VERSION}\n"
            f"Original src/panel.c SHA-256: {BEFORE_SHA256}\n"
            f"Modified src/panel.c SHA-256: {AFTER_SHA256}\n"
            "One edit: TOP -> OVERLAY; Raspberry Pi Debian patches applied by dpkg-source.\n"
            f"CI-only vendor Rust scaling-test fixture initialisers repaired: {repaired_count} (name: None).\\n".replace("\\\\n", "\\n")
            "Only test fixtures changed additionally; no runtime logic changed.\\n".replace("\\\\n", "\\n")
            "SHA-256 checked against descriptor fetched via HTTPS; unsigned .dsc not independently GPG-verified.\n"
            "TEST-ONLY ARM64 BUILD: do not install on Pi before ABI review and a timed recovery plan.\n",
            encoding="utf-8",
        )
        scratch.rename(destination)
        print(f"Source and patch verified: {destination / 'squeekboard-source'}", flush=True)
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        stage_source(args.destination.resolve())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"ACP Squeekboard CI source preparation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
