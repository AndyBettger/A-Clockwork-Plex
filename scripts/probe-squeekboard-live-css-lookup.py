#!/usr/bin/env python3
"""Safely probe same-process GResource CSS reload behaviour in an isolated child.

The previously accepted trial applies Squeekboard colours via a private
G_RESOURCE_OVERLAYS path. This experiment checks whether *new* GLib lookups
and GTK CssProviders notice an atomic change to one expendable resource file.

It NEVER runs/stops/contacts Squeekboard. It neither mutates the accepted
23 palettes nor touches system GTK. Only a throwaway cache folder is written.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

RESOURCE = "/sm/puri/squeekboard/style.css"
PREFIX = "/sm/puri/squeekboard"
A = b"sq_view sq_button { color: #123456; }\n"
B = b"sq_view sq_button { color: #abcdef; }\n"


def atomic_replace(css: Path, replacement: bytes) -> None:
    if css.name != "style.css" or css.is_symlink() or not css.is_file():
        raise RuntimeError("Unsafe throwaway CSS resource")
    staging = css.with_name(".acp-probe-next.css")
    if staging.exists() or staging.is_symlink():
        raise RuntimeError("Unexpected staged probe file")
    with staging.open("xb") as stream:
        stream.write(replacement)
    os.replace(staging, css)


def lookup_in_child(css: Path) -> int:
    expected = PREFIX + "=" + str(css.parent)
    if os.environ.get("G_RESOURCE_OVERLAYS") != expected:
        print("Refusing child: resource override is not the private test folder")
        return 2
    try:
        import gi
        gi.require_version("Gio", "2.0")
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gio, Gtk
        get_bytes = lambda: bytes(Gio.resources_lookup_data(
            RESOURCE, Gio.ResourceLookupFlags.NONE
        ).get_data())
        before = get_bytes()
        provider_before = Gtk.CssProvider.new()
        provider_before.load_from_resource(RESOURCE)
        atomic_replace(css, B)
        after = get_bytes()
        provider_after = Gtk.CssProvider.new()
        provider_after.load_from_resource(RESOURCE)
    except Exception as exc:
        print("CSS resource probe blocked:", type(exc).__name__, str(exc)[:300])
        return 2
    print("Same process, same mapped resource name:", RESOURCE)
    print("Before atomic replacement:", "PASS" if before == A else "FAIL")
    print("After atomic replacement:", "PASS" if after == B else "NO")
    print("GTK3 providers loaded resource before and after:", "YES")
    print("Keyboard untouched; this is NOT proof of in-place Squeekboard repaint.")
    if before == A and after == B:
        print("GRESOURCE RELOOKUP PASS: new CSS bytes visible to same process")
        return 0
    print("GRESOURCE RELOOKUP NOT SUPPORTED: alternate update mechanism required")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    controls = parser.add_mutually_exclusive_group(required=True)
    controls.add_argument("--probe", action="store_true")
    controls.add_argument("--_child", metavar="CSS", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if os.geteuid() == 0:
        print("Use ordinary user, never sudo/root", file=sys.stderr)
        return 2
    if args._child is not None:
        return lookup_in_child(args._child)
    parent = Path.home() / ".cache/a-clockwork-plex"
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        with tempfile.TemporaryDirectory(prefix="c3-gresource-reload-", dir=parent) as root:
            directory = Path(root)
            directory.chmod(0o700)
            css = directory / "style.css"
            css.write_bytes(A)
            env = os.environ.copy()
            # Intentionally throw away any inherited resource overlay; this
            # change is visible to only our short-lived test child.
            env["G_RESOURCE_OVERLAYS"] = PREFIX + "=" + str(directory)
            print("=== ACP SAME-PROCESS RESOURCE RELOOKUP (DISPOSABLE) ===")
            print("Ephemeral test directory:", directory)
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--_child", str(css)],
                env=env, capture_output=True, text=True, timeout=20, check=False,
            )
            print(result.stdout, end="")
            if result.stderr:
                print("GTK/GLib diagnostics:", result.stderr.strip()[:950])
            return result.returncode
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print("CSS probe stopped safely:", str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
