from __future__ import annotations

import json
import re
import urllib.error
from copy import deepcopy
from typing import Any, Callable
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from flask import Flask, jsonify, request

try:
    from .weather_forecast import (
        WeatherForecastService,
        forecast_configuration_error,
        normalise_forecast_config,
    )
except ImportError:  # Supports direct execution imports.
    from weather_forecast import (
        WeatherForecastService,
        forecast_configuration_error,
        normalise_forecast_config,
    )


ConfigProvider = Callable[[], dict[str, Any]]
ConfigSaver = Callable[[dict[str, Any]], None]
LocationSearch = Callable[[str], list[dict[str, Any]]]

_GEOCODING_ENDPOINT = "https://geocoding-api.open-meteo.com/v1/search"
_POSTCODES_IO_ENDPOINT = "https://api.postcodes.io/postcodes"
_GEOCODING_USER_AGENT = "A-Clockwork-Plex/forecast-location"
_UK_POSTCODE_RE = re.compile(
    r"^(?:GIR\s?0AA|[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})$",
    re.IGNORECASE,
)


def public_forecast_config(config: dict[str, Any]) -> dict[str, Any]:
    settings = normalise_forecast_config(config)
    return {
        "enabled": settings["enabled"],
        "provider": settings["provider"],
        "latitude": settings["latitude"],
        "longitude": settings["longitude"],
        "timezone": settings["timezone"],
        "forecast_days": settings["forecast_days"],
        "refresh_minutes": settings["refresh_minutes"],
        "request_timeout_seconds": settings["request_timeout_seconds"],
        "stale_after_hours": settings["stale_after_hours"],
    }


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _location_query(value: Any) -> str:
    query = " ".join(str(value or "").split())
    if len(query) < 2:
        raise ValueError("Enter at least 2 characters of a town, city or postcode.")
    if len(query) > 120:
        raise ValueError("Location search must be 120 characters or fewer.")
    return query


def _text(value: Any) -> str:
    if isinstance(value, (dict, list, tuple, set)):
        return ""
    return str(value or "").strip()


def _looks_like_uk_postcode(query: str) -> bool:
    return bool(_UK_POSTCODE_RE.fullmatch(query.strip().upper()))


def _sanitise_open_meteo_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_results = payload.get("results") or []
    if not isinstance(raw_results, list):
        raise OSError("Forecast location service returned invalid results.")

    results: list[dict[str, Any]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        try:
            latitude = float(item["latitude"])
            longitude = float(item["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            continue

        name = _text(item.get("name"))
        if not name:
            continue

        raw_postcodes = item.get("postcodes")
        if isinstance(raw_postcodes, list):
            postcodes = [
                text
                for text in (_text(value) for value in raw_postcodes[:5])
                if text
            ]
        else:
            postcode = _text(raw_postcodes)
            postcodes = [postcode] if postcode else []

        results.append(
            {
                "name": name,
                "latitude": latitude,
                "longitude": longitude,
                "timezone": _text(item.get("timezone")),
                "country": _text(item.get("country")),
                "country_code": _text(item.get("country_code")).upper(),
                "admin1": _text(item.get("admin1")),
                "admin2": _text(item.get("admin2")),
                "postcodes": postcodes,
            }
        )

    return results


def _lookup_uk_postcode(
    query: str,
    *,
    opener,
    timeout: int,
) -> list[dict[str, Any]]:
    compact = re.sub(r"\s+", "", query).upper()
    request_object = Request(
        f"{_POSTCODES_IO_ENDPOINT}/{quote(compact, safe='')}",
        headers={
            "Accept": "application/json",
            "User-Agent": _GEOCODING_USER_AGENT,
        },
    )

    try:
        with opener(request_object, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return []
        raise OSError("UK postcode service is unavailable.") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OSError("UK postcode service is unavailable.") from exc

    if not isinstance(payload, dict):
        raise OSError("UK postcode service returned invalid data.")
    item = payload.get("result")
    if not isinstance(item, dict):
        return []

    try:
        latitude = float(item["latitude"])
        longitude = float(item["longitude"])
    except (KeyError, TypeError, ValueError):
        return []
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return []

    postcode = _text(item.get("postcode")) or query.upper()
    home_country = _text(item.get("country"))
    return [
        {
            "name": postcode,
            "latitude": latitude,
            "longitude": longitude,
            "timezone": "Europe/London",
            "country": "United Kingdom",
            "country_code": "GB",
            "admin1": home_country,
            "admin2": _text(item.get("admin_district")) or _text(item.get("region")),
            "postcodes": [postcode],
        }
    ]


def search_forecast_locations(
    query: str,
    *,
    opener=None,
    timeout_seconds: int = 5,
    count: int = 8,
) -> list[dict[str, Any]]:
    """Return a small, sanitised forecast-location result set.

    General place search uses Open-Meteo geocoding. If a full UK postcode has
    no Open-Meteo match, Postcodes.io is used as a postcode-specific fallback.
    This remains deliberately read-only: selecting a result in Settings only
    stages the existing latitude/longitude/timezone controls; normal Settings
    save remains the sole persistence path.
    """

    clean_query = _location_query(query)
    result_count = max(1, min(10, int(count)))
    timeout = max(1, min(15, int(timeout_seconds)))
    params = urlencode(
        {
            "name": clean_query,
            "count": result_count,
            "language": "en",
            "format": "json",
        }
    )
    request_object = Request(
        f"{_GEOCODING_ENDPOINT}?{params}",
        headers={
            "Accept": "application/json",
            "User-Agent": _GEOCODING_USER_AGENT,
        },
    )
    open_url = opener or urlopen

    try:
        with open_url(request_object, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OSError("Forecast location service is unavailable.") from exc

    if not isinstance(payload, dict):
        raise OSError("Forecast location service returned invalid data.")
    if payload.get("error"):
        reason = _text(payload.get("reason")) or "Forecast location search failed."
        raise OSError(reason)

    results = _sanitise_open_meteo_results(payload)
    if results or not _looks_like_uk_postcode(clean_query):
        return results
    return _lookup_uk_postcode(clean_query, opener=open_url, timeout=timeout)


def submitted_forecast_config(
    current_config: dict[str, Any],
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("Forecast settings must be a JSON object.")

    config = deepcopy(current_config)
    weather = config.setdefault("weather", {})
    if not isinstance(weather, dict):
        weather = {}
        config["weather"] = weather
    existing = weather.get("forecast")
    forecast = deepcopy(existing) if isinstance(existing, dict) else {}

    forecast["enabled"] = _boolean(payload.get("enabled", forecast.get("enabled", False)))
    forecast["provider"] = "open_meteo"
    forecast["timezone"] = str(
        payload.get("timezone", forecast.get("timezone", "Europe/London"))
    ).strip() or "Europe/London"

    for key in ("latitude", "longitude"):
        raw_value = payload.get(key, forecast.get(key))
        if raw_value is None or raw_value == "":
            forecast[key] = None
            continue
        if isinstance(raw_value, (dict, list, tuple, set)):
            raise ValueError(f"Forecast {key} must be a number.")
        try:
            forecast[key] = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Forecast {key} must be a number.") from exc

    for key in (
        "forecast_days",
        "refresh_minutes",
        "request_timeout_seconds",
        "stale_after_hours",
    ):
        if key not in payload:
            continue
        raw_value = payload[key]
        if isinstance(raw_value, (dict, list, tuple, set, bool)):
            raise ValueError(f"Forecast {key.replace('_', ' ')} must be a whole number.")
        try:
            forecast[key] = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Forecast {key.replace('_', ' ')} must be a whole number.") from exc

    weather["forecast"] = forecast
    settings = normalise_forecast_config(config)
    error = forecast_configuration_error(settings)
    if settings["enabled"] and error:
        raise ValueError(error)

    # Persist bounded normalised values so config.json mirrors runtime truth.
    normalised = public_forecast_config(config)
    weather["forecast"] = normalised
    return config, normalised


def register_weather_forecast_settings_api(
    app: Flask,
    service: WeatherForecastService,
    load_config: ConfigProvider,
    save_config: ConfigSaver,
    *,
    location_search: LocationSearch = search_forecast_locations,
) -> None:
    if "api_weather_forecast_config" in app.view_functions:
        return

    @app.route("/api/weather/forecast/locations", methods=["GET"])
    def api_weather_forecast_locations():
        query = request.args.get("q", "")
        try:
            clean_query = _location_query(query)
            results = location_search(clean_query)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except OSError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 502

        return jsonify({"ok": True, "query": clean_query, "results": results})

    @app.route("/api/weather/forecast/config", methods=["GET", "POST"])
    def api_weather_forecast_config():
        if request.method == "GET":
            config = load_config()
            return jsonify(
                {
                    "ok": True,
                    "forecast": public_forecast_config(config),
                    "status": service.snapshot(),
                }
            )

        payload = request.get_json(silent=True)
        try:
            config, forecast = submitted_forecast_config(load_config(), payload)
            save_config(config)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except OSError as exc:
            return jsonify({"ok": False, "error": f"Could not save forecast settings: {exc}"}), 500

        service.wake()
        status = service.refresh(force=forecast["enabled"])
        return jsonify(
            {
                "ok": True,
                "forecast": forecast,
                "status": status,
                "message": (
                    "Forecast settings saved and refreshed."
                    if forecast["enabled"]
                    else "Forecast settings saved; online forecasts are disabled."
                ),
            }
        )
