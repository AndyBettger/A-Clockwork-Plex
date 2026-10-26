#!/usr/bin/env python3
"""Focus existing ACP Chromium or native Plexamp Wayland windows (Phase B1).

Non-destructive first slice: never starts, kills, minimizes, resizes, or
unfullscreens applications and never changes compositor/autostart settings.
The compositor can refuse to show a window behind an existing fullscreen
client; verify physically before adding any minimize/unfullscreen choreography.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

APP_ID = "Plexamp"
APP_TITLE = "Plexamp"
BROWSER_ID = "chromium"
BROWSER_SUFFIX = " - A Clockwork Plex - Chromium"
# ACP Chromium uses titles such as "Home - A Clockwork Plex - Chromium".
# Never use a generic Chromium app_id for actual focus.
BROWSER_PAGES = frozenset({
    "Home", "Clock", "Weather", "Astronomy", "News", "BBC News", "AirPlay",
    "Airplay", "AirPlay Ready", "Settings", "Plexamp",
    "A Clockwork Plex",
})


class WindowError(Exception):
    pass


def runtime_env() -> dict[str, str]:
    if os.geteuid() == 0:
        raise WindowError("Run as the desktop user (never sudo)")
    env = os.environ.copy()
    runtime = Path(f"/run/user/{os.getuid()}")
    if not runtime.is_dir():
        raise WindowError("No current user desktop runtime directory")
    existing = env.get("XDG_RUNTIME_DIR", "")
    if existing and Path(existing) != runtime:
        raise WindowError("SSH XDG_RUNTIME_DIR differs from desktop session")
    env["XDG_RUNTIME_DIR"] = str(runtime)
    existing_wayland = env.get("WAYLAND_DISPLAY", "")
    if existing_wayland:
        candidate = Path(existing_wayland) if existing_wayland.startswith("/") else runtime / existing_wayland
        if not candidate.is_socket():
            raise WindowError("Configured WAYLAND_DISPLAY is not a live socket")
    else:
        candidate = runtime / "wayland-0"
        if not candidate.is_socket():
            raise WindowError("Expected labwc wayland-0 socket is unavailable")
        env["WAYLAND_DISPLAY"] = "wayland-0"
    if (runtime / "bus").is_socket():
        env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={runtime}/bus"
    return env


def call_wlrctl(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["wlrctl", "toplevel", *args], capture_output=True, text=True,
            env=env, timeout=8, check=False,
        )
    except FileNotFoundError as exc:
        raise WindowError("wlrctl is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise WindowError("wlrctl toplevel command timed out") from exc


def windows(env: dict[str, str]) -> tuple[str | None, str | None]:
    result = call_wlrctl(env, "list")
    if result.returncode != 0:
        raise WindowError(f"Cannot list labwc toplevel windows: {result.stderr.strip()}")
    candidates: list[str] = []
    native_count = 0
    for raw in result.stdout.splitlines():
        app_id, separator, title = raw.partition(": ")
        if not separator:
            continue
        if app_id == APP_ID and title == APP_TITLE:
            native_count += 1
        if app_id == BROWSER_ID and title.endswith(BROWSER_SUFFIX):
            # The title is untrusted window metadata; constrain the ACP pages
            # and use both exact match attributes for compositor focus.
            page = title.removesuffix(BROWSER_SUFFIX)
            if page in BROWSER_PAGES:
                candidates.append(title)
    if native_count > 1:
        raise WindowError("Multiple identical Plexamp windows; refusing ambiguous focus")
    if len(candidates) > 1:
        raise WindowError("Multiple ACP Chromium windows; refusing ambiguous focus")
    return (candidates[0] if candidates else None,
            APP_TITLE if native_count == 1 else None)


def matches(env: dict[str, str], app_id: str, title: str,
            state: str | None = None) -> bool:
    args = ["find", f"app_id:{app_id}", f"title:{title}"]
    if state:
        args.append(f"state:{state}")
    return call_wlrctl(env, *args).returncode == 0


def describe(env: dict[str, str]) -> tuple[str | None, str | None]:
    acp, plexamp = windows(env)
    print("ACP Chromium:", acp or "NOT FOUND")
    print("Native Plexamp:", plexamp or "NOT FOUND")
    if acp:
        print("ACP focused:", matches(env, BROWSER_ID, acp, "active"))
    if plexamp:
        print("Plexamp focused:", matches(env, APP_ID, plexamp, "active"))
        print("Plexamp fullscreen:", matches(env, APP_ID, plexamp, "fullscreen"))
    return acp, plexamp


def focus(env: dict[str, str], destination: str) -> None:
    acp, plexamp = windows(env)
    title = acp if destination == "acp" else plexamp
    app_id = BROWSER_ID if destination == "acp" else APP_ID
    if title is None:
        raise WindowError(f"{destination} window not available; not starting or closing anything")
    if not matches(env, app_id, title):
        raise WindowError("Target window vanished after listing; refusing to focus")
    result = call_wlrctl(env, "focus", f"app_id:{app_id}", f"title:{title}")
    if result.returncode != 0:
        raise WindowError(f"Compositor rejected focus request: {result.stderr.strip()}")
    print(f"Focus REQUESTED: {destination} ({app_id}: {title})")
    # Activation is asynchronous. Don't turn a successful compositor request
    # into a false failure merely because the activation event arrives later.
    for _ in range(5):
        if matches(env, app_id, title, "active"):
            print("Compositor reports target focused: YES")
            return
        time.sleep(0.2)
    print("Compositor reports target focused: NOT CONFIRMED")
    print("Please check the actual screen; fullscreen window stacking may need a separate step.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true", help="Read-only window identity and focus inspection")
    mode.add_argument("--to-acp", action="store_true", help="Focus existing ACP Chromium window")
    mode.add_argument("--to-plexamp", action="store_true", help="Focus existing native Plexamp window")
    args = parser.parse_args()
    try:
        env = runtime_env()
        if args.plan:
            describe(env)
        else:
            focus(env, "acp" if args.to_acp else "plexamp")
        return 0
    except WindowError as exc:
        print("ACP native window handoff: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
