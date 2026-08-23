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
DASHBOARD_PERIOD_LABELS = (
    ("current_week", "Rain this week"),
    ("previous_week", "Rain last week"),
    ("current_month", "Rain this month"),
    ("previous_month", "Rain last month"),
    ("current_year", "Rain this year"),
    ("previous_year", "Rain last year"),
)
DEFAULT_TIMEOUT_SECONDS = 8
DEFAULT_REFRESH_SECONDS = 900
MAX_RANGE_DAYS = 31
CONFIRMED_GAP = "no_station_data"


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


def _date_span(start: date, end: date) -> list[date]:
    if end < start:
        return []
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


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
    return _date_span(start, today)


def dashboard_period_dates(today: date) -> list[tuple[str, str, list[date]]]:
    week_start = today - timedelta(days=today.weekday())
    previous_week_end = week_start - timedelta(days=1)
    previous_week_start = previous_week_end - timedelta(days=6)
    month_start = today.replace(day=1)
    previous_month_end = month_start - timedelta(days=1)
    previous_month_start = previous_month_end.replace(day=1)
    year_start = today.replace(month=1, day=1)
    previous_year_start = date(today.year - 1, 1, 1)
    previous_year_end = date(today.year - 1, 12, 31)
    spans = {
        "current_week": _date_span(week_start, today),
        "previous_week": _date_span(previous_week_start, previous_week_end),
        "current_month": _date_span(month_start, today),
        "previous_month": _date_span(previous_month_start, previous_month_end),
        "current_year": _date_span(year_start, today),
        "previous_year": _date_span(previous_year_start, previous_year_end),
    }
    return [(period, label, spans[period]) for period, label in DASHBOARD_PERIOD_LABELS]


def dashboard_history_dates(today: date) -> list[date]:
    return _date_span(date(today.year - 1, 1, 1), today - timedelta(days=1))


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


def _confirmed_gap(value: Any) -> bool:
    return value == CONFIRMED_GAP


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
        dashboard_history: bool = False,
    ) -> None:
        self._load_config = load_config
        self._cache_path = Path(cache_path)
        self._current_weather = current_weather or (lambda: {})
        self._environment = environment
        self._fetcher = fetcher
        self._today = today_provider
        self._refresh_seconds = max(60, int(refresh_seconds))
        self._dashboard_history = bool(dashboard_history)
        self._lock = threading.RLock()
        self._refresh_lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._status: dict[str, Any] = {
            "status": "pending",
            "last_error": None,
            "last_refresh_at": None,
            "last_success_at": None,
            "fetched_ranges": 0,
            "retried_dates": 0,
            "gauge_status": "pending" if self._dashboard_history else "disabled",
            "gauge_last_error": None,
            "gauge_fetched_ranges": 0,
            "gauge_retried_dates": 0,
        }

    def _provider_config(self) -> tuple[str, str, int]:
        config = self._load_config()
        weather = config.get("weather") if isinstance(config.get("weather"), dict) else {}
        wu = weather.get("weather_underground") if isinstance(weather.get("weather_underground"), dict) else {}
        station_id = str(wu.get("station_id") or "").strip()
        env_name = str(wu.get("api_key_env") or "WEATHER_UNDERGROUND_API_KEY").strip()
        timeout = int(wu.get("request_timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)
        return station_id, str(self._environment(env_name) or "").strip(), max(2, min(60, timeout))

    def _station_record(self, cache: dict[str, Any], station_id: str) -> dict[str, Any]:
        stations = cache.setdefault("stations", {})
        station = stations.setdefault(station_id, {"days": {}, "gaps": {}})
        if not isinstance(station, dict):
            station = {"days": {}, "gaps": {}}
            stations[station_id] = station
        return station

    def _station_days(self, cache: dict[str, Any], station_id: str) -> dict[str, Any]:
        station = self._station_record(cache, station_id)
        days = station.setdefault("days", {})
        if not isinstance(days, dict):
            days = {}
            station["days"] = days
        return days

    def _station_gaps(self, cache: dict[str, Any], station_id: str) -> dict[str, Any]:
        station = self._station_record(cache, station_id)
        gaps = station.setdefault("gaps", {})
        if not isinstance(gaps, dict):
            gaps = {}
            station["gaps"] = gaps
        return gaps

    @staticmethod
    def _request_params(station_id: str, api_key: str, start: date, end: date) -> dict[str, Any]:
        return {
            "stationId": station_id,
            "format": "json",
            "units": "e",
            "numericPrecision": "decimal",
            "startDate": start.strftime("%Y%m%d"),
            "endDate": end.strftime("%Y%m%d"),
            "apiKey": api_key,
        }

    @staticmethod
    def _missing_days(required: list[date], days: dict[str, Any], gaps: dict[str, Any]) -> list[date]:
        return [
            day
            for day in required
            if not _valid_cached_total(days.get(day.isoformat()))
            and not _confirmed_gap(gaps.get(day.isoformat()))
        ]

    def _fetch_missing(
        self,
        missing: list[date],
        *,
        station_id: str,
        api_key: str,
        timeout: int,
        days: dict[str, Any],
        gaps: dict[str, Any],
    ) -> tuple[int, int]:
        fetched_ranges = 0
        retried_dates = 0
        for start, end in contiguous_ranges(missing):
            payload = self._fetcher(
                WEATHER_UNDERGROUND_DAILY_HISTORY_URL,
                self._request_params(station_id, api_key, start, end),
                timeout,
            )
            totals = daily_precip_totals(payload)
            omitted: list[date] = []
            cursor = start
            while cursor <= end:
                key = cursor.isoformat()
                if cursor in totals:
                    days[key] = totals[cursor]
                    gaps.pop(key, None)
                else:
                    days.pop(key, None)
                    omitted.append(cursor)
                cursor += timedelta(days=1)
            fetched_ranges += 1
            if start == end:
                for omitted_day in omitted:
                    gaps[omitted_day.isoformat()] = CONFIRMED_GAP
                continue
            for omitted_day in omitted:
                retry_payload = self._fetcher(
                    WEATHER_UNDERGROUND_DAILY_HISTORY_URL,
                    self._request_params(station_id, api_key, omitted_day, omitted_day),
                    timeout,
                )
                retried_dates += 1
                retry_totals = daily_precip_totals(retry_payload)
                key = omitted_day.isoformat()
                if omitted_day in retry_totals:
                    days[key] = retry_totals[omitted_day]
                    gaps.pop(key, None)
                else:
                    days.pop(key, None)
                    gaps[key] = CONFIRMED_GAP
        return fetched_ranges, retried_dates

    def wake(self) -> None:
        self._wake.set()

    def refresh(self, force: bool = False) -> dict[str, Any]:
        with self._refresh_lock:
            return self._refresh_once(force=force)

    def _refresh_once(self, force: bool = False) -> dict[str, Any]:
        del force
        config = self._load_config()
        period = public_rainfall_config(config)["period"]
        today = self._today()
        station_id, api_key, timeout = self._provider_config()
        now_text = datetime.now().isoformat(timespec="seconds")
        primary_requires_history = period != "today"

        if not station_id:
            primary_status = "configuration_required" if primary_requires_history else "ready"
            primary_error = "Weather Underground station ID is required for historical rainfall." if primary_requires_history else None
            with self._lock:
                self._status.update(
                    status=primary_status,
                    last_error=primary_error,
                    last_refresh_at=now_text,
                    last_success_at=now_text if primary_status == "ready" else self._status.get("last_success_at"),
                    fetched_ranges=0,
                    retried_dates=0,
                    gauge_status="configuration_required" if self._dashboard_history else "disabled",
                    gauge_last_error=("Weather Underground station ID is required for Rainy Day Fund history." if self._dashboard_history else None),
                    gauge_fetched_ranges=0,
                    gauge_retried_dates=0,
                )
            return self.snapshot()

        if not api_key:
            primary_status = "credentials_required" if primary_requires_history else "ready"
            primary_error = "Weather Underground API key is required for historical rainfall." if primary_requires_history else None
            with self._lock:
                self._status.update(
                    status=primary_status,
                    last_error=primary_error,
                    last_refresh_at=now_text,
                    last_success_at=now_text if primary_status == "ready" else self._status.get("last_success_at"),
                    fetched_ranges=0,
                    retried_dates=0,
                    gauge_status="credentials_required" if self._dashboard_history else "disabled",
                    gauge_last_error=("Weather Underground API key is required for Rainy Day Fund history." if self._dashboard_history else None),
                    gauge_fetched_ranges=0,
                    gauge_retried_dates=0,
                )
            return self.snapshot()

        cache = _load_cache(self._cache_path)
        days = self._station_days(cache, station_id)
        gaps = self._station_gaps(cache, station_id)
        required_past = [day for day in period_dates(period, today) if day < today]
        primary_missing = self._missing_days(required_past, days, gaps)
        fetched_ranges = 0
        retried_dates = 0
        try:
            fetched_ranges, retried_dates = self._fetch_missing(
                primary_missing,
                station_id=station_id,
                api_key=api_key,
                timeout=timeout,
                days=days,
                gaps=gaps,
            )
            if primary_missing:
                _save_cache(self._cache_path, cache)
            with self._lock:
                self._status.update(
                    status="ready",
                    last_error=None,
                    last_refresh_at=now_text,
                    last_success_at=now_text,
                    fetched_ranges=fetched_ranges,
                    retried_dates=retried_dates,
                )
        except Exception as exc:
            message = str(exc).replace(api_key, "[redacted]") if api_key else str(exc)
            with self._lock:
                self._status.update(
                    status="error",
                    last_error=message,
                    last_refresh_at=now_text,
                    fetched_ranges=fetched_ranges,
                    retried_dates=retried_dates,
                )
            return self.snapshot()

        if not self._dashboard_history:
            with self._lock:
                self._status.update(
                    gauge_status="disabled",
                    gauge_last_error=None,
                    gauge_fetched_ranges=0,
                    gauge_retried_dates=0,
                )
            return self.snapshot()

        dashboard_required = dashboard_history_dates(today)
        gauge_missing = self._missing_days(dashboard_required, days, gaps)
        primary_keys = {day.isoformat() for day in primary_missing}
        gauge_missing = [day for day in gauge_missing if day.isoformat() not in primary_keys]
        gauge_fetched_ranges = 0
        gauge_retried_dates = 0
        try:
            gauge_fetched_ranges, gauge_retried_dates = self._fetch_missing(
                gauge_missing,
                station_id=station_id,
                api_key=api_key,
                timeout=timeout,
                days=days,
                gaps=gaps,
            )
            if gauge_missing:
                _save_cache(self._cache_path, cache)
            with self._lock:
                self._status.update(
                    gauge_status="ready",
                    gauge_last_error=None,
                    gauge_fetched_ranges=gauge_fetched_ranges,
                    gauge_retried_dates=gauge_retried_dates,
                )
        except Exception as exc:
            message = str(exc).replace(api_key, "[redacted]") if api_key else str(exc)
            with self._lock:
                self._status.update(
                    gauge_status="error",
                    gauge_last_error=message,
                    gauge_fetched_ranges=gauge_fetched_ranges,
                    gauge_retried_dates=gauge_retried_dates,
                )
        return self.snapshot()

    def _calculation_for_dates(
        self,
        *,
        period: str,
        label: str,
        required: list[date],
        today: date,
        weather: dict[str, Any],
        days: dict[str, Any],
        gaps: dict[str, Any],
    ) -> dict[str, Any]:
        values: list[float] = []
        missing_dates: list[str] = []
        pending_dates: list[str] = []
        for day in required:
            key = day.isoformat()
            if day == today:
                try:
                    value = float(weather.get("dailyrainin"))
                except (TypeError, ValueError):
                    value = math.nan
            else:
                raw = days.get(key)
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    value = math.nan
            if math.isfinite(value) and value >= 0:
                values.append(value)
            elif day < today and _confirmed_gap(gaps.get(key)):
                missing_dates.append(key)
            else:
                pending_dates.append(key)
        unavailable = [*missing_dates, *pending_dates]
        total = round(sum(values), 4) if values else None
        return {
            "period": period,
            "label": label,
            "total_in": total,
            "complete": not pending_dates,
            "coverage_complete": not unavailable,
            "unavailable_dates": unavailable,
            "missing_dates": missing_dates,
            "pending_dates": pending_dates,
            "missing_days": len(missing_dates),
            "pending_days": len(pending_dates),
            "required_days": len(required),
            "available_days": len(values),
        }

    def calculation(self, weather: dict[str, Any] | None = None) -> dict[str, Any]:
        config = self._load_config()
        period = public_rainfall_config(config)["period"]
        today = self._today()
        station_id, _api_key, _timeout = self._provider_config()
        cache = _load_cache(self._cache_path)
        days = self._station_days(cache, station_id) if station_id else {}
        gaps = self._station_gaps(cache, station_id) if station_id else {}
        live_weather = weather if isinstance(weather, dict) else self._current_weather()
        return self._calculation_for_dates(
            period=period,
            label=PERIOD_LABELS[period],
            required=period_dates(period, today),
            today=today,
            weather=live_weather,
            days=days,
            gaps=gaps,
        )

    def dashboard_calculations(self, weather: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        today = self._today()
        station_id, _api_key, _timeout = self._provider_config()
        cache = _load_cache(self._cache_path)
        days = self._station_days(cache, station_id) if station_id else {}
        gaps = self._station_gaps(cache, station_id) if station_id else {}
        live_weather = weather if isinstance(weather, dict) else self._current_weather()
        return [
            self._calculation_for_dates(
                period=period,
                label=label,
                required=required,
                today=today,
                weather=live_weather,
                days=days,
                gaps=gaps,
            )
            for period, label, required in dashboard_period_dates(today)
        ]

    def snapshot(self) -> dict[str, Any]:
        calculation = self.calculation()
        station_id, _api_key, _timeout = self._provider_config()
        cache = _load_cache(self._cache_path)
        days = self._station_days(cache, station_id) if station_id else {}
        gaps = self._station_gaps(cache, station_id) if station_id else {}
        with self._lock:
            status = dict(self._status)
        status.update(calculation)
        status["cached_days"] = sum(1 for value in days.values() if _valid_cached_total(value))
        status["gap_days"] = sum(1 for value in gaps.values() if _confirmed_gap(value))
        if status.get("status") in {"error", "configuration_required", "credentials_required"}:
            status["complete"] = False
            status["total_in"] = None
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
    except ImportError:  # pragma: no cover
        return

    projection_target = getattr(dashboard, "core", dashboard)
    current_detail = getattr(projection_target, "weather_detail_data")
    if not getattr(current_detail, "_acp_rainfall_history", False):
        base_weather_detail = current_detail

        def weather_detail_with_historical_rainfall(
            config: dict[str, Any],
            weather: dict[str, Any],
            state: dict[str, Any],
        ) -> dict[str, Any]:
            detail = base_weather_detail(config, weather, state)
            history_gauges: list[dict[str, Any]] = []
            for calculation in service.dashboard_calculations(weather):
                total_in = calculation.get("total_in")
                if not calculation.get("complete") or not isinstance(total_in, (int, float)):
                    continue
                amount_mm = float(total_in) * 25.4
                max_mm = projection_target.dynamic_rain_max_mm(amount_mm)
                missing_days = int(calculation.get("missing_days") or 0)
                history_gauges.append(
                    {
                        "label": calculation["label"],
                        "value": projection_target.format_rain_mm(amount_mm, config),
                        "percent": round(max(0, min(100, amount_mm / max_mm * 100)) if max_mm else 0, 1),
                        "max_label": projection_target.format_rain_mm(max_mm, config),
                        "note": (f"{missing_days} day{'s' if missing_days != 1 else ''} not recorded" if missing_days else None),
                    }
                )
            if history_gauges:
                live_gauges = detail.get("rain_longer_gauges", [])
                lifetime_gauges = [
                    gauge
                    for gauge in live_gauges
                    if isinstance(gauge, dict) and gauge.get("label") == "Total rain"
                ]
                detail["rain_longer_gauges"] = [*history_gauges, *lifetime_gauges]
            return detail

        weather_detail_with_historical_rainfall._acp_rainfall_history = True  # type: ignore[attr-defined]
        projection_target.weather_detail_data = weather_detail_with_historical_rainfall
        dashboard.weather_detail_data = weather_detail_with_historical_rainfall

    @app.route("/api/weather/rainfall", methods=["GET", "POST"])
    def api_weather_rainfall():
        from flask import request

        if request.method == "POST":
            return jsonify(service.refresh(force=True))
        return jsonify(service.snapshot())
