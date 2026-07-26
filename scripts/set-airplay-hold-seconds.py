#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

MIN_SECONDS = 15
MAX_SECONDS = 86400
DEFAULT_SECONDS = 600
ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.json"


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read {CONFIG_PATH}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{CONFIG_PATH} must contain a JSON object.")
    return value


def current_seconds(config: dict[str, Any]) -> int:
    airplay = config.get("airplay") if isinstance(config.get("airplay"), dict) else {}
    try:
        value = int(airplay.get("pause_hold_seconds", DEFAULT_SECONDS))
    except (TypeError, ValueError):
        value = DEFAULT_SECONDS
    return max(MIN_SECONDS, min(MAX_SECONDS, value))


def save_config(config: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = CONFIG_PATH.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(CONFIG_PATH)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Show or set the AirPlay paused-session hold duration."
    )
    value.add_argument(
        "seconds",
        nargs="?",
        type=int,
        help=f"Hold duration in seconds ({MIN_SECONDS}-{MAX_SECONDS}).",
    )
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        config = load_config()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    before = current_seconds(config)
    if args.seconds is None:
        print(before)
        return 0

    if not MIN_SECONDS <= args.seconds <= MAX_SECONDS:
        print(
            f"Hold duration must be between {MIN_SECONDS} and {MAX_SECONDS} seconds.",
            file=sys.stderr,
        )
        return 2

    airplay = config.setdefault("airplay", {})
    if not isinstance(airplay, dict):
        airplay = {}
        config["airplay"] = airplay
    airplay["pause_hold_seconds"] = args.seconds

    try:
        save_config(config)
    except OSError as exc:
        print(f"Could not save {CONFIG_PATH}: {exc}", file=sys.stderr)
        return 1

    print(f"AirPlay pause hold changed from {before} to {args.seconds} seconds.")
    print("Restart a-clockwork-plex.service before starting the next AirPlay session.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
