from __future__ import annotations

"""Supplemental Weather Underground daily-rain history and cached totals."""

import json
import math
import os
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

WEATHER_UNDERGROUND_DAILY_HISTORY_URL = "https://api.weather.com/v2/pws/history/daily"
DEFAULT_PERIOD = "last_7_days"
SUPPORTED_PERIODS = {"today", "last_7_days", "current_month", "current_year"}
PERIOD_LABELS = {
    "today": "Rain today",
    "last_7_days": "Rain last 7 days",
    "current_month": "Rain this month",
    "current_year": "Rain this year",
}
DEFAULT_TIMEOUT_SECONDS = 8
DEFAULT_REFRESH_SECONDS = 900
MAX_RANGE_DAYS = 31


def normalise_rainfall_period(value: Any) -> str:
    period = str(value or DEFAULT_PERIOD).strip().lower()
    return period if period in SUPPORTED_PERIODS else DEFAULT_PERIOD


def public_rainfall_config(config: dict[str, Any]) -> dict[str, str]:
    weather = config.get("weather") if isinstance(config.get("weather"), dict) else {}
    rainfall = weather.get("historical_rainfall") if isinstance(weather.get("historical_rainfall"), dict) else {}
    return {"period": normalise_rainfall_period(rainfall.get("period"))}


def submitted_rainfall_config(config: dict[str, Any], payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Historical rainfall settings must be a JSON object.")
    raw_period = str(payload.get("period", DEFAULT_PERIOD)).strip().lower()
    if raw_period not in SUPPORTED_PERIODS:
        raise ValueError("Historical rainfall period must be today, last_7_days, current_month or current_year.")
    updated = json.loads(json.dumps(config))
    weather = updated.setdefault("weather", {})
    rainfall = weather.setdefault("historical_rainfall", {})
    rainfall["period"] = raw_period
    return updated


def period_dates(period: str, today: date) -> list[date]:
    period = normalise_rainfall_period(period)
    if period == "today":
        start = today
    elif period == "last_7_days":
        start = today - timedelta(days=6)
    elif period == "current_month":
        start = today.replace(day=1)
    else:
        start = today.replace(month=1, day=1)
    return [start + timedelta(days=offset) for offset in range((today - start).days + 1)]


def contiguous_ranges(days: list[date], max_days: int = MAX_RANGE_DAYS) -> list[tuple[date, date]]:
    ordered = sorted(set(days))
    if not ordered:
        return []
    ranges: list[tuple[date, date]] = []
    start = previous = ordered[0]
    for current in ordered[1:]:
        contiguous = current == previous + timedelta(days=1)
        within_limit = (current - start).days < max_days
        if contiguous and within_limit:
            previous = current
            continue
        ranges.append((start, previous))
        start = previous = current
    ranges.append((start, previous))
    return ranges


def _history_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("observations", "summaries", "dailySummaries", "daily"):
        records = payload.get(key)
        if isinstance(records, list):
            return [item for item in records if isinstance(item, dict)]
    if any(key in payload for key in ("obsTimeLocal", "obsTimeUtc", "epoch")):
        return [payload]
    return []


def _record_date(record: dict[str, Any]) -> date | None:
    local = str(record.get("obsTimeLocal") or "").strip()
    if len(local) >= 10:
        try:
            return date.fromisoformat(local[:10])
        except ValueError:
            pass
    utc = str(record.get("obsTimeUtc") or "").strip()
    if len(utc) >= 10:
        try:
            return date.fromisoformat(utc[:10])
        except ValueError:
            pass
    try:
        epoch = float(record.get("epoch"))
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(epoch).date()


def daily_precip_totals(payload: Any) -> dict[date, float]:
    totals: dict[date, float] = {}
    for record in _history_records(payload):
        record_day = _record_date(record)
        imperial = record.get("imperial") if isinstance(record.get("imperial"), dict) else {}
        try:
            total = float(imperial.get("precipTotal"))
        except (TypeError, ValueError):
            continue
        if record_day is not None and math.isfinite(total) and total >= 0:
            totals[record_day] = total
    return totals


def fetch_json(url: str, params: dict[str, Any], timeout: int) -> Any:
    request = Request(f"{url}?{urlencode(params)}", headers={"User-Agent": "A-Clockwork-Plex/1.0"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS provider URL
        return json.loads(response.read().decode("utf-8"))


def _load_cache(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "stations": {}}
    if not isinstance(payload, dict) or payload.get("version") != 1 or not isinstance(payload.get("stations"), dict):
        return {"version": 1, "stations": {}}
    return payload


def _save_cache(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _valid_cached_total(value: Any) -> bool:
    try:
        total = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(total) and total >= 0


class WeatherRainfallHistoryService:
    def __init__(
        self,
        load_config: Callable[[], dict[str, Any]],
        cache_path: Path,
        *,
        current_weather: Callable[[], dict[str, Any]] | None = None,
        environment: Callable[[str], str | None] = os.environ.get,
        fetcher: Callable[[str, dict[str, Any], int], Any] = fetch_json,
        today_provider: Callable[[], date] = date.today,
        refresh_seconds: int = DEFAULT_REFRESH_SECONDS,
    ) -> None:
        self._load_config = load_config
        self._cache_path = Path(cache_path)
        self._current_weather = current_weather or (lambda: {})
        self._environment = environment
        self._fetcher = fetcher
        self._today = today_provider
        self._refresh_seconds = max(60, int(refresh_seconds))
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._status: dict[str, Any] = {
            "status": "pending",
            "last_error": None,
            "last_refresh_at": None,
            "last_success_at": None,
            "fetched_ranges": 0,
        }

    def _provider_config(self) -> tuple[str, str, int]:
        config = self._load_config()
        weather = config.get("weather") if isinstance(config.get("weather"), dict) else {}
        wu = weather.get("weather_underground") if isinstance(weather.get("weather_underground"), dict) else {}
        station_id = str(wu.get("station_id") or "").strip()
        env_name = str(wu.get("api_key_env") or "WEATHER_UNDERGROUND_API_KEY").strip()
        timeout = int(wu.get("request_timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)
        return station_id, str(self._environment(env_name) or "").strip(), max(2, min(60, timeout))

    def _station_days(self, cache: dict[str, Any], station_id: str) -> dict[str, Any]:
        stations = cache.setdefault("stations", {})
        station = stations.setdefault(station_id, {"days": {}})
        days = station.setdefault("days", {})
        if not isinstance(days, dict):
            days = {}
            station["days"] = days
        return days

    def wake(self) -> None:
        self._wake.set()

    def refresh(self, force: bool = False) -> dict[str, Any]:
        del force  # Valid completed-day totals are immutable; missing/invalid dates remain retryable.
        config = self._load_config()
        period = public_rainfall_config(config)["period"]
        today = self._today()
        station_id, api_key, timeout = self._provider_config()
        now_text = datetime.now().isoformat(timespec="seconds")

        # Today is deliberately a live-observation calculation, not a historical
        # provider request. This keeps the option useful with Ecowitt Push and
        # avoids asking Weather Underground history for an incomplete day.
        if period == "today":
            with self._lock:
                self._status.update(
                    status="ready",
                    last_error=None,
                    last_refresh_at=now_text,
                    last_success_at=now_text,
                    fetched_ranges=0,
                )
            return self.snapshot()

        if not station_id:
            with self._lock:
                self._status.update(status="configuration_required", last_error="Weather Underground station ID is required for historical rainfall.", last_refresh_at=now_text)
            return self.snapshot()
        if not api_key:
            with self._lock:
                self._status.update(status="credentials_required", last_error="Weather Underground API key is required for historical rainfall.", last_refresh_at=now_text)
            return self.snapshot()

        cache = _load_cache(self._cache_path)
        days = self._station_days(cache, station_id)
        required_past = [day for day in period_dates(period, today) if day < today]
        missing = [day for day in required_past if not _valid_cached_total(days.get(day.isoformat()))]
        fetched_ranges = 0
        try:
            for start, end in contiguous_ranges(missing):
                params = {
                    "stationId": station_id,
                    "format": "json",
                    "units": "e",
                    "numericPrecision": "decimal",
                    "startDate": start.strftime("%Y%m%d"),
                    "endDate": end.strftime("%Y%m%d"),
                    "apiKey": api_key,
                }
                payload = self._fetcher(WEATHER_UNDERGROUND_DAILY_HISTORY_URL, params, timeout)
                totals = daily_precip_totals(payload)
                cursor = start
                while cursor <= end:
                    key = cursor.isoformat()
                    if cursor in totals:
                        days[key] = totals[cursor]
                    else:
                        # Never turn a transient provider omission into a permanent
                        # cache miss. The aggregate remains incomplete for this
                        # evaluation and the date is retried on a later refresh.
                        days.pop(key, None)
                    cursor += timedelta(days=1)
                fetched_ranges += 1
            if missing:
                _save_cache(self._cache_path, cache)
            with self._lock:
                self._status.update(
                    status="ready",
                    last_error=None,
                    last_refresh_at=now_text,
                    last_success_at=now_text,
                    fetched_ranges=fetched_ranges,
                )
        except Exception as exc:  # Supplemental history must never take current observations down.
            message = str(exc).replace(api_key, "[redacted]") if api_key else str(exc)
            with self._lock:
                self._status.update(status="error", last_error=message, last_refresh_at=now_text, fetched_ranges=fetched_ranges)
        return self.snapshot()

    def calculation(self, weather: dict[str, Any] | None = None) -> dict[str, Any]:
        config = self._load_config()
        period = public_rainfall_config(config)["period"]
        label = PERIOD_LABELS[period]
        today = self._today()
        station_id, _api_key, _timeout = self._provider_config()
        cache = _load_cache(self._cache_path)
        days = self._station_days(cache, station_id) if station_id else {}
        live_weather = weather if isinstance(weather, dict) else self._current_weather()
        required = period_dates(period, today)
        values: list[float] = []
        unavailable: list[str] = []
        for day in required:
            if day == today:
                try:
                    value = float(live_weather.get("dailyrainin"))
                except (TypeError, ValueError):
                    value = math.nan
            else:
                raw = days.get(day.isoformat())
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    value = math.nan
            if math.isfinite(value) and value >= 0:
                values.append(value)
            else:
                unavailable.append(day.isoformat())
        return {
            "period": period,
            "label": label,
            "total_in": round(sum(values), 4) if not unavailable else None,
            "complete": not unavailable,
            "unavailable_dates": unavailable,
            "required_days": len(required),
            "available_days": len(values),
        }

    def snapshot(self) -> dict[str, Any]:
        calculation = self.calculation()
        station_id, _api_key, _timeout = self._provider_config()
        cache = _load_cache(self._cache_path)
        days = self._station_days(cache, station_id) if station_id else {}
        with self._lock:
            status = dict(self._status)
        status.update(calculation)
        status["cached_days"] = sum(1 for value in days.values() if _valid_cached_total(value))
        return status

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="weather-rainfall-history", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            self.refresh()
            self._wake.wait(self._refresh_seconds)
            self._wake.clear()

    def shutdown(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)


def register_weather_rainfall(app: Any, dashboard: Any, service: WeatherRainfallHistoryService) -> None:
    try:
        from flask import jsonify
    except ImportError:  # pragma: no cover - Flask is an application dependency.
        return

    if not getattr(dashboard.weather_detail_data, "_acp_rainfall_history", False):
        base_weather_detail = dashboard.weather_detail_data

        def weather_detail_with_historical_rainfall(
            config: dict[str, Any],
            weather: dict[str, Any],
            state: dict[str, Any],
        ) -> dict[str, Any]:
            detail = base_weather_detail(config, weather, state)
            calculation = service.calculation(weather)
            total_in = calculation.get("total_in")
            if calculation.get("period") != "today" and isinstance(total_in, (int, float)):
                amount_mm = float(total_in) * 25.4
                max_mm = dashboard.dynamic_rain_max_mm(amount_mm)
                value = dashboard.format_rain_mm(amount_mm, config)
                gauge = {
                    "label": calculation["label"],
                    "value": value,
                    "percent": round(
                        max(0, min(100, amount_mm / max_mm * 100)) if max_mm else 0,
                        1,
                    ),
                    "max_label": dashboard.format_rain_mm(max_mm, config),
                }
                detail["rain_longer_gauges"] = [
                    gauge,
                    *detail.get("rain_longer_gauges", []),
                ]
            return detail

        weather_detail_with_historical_rainfall._acp_rainfall_history = True  # type: ignore[attr-defined]
        dashboard.weather_detail_data = weather_detail_with_historical_rainfall

    @app.route("/api/weather/rainfall", methods=["GET", "POST"])
    def api_weather_rainfall():
        from flask import request

        if request.method == "POST":
            return jsonify(service.refresh(force=True))
        return jsonify(service.snapshot())
