#!/usr/bin/env python3
"""Stage C3 private, live-replaceable native Squeekboard CSS (not a keyboard trial).

This is a SEPARATE user-owned, 0700 directory with a single selected style.css.
It draws exclusively from the 23 SHA-verified/unaltered C2 GLib palette files.
C3's experimental renderer can watch its directory for atomic style.css
replacement without restarting or changing current text-entry focus.

--plan   read-only check of accepted C2 sources, default/fallback classic_dark.
--stage  one-time PRIVATE filesystem creation, default classic_dark.
--check  read-only verification: exact selected stylesheet must be one of 23.
--select PALETTE  explicitly replace only C3's style.css atomically.

No command launches/stops any keyboard, changes a GTK/system setting or
modifies the accepted C2 stage. No AC P browser bridge or trial process yet.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile

ROOT = Path.home() / ".cache/a-clockwork-plex/squeekboard-c3-hot-css-v1"
RESOURCE_PREFIX = "/sm/puri/squeekboard"
DEFAULT_PALETTE = "classic_dark"
README_NAME = "README.txt"
STYLE_NAME = "style.css"
MANIFEST = (
    "ACP C3 private hot CSS test stage; not a system GTK stylesheet.\n"
    "Single selectable style.css mapped only inside a future candidate process.\n"
    "No keyboard/service/autostart/audio/Headless/NFC changes are made here.\n"
    "Accepted C2 GB layouts and all 23 original CSS resources remain unchanged.\n"
)


class CSSStageError(Exception):
    pass


def source_module():
    source = Path(__file__).resolve().with_name("probe-squeekboard-resource-overlay.py")
    spec = importlib.util.spec_from_file_location("acp_c3_readonly_c2_css_source", source)
    if not spec or not spec.loader:
        raise CSSStageError("Accepted C2 CSS source module unavailable")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def palettes() -> dict[str, bytes]:
    """Require the entire accepted C2 stage to match freshly generated ACP CSS."""
    source = source_module()
    expected = source.samples()
    source.verify_stage(expected)
    if len(expected) != 23 or DEFAULT_PALETTE not in expected:
        raise CSSStageError("Expected 23 validated ACP styles including Classic Dark")
    return {name: css.encode("utf-8") for name, css in expected.items()}


def _directory(path: Path, *, private: bool = False) -> None:
    if path.is_symlink() or not path.is_dir() or path.stat().st_uid != os.getuid():
        raise CSSStageError("Unsafe or unowned C3 cache directory: " + str(path))
    if private and stat.S_IMODE(path.stat().st_mode) != 0o700:
        raise CSSStageError("C3 test directory must have 0700 permissions")


def _file(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise CSSStageError("Expected regular C3 file missing: " + str(path))
    meta = path.stat()
    if meta.st_uid != os.getuid() or meta.st_nlink != 1 or stat.S_IMODE(meta.st_mode) != 0o600:
        raise CSSStageError("Unsafe C3 test file ownership/link count/mode: " + str(path))
    return path.read_bytes()


def inspect(expected: dict[str, bytes]) -> str:
    """Refuse stale, altered, symlinked or unexpected C3 filesystem content."""
    _directory(ROOT, private=True)
    actual = {p.name for p in ROOT.iterdir()}
    if actual != {README_NAME, STYLE_NAME}:
        raise CSSStageError("C3 directory includes missing/unexpected files")
    if _file(ROOT / README_NAME) != MANIFEST.encode("utf-8"):
        raise CSSStageError("C3 manifest differs from accepted test-only text")
    selected = _file(ROOT / STYLE_NAME)
    found = [name for name, value in expected.items() if selected == value]
    if len(found) != 1:
        raise CSSStageError("C3 active CSS not an exact accepted ACP palette")
    return found[0]


def _parent() -> None:
    parent = ROOT.parent
    if parent.is_symlink():
        raise CSSStageError("C3 cache parent cannot be a symlink")
    if parent.exists():
        _directory(parent)
    else:
        # The well-known cache prefix is the only new parent we may create.
        home_cache = parent.parent
        if home_cache.is_symlink():
            raise CSSStageError("Home cache symlink refused")
        if not home_cache.is_dir() or home_cache.stat().st_uid != os.getuid():
            raise CSSStageError("Home cache directory must already exist")
        parent.mkdir(mode=0o700)


def stage(expected: dict[str, bytes]) -> None:
    if ROOT.exists() or ROOT.is_symlink():
        raise CSSStageError("Refusing to overwrite existing C3 test stage")
    _parent()
    temp = Path(tempfile.mkdtemp(prefix=".c3-hot-css-stage-", dir=ROOT.parent))
    try:
        temp.chmod(0o700)
        for name, content in (
            (README_NAME, MANIFEST.encode("utf-8")),
            (STYLE_NAME, expected[DEFAULT_PALETTE]),
        ):
            path = temp / name
            with path.open("xb") as dest:
                dest.write(content)
            path.chmod(0o600)
        # Atomically expose a complete stage, never an incomplete stylesheet.
        temp.rename(ROOT)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    if inspect(expected) != DEFAULT_PALETTE:
        raise CSSStageError("C3 Classic Dark staging verification failed")


def select(expected: dict[str, bytes], name: str) -> tuple[str, bool]:
    if name not in expected:
        raise CSSStageError("Unknown ACP Squeekboard palette: " + name)
    previous = inspect(expected)
    if name == previous:
        return previous, False
    # Only one candidate-specific resource file may change; replacing the
    # directory or changing C2's existing files is forbidden.
    staging = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".c3-next-style-", suffix=".tmp",
            dir=ROOT, delete=False,
        ) as stream:
            staging = Path(stream.name)
            os.fchmod(stream.fileno(), 0o600)
            stream.write(expected[name])
        if staging.is_symlink() or _file(staging) != expected[name]:
            raise CSSStageError("Temporary private C3 CSS did not verify")
        os.replace(staging, ROOT / STYLE_NAME)
        staging = None
    finally:
        if staging is not None and staging.exists():
            staging.unlink()
    if inspect(expected) != name:
        raise CSSStageError("C3 post-selection verification failed")
    return previous, True


def resource_environment() -> dict[str, str]:
    """Values for a FUTURE candidate-only handover; never export them globally."""
    return {
        "G_RESOURCE_OVERLAYS": RESOURCE_PREFIX + "=" + str(ROOT),
        "ACP_SQUEEKBOARD_CSS_DIR": str(ROOT),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--stage", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--select", metavar="PALETTE")
    args = parser.parse_args()
    if os.geteuid() == 0:
        print("Refusing sudo/root for candidate-only CSS", file=sys.stderr)
        return 2
    try:
        expected = palettes()
        if args.plan:
            print("=== ACP C3 PRIVATE HOT CSS PLAN (READ ONLY) ===")
            print("Destination:", ROOT)
            print("Palette inventory:", len(expected))
            print("Default/fallback:", DEFAULT_PALETTE)
            if ROOT.exists() or ROOT.is_symlink():
                print("Existing C3 palette:", inspect(expected))
            else:
                print("C3 private stage absent; --stage can create it.")
            print("PLAN PASS; no keyboard, files or system settings changed.")
        elif args.stage:
            stage(expected)
            print("STAGE PASS: private C3 style.css created as Classic Dark")
            print("C2 immutable resource stage and stock OSK unchanged.")
        elif args.check:
            current = inspect(expected)
            print("C3 PRIVATE CSS CHECK PASS: " + current)
            print("Exact accepted palette bytes:", hashlib.sha256(expected[current]).hexdigest())
            print("Candidate-only GResource prefix:", RESOURCE_PREFIX)
            print("No keyboard process or global GTK settings changed.")
        else:
            previous, changed = select(expected, args.select)
            print("C3 PRIVATE CSS SELECTION:", previous, "->", args.select)
            print("Atomic style.css change:", "YES" if changed else "NO")
            print("Selection only; no running keyboard, service or GTK settings changed.")
        return 0
    except (CSSStageError, OSError, KeyError, ValueError) as exc:
        print("ACP C3 private CSS: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
