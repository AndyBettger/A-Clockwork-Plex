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
_NIGHT_STYLES = {"classic", "astronomy"}
_NIGHT_ACTIVE_STYLES = {"same", *_NIGHT_STYLES}
_MAX_CLOCK_CARD_SLOTS = 8
_CLOCK_CARD_SLOT_GROUPS = {
    "outdoor_temp": "temperature_summary",
    "indoor_temp": "temperature_summary",
    "humidity": "humidity_summary",
    "indoor_humidity": "humidity_summary",
    "wind_speed": "wind_summary",
    "wind_gust": "wind_summary",
    "solar": "solar_uv_summary",
    "uv": "solar_uv_summary",
    "daily_rain": "rain_summary",
    "event_rain": "rain_summary",
}


def _clock_time(value: Any, fallback: str, label: str) -> str:
    candidate = str(value if value is not None else fallback).strip()
    if not _TIME_RE.fullmatch(candidate):
        raise ValueError(f"{label} must use 24-hour HH:MM format.")
    return candidate


def _night_style(value: Any, fallback: str, *, active: bool = False) -> str:
    allowed = _NIGHT_ACTIVE_STYLES if active else _NIGHT_STYLES
    candidate = str(value if value is not None else fallback).strip().lower()
    return candidate if candidate in allowed else fallback


def _clock_card_slot_count(values: Any) -> int:
    if not isinstance(values, list):
        return 0
    slots: list[str] = []
    for value in values:
        card_id = str(value)
        slot_id = _CLOCK_CARD_SLOT_GROUPS.get(card_id, card_id)
        if slot_id not in slots:
            slots.append(slot_id)
    return len(slots)


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
                "night_dim_active_level_percent": _base._integer(
                    dashboard.get("night_dim_active_level_percent"), 35, 5, 80
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
                "night_dim_style": _night_style(
                    dashboard.get("night_dim_style"), "classic"
                ),
                "night_dim_active_style": _night_style(
                    dashboard.get("night_dim_active_style"), "same", active=True
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
                "night_dim_active_level_percent": _base._integer(
                    source.get("night_dim_active_level_percent"),
                    dashboard.get("night_dim_active_level_percent", 35),
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
                "night_dim_style": _night_style(
                    source.get("night_dim_style"),
                    _night_style(dashboard.get("night_dim_style"), "classic"),
                ),
                "night_dim_active_style": _night_style(
                    source.get("night_dim_active_style"),
                    _night_style(
                        dashboard.get("night_dim_active_style"), "same", active=True
                    ),
                    active=True,
                ),
            }
        )

    def _normalise_weather(self, config: dict[str, Any], payload: Any) -> None:
        super()._normalise_weather(config, payload)
        weather = _base._object(config.get("weather"))
        slot_count = _clock_card_slot_count(weather.get("clock_cards"))
        if slot_count > _MAX_CLOCK_CARD_SLOTS:
            raise ValueError(
                f"Clock weather cards support at most {_MAX_CLOCK_CARD_SLOTS} displayed slots."
            )


register_unified_settings_api = _base.register_unified_settings_api

__all__ = ["UnifiedSettingsService", "register_unified_settings_api"]
