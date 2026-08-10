from __future__ import annotations

import re
import urllib.parse
from typing import Any


WEATHER_UNDERGROUND_CURRENT_URL = "https://api.weather.com/v2/pws/observations/current"
WEATHER_UNDERGROUND_RECENT_HISTORY_URL = "https://api.weather.com/v2/pws/observations/all/1day"
DEFAULT_PROVIDER = "ecowitt_push"
DEFAULT_API_KEY_ENV = "WEATHER_UNDERGROUND_API_KEY"
DEFAULT_REFRESH_SECONDS = 60
DEFAULT_STALE_SECONDS = 300
DEFAULT_TIMEOUT_SECONDS = 8
DEFAULT_PRESSURE_HISTORY_HOURS = 6
SUPPORTED_PROVIDERS = {"ecowitt_push", "weather_underground"}
_ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_STATION_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def _integer(value: Any, fallback: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = fallback
    return max(minimum, min(maximum, parsed))


def normalise_observation_config(config: dict[str, Any]) -> dict[str, Any]:
    weather = config.get("weather") if isinstance(config.get("weather"), dict) else {}
    provider = str(weather.get("provider") or DEFAULT_PROVIDER).strip().lower()

    ecowitt = weather.get("ecowitt_push") if isinstance(weather.get("ecowitt_push"), dict) else {}
    wunderground = (
        weather.get("weather_underground")
        if isinstance(weather.get("weather_underground"), dict)
        else {}
    )

    return {
        "provider": provider,
        "ecowitt_push": {
            "path": str(ecowitt.get("path") or "/ecowitt").strip() or "/ecowitt",
            "fresh_seconds": _integer(ecowitt.get("fresh_seconds"), 180, 30, 3600),
        },
        "weather_underground": {
            "station_id": str(wunderground.get("station_id") or "").strip().upper(),
            "api_key_env": str(wunderground.get("api_key_env") or DEFAULT_API_KEY_ENV).strip(),
            "refresh_seconds": _integer(
                wunderground.get("refresh_seconds"),
                DEFAULT_REFRESH_SECONDS,
                30,
                3600,
            ),
            "stale_seconds": _integer(
                wunderground.get("stale_seconds"),
                DEFAULT_STALE_SECONDS,
                60,
                21600,
            ),
            "request_timeout_seconds": _integer(
                wunderground.get("request_timeout_seconds"),
                DEFAULT_TIMEOUT_SECONDS,
                2,
                60,
            ),
            "pressure_history_hours": _integer(
                wunderground.get("pressure_history_hours"),
                DEFAULT_PRESSURE_HISTORY_HOURS,
                3,
                24,
            ),
        },
    }


def observation_configuration_error(settings: dict[str, Any]) -> str | None:
    provider = str(settings.get("provider") or "").strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        return f"Unsupported weather observation provider: {provider or 'empty'}."
    if provider == "ecowitt_push":
        return None

    wunderground = settings.get("weather_underground")
    if not isinstance(wunderground, dict):
        return "Weather Underground settings are missing."

    station_id = str(wunderground.get("station_id") or "").strip()
    if not station_id:
        return "Weather Underground station ID is required."
    if not _STATION_ID.fullmatch(station_id):
        return "Weather Underground station ID contains unsupported characters."

    api_key_env = str(wunderground.get("api_key_env") or "").strip()
    if not _ENVIRONMENT_NAME.fullmatch(api_key_env):
        return "Weather Underground API-key environment variable name is invalid."
    return None


def _weather_underground_query(settings: dict[str, Any], api_key: str) -> dict[str, str]:
    wunderground = settings.get("weather_underground")
    if not isinstance(wunderground, dict):
        raise ValueError("Weather Underground settings are missing.")
    station_id = str(wunderground.get("station_id") or "").strip().upper()
    if not station_id:
        raise ValueError("Weather Underground station ID is required.")
    if not str(api_key or "").strip():
        raise ValueError("Weather Underground API key is required.")
    return {
        "stationId": station_id,
        "format": "json",
        "units": "e",
        "numericPrecision": "decimal",
        "apiKey": str(api_key).strip(),
    }


def build_weather_underground_current_url(settings: dict[str, Any], api_key: str) -> str:
    query = urllib.parse.urlencode(_weather_underground_query(settings, api_key))
    return f"{WEATHER_UNDERGROUND_CURRENT_URL}?{query}"


def build_weather_underground_recent_history_url(settings: dict[str, Any], api_key: str) -> str:
    query = urllib.parse.urlencode(_weather_underground_query(settings, api_key))
    return f"{WEATHER_UNDERGROUND_RECENT_HISTORY_URL}?{query}"


def weather_underground_current_to_dashboard(payload: dict[str, Any]) -> dict[str, Any]:
    observations = payload.get("observations") if isinstance(payload, dict) else None
    if not isinstance(observations, list) or not observations or not isinstance(observations[0], dict):
        raise ValueError("Weather Underground response did not contain a current observation.")

    observation = observations[0]
    imperial = observation.get("imperial") if isinstance(observation.get("imperial"), dict) else {}
    result: dict[str, Any] = {}

    direct_fields = {
        "obsTimeUtc": "dateutc",
        "softwareType": "stationtype",
        "humidity": "humidity",
        "winddir": "winddir",
        "solarRadiation": "solarradiation",
        "uv": "uv",
    }
    for source, destination in direct_fields.items():
        value = observation.get(source)
        if value is not None:
            result[destination] = value

    imperial_fields = {
        "temp": "tempf",
        "windSpeed": "windspeedmph",
        "windGust": "windgustmph",
        "pressure": "pressurein",
        "precipRate": "rainratein",
        "precipTotal": "dailyrainin",
    }
    for source, destination in imperial_fields.items():
        value = imperial.get(source)
        if value is not None:
            result[destination] = value

    station_id = observation.get("stationID")
    if station_id:
        result["model"] = f"Weather Underground PWS {station_id}"
    return result
