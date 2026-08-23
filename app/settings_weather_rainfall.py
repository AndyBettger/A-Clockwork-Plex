from __future__ import annotations

"""Add historical-rainfall preferences/status to production Unified Settings."""

from typing import Any

try:
    from . import settings_unified_scheduled as _base
    from .weather_rainfall_history import (
        WeatherRainfallHistoryService,
        public_rainfall_config,
        submitted_rainfall_config,
    )
except ImportError:  # Supports direct execution imports.
    import settings_unified_scheduled as _base
    from weather_rainfall_history import (
        WeatherRainfallHistoryService,
        public_rainfall_config,
        submitted_rainfall_config,
    )


MIN_AIRPLAY_PAUSE_HOLD_SECONDS = 30
MAX_AIRPLAY_PAUSE_HOLD_SECONDS = 420


def _bounded_airplay_pause_hold_seconds(value: Any) -> int:
    try:
        seconds = int(str(value).strip())
    except (TypeError, ValueError):
        seconds = MAX_AIRPLAY_PAUSE_HOLD_SECONDS
    return max(
        MIN_AIRPLAY_PAUSE_HOLD_SECONDS,
        min(MAX_AIRPLAY_PAUSE_HOLD_SECONDS, seconds),
    )


class UnifiedSettingsService(_base.UnifiedSettingsService):
    """Production Settings extended with rainfall history and final appliance bounds."""

    def __init__(
        self,
        *,
        rainfall: WeatherRainfallHistoryService | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._rainfall = rainfall

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
        settings.setdefault("weather", {})["historical_rainfall"] = public_rainfall_config(config)
        airplay = settings.setdefault("airplay", {})
        airplay["pause_hold_seconds"] = _bounded_airplay_pause_hold_seconds(
            airplay.get("pause_hold_seconds")
        )
        return settings

    def snapshot(self) -> dict[str, Any]:
        snapshot = super().snapshot()
        if self._rainfall is not None:
            snapshot.setdefault("status", {})["weather_rainfall"] = self._rainfall.snapshot()
        return snapshot

    def _normalise_weather(self, config: dict[str, Any], payload: Any) -> None:
        super()._normalise_weather(config, payload)
        source = payload if isinstance(payload, dict) else {}
        rainfall_payload = source.get("historical_rainfall")
        if rainfall_payload is None:
            return
        updated = submitted_rainfall_config(config, rainfall_payload)
        config.clear()
        config.update(updated)

    def _normalise_airplay(self, config: dict[str, Any], payload: Any) -> None:
        super()._normalise_airplay(config, payload)
        airplay = config.setdefault("airplay", {})
        airplay["pause_hold_seconds"] = _bounded_airplay_pause_hold_seconds(
            airplay.get("pause_hold_seconds")
        )

    def apply(self, payload: Any) -> dict[str, Any]:
        before = public_rainfall_config(self._load_config())
        result = super().apply(payload)
        after = public_rainfall_config(self._load_config())
        changed_rainfall = before != after
        result.setdefault("changed", {})["weather_rainfall_refreshed"] = changed_rainfall
        if changed_rainfall and self._rainfall is not None:
            self._rainfall.wake()
            result.setdefault("status", {})["weather_rainfall"] = self._rainfall.refresh()
        return result


register_unified_settings_api = _base.register_unified_settings_api

__all__ = ["UnifiedSettingsService", "register_unified_settings_api"]
