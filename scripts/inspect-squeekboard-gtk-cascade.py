#!/usr/bin/env python3
"""Read-only GTK3 CSS cascade probe for ACP's isolated Squeekboard trial.

This is *not* Squeekboard. It connects a short-lived, invisible GTK client to
labwc and tests GtkStyleContexts with sq_view/sq_button CSS node names. The
staged palette is passed as XDG_CONFIG_HOME to a fresh subprocess before GTK
initialisation; no keyboard, settings, service, or global GTK file is changed.

Run as the normal commissioned Pi user:
    python3 scripts/inspect-squeekboard-gtk-cascade.py --probe
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

STAGE = Path.home() / ".cache/a-clockwork-plex/squeekboard-c2-uk-theme-v1/themes"
PALETTE = "midnight_blue"
EXPECTED_PATTERN = re.compile(r"sq_view\s+sq_button\s*\{[^}]*\bcolor:\s*(#[a-fA-F0-9]{6})\s*;", re.DOTALL)


def palette_path() -> Path:
    root = STAGE / PALETTE
    css = root / "gtk-3.0/gtk.css"
    if root.is_symlink() or css.is_symlink() or not root.is_dir() or not css.is_file():
        raise RuntimeError("Private Midnight Blue GTK CSS stage is missing or unsafe")
    return css


def expected_colour(css: Path) -> str:
    match = EXPECTED_PATTERN.search(css.read_text(encoding="utf-8"))
    if not match:
        raise RuntimeError("Expected sq_view sq_button text-colour rule is absent")
    return match.group(1).lower()


def child_environment() -> dict[str, str]:
    env = os.environ.copy()
    env["XDG_CONFIG_HOME"] = str(STAGE / PALETTE)
    env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
    env["WAYLAND_DISPLAY"] = "wayland-0"
    env["GDK_BACKEND"] = "wayland"
    return env


def format_colour(rgba) -> str:
    return "#" + "".join(f"{round(max(0, min(1, value)) * 255):02x}"
                         for value in (rgba.red, rgba.green, rgba.blue))


def child(css: Path, expected: str) -> int:
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gdk, Gtk
    except (ImportError, ValueError, RuntimeError) as exc:
        print("GTK3 Python bindings unavailable:", exc)
        return 2

    init = Gtk.init_check([])
    success = init[0] if isinstance(init, tuple) else init
    if not success:
        print("Cannot initialise GTK3 on the current Wayland session (no keyboard affected).")
        return 2
    screen = Gdk.Screen.get_default()
    if screen is None:
        print("No default GTK3 screen for this SSH/Wayland session.")
        return 2

    # Match Squeekboard's GtkWidgetPath node names without running a keyboard
    # or registering system-wide widget types. GTK3 >=3.20 supports these names.
    def context():
        path = Gtk.WidgetPath.new()
        path.append_type(Gtk.Widget.__gtype__)
        path.iter_set_object_name(0, "sq_view")
        path.append_type(Gtk.Widget.__gtype__)
        path.iter_set_object_name(1, "sq_button")
        ctx = Gtk.StyleContext.new()
        ctx.set_screen(screen)
        ctx.set_path(path)
        return ctx

    def colour(ctx):
        return format_colour(ctx.get_color(Gtk.StateFlags.NORMAL))

    theme = Gtk.Settings.get_default().get_property("gtk-theme-name")
    print("GTK theme:", theme)
    print("GTK XDG_CONFIG_HOME:", os.environ.get("XDG_CONFIG_HOME"))
    print("Expected ACP key-text colour:", expected)
    print("Emulated CSS path: sq_view sq_button (not a running keyboard)")

    automatic = colour(context())
    print("Automatic XDG user CSS:", automatic,
          "MATCH" if automatic == expected else "NO MATCH")

    provider = Gtk.CssProvider.new()
    provider.load_from_path(str(css))
    screen_ctx = context()
    Gtk.StyleContext.add_provider_for_screen(
        screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
    via_screen = colour(screen_ctx)
    print("Explicit USER screen CSS:", via_screen,
          "MATCH" if via_screen == expected else "NO MATCH")

    direct_ctx = context()
    direct_ctx.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
    via_context = colour(direct_ctx)
    print("Explicit USER context CSS:", via_context,
          "MATCH" if via_context == expected else "NO MATCH")

    print("No GUI window created; no keyboard/service/configuration changed.")
    print("This process tests GTK's cascade only, NOT Squeekboard's live renderer.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--probe", action="store_true", help="Run invisible, short-lived GTK3 cascade test")
    group.add_argument("--_child", action="store_true", help=argparse.SUPPRESS)
    args = p.parse_args()
    if os.geteuid() == 0:
        print("Never run as root or via sudo.", file=sys.stderr)
        return 2
    try:
        css = palette_path()
        expected = expected_colour(css)
        if args._child:
            return child(css, expected)
        print("=== ACP ISOLATED GTK3 CASCADE PROBE ===")
        print("Staged stylesheet:", css)
        print("Read-only probe: no process/service/keyboard alteration")
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--_child"],
            env=child_environment(), timeout=20, check=False, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        print(result.stdout, end="")
        if result.stderr:
            print("GTK diagnostics:", result.stderr.strip()[:1200])
        return result.returncode
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print("GTK CSS cascade check stopped safely:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
