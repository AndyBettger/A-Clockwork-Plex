from __future__ import annotations

import json
import os
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Callable

from flask import Flask, jsonify


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

FetchJson = Callable[[str, float], dict[str, Any]]
ConfigProvider = Callable[[], dict[str, Any]]
ObservationWriter = Callable[[dict[str, Any]], Any]
EnvironmentProvider = Callable[[str], str | None]
NowProvider = Callable[[], datetime]


def _now() -> datetime:
    return datetime.now().astimezone()


def _iso(moment: datetime | None) -> str | None:
    return moment.isoformat(timespec="seconds") if moment else None


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.astimezone()


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
        # The dashboard already treats baromrelin as an inHg source key and
        # converts it to the selected hPa/inHg display unit.
        "pressure": "baromrelin",
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


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "A-Clockwork-Plex/weather-observations"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Weather Underground returned HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        raise RuntimeError(f"Weather Underground request failed: {reason or 'network error'}.") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError("Weather Underground returned invalid JSON.") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Weather Underground returned an unexpected response shape.")
    return payload


class WeatherObservationService:
    """Owned remote observation poller; Ecowitt push remains passive."""

    def __init__(
        self,
        load_config: ConfigProvider,
        write_observation: ObservationWriter,
        *,
        fetcher: FetchJson = fetch_json,
        environment: EnvironmentProvider = os.environ.get,
        now_provider: NowProvider = _now,
    ) -> None:
        self._load_config = load_config
        self._write_observation = write_observation
        self._fetcher = fetcher
        self._environment = environment
        self._now = now_provider
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._provider = DEFAULT_PROVIDER
        self._last_attempt_at: datetime | None = None
        self._last_success_at: datetime | None = None
        self._last_observation_at: datetime | None = None
        self._last_error: str | None = None
        self._last_field_count = 0

    def _settings(self) -> dict[str, Any]:
        return normalise_observation_config(self._load_config())

    def _public_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        provider = settings.get("provider")
        if provider == "weather_underground":
            wunderground = settings.get("weather_underground", {})
            return {
                "provider": provider,
                "station_id": wunderground.get("station_id"),
                "api_key_env": wunderground.get("api_key_env"),
                "refresh_seconds": wunderground.get("refresh_seconds"),
                "stale_seconds": wunderground.get("stale_seconds"),
                "request_timeout_seconds": wunderground.get("request_timeout_seconds"),
                "pressure_history_hours": wunderground.get("pressure_history_hours"),
            }
        ecowitt = settings.get("ecowitt_push", {})
        return {
            "provider": "ecowitt_push",
            "path": ecowitt.get("path"),
            "fresh_seconds": ecowitt.get("fresh_seconds"),
        }

    def _status_locked(self, settings: dict[str, Any]) -> str:
        provider = str(settings.get("provider") or DEFAULT_PROVIDER)
        if provider == "ecowitt_push":
            return "push"

        error = observation_configuration_error(settings)
        if error:
            return "configuration_required"

        wunderground = settings.get("weather_underground", {})
        api_key_env = str(wunderground.get("api_key_env") or DEFAULT_API_KEY_ENV)
        if not str(self._environment(api_key_env) or "").strip():
            return "credentials_required"

        if self._last_success_at is None:
            return "error" if self._last_error else "pending"

        age = max((self._now() - self._last_success_at).total_seconds(), 0)
        stale_seconds = int(wunderground.get("stale_seconds", DEFAULT_STALE_SECONDS))
        if age > stale_seconds:
            return "stale"
        if self._last_error:
            return "degraded"
        return "ready"

    def snapshot(self) -> dict[str, Any]:
        settings = self._settings()
        with self._lock:
            provider = str(settings.get("provider") or DEFAULT_PROVIDER)
            error = observation_configuration_error(settings)
            public = self._public_settings(settings)
            credential_available = None
            if provider == "weather_underground" and not error:
                env_name = str(public.get("api_key_env") or DEFAULT_API_KEY_ENV)
                credential_available = bool(str(self._environment(env_name) or "").strip())
            return {
                "ok": self._status_locked(settings) in {"push", "ready", "degraded", "pending"},
                "status": self._status_locked(settings),
                "configured": error is None,
                "provider": provider,
                "settings": public,
                "credential_available": credential_available,
                "last_attempt_at": _iso(self._last_attempt_at),
                "last_success_at": _iso(self._last_success_at),
                "last_observation_at": _iso(self._last_observation_at),
                "last_field_count": self._last_field_count,
                "last_error": error or self._last_error,
                "worker": self.worker_status(),
            }

    def _due_locked(self, settings: dict[str, Any], force: bool) -> bool:
        if force or self._last_attempt_at is None:
            return True
        wunderground = settings.get("weather_underground", {})
        refresh_seconds = int(wunderground.get("refresh_seconds", DEFAULT_REFRESH_SECONDS))
        return self._now() - self._last_attempt_at >= timedelta(seconds=refresh_seconds)

    def refresh(self, force: bool = False) -> dict[str, Any]:
        settings = self._settings()
        provider = str(settings.get("provider") or DEFAULT_PROVIDER)
        with self._lock:
            self._provider = provider
            if provider == "ecowitt_push":
                self._last_error = None
                return self.snapshot()

            config_error = observation_configuration_error(settings)
            if config_error:
                self._last_error = None
                return self.snapshot()

            wunderground = settings.get("weather_underground", {})
            api_key_env = str(wunderground.get("api_key_env") or DEFAULT_API_KEY_ENV)
            api_key = str(self._environment(api_key_env) or "").strip()
            if not api_key:
                self._last_error = None
                return self.snapshot()

            if not self._due_locked(settings, force):
                return self.snapshot()
            self._last_attempt_at = self._now()

        url = build_weather_underground_current_url(settings, api_key)
        timeout = float(wunderground.get("request_timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
        try:
            payload = self._fetcher(url, timeout)
            observation = weather_underground_current_to_dashboard(payload)
            self._write_observation(observation)
        except Exception as exc:
            message = str(exc).replace(api_key, "[redacted]")
            with self._lock:
                self._last_error = message or "Weather Underground refresh failed."
            return self.snapshot()

        observed_at = _parse_time(observation.get("dateutc"))
        with self._lock:
            self._last_success_at = self._now()
            self._last_observation_at = observed_at
            self._last_field_count = len(observation)
            self._last_error = None
        return self.snapshot()

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._worker_loop,
                name="weather-observations",
                daemon=True,
            )
            self._thread.start()

    def shutdown(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        self._wake_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=timeout)

    def wake(self) -> None:
        self._wake_event.set()

    def worker_status(self) -> dict[str, Any]:
        thread = self._thread
        return {
            "running": bool(thread and thread.is_alive()),
            "name": thread.name if thread else None,
        }

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.refresh(force=False)
            except Exception as exc:  # Defensive: the daemon must remain alive.
                with self._lock:
                    self._last_error = str(exc) or "Weather observation worker failed."
            self._wake_event.wait(timeout=30)
            self._wake_event.clear()


def register_weather_observation_api(app: Flask, service: WeatherObservationService) -> None:
    if "api_weather_observations" in app.view_functions:
        return

    @app.route("/api/weather/observations", methods=["GET", "POST"])
    def api_weather_observations():
        if service.snapshot().get("provider") == "ecowitt_push":
            return jsonify(service.snapshot())
        if flask_request_method() == "POST":
            return jsonify(service.refresh(force=True))
        return jsonify(service.snapshot())


def flask_request_method() -> str:
    # Kept behind a tiny helper so tests can exercise service logic without a
    # Flask request context.
    from flask import request

    return request.method
