"""Read-only Python parity model for ACP's browser night schedule.

This module is NOT a scheduler, OSK service or palette writer. It deliberately
models only the part of ACPDisplayDimming that can be derived reliably from
stored settings and UK wall clock, plus explicitly supplied (never guessed)
alarm/preview state. Browser-local interaction lifetime, preview ownership,
native Plexamp visibility and alarm status remain separate unresolved inputs.

Authority: app/static/js/display-dimming.js scheduledNow() and dimRequired().
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any
from zoneinfo import ZoneInfo


UK = ZoneInfo("Europe/London")
CLOCK_RE = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d\Z")


@dataclass(frozen=True)
class NightSchedulePlan:
    scheduled: bool
    active: bool
    preview: bool
    alarm_visible: bool
    local_clock: str
    reason: str


def _minute(value: Any) -> int:
    if not isinstance(value, str) or not CLOCK_RE.fullmatch(value):
        raise ValueError("Expected a validated 24-hour HH:MM local clock")
    return int(value[:2]) * 60 + int(value[3:])


def schedule_plan(
    settings: dict[str, Any],
    at: datetime,
    *,
    alarm_visible: bool,
    preview_active: bool = False,
) -> NightSchedulePlan:
    """Pure, side-effect-free mirror of scheduledNow()/dimRequired().

    ACP's browser uses *local wall clock minutes* for the night schedule.
    Convert the injected aware instant to UK time (incl. BST/GMT and DST fold),
    rather than measuring elapsed hours since schedule start. An alarm/preview
    is only reflected when an external authorised caller *explicitly* provides
    its state; the server must not infer these browser-local conditions.
    """
    if not isinstance(settings, dict):
        raise ValueError("Expected validated display settings")
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("An explicit timezone-aware instant is required")
    if type(alarm_visible) is not bool or type(preview_active) is not bool:
        raise ValueError("Explicit alarm and preview flags must be boolean")
    enabled = settings.get("night_dim_enabled")
    if type(enabled) is not bool:
        raise ValueError("Missing validated night_dim_enabled boolean")
    start = _minute(settings.get("night_dim_start"))
    end = _minute(settings.get("night_dim_end"))
    local = at.astimezone(UK)
    current = local.hour * 60 + local.minute
    if not enabled:
        scheduled = False
    elif start == end:
        scheduled = True
    elif start < end:
        scheduled = start <= current < end
    else:
        scheduled = current >= start or current < end
    active = (scheduled or preview_active) and not alarm_visible
    reason = (
        "alarm suppresses night" if alarm_visible and (scheduled or preview_active)
        else "preview supplied by browser" if preview_active
        else "inside scheduled local wall-clock interval" if scheduled
        else "daytime / disabled schedule"
    )
    return NightSchedulePlan(
        scheduled=scheduled,
        active=active,
        preview=preview_active,
        alarm_visible=alarm_visible,
        local_clock=local.strftime("%Y-%m-%d %H:%M %Z"),
        reason=reason,
    )
