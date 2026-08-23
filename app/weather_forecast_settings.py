from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

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
) -> None:
    if "api_weather_forecast_config" in app.view_functions:
        return

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
