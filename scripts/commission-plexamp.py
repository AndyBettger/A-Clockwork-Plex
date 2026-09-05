#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.plexamp_commissioning import (  # noqa: E402
    PlexampCommissioningError,
    PlexampCommissioningManager,
)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Capture/verify the narrow A Clockwork Plex Plexamp commissioning baseline."
    )
    parser.add_argument("action", choices=("plan", "commission"))
    parser.add_argument("--home", type=Path, default=Path.home())
    args = parser.parse_args(argv[1:])

    manager = PlexampCommissioningManager(home=args.home)
    try:
        result = manager.plan() if args.action == "plan" else manager.commission()
    except PlexampCommissioningError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc),
                    "rolled_back": exc.rolled_back,
                    "rollback_failures": exc.rollback_failures,
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
