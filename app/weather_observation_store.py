from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from flask import jsonify


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

    This is the single storage contract for remote polling and direct station
    pushes. It owns current observation replacement, issue time, daily extremes
    and pressure-history updates; provider code only maps upstream payloads into
    the dashboard weather-key vocabulary.
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


def promote_ecowitt_observation_store(app: Any, dashboard: Any) -> None:
    """Make the production Ecowitt endpoint use the shared storage authority.

    dashboard_core owns the historical route declaration for compatibility, but
    app/runner.py is the production composition root. Replacing that endpoint's
    view function here keeps its URL and response contract while ensuring both
    Ecowitt push and Weather Underground polling reach the same state writer.
    """

    if "api_weather_ecowitt" not in app.view_functions:
        raise RuntimeError("The established Ecowitt weather endpoint is unavailable.")

    def api_weather_ecowitt_shared():
        config = dashboard.load_config()
        state = dashboard.load_state(config)
        payload = dashboard.normalise_weather_payload()
        if payload:
            state = store_dashboard_observation(dashboard, payload)
            return jsonify(
                {
                    "ok": True,
                    "stored": True,
                    "received_fields": len(state.get("weather", {})),
                    "last_weather_update": state.get("last_weather_update"),
                }
            )

        return jsonify(
            {
                "ok": True,
                "stored": False,
                "received_fields": 0,
                "message": "No weather fields received; existing cached weather was left unchanged.",
                "cached_fields": len(state.get("weather", {})),
                "last_weather_update": state.get("last_weather_update"),
                "weather_display": dashboard.pick_weather_fields(
                    config,
                    state.get("weather", {}),
                    state,
                ),
                "weather_detail": dashboard.weather_detail_data(
                    config,
                    state.get("weather", {}),
                    state,
                ),
            }
        )

    app.view_functions["api_weather_ecowitt"] = api_weather_ecowitt_shared
