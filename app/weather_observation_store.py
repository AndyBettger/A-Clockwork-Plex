from __future__ import annotations

from datetime import datetime
from typing import Any, Callable


SENSITIVE_WEATHER_KEYS = {"passkey", "password", "secret", "token", "api_key", "apikey"}
NowProvider = Callable[[], datetime]


def sanitise_weather_observation(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Weather observation must be an object.")

    clean: dict[str, Any] = {}
    for key, value in payload.items():
        key_text = str(key).strip()
        if not key_text or key_text.lower() in SENSITIVE_WEATHER_KEYS:
            continue
        if value is None or not str(value).strip():
            continue
        clean[key_text] = value

    if not clean:
        raise ValueError("Weather observation contained no usable fields.")
    return clean


def store_dashboard_observation(
    dashboard: Any,
    payload: dict[str, Any],
    *,
    now_provider: NowProvider = datetime.now,
) -> dict[str, Any]:
    """Persist one observation through the dashboard's established state model.

    This is the single storage contract remote polling and direct station pushes
    are converging on. It owns current observation replacement, issue time,
    daily extremes and pressure-history updates; provider code should only map
    upstream payloads into the dashboard weather-key vocabulary.
    """

    clean = sanitise_weather_observation(payload)
    config = dashboard.load_config()
    state = dashboard.load_state(config)
    state["weather"] = clean
    state["last_weather_update"] = now_provider().isoformat(timespec="seconds")
    dashboard.update_weather_extremes(state, clean)
    dashboard.update_pressure_history(state, clean)
    dashboard.save_json(dashboard.STATE_PATH, state)
    return state
