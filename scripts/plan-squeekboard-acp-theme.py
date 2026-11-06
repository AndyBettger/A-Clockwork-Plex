#!/usr/bin/env python3
"""Read-only ACP -> native Squeekboard palette contract (Stage C2).

Design authority: app/static/js/display-dimming.js ACPDisplayDimming.status()
  - active: actual night dimming (includes scheduled/preview and alarm exceptions)
  - interacting: night interaction or awake timeout
  - effectiveStyle: 'classic' or 'astronomy' after activeStyle 'same' resolution

This resolver NEVER predicts night mode from wall time or swaps a running OSK.
It selects one of the 23 previously staged ACP palettes. The future theme
bridge must sample actual runtime status and reapply CSS IN PLACE when night
starts/ends even if Squeekboard is focused (also handle idle/active night
interaction changes). Never restart a focused keyboard or alter system GTK.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys
from typing import Any

FALLBACK_THEME = "classic_dark"
DAYTIME_THEMES = (
    "classic_dark",
    "midnight_blue",
    "amber_terminal",
    "green_phosphor",
    "aubergine",
    "steel_cyan",
    "crimson_glow",
)
NIGHT_STYLES = ("classic", "astronomy")


@dataclass(frozen=True)
class PaletteDecision:
    palette: str
    daytime_theme: str
    night_active: bool
    interacting: bool
    effective_style: str
    reason: str


def select_palette(daytime_theme: Any, night_status: dict[str, Any] | None = None) -> PaletteDecision:
    """Resolve the live browser's known, explicit state without side effects.

    Invalid or missing display theme deliberately falls back to Classic Dark.
    Never interpret just 'scheduled' as visual night mode; display-dimming.js
    suppresses dimRequired() on an alarm and allows bounded previews.
    """
    daytime = daytime_theme if daytime_theme in DAYTIME_THEMES else FALLBACK_THEME
    data = night_status if isinstance(night_status, dict) else {}
    active = data.get("active") is True
    interacting = active and data.get("interacting") is True
    if not active:
        return PaletteDecision(daytime, daytime, False, False, "daytime", "no active night dimming")
    style = data.get("effectiveStyle")
    if style not in NIGHT_STYLES:
        # Fail closed to classic dim: never infer astronomy-red from a stale
        # preference when live effective style is absent or ambiguous.
        style = "classic"
    suffix = "active" if interacting else "idle"
    palette = (
        f"astronomy_night_{suffix}" if style == "astronomy"
        else f"{daytime}_night_classic_{suffix}"
    )
    return PaletteDecision(palette, daytime, True, interacting, style, "live night appearance")


def stylesheet_inventory() -> tuple[str, ...]:
    """Use the existing verified ACP CSS generator; don't duplicate styles."""
    path = Path(__file__).resolve().with_name("stage-squeekboard-uk-theme.py")
    spec = importlib.util.spec_from_file_location("acp_c2_known_palettes", path)
    if not spec or not spec.loader:
        raise RuntimeError("ACP staged palette definition unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return tuple(sorted(module.styles()))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true", help="Print a read-only palette selection")
    parser.add_argument("--daytime", default=FALLBACK_THEME,
                        help="ACP display.daytime_theme, default Classic Dark")
    parser.add_argument("--night-active", action="store_true",
                        help="ACPDisplayDimming.status().active (not just scheduled)")
    parser.add_argument("--interacting", action="store_true",
                        help="ACPDisplayDimming.status().interacting")
    parser.add_argument("--effective-style", default="classic",
                        choices=NIGHT_STYLES,
                        help="ACPDisplayDimming.status().effectiveStyle")
    args = parser.parse_args()
    if not args.plan:
        parser.print_help()
        return 2
    try:
        decision = select_palette(args.daytime, {
            "active": args.night_active,
            "interacting": args.interacting,
            "effectiveStyle": args.effective_style,
        })
        known = stylesheet_inventory()
        if len(known) != 23 or decision.palette not in known:
            raise RuntimeError("Palette absent from 23 accepted staged styles")
        print("=== ACP NATIVE SQUEEKBOARD THEME PLAN (READ ONLY) ===")
        print("Requested daytime:", args.daytime)
        print("Resolved daytime:", decision.daytime_theme)
        print("Night active:", decision.night_active)
        print("Interacting:", decision.interacting)
        print("Effective appearance:", decision.effective_style)
        print("Selected palette:", decision.palette)
        print("Reason:", decision.reason)
        print("Default/fallback palette:", FALLBACK_THEME)
        print("Palette inventory:", len(known), "staged variants")
        print("PLAN PASS; no Squeekboard process, focus, config, CSS or service changed.")
        print("Live theme synchronisation remains UNIMPLEMENTED and must not interrupt typing.")
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print("ACP native Squeekboard theme contract: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
