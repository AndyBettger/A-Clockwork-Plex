#!/usr/bin/env python3
"""Apply C3 hot-CSS Squeekboard patch ONLY inside throwaway ARM64 CI build.

Unlike scripts/ci/audit-squeekboard-hot-css-source.py, this edits the extracted
candidate C file so the isolated compiler can verify linkage. It is not an
installer and must never run on the commissioned Pi. Source and patched byte
SHA-256 values are pinned to the separately reviewed successful source audit.

The original accepted C2 ARM64 build and the user's 180s/240s OSK recovery
are not connected to this script.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import platform
import subprocess
import sys

VENDOR_C_SHA256 = "bc1076aa72c9b56ab752bd84815593c1228f13e74033de87f231597b27e97353"
PATCHED_C_SHA256 = "f4f45a776e11cc3d1e35631e5f19451e7746a6e53173467bf46580c688759f40"
RELATIVE_C = Path("eek/eek-gtk-keyboard.c")


class CandidateBuildError(RuntimeError):
    pass


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def generate_checked_patch(
    original: bytes,
    *,
    expected_vendor: str = VENDOR_C_SHA256,
    expected_candidate: str = PATCHED_C_SHA256,
) -> bytes:
    """Pure: validate both pinned hashes, including a reversible diff."""
    if digest(original) != expected_vendor:
        raise CandidateBuildError("Vendor C SHA-256 differs from source-only ARM64 audit")
    try:
        original_text = original.decode("utf-8")
        # Source audit owns the insertion structure/reversal safety checks.
        from importlib.util import module_from_spec, spec_from_file_location
        auditor_path = Path(__file__).resolve().with_name("audit-squeekboard-hot-css-source.py")
        spec = spec_from_file_location("acp_c3_build_patch_auditor", auditor_path)
        if not spec or not spec.loader:
            raise CandidateBuildError("Auditor is missing")
        auditor = module_from_spec(spec)
        spec.loader.exec_module(auditor)
        patch = auditor.patcher()
        candidate_text = patch.patch_keyboard_source(original_text)
        candidate = candidate_text.encode("utf-8")
    except (UnicodeError, OSError, RuntimeError, ValueError) as exc:
        raise CandidateBuildError(f"Candidate source transformation refused: {exc}") from exc
    if digest(candidate) != expected_candidate:
        raise CandidateBuildError("Candidate C SHA-256 differs from reviewed source-only diff")
    if candidate == original:
        raise CandidateBuildError("No candidate patch generated")
    return candidate


def validate_disposable_ci_environment(source_tree: Path) -> Path:
    """The helper must not be executable as a generic C file replacer."""
    if os.geteuid() != 0 or os.environ.get("GITHUB_ACTIONS") != "true":
        raise CandidateBuildError("Requires GitHub Actions' disposable container root")
    if not Path("/.dockerenv").is_file():
        raise CandidateBuildError("Not in disposable Docker CI container")
    if platform.machine() != "aarch64":
        raise CandidateBuildError("ARM64 build-only host required")
    if subprocess.run(
        ["dpkg", "--print-architecture"], capture_output=True, text=True,
        check=False, timeout=10,
    ).stdout.strip() != "arm64":
        raise CandidateBuildError("Debian arm64 container required")
    if source_tree.is_symlink() or not source_tree.is_dir():
        raise CandidateBuildError("Source tree missing or symlinked")
    # The only permitted destination is from the C3 container builder's
    # mktemp /tmp/acp-squeekboard-c3-arm64-XXXXXXXX/vendor/squeekboard-source.
    parent = source_tree.parent
    staging = parent.parent
    if (
        source_tree.name != "squeekboard-source"
        or parent.name != "vendor"
        or not staging.name.startswith("acp-squeekboard-c3-arm64-")
        or staging.parent != Path("/tmp")
        or parent.is_symlink()
        or staging.is_symlink()
    ):
        raise CandidateBuildError("Refusing source tree outside C3 disposable build root")
    path = source_tree / RELATIVE_C
    if path.is_symlink() or not path.is_file():
        raise CandidateBuildError("Vendor C source missing or symlinked")
    return path


def apply_to_disposable_ci(source_tree: Path) -> tuple[str, str]:
    target = validate_disposable_ci_environment(source_tree)
    original = target.read_bytes()
    candidate = generate_checked_patch(original)
    # Temp file kept in *same directory* as target; atomic replace; no copy
    # to the Pi, accepted C2 artifact directory or global /usr system paths.
    temporary = target.with_name(".acp-c3-hot-css-build-candidate.tmp")
    if temporary.exists() or temporary.is_symlink():
        raise CandidateBuildError("Unrecognised candidate temporary file: refuse overwrite")
    try:
        with temporary.open("xb") as stream:
            stream.write(candidate)
        os.replace(temporary, target)
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()
    if digest(target.read_bytes()) != PATCHED_C_SHA256:
        raise CandidateBuildError("Build candidate source verification failed")
    return digest(original), digest(candidate)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-tree", required=True, type=Path)
    args = parser.parse_args()
    try:
        orig_sha, proposed_sha = apply_to_disposable_ci(args.source_tree)
        print("HOT CSS SOURCE PATCH: APPLIED TO DISPOSABLE CI ONLY")
        print("Vendor extracted C SHA-256:", orig_sha)
        print("Patched compiler-input C SHA-256:", proposed_sha)
        print("Accepted C2 keyboard, Pi OSK, 23 immutable CSS palettes: UNCHANGED")
        return 0
    except (CandidateBuildError, OSError, subprocess.TimeoutExpired) as exc:
        print("C3 CI source patch REFUSED:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
