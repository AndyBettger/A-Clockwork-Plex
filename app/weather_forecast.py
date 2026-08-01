from __future__ import annotations

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from flask import Flask, jsonify


OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CACHE_SCHEMA_VERSION = 1
DEFAULT_TIMEZONE = "Europe/London"
DEFAULT_FORECAST_DAYS = 7
DEFAULT_REFRESH_MINUTES = 30
DEFAULT_TIMEOUT_SECONDS = 8
DEFAULT_STALE_HOURS = 6

FetchJson = Callable[[str, float], dict[str, Any]]
ConfigProvider = Callable[[], dict[str, Any]]
NowProvider = Callable[[], datetime]


WMO_CODES: dict[int, tuple[str, str]] = {
    0: ("Clear sky", "clear"),
    1: ("Mainly clear", "mostly-clear"),
    2: ("Partly cloudy", "partly-cloudy"),
    3: ("Overcast", "cloudy"),
    45: ("Fog", "fog"),
    48: ("Rime fog", "fog"),
    51: ("Light drizzle", "drizzle"),
    53: ("Drizzle", "drizzle"),
    55: ("Heavy drizzle", "drizzle"),
    56: ("Light freezing drizzle", "freezing-rain"),
    57: ("Heavy freezing drizzle", "freezing-rain"),
    61: ("Light rain", "rain"),
    63: ("Rain", "rain"),
    65: ("Heavy rain", "heavy-rain"),
    66: ("Light freezing rain", "freezing-rain"),
    67: ("Heavy freezing rain", "freezing-rain"),
    71: ("Light snow", "snow"),
    73: ("Snow", "snow"),
    75: ("Heavy snow", "heavy-snow"),
    77: ("Snow grains", "snow"),
    80: ("Light rain showers", "showers"),
    81: ("Rain showers", "showers"),
    82: ("Heavy rain showers", "heavy-showers"),
    85: ("Light snow showers", "snow-showers"),
    86: ("Heavy snow showers", "snow-showers"),
    95: ("Thunderstorm", "thunderstorm"),
    96: ("Thunderstorm with hail", "thunderstorm-hail"),
    99: ("Severe thunderstorm with hail", "thunderstorm-hail"),
}


def _now() -> datetime:
    return datetime.now().astimezone()


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.astimezone()


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any, fallback: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = fallback
    return max(minimum, min(maximum, parsed))


def _boolean(value: Any, fallback: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return fallback


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


def weather_code(code: Any) -> dict[str, Any]:
    numeric = _integer(code, -1, -1, 999)
    label, tone = WMO_CODES.get(numeric, ("Unknown conditions", "unknown"))
    return {"code": None if numeric < 0 else numeric, "label": label, "tone": tone}


def normalise_forecast_config(config: dict[str, Any]) -> dict[str, Any]:
    weather = config.get("weather") if isinstance(config.get("weather"), dict) else {}
    forecast = weather.get("forecast") if isinstance(weather.get("forecast"), dict) else {}
    units = weather.get("units") if isinstance(weather.get("units"), dict) else {}

    latitude = _number(forecast.get("latitude"))
    longitude = _number(forecast.get("longitude"))
    provider = str(forecast.get("provider") or "open_meteo").strip().lower()
    timezone_name = str(forecast.get("timezone") or DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    temperature = str(units.get("temperature") or "c").strip().lower()
    wind = str(units.get("wind") or "mph").strip().lower()
    rain = str(units.get("rain") or "mm").strip().lower()

    return {
        "enabled": _boolean(forecast.get("enabled"), False),
        "provider": provider,
        "latitude": latitude,
        "longitude": longitude,
        "timezone": timezone_name,
        "forecast_days": _integer(
            forecast.get("forecast_days"),
            DEFAULT_FORECAST_DAYS,
            1,
            16,
        ),
        "refresh_minutes": _integer(
            forecast.get("refresh_minutes"),
            DEFAULT_REFRESH_MINUTES,
            10,
            360,
        ),
        "request_timeout_seconds": _integer(
            forecast.get("request_timeout_seconds"),
            DEFAULT_TIMEOUT_SECONDS,
            2,
            30,
        ),
        "stale_after_hours": _integer(
            forecast.get("stale_after_hours"),
            DEFAULT_STALE_HOURS,
            1,
            72,
        ),
        "temperature_unit": "fahrenheit" if temperature == "f" else "celsius",
        "wind_speed_unit": (
            "kmh" if wind == "kmh" else "ms" if wind in {"m/s", "ms", "mps"} else "mph"
        ),
        "precipitation_unit": "inch" if rain == "in" else "mm",
    }


def forecast_configuration_error(settings: dict[str, Any]) -> str | None:
    if not settings.get("enabled"):
        return "Forecast provider is disabled."
    if settings.get("provider") != "open_meteo":
        return f"Unsupported forecast provider: {settings.get('provider') or 'unknown'}"
    latitude = settings.get("latitude")
    longitude = settings.get("longitude")
    if latitude is None or longitude is None:
        return "Forecast latitude and longitude have not been configured."
    if not -90 <= float(latitude) <= 90:
        return "Forecast latitude must be between -90 and 90."
    if not -180 <= float(longitude) <= 180:
        return "Forecast longitude must be between -180 and 180."
    return None


def build_open_meteo_url(settings: dict[str, Any]) -> str:
    query = {
        "latitude": settings["latitude"],
        "longitude": settings["longitude"],
        "timezone": settings["timezone"],
        "forecast_days": settings["forecast_days"],
        "temperature_unit": settings["temperature_unit"],
        "wind_speed_unit": settings["wind_speed_unit"],
        "precipitation_unit": settings["precipitation_unit"],
        "current": ",".join(
            [
                "temperature_2m",
                "apparent_temperature",
                "precipitation",
                "weather_code",
                "wind_speed_10m",
                "wind_gusts_10m",
            ]
        ),
        "hourly": ",".join(
            [
                "temperature_2m",
                "apparent_temperature",
                "precipitation_probability",
                "precipitation",
                "weather_code",
                "wind_speed_10m",
                "wind_gusts_10m",
            ]
        ),
        "daily": ",".join(
            [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "precipitation_probability_max",
                "wind_speed_10m_max",
                "wind_gusts_10m_max",
                "sunrise",
                "sunset",
            ]
        ),
    }
    return f"{OPEN_METEO_FORECAST_URL}?{urllib.parse.urlencode(query)}"


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "A-Clockwork-Plex/1 weather-forecast",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Open-Meteo returned HTTP {exc.code}: {detail or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Open-Meteo: {exc.reason}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read Open-Meteo response: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Open-Meteo returned a non-object JSON response.")
    if payload.get("error"):
        raise RuntimeError(str(payload.get("reason") or "Open-Meteo rejected the request."))
    return payload


def _series_value(series: dict[str, Any], name: str, index: int) -> Any:
    values = series.get(name)
    if not isinstance(values, list) or index >= len(values):
        return None
    return values[index]


def _units(payload: dict[str, Any], section: str) -> dict[str, Any]:
    value = payload.get(f"{section}_units")
    return value if isinstance(value, dict) else {}


def normalise_open_meteo_payload(
    payload: dict[str, Any],
    settings: dict[str, Any],
    fetched_at: datetime,
) -> dict[str, Any]:
    current = payload.get("current") if isinstance(payload.get("current"), dict) else {}
    current_units = _units(payload, "current")
    hourly = payload.get("hourly") if isinstance(payload.get("hourly"), dict) else {}
    hourly_units = _units(payload, "hourly")
    daily = payload.get("daily") if isinstance(payload.get("daily"), dict) else {}
    daily_units = _units(payload, "daily")

    hourly_times = hourly.get("time") if isinstance(hourly.get("time"), list) else []
    hourly_items: list[dict[str, Any]] = []
    for index, valid_at in enumerate(hourly_times[:48]):
        condition = weather_code(_series_value(hourly, "weather_code", index))
        hourly_items.append(
            {
                "valid_at": valid_at,
                "temperature": _series_value(hourly, "temperature_2m", index),
                "apparent_temperature": _series_value(hourly, "apparent_temperature", index),
                "precipitation_probability": _series_value(
                    hourly, "precipitation_probability", index
                ),
                "precipitation": _series_value(hourly, "precipitation", index),
                "wind_speed": _series_value(hourly, "wind_speed_10m", index),
                "wind_gust": _series_value(hourly, "wind_gusts_10m", index),
                "condition": condition,
            }
        )

    daily_times = daily.get("time") if isinstance(daily.get("time"), list) else []
    daily_items: list[dict[str, Any]] = []
    for index, date_value in enumerate(daily_times):
        condition = weather_code(_series_value(daily, "weather_code", index))
        daily_items.append(
            {
                "date": date_value,
                "temperature_max": _series_value(daily, "temperature_2m_max", index),
                "temperature_min": _series_value(daily, "temperature_2m_min", index),
                "precipitation_sum": _series_value(daily, "precipitation_sum", index),
                "precipitation_probability_max": _series_value(
                    daily, "precipitation_probability_max", index
                ),
                "wind_speed_max": _series_value(daily, "wind_speed_10m_max", index),
                "wind_gust_max": _series_value(daily, "wind_gusts_10m_max", index),
                "sunrise": _series_value(daily, "sunrise", index),
                "sunset": _series_value(daily, "sunset", index),
                "condition": condition,
            }
        )

    current_condition = weather_code(current.get("weather_code"))
    return {
        "provider": "open_meteo",
        "provider_label": "Open-Meteo",
        "attribution": {
            "label": "Weather data by Open-Meteo.com",
            "url": "https://open-meteo.com/",
            "licence": "CC BY 4.0",
        },
        "requested_location": {
            "latitude": settings["latitude"],
            "longitude": settings["longitude"],
            "timezone": settings["timezone"],
        },
        "resolved_location": {
            "latitude": payload.get("latitude"),
            "longitude": payload.get("longitude"),
            "elevation": payload.get("elevation"),
            "timezone": payload.get("timezone"),
            "timezone_abbreviation": payload.get("timezone_abbreviation"),
        },
        "fetched_at": _iso(fetched_at),
        "current": {
            "valid_at": current.get("time"),
            "temperature": current.get("temperature_2m"),
            "apparent_temperature": current.get("apparent_temperature"),
            "precipitation": current.get("precipitation"),
            "wind_speed": current.get("wind_speed_10m"),
            "wind_gust": current.get("wind_gusts_10m"),
            "condition": current_condition,
        },
        "hourly": hourly_items,
        "daily": daily_items,
        "units": {
            "temperature": current_units.get("temperature_2m")
            or hourly_units.get("temperature_2m")
            or daily_units.get("temperature_2m_max"),
            "precipitation": current_units.get("precipitation")
            or hourly_units.get("precipitation")
            or daily_units.get("precipitation_sum"),
            "precipitation_probability": hourly_units.get("precipitation_probability")
            or daily_units.get("precipitation_probability_max"),
            "wind_speed": current_units.get("wind_speed_10m")
            or hourly_units.get("wind_speed_10m")
            or daily_units.get("wind_speed_10m_max"),
        },
    }


def _empty_cache() -> dict[str, Any]:
    return {
        "schema_version": CACHE_SCHEMA_VERSION,
        "provider": "open_meteo",
        "status": "disabled",
        "configured": False,
        "enabled": False,
        "fetched_at": None,
        "expires_at": None,
        "stale_after": None,
        "last_attempt_at": None,
        "last_error": None,
        "forecast": None,
    }


class WeatherForecastService:
    """Own forecast fetching, disk caching and stale-data fallback."""

    def __init__(
        self,
        load_config: ConfigProvider,
        cache_path: Path,
        *,
        fetcher: FetchJson = fetch_json,
        now_provider: NowProvider = _now,
    ) -> None:
        self._load_config = load_config
        self._cache_path = cache_path
        self._fetcher = fetcher
        self._now = now_provider
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._cache = self._load_cache()

    def _load_cache(self) -> dict[str, Any]:
        if not self._cache_path.exists():
            return _empty_cache()
        try:
            payload = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return _empty_cache()
        if not isinstance(payload, dict):
            return _empty_cache()
        cache = _empty_cache()
        cache.update(payload)
        return cache

    def _save_cache(self) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._cache_path.with_suffix(self._cache_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self._cache, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self._cache_path)

    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop_event.clear()
        self._worker = threading.Thread(
            target=self._worker_loop,
            name="weather-forecast",
            daemon=True,
        )
        self._worker.start()

    def shutdown(self, timeout: float = 3.0) -> None:
        self._stop_event.set()
        self._wake_event.set()
        worker = self._worker
        if worker and worker.is_alive():
            worker.join(timeout=max(0.1, timeout))

    def wake(self) -> None:
        self._wake_event.set()

    def worker_status(self) -> dict[str, Any]:
        worker = self._worker
        return {"running": bool(worker and worker.is_alive())}

    def _due(self, now: datetime) -> bool:
        expires_at = _parse_time(self._cache.get("expires_at"))
        return expires_at is None or now >= expires_at

    def refresh(self, *, force: bool = False) -> dict[str, Any]:
        config = self._load_config()
        settings = normalise_forecast_config(config)
        now = self._now()
        configuration_error = forecast_configuration_error(settings)

        with self._lock:
            self._cache["provider"] = settings["provider"]
            self._cache["enabled"] = settings["enabled"]
            self._cache["configured"] = configuration_error is None

            if configuration_error:
                self._cache["status"] = (
                    "disabled" if not settings["enabled"] else "configuration_required"
                )
                self._cache["last_error"] = configuration_error
                self._save_cache()
                return self.snapshot()

            if not force and not self._due(now) and self._cache.get("forecast"):
                return self.snapshot()

            self._cache["last_attempt_at"] = _iso(now)

        try:
            url = build_open_meteo_url(settings)
            payload = self._fetcher(url, float(settings["request_timeout_seconds"]))
            forecast = normalise_open_meteo_payload(payload, settings, now)
        except Exception as exc:
            with self._lock:
                self._cache["last_error"] = str(exc)
                self._cache["status"] = "stale" if self._cache.get("forecast") else "error"
                self._save_cache()
                return self.snapshot()

        expires_at = now + timedelta(minutes=int(settings["refresh_minutes"]))
        stale_after = now + timedelta(hours=int(settings["stale_after_hours"]))
        with self._lock:
            self._cache.update(
                {
                    "schema_version": CACHE_SCHEMA_VERSION,
                    "provider": "open_meteo",
                    "status": "ready",
                    "configured": True,
                    "enabled": True,
                    "fetched_at": _iso(now),
                    "expires_at": _iso(expires_at),
                    "stale_after": _iso(stale_after),
                    "last_attempt_at": _iso(now),
                    "last_error": None,
                    "forecast": forecast,
                }
            )
            self._save_cache()
            return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            output = deepcopy(self._cache)
        now = self._now()
        stale_after = _parse_time(output.get("stale_after"))
        output["stale"] = bool(
            output.get("forecast") and stale_after is not None and now >= stale_after
        )
        if output["stale"] and output.get("status") == "ready":
            output["status"] = "stale"
        output["refresh_due"] = self._due(now)
        output["worker"] = self.worker_status()
        return output

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.refresh()
            except Exception as exc:
                with self._lock:
                    self._cache["last_error"] = str(exc)
                    self._cache["status"] = "stale" if self._cache.get("forecast") else "error"
                    try:
                        self._save_cache()
                    except OSError:
                        pass
            self._wake_event.wait(60)
            self._wake_event.clear()


def register_weather_forecast_api(app: Flask, service: WeatherForecastService) -> None:
    if "api_weather_forecast" in app.view_functions:
        return

    @app.route("/api/weather/forecast", methods=["GET", "POST"])
    def api_weather_forecast():
        if app.request_class.environ_property if False else False:  # pragma: no cover
            pass
        from flask import request

        if request.method == "POST":
            return jsonify(service.refresh(force=True))
        return jsonify(service.snapshot())
