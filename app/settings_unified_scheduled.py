from __future__ import annotations

"""Bind unified Settings to promoted production policies.

The preserved alarm_audio_core module deliberately keeps scheduled playback
locked for its historical explicit-test boundary. Production promotes that
boundary in alarm_audio_scheduled, so the unified Settings transaction must use
the promoted normaliser as well or every save would clear scheduled_enabled.

This module also extends the established transaction with the dashboard-wide
display theme/night-dimming model and the promoted weather-observation provider
contract. Keeping those models here lets the browser use the same revisioned
Settings authority without disturbing the already validated base transaction.
"""

import re
from typing import Any

try:
    from . import settings_unified as _base
    from .alarm_audio_scheduled import normalise_audio_settings
    from .weather_observation_settings import (
        public_observation_config,
        submitted_observation_config,
    )
    from .weather_observations import WeatherObservationService
except ImportError:  # Supports direct execution imports.
    import settings_unified as _base
    from alarm_audio_scheduled import normalise_audio_settings
    from weather_observation_settings import (
        public_observation_config,
        submitted_observation_config,
    )
    from weather_observations import WeatherObservationService


# UnifiedSettingsService resolves this module global at call time. Rebinding it
# here keeps all of the established transaction implementation and validators,
# while ensuring production Settings uses the same two-key safety policy as the
# promoted ScheduledAlarmAudioManager.
_base.normalise_audio_settings = normalise_audio_settings

_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
_DAYTIME_THEMES = {
    "classic_dark",
    "midnight_blue",
    "amber_terminal",
    "green_phosphor",
    "aubergine",
    "steel_cyan",
}
_NIGHT_STYLES = {"classic", "astronomy"}
_NIGHT_ACTIVE_STYLES = {"same", *_NIGHT_STYLES}
_ALARM_INDICATOR_MODES = {"within_12h", "any_future"}
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


def _daytime_theme(value: Any, fallback: str = "classic_dark") -> str:
    candidate = str(value if value is not None else fallback).strip().lower()
    return candidate if candidate in _DAYTIME_THEMES else fallback


def _night_style(value: Any, fallback: str, *, active: bool = False) -> str:
    allowed = _NIGHT_ACTIVE_STYLES if active else _NIGHT_STYLES
    candidate = str(value if value is not None else fallback).strip().lower()
    return candidate if candidate in allowed else fallback


def _alarm_indicator_mode(value: Any, fallback: str = "within_12h") -> str:
    candidate = str(value if value is not None else fallback).strip().lower()
    return candidate if candidate in _ALARM_INDICATOR_MODES else fallback


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
    """Production Settings with display themes and observation providers."""

    def __init__(
        self,
        *,
        observations: WeatherObservationService | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._observations = observations

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
                "daytime_theme": _daytime_theme(
                    dashboard.get("daytime_theme"), "classic_dark"
                ),
                "alarm_indicator_mode": _alarm_indicator_mode(
                    dashboard.get("alarm_indicator_mode"), "within_12h"
                ),
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
        weather = settings.setdefault("weather", {})
        weather["observations"] = public_observation_config(config)
        return settings

    def snapshot(self) -> dict[str, Any]:
        snapshot = super().snapshot()
        if self._observations is not None:
            snapshot.setdefault("status", {})["weather_observations"] = (
                self._observations.snapshot()
            )
        return snapshot

    def _normalise_display(self, config: dict[str, Any], payload: Any) -> None:
        super()._normalise_display(config, payload)
        source = _base._object(payload)
        dashboard = config.setdefault("dashboard", {})
        dashboard.update(
            {
                "daytime_theme": _daytime_theme(
                    source.get("daytime_theme"),
                    _daytime_theme(dashboard.get("daytime_theme"), "classic_dark"),
                ),
                "alarm_indicator_mode": _alarm_indicator_mode(
                    source.get("alarm_indicator_mode"),
                    _alarm_indicator_mode(
                        dashboard.get("alarm_indicator_mode"), "within_12h"
                    ),
                ),
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
        source = _base._object(payload)
        observations_payload = source.get("observations")
        if observations_payload is not None:
            if not isinstance(observations_payload, dict):
                raise ValueError("Weather observation settings must be a JSON object.")
            updated, _normalised = submitted_observation_config(
                config,
                observations_payload,
            )
            config.clear()
            config.update(updated)

        weather = _base._object(config.get("weather"))
        slot_count = _clock_card_slot_count(weather.get("clock_cards"))
        if slot_count > _MAX_CLOCK_CARD_SLOTS:
            raise ValueError(
                f"Clock weather cards support at most {_MAX_CLOCK_CARD_SLOTS} displayed slots."
            )

    def apply(self, payload: Any) -> dict[str, Any]:
        before_observations = public_observation_config(self._load_config())
        result = super().apply(payload)
        after_observations = public_observation_config(self._load_config())
        observations_changed = before_observations != after_observations

        changed = result.setdefault("changed", {})
        changed["weather_observations_refreshed"] = observations_changed
        if observations_changed and self._observations is not None:
            self._observations.wake()
            result.setdefault("status", {})["weather_observations"] = (
                self._observations.refresh(
                    force=after_observations.get("provider") == "weather_underground"
                )
            )
        return result


register_unified_settings_api = _base.register_unified_settings_api

__all__ = ["UnifiedSettingsService", "register_unified_settings_api"]
