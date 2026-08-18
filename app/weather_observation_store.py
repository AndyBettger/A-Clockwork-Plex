from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from flask import jsonify

try:
    from .weather_live_state import (
        augment_derived_rain,
        extract_indoor_observation,
        fresh_supplemental_indoor,
        indoor_fresh_seconds,
        update_supplemental_indoor_state,
        weather_underground_station_id,
    )
except ImportError:  # Supports direct execution through app/runner.py.
    from weather_live_state import (
        augment_derived_rain,
        extract_indoor_observation,
        fresh_supplemental_indoor,
        indoor_fresh_seconds,
        update_supplemental_indoor_state,
        weather_underground_station_id,
    )


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


def configured_observation_provider(config: dict[str, Any] | Any) -> str:
    """Return the configured live-observation authority.

    Ecowitt remains the compatibility default for older configuration files.
    Supplemental providers such as Weather Underground history do not change
    this value; only weather.provider owns the live observation projection.
    """

    if not isinstance(config, dict):
        return "ecowitt_push"
    weather = config.get("weather")
    if not isinstance(weather, dict):
        return "ecowitt_push"
    provider = str(weather.get("provider") or "ecowitt_push").strip().lower()
    return provider or "ecowitt_push"


def store_dashboard_observation(
    dashboard: Any,
    payload: dict[str, Any],
    *,
    now_provider: NowProvider = datetime.now,
) -> dict[str, Any]:
    """Persist one observation through the dashboard's established state model.

    This is the single storage contract for the selected remote poller or direct
    station push. It owns current observation replacement, issue time, daily
    extremes and pressure-history updates; provider code only maps upstream
    payloads into the dashboard weather-key vocabulary.

    With WU selected, its observation remains authoritative for outdoor/current
    fields. Fresh Ecowitt indoor readings are merged only as supplementary data,
    and locally derived Hourly/Event rain fills the two fields WU does not supply.
    """

    clean = sanitise_weather_observation(payload)
    config = dashboard.load_config()
    state = dashboard.load_state(config)
    now = now_provider()
    provider = configured_observation_provider(config)

    if provider == "weather_underground":
        clean = augment_derived_rain(
            state,
            clean,
            now,
            station_id=weather_underground_station_id(config),
        )
        clean.update(
            fresh_supplemental_indoor(
                state,
                now,
                fresh_seconds=indoor_fresh_seconds(config),
            )
        )

    state["weather"] = clean
    state["last_weather_update"] = now.isoformat(timespec="seconds")
    dashboard.update_weather_extremes(state, clean)
    dashboard.update_pressure_history(state, clean)
    dashboard.save_json(dashboard.STATE_PATH, state)
    return state


def _store_supplemental_indoor(
    dashboard: Any,
    config: dict[str, Any],
    state: dict[str, Any],
    payload: dict[str, Any],
    *,
    now_provider: NowProvider = datetime.now,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Persist only Ecowitt indoor fields without touching WU outdoor authority."""

    indoor = extract_indoor_observation(payload)
    if not indoor:
        return state, {}

    now = now_provider()
    update_supplemental_indoor_state(state, indoor, now)
    current = state.get("weather") if isinstance(state.get("weather"), dict) else {}
    state["weather"] = {**current, **indoor}
    dashboard.update_weather_extremes(state, indoor)
    dashboard.save_json(dashboard.STATE_PATH, state)
    return state, indoor


def promote_ecowitt_observation_store(app: Any, dashboard: Any) -> None:
    """Make the production Ecowitt endpoint use the shared storage authority.

    dashboard_core owns the historical route declaration for compatibility, but
    app/runner.py is the production composition root. Replacing that endpoint's
    view function here keeps its URL and response contract while ensuring an
    Ecowitt push can update current outdoor weather only while Ecowitt is the
    configured live-observation authority. When Weather Underground is selected,
    station pushes are acknowledged and may refresh the two supplementary indoor
    readings, but cannot overwrite WU outdoor/current fields.
    """

    if "api_weather_ecowitt" not in app.view_functions:
        raise RuntimeError("The established Ecowitt weather endpoint is unavailable.")

    def api_weather_ecowitt_shared():
        config = dashboard.load_config()
        state = dashboard.load_state(config)
        provider = configured_observation_provider(config)
        payload = dashboard.normalise_weather_payload()

        if provider != "ecowitt_push":
            state, indoor = _store_supplemental_indoor(dashboard, config, state, payload)
            return jsonify(
                {
                    "ok": True,
                    "stored": False,
                    "supplemental_indoor_stored": bool(indoor),
                    "received_fields": len(indoor),
                    "message": (
                        "Ecowitt push acknowledged without replacing outdoor weather because "
                        f"the selected live weather provider is {provider}."
                    ),
                    "cached_fields": len(state.get("weather", {})),
                    "last_weather_update": state.get("last_weather_update"),
                    "last_weather_indoor_update": state.get("last_weather_indoor_update"),
                }
            )

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
