from __future__ import annotations

from copy import deepcopy
from typing import Any

try:
    from .weather_observations import (
        SUPPORTED_PROVIDERS,
        normalise_observation_config,
        observation_configuration_error,
    )
except ImportError:  # Supports direct execution imports.
    from weather_observations import (
        SUPPORTED_PROVIDERS,
        normalise_observation_config,
        observation_configuration_error,
    )


SENSITIVE_SUBMITTED_KEYS = {"api_key", "apikey", "password", "secret", "token"}


def public_observation_config(config: dict[str, Any]) -> dict[str, Any]:
    settings = normalise_observation_config(config)
    return {
        "provider": settings["provider"],
        "ecowitt_push": dict(settings["ecowitt_push"]),
        "weather_underground": dict(settings["weather_underground"]),
    }


def _integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, (dict, list, tuple, set, bool)):
        raise ValueError(f"{label} must be a whole number.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a whole number.") from exc
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{label} must be from {minimum} to {maximum} seconds.")
    return parsed


def _reject_secret_fields(payload: dict[str, Any]) -> None:
    for key in payload:
        if str(key).strip().lower() in SENSITIVE_SUBMITTED_KEYS:
            raise ValueError(
                "Weather Underground API keys must be supplied through the configured environment variable, not Settings."
            )


def submitted_observation_config(
    current_config: dict[str, Any],
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("Weather observation settings must be a JSON object.")
    _reject_secret_fields(payload)

    config = deepcopy(current_config)
    weather = config.setdefault("weather", {})
    if not isinstance(weather, dict):
        weather = {}
        config["weather"] = weather

    current = normalise_observation_config(config)
    provider = str(payload.get("provider", current["provider"])).strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported weather observation provider: {provider or 'empty'}.")
    weather["provider"] = provider

    ecowitt_payload = payload.get("ecowitt_push")
    if ecowitt_payload is not None:
        if not isinstance(ecowitt_payload, dict):
            raise ValueError("Ecowitt push settings must be a JSON object.")
        _reject_secret_fields(ecowitt_payload)
        ecowitt = dict(current["ecowitt_push"])
        if "path" in ecowitt_payload:
            path = str(ecowitt_payload.get("path") or "").strip()
            if not path.startswith("/") or "?" in path or "#" in path:
                raise ValueError("Ecowitt push path must be an absolute URL path without a query or fragment.")
            ecowitt["path"] = path
        if "fresh_seconds" in ecowitt_payload:
            ecowitt["fresh_seconds"] = _integer(
                ecowitt_payload["fresh_seconds"],
                "Ecowitt freshness",
                30,
                3600,
            )
        weather["ecowitt_push"] = ecowitt

    wunderground_payload = payload.get("weather_underground")
    if wunderground_payload is not None:
        if not isinstance(wunderground_payload, dict):
            raise ValueError("Weather Underground settings must be a JSON object.")
        _reject_secret_fields(wunderground_payload)
        wunderground = dict(current["weather_underground"])
        if "station_id" in wunderground_payload:
            wunderground["station_id"] = str(
                wunderground_payload.get("station_id") or ""
            ).strip().upper()
        if "api_key_env" in wunderground_payload:
            wunderground["api_key_env"] = str(
                wunderground_payload.get("api_key_env") or ""
            ).strip()
        integer_fields = {
            "refresh_seconds": ("Weather Underground refresh interval", 30, 3600),
            "stale_seconds": ("Weather Underground stale interval", 60, 21600),
            "request_timeout_seconds": ("Weather Underground request timeout", 2, 60),
            "pressure_history_hours": ("Weather Underground pressure-history hours", 3, 24),
        }
        for key, (label, minimum, maximum) in integer_fields.items():
            if key in wunderground_payload:
                wunderground[key] = _integer(
                    wunderground_payload[key],
                    label,
                    minimum,
                    maximum,
                )
        weather["weather_underground"] = wunderground

    normalised = normalise_observation_config(config)
    error = observation_configuration_error(normalised)
    if error:
        raise ValueError(error)

    weather["provider"] = normalised["provider"]
    weather["ecowitt_push"] = normalised["ecowitt_push"]
    weather["weather_underground"] = normalised["weather_underground"]
    return config, public_observation_config(config)
