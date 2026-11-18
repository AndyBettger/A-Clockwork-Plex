#!/usr/bin/env python3
"""Test a GTK3 key-style context reloading private GLib CSS IN PLACE.

The already-Pi-verified GResource probe showed a process can see new bytes,
but did not inspect GTK's computed styles. This separate disposable test
keeps one Gtk.StyleContext and one Gtk.CssProvider alive, atomically switches
a throwaway CSS resource, reloads *that same provider*, then reads the
existing context's computed text colour again.

No window, keyboard, global GTK setting, service or accepted ACP palette
is touched. --without-invalidate tests automatic provider-driven recalculation
without Gtk.StyleContext.invalidate (deprecated). This is NOT a real
Squeekboard paint/focus test.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile

EXPECTED_BEFORE = "#123456"
EXPECTED_AFTER = "#abcdef"


def resource_probe():
    source = Path(__file__).resolve().with_name("probe-squeekboard-live-css-lookup.py")
    spec = importlib.util.spec_from_file_location("acp_c3_disposable_css", source)
    if not spec or not spec.loader:
        raise RuntimeError("Original disposable GLib resource probe unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def colour(rgba) -> str:
    return "#" + "".join(
        f"{round(max(0.0, min(1.0, n)) * 255):02x}"
        for n in (rgba.red, rgba.green, rgba.blue)
    )


def child(css: Path, *, manual_invalidate: bool = True) -> int:
    original = resource_probe()
    if (
        css.name != "style.css"
        or css.is_symlink()
        or not css.is_file()
        or os.environ.get("G_RESOURCE_OVERLAYS")
        != original.PREFIX + "=" + str(css.parent)
    ):
        print("Refusing GTK child: isolated GLib CSS overlay not established")
        return 2
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk, Gtk
        initialized = Gtk.init_check([])
        ok = initialized[0] if isinstance(initialized, tuple) else initialized
        if not ok:
            print("GTK3 cannot initialise on labwc Wayland; original OSK unaffected")
            return 2
        screen = Gdk.Screen.get_default()
        if screen is None:
            print("No GTK screen in test Wayland session")
            return 2

        # Same sq_view -> sq_button CSS node names accepted by the earlier
        # GTK cascade test. Keep *one* style context alive throughout.
        path = Gtk.WidgetPath.new()
        path.append_type(Gtk.Widget.__gtype__)
        path.iter_set_object_name(0, "sq_view")
        path.append_type(Gtk.Widget.__gtype__)
        path.iter_set_object_name(1, "sq_button")
        context = Gtk.StyleContext.new()
        context.set_screen(screen)
        context.set_path(path)

        provider = Gtk.CssProvider.new()
        provider.load_from_resource(original.RESOURCE)
        context.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        before = colour(context.get_color(Gtk.StateFlags.NORMAL))
        original.atomic_replace(css, original.B)

        # Reuse the *same provider and same context*, rather than creating
        # a new one, to check GTK's colour cascade invalidation on reload.
        provider.load_from_resource(original.RESOURCE)
        if manual_invalidate:
            # Legacy comparison only. Modern GTK3 providers should invalidate
            # dependent styles automatically when their rules are reloaded.
            context.invalidate()
        after = colour(context.get_color(Gtk.StateFlags.NORMAL))
    except Exception as exc:
        print("GTK3 in-place CSS check blocked:", type(exc).__name__, str(exc)[:300])
        return 2

    print("Emulated style path: sq_view sq_button")
    print("Same context and same provider before/after: YES")
    print("Explicit deprecated context.invalidate() used:", "YES" if manual_invalidate else "NO")
    print("Computed initial key text colour:", before,
          "PASS" if before == EXPECTED_BEFORE else "FAIL")
    print("Computed reloaded key text colour:", after,
          "PASS" if after == EXPECTED_AFTER else "FAIL")
    print("No GTK window, Squeekboard process, global theme or ACP settings touched.")
    print("Synthetic GTK computation only; running keyboard repaint still unverified.")
    if before == EXPECTED_BEFORE and after == EXPECTED_AFTER:
        print("IN-PLACE GTK STYLE CONTEXT RELOAD: PASS")
        return 0
    print("IN-PLACE GTK STYLE CONTEXT RELOAD: NOT CONFIRMED")
    return 1


def isolated_environment(directory: Path) -> dict[str, str]:
    original = resource_probe()
    env = os.environ.copy()
    env["G_RESOURCE_OVERLAYS"] = original.PREFIX + "=" + str(directory)
    env["GDK_BACKEND"] = "wayland"
    env["WAYLAND_DISPLAY"] = "wayland-0"
    env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
    return env


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--probe", action="store_true", help="Run disposable GTK3 style-context test")
    actions.add_argument("--_child", type=Path, metavar="CSS", help=argparse.SUPPRESS)
    # This switches behaviour within EITHER operation, not a new operation.
    # Do not put it in the mutually exclusive --probe/--_child group.
    parser.add_argument("--without-invalidate", action="store_true",
                        help="Test whether reloading provider alone refreshes an existing style context")
    args = parser.parse_args()
    if os.geteuid() == 0:
        print("Never run via sudo or as root.", file=sys.stderr)
        return 2
    if args._child is not None:
        return child(args._child, manual_invalidate=not args.without_invalidate)
    try:
        source = resource_probe()
        parent = Path.home() / ".cache/a-clockwork-plex"
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(prefix="c3-gtk-style-context-", dir=parent) as root:
            directory = Path(root)
            directory.chmod(0o700)
            css = directory / "style.css"
            css.write_bytes(source.A)
            print("=== ACP DISPOSABLE GTK3 IN-PLACE STYLE CHECK ===")
            if args.without_invalidate:
                print("Automatic provider-driven style update (no deprecated invalidate)")
            print("Private, automatically cleaned CSS:", css)
            response = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--_child", str(css)]
                + (["--without-invalidate"] if args.without_invalidate else []),
                env=isolated_environment(directory), capture_output=True,
                text=True, timeout=20, check=False,
            )
            print(response.stdout, end="")
            if response.stderr:
                print("GTK/GLib diagnostics:", response.stderr.strip()[:900])
            return response.returncode
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print("GTK3 style-context probe safely stopped:", str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
