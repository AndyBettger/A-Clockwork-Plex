#!/usr/bin/env python3
"""Read-only check of staged Stage C2 UK Squeekboard layout/theme files.

Never starts, stops or restyles the running keyboard. Checks exact generated
contents against the pinned installed vendor files and ACP CSS tokens, then
runs optional local YAML/Squeekboard layout parsers if already installed.
No packages or dependencies are installed.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys


class CheckError(Exception):
    pass


def generator():
    path = Path(__file__).resolve().with_name("stage-squeekboard-uk-theme.py")
    spec = importlib.util.spec_from_file_location("acp_c2_uk_theme_stage", path)
    if spec is None or spec.loader is None:
        raise CheckError("Offline stage generator not found")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_read(root: Path, relative: str) -> str:
    dest = root / relative
    if not dest.is_file() or dest.is_symlink() or not dest.resolve().is_relative_to(root):
        raise CheckError("Missing, unsafe or symlinked staged file: " + relative)
    try:
        return dest.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CheckError("Cannot read staged file: " + relative) from exc


def staged_files(root: Path) -> dict[str, str]:
    """Do not follow symlinks; allow only the manifest and generated files."""
    names = {}
    for folder, subdirs, files in os.walk(root, followlinks=False):
        for name in subdirs:
            entry = Path(folder) / name
            if entry.is_symlink():
                raise CheckError("Symlinked stage directory: " + str(entry))
        for name in files:
            file = Path(folder) / name
            if file.is_symlink():
                raise CheckError("Symlinked stage file: " + str(file))
            rel = file.relative_to(root).as_posix()
            names[rel] = str(file)
    return names


def validate_yaml(layouts: dict[str, str], root: Path) -> tuple[int, int]:
    yaml_present = importlib.util.find_spec("yaml") is not None
    if yaml_present:
        import yaml  # Installed on Pi, if available; never install a dependency.
        for name in sorted(layouts):
            try:
                data = yaml.safe_load(layouts[name])
            except yaml.YAMLError as exc:
                raise CheckError("YAML parser rejected " + name + ": " + str(exc)) from exc
            if not isinstance(data, dict) or not isinstance(data.get("views"), dict):
                raise CheckError("YAML parser did not find keyboard views in " + name)
        print("YAML SYNTAX: PASS (installed PyYAML)")
    else:
        print("YAML SYNTAX: NOT CHECKED (PyYAML is not installed; no install attempted)")

    parser = shutil.which("squeekboard-test-layout")
    if not parser:
        print("SQUEEKBOARD LAYOUT PARSER: NOT AVAILABLE (binary not installed)")
        return len(layouts) if yaml_present else 0, 0

    for name in sorted(layouts):
        candidate = root / "keyboards" / name
        try:
            result = subprocess.run(
                [parser, str(candidate)], capture_output=True, text=True,
                timeout=12, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise CheckError("Squeekboard parser unavailable for " + name) from exc
        if result.returncode != 0 or "Test result: OK" not in result.stdout:
            raise CheckError("Squeekboard parser rejected " + name +
                             " (see local parser output, no runtime change)")
    print("SQUEEKBOARD LAYOUT PARSER: PASS (" + str(len(layouts)) + " files)")
    return len(layouts) if yaml_present else 0, len(layouts)


def validate() -> None:
    if os.geteuid() == 0:
        raise CheckError("Use the ordinary Pi account, never sudo")
    g = generator()
    # stock() pins both the exact installed Squeekboard package and ELF SHA.
    layouts, themes = g.stock(), g.styles()
    root = g.DEST
    if not root.is_dir() or root.is_symlink():
        raise CheckError("Private Stage C2 directory missing or unsafe; nothing modified")
    root = root.resolve()
    if root.stat().st_uid != os.getuid():
        raise CheckError("Stage directory is not owned by this user")

    required = {"README.txt"}
    required.update("keyboards/" + name for name in layouts)
    required.update("themes/" + name + "/gtk-3.0/gtk.css" for name in themes)
    actual = set(staged_files(root))
    if required != actual:
        raise CheckError("Stage manifest differs; missing=" +
                         repr(sorted(required - actual)) +
                         " unexpected=" + repr(sorted(actual - required)))

    header = safe_read(root, "README.txt")
    if "OFFLINE" not in header or "no keyboard/theme service activated" not in header:
        raise CheckError("Stage safety manifest is absent or incorrect")
    for name, expected in layouts.items():
        if safe_read(root, "keyboards/" + name) != expected:
            raise CheckError("UK keyboard differs from verified vendor-derived file: " + name)
    for name, expected in themes.items():
        if safe_read(root, "themes/" + name + "/gtk-3.0/gtk.css") != expected:
            raise CheckError("Theme differs from current ACP palette: " + name)

    print("VENDOR / STAGING MANIFEST: PASS (binary/package pinned)")
    print("UK LAYOUT CONTENT: PASS (" + str(len(layouts)) + " exact vendor-derived files)")
    print("ACP GTK3 PALETTE CONTENT: PASS (" + str(len(themes)) +
          " sample styles; not runtime-applied)")
    validate_yaml(layouts, root)
    print("STATIC STAGE CHECK: PASS; stock OSK, global GTK and audio unchanged")
    print("Physical key output, GTK appearance, and live ACP day/night sync: NOT YET TESTED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Read-only staged layout/style check")
    args = parser.parse_args()
    if not args.check:
        parser.print_help()
        return 2
    try:
        validate()
    except (CheckError, OSError, ValueError) as exc:
        print("ACP C2 stage validation: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
