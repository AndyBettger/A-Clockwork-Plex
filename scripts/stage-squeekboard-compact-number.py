#!/usr/bin/env python3
"""Offline-only compact numeric Squeekboard experiment (Stage C2).

Creates a NEW versioned private GB keyboard directory. The physically accepted
squeekboard-c2-uk-theme-v1, themed GLib resources, and stock OSK remain intact.
No service, desktop setting, running keyboard or trial state is touched.

Run --plan, then --stage, then --check. Do NOT use as the live trial's
SQUEEKBOARD_KEYBOARDSDIR until separately integrated into guarded controller.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path.home() / ".cache/a-clockwork-plex/squeekboard-c2-compact-number-v1"
MARGIN_FRACTION = 0.45
MANIFEST = (
    "ACP C2 compact-number-v1 OFFLINE test-only candidate; never installed.\n"
    "Copied only verified GB YAML from accepted Stage C2 v1; modified number/gb.yaml.\n"
    "No keyboard, service, GTK configuration or audio touched.\n"
)


class CompactError(Exception):
    pass


def accepted_validator():
    path = Path(__file__).resolve().with_name("validate-squeekboard-uk-theme-stage.py")
    spec = importlib.util.spec_from_file_location("acp_c2_stable_stage", path)
    if not spec or not spec.loader:
        raise CompactError("Accepted UK layout stage validator unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def input_layouts() -> dict[str, str]:
    validator = accepted_validator()
    try:
        validator.validate()  # Verify exact original vendor, seven YAML, 23 CSS first.
    except (validator.CheckError, OSError) as exc:
        raise CompactError("Accepted UK keyboard stage validation failed: " + str(exc)) from exc
    base = validator.generator().DEST.resolve()
    layouts = {}
    for name in validator.generator().stock():
        layouts[name] = validator.safe_read(base, "keyboards/" + name)
    if "number/gb.yaml" not in layouts or len(layouts) != 7:
        raise CompactError("Expected precisely seven accepted GB keymap files")
    return layouts


def compact_numeric(original: str) -> tuple[str, float, float]:
    """Use only the vendor YAML's outline widths; preserve every key/action.

    Add side margins equal to 45% of the widest row's virtual width. Estimated
    content occupancy is 1/(1+2*.45) ~= 52.6%. The vendor runtime may impose
    extra panel geometry, so this is a *hypothesis* pending physical validation.
    """
    try:
        import yaml
        data = yaml.safe_load(original)
    except (ImportError, ValueError, Exception) as exc:
        raise CompactError("PyYAML cannot parse vendor numeric layout") from exc
    if not isinstance(data, dict):
        raise CompactError("Numeric YAML structure is not a mapping")
    if "margins" in data:
        raise CompactError("Vendor already defines margins; manual review needed")
    if "views" not in data or set(data["views"]) != {"base"}:
        raise CompactError("Unexpected numeric view structure")
    outlines = data.get("outlines")
    buttons = data.get("buttons")
    if not isinstance(outlines, dict) or not isinstance(buttons, dict):
        raise CompactError("Numeric outline/button mapping unavailable")
    default = outlines.get("default")
    if not isinstance(default, dict):
        raise CompactError("Numeric default outline unavailable")
    if not isinstance(data["views"]["base"], list) or len(data["views"]["base"]) != 4:
        raise CompactError("Unexpected numeric row count")
    widths = []
    for row in data["views"]["base"]:
        if not isinstance(row, str):
            raise CompactError("Unexpected numeric row type")
        names = row.split()
        if not 4 <= len(names) <= 5:
            raise CompactError("Unexpected numeric column count")
        total = 0.0
        for name in names:
            spec = buttons.get(name, {})
            if not isinstance(spec, dict):
                raise CompactError("Invalid numeric button definition")
            outline = outlines.get(spec.get("outline", "default"))
            if not isinstance(outline, dict):
                raise CompactError("Unknown numeric button outline")
            width = outline.get("width")
            if not isinstance(width, (float, int)) or not 0 < width < 1000:
                raise CompactError("Unexpected numeric outline width")
            total += width
        widths.append(total)
    max_width = max(widths)
    if not 100 < max_width < 1000:
        raise CompactError("Unreasonable native numeric keyboard width")
    side = round(max_width * MARGIN_FRACTION, 3)
    if not original.startswith("---\n") or original.count("\nmargins:") != 0:
        raise CompactError("Numeric YAML header changed; review before staging")
    amended = original.replace(
        "---\n", f"---\nmargins: {{ top: 0, side: {side:g}, bottom: 0 }}\n", 1,
    )
    # Literal body-preserving insertion, never regenerate or reformat a key.
    if amended.split("\n", 2)[2] != original.split("\n", 1)[1]:
        raise CompactError("Numeric keyboard edit changed key definitions")
    return amended, max_width, side


def expected_layouts(layouts: dict[str, str]) -> tuple[dict[str, str], float, float]:
    out = dict(layouts)
    out["number/gb.yaml"], max_width, side = compact_numeric(layouts["number/gb.yaml"])
    return out, max_width, side


def actual_manifest() -> set[str]:
    if not ROOT.is_dir() or ROOT.is_symlink() or ROOT.stat().st_uid != os.getuid():
        raise CompactError("Private compact-numeric stage absent or wrong owner")
    files = set()
    for folder, dirs, names in os.walk(ROOT, followlinks=False):
        for name in dirs:
            if (Path(folder) / name).is_symlink():
                raise CompactError("Symlink in private compact stage")
        for name in names:
            file = Path(folder) / name
            if file.is_symlink():
                raise CompactError("Symlink file in private compact stage")
            files.add(file.relative_to(ROOT).as_posix())
    return files


def verify(expected: dict[str, str]) -> None:
    required = {"README.txt"} | {"keyboards/" + name for name in expected}
    if actual_manifest() != required:
        raise CompactError("Compact stage file manifest does not match")
    if (ROOT / "README.txt").read_text(encoding="utf-8") != MANIFEST:
        raise CompactError("Compact stage safety manifest differs")
    for name, content in expected.items():
        file = ROOT / "keyboards" / name
        if file.read_text(encoding="utf-8") != content:
            raise CompactError("Compact keyboard changed after staging: " + name)
    print("COMPACT NUMERIC PRIVATE STAGE: PASS (7 exact files)")
    print("Accepted v1 keyboard and global GTK remain unchanged.")


def stage(expected: dict[str, str]) -> None:
    if ROOT.exists() or ROOT.is_symlink():
        raise CompactError("Refusing to overwrite an existing compact stage")
    ROOT.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    scratch = Path(tempfile.mkdtemp(prefix=".compact-number-", dir=ROOT.parent))
    try:
        scratch.chmod(0o700)
        for name, content in expected.items():
            target = scratch / "keyboards" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        (scratch / "README.txt").write_text(MANIFEST, encoding="utf-8")
        scratch.rename(ROOT)
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--plan", action="store_true")
    action.add_argument("--stage", action="store_true")
    action.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if os.geteuid() == 0:
        print("Never run with sudo or as root.", file=sys.stderr)
        return 2
    try:
        original = input_layouts()
        expected, width, side = expected_layouts(original)
        ratio = 100 / (1 + 2 * MARGIN_FRACTION)
        print(f"Original maximum numeric row outline width: {width:.2f} units")
        print(f"Proposed symmetric side margin: {side:g} units")
        print(f"Estimated keyboard-content share of panel width: {ratio:.1f}% (not yet physical)")
        print("Changed keymap: number/gb.yaml only; all keys/actions unchanged.")
        print("Private candidate:", ROOT)
        if args.plan:
            if ROOT.exists() or ROOT.is_symlink():
                verify(expected)
            else:
                print("PLAN PASS: new private stage can be created without touching accepted v1.")
        elif args.stage:
            stage(expected)
            verify(expected)
        elif args.check:
            verify(expected)
        else:
            parser.print_help()
            return 2
        print("No OSK processes, services, original YAML or themes changed.")
        return 0
    except (CompactError, OSError, ValueError) as exc:
        print("ACP compact numeric stage: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
