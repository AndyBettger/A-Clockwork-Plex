#!/usr/bin/env python3
"""Read-only audit of the C3 hot-CSS patch against an extracted Squeekboard source.

Only inspects eek/eek-gtk-keyboard.c; NEVER writes to, patches, compiles,
runs, installs or restarts a keyboard. The separate disposable CI runner
may redirect this program's stdout (audit and diff) to a report file.

Pinning of official Debian sources (version and downloaded tarball
checksums from .dsc, plus known panel.c SHA-256) is performed by the
existing scripts/ci/prepare-squeekboard-overlay-source.py before this
verifier sees the extracted source tree.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import importlib.util
from pathlib import Path
import sys

KEYBOARD_SOURCE = Path("eek/eek-gtk-keyboard.c")


class AuditError(RuntimeError):
    pass


def patcher():
    path = Path(__file__).resolve().with_name("patch-squeekboard-hot-css.py")
    spec = importlib.util.spec_from_file_location("acp_c3_css_patch_for_audit", path)
    if not spec or not spec.loader:
        raise AuditError("Isolated CSS patch helper missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_source_tree(source_root: Path) -> dict[str, str | int]:
    """Validate a source tree; produce diff and hashes IN MEMORY only."""
    if source_root.is_symlink() or not source_root.is_dir():
        raise AuditError("Source directory absent or symlinked")
    source_path = source_root / KEYBOARD_SOURCE
    if source_path.is_symlink() or not source_path.is_file():
        raise AuditError("Vendor eek/eek-gtk-keyboard.c absent or symlinked")
    try:
        original_bytes = source_path.read_bytes()
        original = original_bytes.decode("utf-8")
        patch = patcher()
        amended = patch.patch_keyboard_source(original)
        if amended == original:
            raise AuditError("No CSS hook added")
        if not amended.startswith(original.splitlines(keepends=True)[0]):
            raise AuditError("Unexpected vendor file prefix change")
        # Ensure exactly the five intentional source insertions are reversible.
        restored = amended
        for insertion in (
            patch.INCLUDE, patch.PRIVATE, patch.HELPERS,
            patch.DISPOSE_CLEANUP, patch.NEW_WATCH,
        ):
            if restored.count(insertion) != 1:
                raise AuditError("Inserted patch content missing or duplicated")
            restored = restored.replace(insertion, "", 1)
        if restored != original:
            raise AuditError("Patched text changed existing vendor content")
        diff = "".join(difflib.unified_diff(
            original.splitlines(keepends=True),
            amended.splitlines(keepends=True),
            fromfile="vendor/eek/eek-gtk-keyboard.c",
            tofile="candidate/eek/eek-gtk-keyboard.c",
            n=4,
        ))
        if diff.count("\n@@ ") not in range(1, 8):
            raise AuditError("Diff differs from expected limited insertion scope")
        return {
            "vendor_path": str(KEYBOARD_SOURCE),
            "original_sha256": hashlib.sha256(original_bytes).hexdigest(),
            "candidate_sha256": hashlib.sha256(amended.encode("utf-8")).hexdigest(),
            "original_bytes": len(original_bytes),
            "candidate_bytes": len(amended.encode("utf-8")),
            "insertions": 5,
            "diff": diff,
        }
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
        raise AuditError(f"Vendor source audit refused: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-tree", type=Path, required=True,
                        help="Path of already verified, extracted Debian Squeekboard source")
    parser.add_argument("--expected-vendor-sha256", default=None,
                        help="Optional previously reviewed full-file SHA-256 (fail closed on mismatch)")
    parser.add_argument("--show-diff", action="store_true",
                        help="Print exact additive source diff (no file modifications)")
    args = parser.parse_args()
    try:
        audit = verify_source_tree(args.source_tree)
        expected = args.expected_vendor_sha256
        if expected is not None and (
            len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected)
            or audit["original_sha256"] != expected
        ):
            raise AuditError("Vendor keyboard C SHA-256 did not match expected pin")
        print("=== ACP C3 PINNED SOURCE HOOK AUDIT: READ ONLY ===")
        print("Source path:", audit["vendor_path"])
        print("Original SHA-256:", audit["original_sha256"])
        print("Proposed SHA-256:", audit["candidate_sha256"])
        print("Original byte count:", audit["original_bytes"])
        print("Proposed byte count:", audit["candidate_bytes"])
        print("Reversible isolated insertions:", audit["insertions"])
        print("Only proposed additions: PASS; original contents fully preserved.")
        print("Keyboard runtime, binary, package, GTK, source file: UNCHANGED")
        if args.show_diff:
            print("=== BEGIN PROPOSED SOURCE DIFF ===")
            print(audit["diff"], end="")
            print("=== END PROPOSED SOURCE DIFF ===")
        print("SOURCE PATCH COMPATIBILITY: PASS (no compilation performed)")
        return 0
    except AuditError as exc:
        print("SOURCE PATCH COMPATIBILITY: FAIL:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
