#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


DEFAULT_DASHBOARD_BASE = "http://localhost:8088"
START_NAME = "a-clockwork-plex-airplay-start"
END_NAME = "a-clockwork-plex-airplay-end"
INVALID_BASE_RE = re.compile(r"[\s\"'`\\\\]")


def validate_dashboard_base(value: str) -> str:
    base = str(value or "").strip()
    if not base:
        raise ValueError("Dashboard base URL cannot be blank.")
    if INVALID_BASE_RE.search(base):
        raise ValueError(
            "Dashboard base URL must not contain spaces, quotes, backticks or backslashes."
        )
    if not (base.startswith("http://") or base.startswith("https://")):
        raise ValueError("Dashboard base URL must begin with http:// or https://.")
    return base


def render_start_wrapper(dashboard_base: str = DEFAULT_DASHBOARD_BASE) -> str:
    base = validate_dashboard_base(dashboard_base)
    return f'''#!/bin/bash
set -euo pipefail

DASHBOARD_BASE="{base}"

/usr/bin/logger -t shairport-plexamp "AirPlay starting - publishing playing intent to PlaybackCoordinator"
/usr/bin/curl -fsS "$DASHBOARD_BASE/api/airplay/start" >/dev/null || true

/usr/bin/logger -t shairport-plexamp "PlaybackCoordinator owns Plexamp pause; shared ALSA services remain running"
'''


def render_end_wrapper(dashboard_base: str = DEFAULT_DASHBOARD_BASE) -> str:
    base = validate_dashboard_base(dashboard_base)
    return f'''#!/bin/bash
set -euo pipefail

DASHBOARD_BASE="{base}"

remote_available_status() {{
    if command -v /usr/bin/busctl >/dev/null 2>&1; then
        /usr/bin/busctl --system get-property \\
            org.gnome.ShairportSync \\
            /org/gnome/ShairportSync \\
            org.gnome.ShairportSync.RemoteControl \\
            Available 2>/dev/null || printf 'unknown'
    else
        printf 'unknown'
    fi
}}

remote_player_state() {{
    if command -v /usr/bin/busctl >/dev/null 2>&1; then
        /usr/bin/busctl --system get-property \\
            org.gnome.ShairportSync \\
            /org/gnome/ShairportSync \\
            org.gnome.ShairportSync.RemoteControl \\
            PlayerState 2>/dev/null || printf 'unknown'
    else
        printf 'unknown'
    fi
}}

post_pause_event() {{
    /usr/bin/curl -fsS -X POST \\
        -H 'Content-Type: application/json' \\
        --data '{{"source":"airplay","event":"paused","details":{{"origin":"shairport-end-wrapper"}}}}' \\
        "$DASHBOARD_BASE/api/playback/events" >/dev/null
}}

PLAYER_STATE="$(remote_player_state)"
REMOTE_AVAILABLE="$(remote_available_status)"

# A stale END may arrive just after START on resume. The newer START route has
# already journalled airplay.playing, so this older END must not overwrite it.
if [ "$PLAYER_STATE" = 's "Playing"' ]; then
    /usr/bin/logger -t shairport-plexamp "AirPlay END observed after playback resumed - retaining the newer playing session"
    exit 0
fi

if [ "$REMOTE_AVAILABLE" = "b false" ]; then
    /usr/bin/logger -t shairport-plexamp "AirPlay sender disconnected during active-state exit - ending the dashboard session"
    /usr/bin/curl -fsS "$DASHBOARD_BASE/api/airplay/end" >/dev/null || true
    exit 0
fi

if post_pause_event; then
    /usr/bin/logger -t shairport-plexamp "AirPlay paused with sender available - PlaybackCoordinator owns the configured hold"
else
    /usr/bin/logger -t shairport-plexamp "AirPlay pause event could not reach PlaybackCoordinator; the current screen was left untouched"
fi
'''


def write_wrappers(output_dir: Path, dashboard_base: str = DEFAULT_DASHBOARD_BASE) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    start = output_dir / START_NAME
    end = output_dir / END_NAME
    start.write_text(render_start_wrapper(dashboard_base), encoding="utf-8")
    end.write_text(render_end_wrapper(dashboard_base), encoding="utf-8")
    return start, end


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render the A Clockwork Plex Shairport lifecycle callback wrappers."
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--dashboard-base", default=DEFAULT_DASHBOARD_BASE)
    arguments = parser.parse_args()

    try:
        write_wrappers(arguments.output_dir, arguments.dashboard_base)
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
