"""Read-only evidence model for ACP night alarm + Linux-input state parity.

This is NOT a Squeekboard controller or a second authority for the OSK. The
existing browser ACPDisplayDimming model stays authoritative while C3 is in
trial. External callers MUST supply observed presentation, scheduler and
input data; this module performs no reads, writes, network or service calls.

Sources:
 * display-dimming.js: alarmVisible(), pollLinuxInputActivity(), interact()
 * alarm_runtime.py: status().screen_required during ringing/not snoozing
 * screen_projection_activity.py: snapshot().screen.input_activity.sequence
 * input_activity.py: LinuxInputActivityMonitor.snapshot().sequence

These sources do not prove identical state: a ringing alarm need not yet have
been presented by the browser, and native user interaction may occur while
the browser is backgrounded. Disagreement is diagnostic, NEVER auto-resolved.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class AlarmObservation:
    browser_visible: bool | None
    server_screen_required: bool | None
    agreement: str
    safe_for_shadow_suppression: bool
    reason: str


@dataclass(frozen=True)
class LinuxInputDecision:
    next_sequence: int | None
    action: str
    wake_until: datetime | None


def alarm_observation(
    *,
    browser_alarm_visible: bool | None,
    scheduler_status: dict[str, Any] | None,
) -> AlarmObservation:
    """Compare explicit browser presentation and server alarm screen request.

    Browser alarmVisible() checks pathname, activePage or mode-alarm. Server
    'screen_required' describes a requested screen, not proof it was presented.
    Never infer one from the other or suppress via an unresolved observation.
    """
    if browser_alarm_visible is not None and type(browser_alarm_visible) is not bool:
        raise ValueError("browser alarm-visible observation must be boolean or unknown")
    if scheduler_status is not None and not isinstance(scheduler_status, dict):
        raise ValueError("scheduler status must be a mapping or unknown")
    requested = None
    if scheduler_status is not None and "screen_required" in scheduler_status:
        requested = scheduler_status["screen_required"]
        if type(requested) is not bool:
            raise ValueError("screen_required must be a boolean")
    if browser_alarm_visible is None or requested is None:
        return AlarmObservation(browser_alarm_visible, requested, "incomplete", False,
                                "browser and server alarm observations not both available")
    if browser_alarm_visible != requested:
        return AlarmObservation(browser_alarm_visible, requested, "disagree", False,
                                "screen request is not proof of browser presentation")
    return AlarmObservation(browser_alarm_visible, requested, "agree", True,
                            "both independent alarm observations agree")


def _aware(value: datetime) -> bool:
    return (isinstance(value, datetime) and value.tzinfo is not None
            and value.utcoffset() is not None)


def linux_input_step(
    *,
    screen_snapshot: dict[str, Any] | None,
    last_sequence: int | None,
    now: datetime,
    night_enabled: bool,
    night_scheduled: bool,
    browser_alarm_visible: bool,
    preview_until: datetime | None,
    wake_seconds: int,
) -> LinuxInputDecision:
    """Pure mirror of browser Linux-input *polling* branch (not DOM events).

    When the browser would not poll, preserve last_sequence. Otherwise its
    first sequence is only a baseline; a device reset is rebaselined. During
    preview, it consumes newer sequences without replaying the preview tap.
    The return value is merely a proposed interaction deadline for a future
    comparative shadow evaluator: it changes NO live state.
    """
    if not _aware(now):
        raise ValueError("now must be a timezone-aware instant")
    if preview_until is not None and not _aware(preview_until):
        raise ValueError("preview deadline must be timezone-aware")
    for name, value in (
        ("night_enabled", night_enabled),
        ("night_scheduled", night_scheduled),
        ("browser_alarm_visible", browser_alarm_visible),
    ):
        if type(value) is not bool:
            raise ValueError(f"{name} must be an explicit boolean")
    if type(wake_seconds) is not int or not 5 <= wake_seconds <= 300:
        raise ValueError("wake_seconds must be a validated 5..300 integer")
    if last_sequence is not None and (
        type(last_sequence) is not int or last_sequence < 0
    ):
        raise ValueError("last_sequence must be a nonnegative integer or unknown")

    preview = preview_until is not None and now < preview_until
    if not night_enabled or browser_alarm_visible or not (night_scheduled or preview):
        return LinuxInputDecision(last_sequence, "poll-gated", None)

    if not isinstance(screen_snapshot, dict):
        raise ValueError("expected /api/screen/state JSON object")
    screen = screen_snapshot.get("screen")
    if not isinstance(screen, dict):
        raise ValueError("expected screen projection")
    activity = screen.get("input_activity")
    if not isinstance(activity, dict):
        raise ValueError("expected screen.input_activity")
    sequence = activity.get("sequence")
    if type(sequence) is not int or sequence < 0:
        raise ValueError("invalid LinuxInputActivityMonitor sequence")

    if last_sequence is None:
        return LinuxInputDecision(sequence, "initial-baseline", None)
    if sequence < last_sequence:
        return LinuxInputDecision(sequence, "device-sequence-reset", None)
    if sequence == last_sequence:
        return LinuxInputDecision(sequence, "unchanged", None)
    if preview:
        return LinuxInputDecision(sequence, "preview-input-suppressed", None)
    return LinuxInputDecision(sequence, "activity-observed",
                              now + timedelta(seconds=wake_seconds))
