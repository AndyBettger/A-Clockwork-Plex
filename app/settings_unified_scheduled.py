from __future__ import annotations

"""Bind unified Settings to promoted production policies.

The preserved alarm_audio_core module deliberately keeps scheduled playback
locked for its historical explicit-test boundary. Production promotes that
boundary in alarm_audio_scheduled, so the unified Settings transaction must use
the promoted normaliser as well or every save would clear scheduled_enabled.

This module also extends the established transaction with the dashboard-wide
night-dimming model. Keeping that model here lets the browser use the same
revisioned Settings authority without disturbing the already validated base
transaction implementation.
"""

import re
from typing import Any

try:
    from . import settings_unified as _base
    from .alarm_audio_scheduled import normalise_audio_settings
except ImportError:  # Supports direct execution imports.
    import settings_unified as _base
    from alarm_audio_scheduled import normalise_audio_settings


# UnifiedSettingsService resolves this module global at call time. Rebinding it
# here keeps all of the established transaction implementation and validators,
# while ensuring production Settings uses the same two-key safety policy as the
# promoted ScheduledAlarmAudioManager.
_base.normalise_audio_settings = normalise_audio_settings

_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _clock_time(value: Any, fallback: str, label: str) -> str:
    candidate = str(value if value is not None else fallback).strip()
    if not _TIME_RE.fullmatch(candidate):
        raise ValueError(f"{label} must use 24-hour HH:MM format.")
    return candidate


class UnifiedSettingsService(_base.UnifiedSettingsService):
    """Production Settings service with scheduled display-dimming support."""

    def _public_settings(
        self,
        config: dict[str, Any],
        *,
        eq_status: dict[str, Any] | None = None,
        receiver_status: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        settings = super()._public_settings(
            config,
            eq_status=eq_status,
            receiver_status=receiver_status,
        )
        dashboard = _base._object(config.get("dashboard"))
        display = settings.setdefault("display", {})
        display.update(
            {
                "night_dim_enabled": _base._boolean(
                    dashboard.get("night_dim_enabled"), False
                ),
                "night_dim_start": _clock_time(
                    dashboard.get("night_dim_start"), "22:00", "Night dim start"
                ),
                "night_dim_end": _clock_time(
                    dashboard.get("night_dim_end"), "07:00", "Night dim end"
                ),
                "night_dim_level_percent": _base._integer(
                    dashboard.get("night_dim_level_percent"), 18, 5, 80
                ),
                "night_dim_wake_seconds": _base._integer(
                    dashboard.get("night_dim_wake_seconds"), 30, 5, 300
                ),
                "night_clock_mode": _base._boolean(
                    dashboard.get("night_clock_mode"), True
                ),
                "night_burn_in_shift": _base._boolean(
                    dashboard.get("night_burn_in_shift"), True
                ),
            }
        )
        return settings

    def _normalise_display(self, config: dict[str, Any], payload: Any) -> None:
        super()._normalise_display(config, payload)
        source = _base._object(payload)
        dashboard = config.setdefault("dashboard", {})
        dashboard.update(
            {
                "night_dim_enabled": _base._boolean(
                    source.get("night_dim_enabled"),
                    _base._boolean(dashboard.get("night_dim_enabled"), False),
                ),
                "night_dim_start": _clock_time(
                    source.get("night_dim_start"),
                    str(dashboard.get("night_dim_start", "22:00")),
                    "Night dim start",
                ),
                "night_dim_end": _clock_time(
                    source.get("night_dim_end"),
                    str(dashboard.get("night_dim_end", "07:00")),
                    "Night dim end",
                ),
                "night_dim_level_percent": _base._integer(
                    source.get("night_dim_level_percent"),
                    dashboard.get("night_dim_level_percent", 18),
                    5,
                    80,
                ),
                "night_dim_wake_seconds": _base._integer(
                    source.get("night_dim_wake_seconds"),
                    dashboard.get("night_dim_wake_seconds", 30),
                    5,
                    300,
                ),
                "night_clock_mode": _base._boolean(
                    source.get("night_clock_mode"),
                    _base._boolean(dashboard.get("night_clock_mode"), True),
                ),
                "night_burn_in_shift": _base._boolean(
                    source.get("night_burn_in_shift"),
                    _base._boolean(dashboard.get("night_burn_in_shift"), True),
                ),
            }
        )


register_unified_settings_api = _base.register_unified_settings_api

__all__ = ["UnifiedSettingsService", "register_unified_settings_api"]
