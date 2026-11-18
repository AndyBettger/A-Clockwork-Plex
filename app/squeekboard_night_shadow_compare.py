"""Offline, read-only comparison of ACP browser and prospective Python night state.

It neither owns Squeekboard nor collects/sends observations. A future explicit
diagnostic tool may supply these snapshots; no live route or timer is installed.

The browser owns the immediate C3 CSS writer. Schedule state, alarm presentation
and input activity have distinct authorities, and disagreement must NEVER be
silently resolved into a new palette or interpreted as permission to write CSS.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

try:
    from .squeekboard_night_schedule_plan import schedule_plan
    from .squeekboard_night_observation_plan import alarm_observation, linux_input_step
except ImportError:  # Script-loaded module on the current Pi, not a package.
    from squeekboard_night_schedule_plan import schedule_plan
    from squeekboard_night_observation_plan import alarm_observation, linux_input_step


@dataclass(frozen=True)
class ShadowResult:
    verdict: str
    comparisons: dict[str, str]
    disagreements: tuple[str, ...]
    limitations: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "comparisons": dict(self.comparisons),
            "disagreements": list(self.disagreements),
            "limitations": list(self.limitations),
            "authority": "diagnostic-only; browser continues to own C3 CSS",
        }


def _bool(obj: dict[str, Any], key: str) -> bool:
    v = obj.get(key)
    if type(v) is not bool:
        raise ValueError(f"{key} must be explicitly boolean")
    return v


def _minutes(value: Any) -> int:
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        raise ValueError("Expected HH:MM")
    hour, minute = value[:2], value[3:]
    if not (hour.isdigit() and minute.isdigit()
            and 0 <= int(hour) < 24 and 0 <= int(minute) < 60):
        raise ValueError("Invalid HH:MM")
    return int(hour) * 60 + int(minute)


def _near_boundary(moment: datetime, settings: dict[str, Any], seconds: int = 3) -> bool:
    """A browser and a server snapshot straddling a real edge is inconclusive."""
    from zoneinfo import ZoneInfo
    local = moment.astimezone(ZoneInfo("Europe/London"))
    now = local.hour * 60 + local.minute
    seconds_into_minute = local.second + local.microsecond / 1_000_000
    for key in ("night_dim_start", "night_dim_end"):
        boundary = _minutes(settings[key])
        # Detect within 3s either side of a boundary, including 00:00 wrap.
        delta_min = (now - boundary) % 1440
        if (delta_min == 0 and seconds_into_minute <= seconds
                or delta_min == 1439 and seconds_into_minute >= 60 - seconds):
            return True
    return False


def compare(
    *,
    server_settings: dict[str, Any],
    browser_status: dict[str, Any],
    browser_alarm_visible: bool,
    server_alarm_status: dict[str, Any] | None,
    observed_at: datetime,
    screen_snapshot: dict[str, Any] | None = None,
    prior_input_sequence: int | None = None,
) -> ShadowResult:
    """Pure diagnostic: compare *one* explicit browser snapshot with server data.

    All data must be captured by a deliberate caller. A single observation does
    not prove long-background reliability, elapsed preview expiry, or correctness
    of a browser that has stopped reporting.
    """
    if not isinstance(server_settings, dict) or not isinstance(browser_status, dict):
        raise ValueError("Expected server settings and browser status mappings")
    if type(browser_alarm_visible) is not bool:
        raise ValueError("browser_alarm_visible must be boolean")
    if (not isinstance(observed_at, datetime) or observed_at.tzinfo is None
            or observed_at.utcoffset() is None):
        raise ValueError("An aware browser observation time is required")
    for key in ("scheduled", "active", "previewing", "interacting"):
        _bool(browser_status, key)
    for key in ("enabled",):
        _bool(browser_status, key)
    if not isinstance(browser_status.get("start"), str) or not isinstance(browser_status.get("end"), str):
        raise ValueError("Browser night start/end required")
    if browser_status.get("style") not in ("classic", "astronomy"):
        raise ValueError("Unrecognised browser idle style")
    if browser_status.get("activeStyle") not in ("same", "classic", "astronomy"):
        raise ValueError("Unrecognised browser active style")
    if browser_status.get("effectiveStyle") not in ("classic", "astronomy"):
        raise ValueError("Unrecognised effective night style")
    wake = server_settings.get("night_dim_wake_seconds")
    if type(wake) is not int or not 5 <= wake <= 300:
        raise ValueError("Expected validated night wake seconds")
    if type(browser_status.get("wakeSeconds")) is not int:
        raise ValueError("Expected browser wake seconds")

    schedule = schedule_plan(server_settings, observed_at,
                             alarm_visible=browser_alarm_visible,
                             preview_active=browser_status["previewing"])
    alarm = alarm_observation(
        browser_alarm_visible=browser_alarm_visible,
        scheduler_status=server_alarm_status,
    )
    comparisons: dict[str, str] = {}
    disagreements: list[str] = []
    limitations: list[str] = []
    def check(name: str, observed: Any, expected: Any) -> None:
        if observed == expected:
            comparisons[name] = "match"
        else:
            comparisons[name] = "mismatch"
            disagreements.append(name)

    # Settings may have been changed in ACP without yet reaching the persisted
    # server config. This is drift, not evidence that the scheduling math broke.
    check("settings", (
        browser_status["enabled"], browser_status["start"],
        browser_status["end"], browser_status["style"],
        browser_status["activeStyle"], browser_status["wakeSeconds"],
    ), (
        server_settings.get("night_dim_enabled"),
        server_settings.get("night_dim_start"),
        server_settings.get("night_dim_end"),
        server_settings.get("night_dim_style"),
        server_settings.get("night_dim_active_style"),
        wake,
    ))
    check("effective_style", browser_status["effectiveStyle"], (
        browser_status["activeStyle"] if browser_status["interacting"]
        and browser_status["activeStyle"] != "same" else browser_status["style"]
    ))

    if _near_boundary(observed_at, server_settings):
        comparisons["scheduled"] = "unknown"
        limitations.append("near schedule boundary; do not interpret clock drift")
    elif comparisons["settings"] == "mismatch":
        comparisons["scheduled"] = "unknown"
        limitations.append("browser/server settings differ; schedule parity inconclusive")
    else:
        check("scheduled", browser_status["scheduled"], schedule.scheduled)

    if comparisons["scheduled"] == "unknown" or alarm.agreement != "agree":
        comparisons["active"] = "unknown"
        limitations.append("alarm presentation or scheduled interval not independently settled")
    else:
        check("active", browser_status["active"], schedule.active)

    comparisons["alarm_presentation"] = alarm.agreement
    if alarm.agreement != "agree":
        limitations.append("server alarm screen request is not browser presentation")
    # Native input activity has no intrinsic browser-interaction TTL; the
    # caller can provide a prior sequence, but not a timeline from one sample.
    if screen_snapshot is None:
        comparisons["linux_input"] = "unknown"
        limitations.append("no Linux input snapshot; cannot infer interactions")
    else:
        preview_until = (
            observed_at + timedelta(seconds=1)
            if browser_status["previewing"] else None
        )
        input_decision = linux_input_step(
            screen_snapshot=screen_snapshot,
            last_sequence=prior_input_sequence,
            now=observed_at,
            night_enabled=browser_status["enabled"],
            night_scheduled=browser_status["scheduled"],
            browser_alarm_visible=browser_alarm_visible,
            preview_until=preview_until,
            wake_seconds=browser_status["wakeSeconds"],
        )
        comparisons["linux_input"] = input_decision.action
        limitations.append("Linux input sequence comparison is diagnostic; no wake scheduled")
    if disagreements:
        verdict = "mismatch"
    elif ("unknown" in comparisons.values() or alarm.agreement != "agree"):
        verdict = "inconclusive"
    else:
        verdict = "match"
    limitations.append("one sample cannot prove background timer liveness")
    return ShadowResult(
        verdict=verdict,
        comparisons=comparisons,
        disagreements=tuple(disagreements),
        limitations=tuple(limitations),
    )
