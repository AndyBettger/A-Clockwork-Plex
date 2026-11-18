#!/usr/bin/env python3
"""Read-only inventory before ACP's UK/themed native Squeekboard trial.

Run as the ordinary desktop user:
    python3 scripts/inspect-squeekboard-theme-layout.py --inspect

Never starts, stops, edits, configures, installs or replaces a keyboard.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
VENDOR = Path("/usr/bin/squeekboard")
ACCEPTED_SHA256 = "2ad3ef3750c26b94427deb7423041293c1ae658027261a38623373af1a243338"
# Squeekboard 1.43.x's layout loader defaults to /usr/share/misc/squeekboard/keyboards.
# Keep the previously probed directories for completeness; layouts can also be embedded.
SYSTEM_LAYOUTS = (Path("/usr/share/misc/squeekboard/keyboards"),
                  Path("/usr/share/squeekboard/keyboards"),
                  Path("/usr/local/share/squeekboard/keyboards"))
USER_LAYOUT = Path.home() / ".local/share/squeekboard/keyboards"
LAYOUT_NAMES = (
    "gb.yaml", "gb_wide.yaml", "us.yaml", "us_wide.yaml",
    "number/gb.yaml", "number/us.yaml",
    "email/gb.yaml", "email/us.yaml",
    "url/gb.yaml", "url/us.yaml",
    "terminal/gb.yaml", "terminal/us.yaml",
)


def probe(*args: str) -> str:
    """Execute only fixed read-only inventory commands."""
    if not shutil.which(args[0]):
        return "(command not installed)"
    try:
        result = subprocess.run(args, check=False, capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "(unavailable: " + type(exc).__name__ + ")"
    if result.returncode != 0:
        return "(not available from this SSH/session environment)"
    return result.stdout.strip() or "(empty)"


def layouts_in(folder: Path) -> str:
    if not folder.is_dir():
        return "(directory absent)"
    present = [name for name in LAYOUT_NAMES if (folder / name).is_file()]
    return ", ".join(present) if present else "(no matching layout filenames)"


def gtk_css_state(path: Path) -> str:
    if not path.exists():
        return "absent"
    if path.is_symlink():
        return "symlink (left untouched)"
    if path.is_file():
        return "present, existing user file (contents not read)"
    return "non-file path (left untouched)"


def acp_palettes() -> str:
    source = REPO / "app/static/css/daytime-themes.css"
    try:
        content = source.read_text(encoding="utf-8")
    except OSError:
        return "(could not read ACP theme tokens)"
    values = sorted(set(re.findall(r'data-daytime-theme="([a-z_]+)"', content)))
    return ", ".join(["classic_dark", *[v for v in values if v != "classic_dark"]])


def inspect() -> None:
    print("=== ACP native keyboard UK/theme preflight: READ ONLY ===")
    print("Vendor Squeekboard package: " +
          probe("dpkg-query", "-W", "-f=$" + "{Version}", "squeekboard"))
    if VENDOR.is_file():
        try:
            with VENDOR.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            print("Vendor binary matches accepted SHA-256: " +
                  ("YES" if digest == ACCEPTED_SHA256 else "NO - recheck before any trial"))
        except OSError:
            print("Vendor binary SHA-256: unreadable")
    else:
        print("Vendor binary: not found")
    print("Squeekboard process: " + probe("pgrep", "-a", "-x", "squeekboard"))
    # The package may compile YAML layouts into the binary even if the on-disk
    # search directory is absent. Check the actual package inventory as well.
    package_files = probe("dpkg-query", "-L", "squeekboard")
    if package_files.startswith("("):
        print("Package layout YAML inventory: " + package_files)
    else:
        yaml_paths = [p for p in package_files.splitlines()
                      if p.endswith(".yaml") and "/keyboards/" in p]
        print("Package layout YAML inventory: " +
              (", ".join(yaml_paths[:20]) if yaml_paths else
               "(none on disk; keyboard layouts may be embedded in the binary)"))
    print("GNOME input source(s): " +
          probe("gsettings", "get", "org.gnome.desktop.input-sources", "sources"))
    print("GNOME XKB options: " +
          probe("gsettings", "get", "org.gnome.desktop.input-sources", "xkb-options"))
    print("GNOME GTK theme: " +
          probe("gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"))
    print("Host XKB setup: " + probe("localectl", "status").replace("\n", "; "))
    for directory in (*SYSTEM_LAYOUTS, USER_LAYOUT):
        print("Layouts " + str(directory) + ": " + layouts_in(directory))
    print("Layout override mechanism: SQUEEKBOARD_KEYBOARDSDIR (candidate process only)")
    print("Default GTK3 user stylesheet: " +
          gtk_css_state(Path.home() / ".config/gtk-3.0/gtk.css"))
    print("ACP daytime theme IDs: " + acp_palettes())
    print("ACP night variants: daytime, classic dim, astronomy red")
    print("=== NO keyboard processes, desktop settings, files or audio changed ===")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true", help="Show read-only inventory")
    if not parser.parse_args().inspect:
        parser.print_help()
        return 2
    inspect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
