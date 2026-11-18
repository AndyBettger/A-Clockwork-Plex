#!/usr/bin/env python3
"""Stage and test a private GLib resource overlay; NEVER launches Squeekboard.

Squeekboard's Rust stylesheet loader reads the embedded resource
/sm/puri/squeekboard/style.css. GLib G_RESOURCE_OVERLAYS may override exactly
this path per *process* without replacing the executable or editing global GTK.

Run --stage once, then --probe. Both leave the running OSK untouched.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path.home() / ".cache/a-clockwork-plex/squeekboard-c2-gresource-v1"
RESOURCE_PREFIX = "/sm/puri/squeekboard"
RESOURCE = RESOURCE_PREFIX + "/style.css"
COMMON_IMPORT = '@import url("resource:///sm/puri/squeekboard/common.css");\n'
THEME = "midnight_blue"


class OverlayError(Exception):
    pass


def stage_validator():
    path = Path(__file__).resolve().with_name("validate-squeekboard-uk-theme-stage.py")
    spec = importlib.util.spec_from_file_location("acp_c2_stage_validator", path)
    if not spec or not spec.loader:
        raise OverlayError("UK/theme stage validator is absent")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def samples() -> dict[str, str]:
    validator = stage_validator()
    validator.validate()  # Pins actual vendor package, GB YAML, and all 23 ACP palettes.
    return {name: COMMON_IMPORT + css for name, css in validator.generator().styles().items()}


def destination(name: str) -> Path:
    if name not in stage_validator().generator().styles():
        raise OverlayError("Unknown ACP palette")
    return ROOT / "palettes" / name / "style.css"


def verify_stage(expected: dict[str, str]) -> None:
    if not ROOT.is_dir() or ROOT.is_symlink() or ROOT.stat().st_uid != os.getuid():
        raise OverlayError("Private GLib resource stage missing or not owned by user")
    actual = set()
    for base, directories, files in os.walk(ROOT, followlinks=False):
        for name in directories:
            if (Path(base) / name).is_symlink():
                raise OverlayError("Symlink in resource overlay stage")
        for name in files:
            path = Path(base) / name
            if path.is_symlink():
                raise OverlayError("Symlink in resource overlay stage")
            actual.add(path.relative_to(ROOT).as_posix())
    required = {"README.txt"}
    required |= {"palettes/" + name + "/style.css" for name in expected}
    if actual != required:
        raise OverlayError("Resource overlay stage has missing or unexpected files")
    for name, content in expected.items():
        if destination(name).read_text(encoding="utf-8") != content:
            raise OverlayError("Resource style changed after staging: " + name)
    if "test-only" not in (ROOT / "README.txt").read_text(encoding="utf-8"):
        raise OverlayError("Test-only stage manifest missing")


def stage(expected: dict[str, str]) -> None:
    if ROOT.exists() or ROOT.is_symlink():
        raise OverlayError("Refusing to overwrite existing stage " + str(ROOT))
    ROOT.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = Path(tempfile.mkdtemp(prefix=".c2-gresource-", dir=ROOT.parent))
    try:
        temporary.chmod(0o700)
        for name, css in expected.items():
            path = temporary / "palettes" / name / "style.css"
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.write_text(css, encoding="utf-8")
        (temporary / "README.txt").write_text(
            "ACP C2 test-only GLib resource stylesheet overrides; not installed.\n"
            "Preserves Squeekboard's embedded common.css via resource import.\n"
            "No processes, services or GTK application settings altered.\n",
            encoding="utf-8",
        )
        temporary.rename(ROOT)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def trial_override(name: str) -> str:
    """Only a private, validated resource root is permitted."""
    css = destination(name)
    if not css.is_file() or css.is_symlink():
        raise OverlayError("Missing private GLib overlay file")
    return RESOURCE_PREFIX + "=" + str(css.parent)


def child_lookup(css: Path) -> int:
    try:
        import gi
        gi.require_version("Gio", "2.0")
        from gi.repository import Gio
        actual = Gio.resources_lookup_data(
            RESOURCE, Gio.ResourceLookupFlags.NONE
        ).get_data()
        info = Gio.resources_get_info(RESOURCE, Gio.ResourceLookupFlags.NONE)
    except (ImportError, ValueError, RuntimeError, Exception) as exc:
        print("GLib resource probe failed:", type(exc).__name__, str(exc)[:180])
        return 2
    expected = css.read_bytes()
    print("Resource lookup:", RESOURCE)
    print("Exact candidate CSS bytes:", "PASS" if actual == expected else "FAIL")
    print("Resource-info lookup:", "PASS" if info else "FAIL")
    print("Import of vendor common.css preserved:", "YES" if expected.startswith(COMMON_IMPORT.encode()) else "NO")
    print("Original Squeekboard not executed; GTK and OSK unchanged.")
    return 0 if actual == expected and info else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--plan", action="store_true")
    actions.add_argument("--stage", action="store_true")
    actions.add_argument("--probe", action="store_true")
    actions.add_argument("--_child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if os.geteuid() == 0:
        print("Never use sudo/root for this test.", file=sys.stderr)
        return 2
    try:
        if args._child:
            return child_lookup(destination(THEME))
        expected = samples()
        if args.stage:
            stage(expected)
            verify_stage(expected)
            print("Staged privately:", ROOT)
        elif args.plan:
            print("Private destination:", ROOT)
            print("Exact ACP palettes:", len(expected))
            if ROOT.exists():
                verify_stage(expected)
                print("Existing resource stage: VERIFIED")
            else:
                print("Stage absent; --stage can safely create it.")
        else:
            verify_stage(expected)
            env = os.environ.copy()
            env["G_RESOURCE_OVERLAYS"] = trial_override(THEME)
            print("=== ISOLATED GLIB RESOURCE LOOKUP ===")
            print("Candidate-only override:", env["G_RESOURCE_OVERLAYS"])
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--_child"],
                env=env, capture_output=True, text=True, timeout=15, check=False,
            )
            print(result.stdout, end="")
            if result.stderr:
                print("GLib diagnostic:", result.stderr.strip()[:1000])
            return result.returncode
        print("No Squeekboard, GTK configuration, package or services changed.")
        return 0
    except (OverlayError, OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print("ACP GLib resource overlay: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
