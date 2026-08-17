from __future__ import annotations

"""Incremental Weather Underground archive used for the Rain lifetime gauge.

The documented PWS daily-history API can query arbitrary historical date ranges,
but does not expose a documented station-inception field.  This service therefore
walks backwards in 31-day blocks from the year before the existing dashboard
comparison window.  Two consecutive years' worth of empty probe blocks are used
as the automatic pre-station boundary; deployments with an unusual multi-year
mid-life outage can override that heuristic with
``weather.historical_rainfall.lifetime_start_date`` (YYYY-MM-DD).

Older history lives in its own cache so it cannot race the selected-period / Rainy
Day Fund cache owned by ``WeatherRainfallHistoryService``.
"""

import json
import math
import os
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

try:
    from .weather_rainfall_history import (
        CONFIRMED_GAP,
        DEFAULT_TIMEOUT_SECONDS,
        MAX_RANGE_DAYS,
        WEATHER_UNDERGROUND_DAILY_HISTORY_URL,
        contiguous_ranges,
        daily_precip_totals,
        fetch_json,
    )
except ImportError:  # Supports direct execution imports.
    from weather_rainfall_history import (
        CONFIRMED_GAP,
        DEFAULT_TIMEOUT_SECONDS,
        MAX_RANGE_DAYS,
        WEATHER_UNDERGROUND_DAILY_HISTORY_URL,
        contiguous_ranges,
        daily_precip_totals,
        fetch_json,
    )

ARCHIVE_VERSION = 1
DISCOVERY_FLOOR = date(1995, 1, 1)
DEFAULT_REFRESH_SECONDS = 900
DEFAULT_PROBE_RANGES_PER_REFRESH = 36
DEFAULT_COVERAGE_RANGES_PER_REFRESH = 4
DEFAULT_EMPTY_RANGES_TO_STOP = 24  # roughly two years of 31-day blocks


def _load_cache(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": ARCHIVE_VERSION, "stations": {}}
    if (
        not isinstance(payload, dict)
        or payload.get("version") != ARCHIVE_VERSION
        or not isinstance(payload.get("stations"), dict)
    ):
        return {"version": ARCHIVE_VERSION, "stations": {}}
    return payload


def _save_cache(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _valid_total(value: Any) -> bool:
    try:
        total = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(total) and total >= 0


def _confirmed_gap(value: Any) -> bool:
    return value == CONFIRMED_GAP


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError:
        return None


def _date_span(start: date, end: date) -> list[date]:
    if end < start:
        return []
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def _earliest_numeric_day(days: dict[str, Any]) -> date | None:
    candidates = [
        parsed
        for key, value in days.items()
        if _valid_total(value) and (parsed := _parse_date(key)) is not None
    ]
    return min(candidates) if candidates else None


class WeatherRainfallLifetimeService:
    def __init__(
        self,
        load_config: Callable[[], dict[str, Any]],
        archive_path: Path,
        *,
        recent_cache_path: Path | None = None,
        current_weather: Callable[[], dict[str, Any]] | None = None,
        environment: Callable[[str], str | None] = os.environ.get,
        fetcher: Callable[[str, dict[str, Any], int], Any] = fetch_json,
        today_provider: Callable[[], date] = date.today,
        refresh_seconds: int = DEFAULT_REFRESH_SECONDS,
        probe_ranges_per_refresh: int = DEFAULT_PROBE_RANGES_PER_REFRESH,
        coverage_ranges_per_refresh: int = DEFAULT_COVERAGE_RANGES_PER_REFRESH,
        empty_ranges_to_stop: int = DEFAULT_EMPTY_RANGES_TO_STOP,
    ) -> None:
        self._load_config = load_config
        self._archive_path = Path(archive_path)
        self._recent_cache_path = Path(recent_cache_path) if recent_cache_path else None
        self._current_weather = current_weather or (lambda: {})
        self._environment = environment
        self._fetcher = fetcher
        self._today = today_provider
        self._refresh_seconds = max(60, int(refresh_seconds))
        self._probe_ranges_per_refresh = max(1, int(probe_ranges_per_refresh))
        self._coverage_ranges_per_refresh = max(1, int(coverage_ranges_per_refresh))
        self._empty_ranges_to_stop = max(2, int(empty_ranges_to_stop))
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
            "retried_dates": 0,
            "discovery_complete": False,
            "coverage_complete": False,
        }

    def _provider_config(self) -> tuple[str, str, int, date | None]:
        config = self._load_config()
        weather = config.get("weather") if isinstance(config.get("weather"), dict) else {}
        wu = weather.get("weather_underground") if isinstance(weather.get("weather_underground"), dict) else {}
        rainfall = weather.get("historical_rainfall") if isinstance(weather.get("historical_rainfall"), dict) else {}
        station_id = str(wu.get("station_id") or "").strip()
        env_name = str(wu.get("api_key_env") or "WEATHER_UNDERGROUND_API_KEY").strip()
        timeout = int(wu.get("request_timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)
        configured_start = _parse_date(rainfall.get("lifetime_start_date"))
        return (
            station_id,
            str(self._environment(env_name) or "").strip(),
            max(2, min(60, timeout)),
            configured_start,
        )

    @staticmethod
    def _archive_end(today: date) -> date:
        return date(today.year - 2, 12, 31)

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
    def _station_record(cache: dict[str, Any], station_id: str) -> dict[str, Any]:
        stations = cache.setdefault("stations", {})
        station = stations.setdefault(station_id, {"days": {}, "gaps": {}, "meta": {}})
        if not isinstance(station, dict):
            station = {"days": {}, "gaps": {}, "meta": {}}
            stations[station_id] = station
        for key in ("days", "gaps", "meta"):
            if not isinstance(station.get(key), dict):
                station[key] = {}
        return station

    def _recent_first_record(self, station_id: str) -> date | None:
        if self._recent_cache_path is None:
            return None
        cache = _load_cache(self._recent_cache_path)
        station = cache.get("stations", {}).get(station_id, {})
        days = station.get("days", {}) if isinstance(station, dict) else {}
        return _earliest_numeric_day(days) if isinstance(days, dict) else None

    def _probe_range(
        self,
        *,
        station_id: str,
        api_key: str,
        timeout: int,
        start: date,
        end: date,
        days: dict[str, Any],
    ) -> int:
        payload = self._fetcher(
            WEATHER_UNDERGROUND_DAILY_HISTORY_URL,
            self._request_params(station_id, api_key, start, end),
            timeout,
        )
        totals = daily_precip_totals(payload)
        for record_day, total in totals.items():
            if start <= record_day <= end:
                days[record_day.isoformat()] = total
        return len(totals)

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
        ranges = contiguous_ranges(missing)[: self._coverage_ranges_per_refresh]
        for start, end in ranges:
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

    def _calculate(
        self,
        *,
        station_id: str,
        configured_start: date | None,
        today: date,
        cache: dict[str, Any],
    ) -> dict[str, Any]:
        station = self._station_record(cache, station_id) if station_id else {"days": {}, "gaps": {}, "meta": {}}
        days = station.get("days", {})
        gaps = station.get("gaps", {})
        meta = station.get("meta", {})
        archive_first = _earliest_numeric_day(days)
        recent_first = self._recent_first_record(station_id) if station_id else None
        first_record = configured_start or archive_first or recent_first
        archive_end = self._archive_end(today)

        values = [float(value) for value in days.values() if _valid_total(value)]
        missing_days = sum(1 for value in gaps.values() if _confirmed_gap(value))
        return {
            "total_in": round(sum(values), 4) if values else 0.0,
            "available_days": len(values),
            "missing_days": missing_days,
            "first_record_date": first_record.isoformat() if first_record else None,
            "archive_end_date": archive_end.isoformat(),
            "configured_start_date": configured_start.isoformat() if configured_start else None,
            "discovery_complete": bool(meta.get("discovery_complete")),
            "coverage_complete": bool(meta.get("coverage_complete")),
            "probe_cursor_end": meta.get("probe_cursor_end"),
            "empty_probe_ranges": int(meta.get("empty_probe_ranges") or 0),
        }

    def refresh(self, force: bool = False) -> dict[str, Any]:
        del force
        today = self._today()
        archive_end = self._archive_end(today)
        station_id, api_key, timeout, configured_start = self._provider_config()
        now_text = datetime.now().isoformat(timespec="seconds")

        if not station_id:
            with self._lock:
                self._status.update(
                    status="configuration_required",
                    last_error="Weather Underground station ID is required for lifetime rainfall.",
                    last_refresh_at=now_text,
                    fetched_ranges=0,
                    retried_dates=0,
                )
            return self.snapshot()
        if not api_key:
            with self._lock:
                self._status.update(
                    status="credentials_required",
                    last_error="Weather Underground API key is required for lifetime rainfall.",
                    last_refresh_at=now_text,
                    fetched_ranges=0,
                    retried_dates=0,
                )
            return self.snapshot()

        cache = _load_cache(self._archive_path)
        station = self._station_record(cache, station_id)
        days: dict[str, Any] = station["days"]
        gaps: dict[str, Any] = station["gaps"]
        meta: dict[str, Any] = station["meta"]
        fetched_ranges = 0
        retried_dates = 0

        try:
            if configured_start is not None:
                meta["discovery_complete"] = True
                meta["first_record_date"] = configured_start.isoformat()
                meta["probe_cursor_end"] = None
                meta["empty_probe_ranges"] = 0
            elif not meta.get("discovery_complete"):
                cursor_end = _parse_date(meta.get("probe_cursor_end")) or archive_end
                empty_ranges = int(meta.get("empty_probe_ranges") or 0)
                first_record = _parse_date(meta.get("first_record_date")) or _earliest_numeric_day(days)

                for _ in range(self._probe_ranges_per_refresh):
                    if cursor_end < DISCOVERY_FLOOR:
                        meta["discovery_complete"] = True
                        break
                    start = max(DISCOVERY_FLOOR, cursor_end - timedelta(days=MAX_RANGE_DAYS - 1))
                    found = self._probe_range(
                        station_id=station_id,
                        api_key=api_key,
                        timeout=timeout,
                        start=start,
                        end=cursor_end,
                        days=days,
                    )
                    fetched_ranges += 1
                    if found:
                        block_first = min(
                            day for day in (_parse_date(key) for key, value in days.items() if _valid_total(value)) if day is not None
                        )
                        first_record = min(first_record, block_first) if first_record else block_first
                        empty_ranges = 0
                    else:
                        empty_ranges += 1

                    cursor_end = start - timedelta(days=1)
                    meta["probe_cursor_end"] = cursor_end.isoformat()
                    meta["empty_probe_ranges"] = empty_ranges
                    meta["first_record_date"] = first_record.isoformat() if first_record else None

                    if empty_ranges >= self._empty_ranges_to_stop:
                        meta["discovery_complete"] = True
                        break
                    if start == DISCOVERY_FLOOR:
                        meta["discovery_complete"] = True
                        break

            first_record = configured_start or _parse_date(meta.get("first_record_date")) or _earliest_numeric_day(days)
            if meta.get("discovery_complete"):
                if first_record is None or first_record > archive_end:
                    meta["coverage_complete"] = True
                else:
                    required = _date_span(first_record, archive_end)
                    missing = [
                        day
                        for day in required
                        if not _valid_total(days.get(day.isoformat()))
                        and not _confirmed_gap(gaps.get(day.isoformat()))
                    ]
                    if missing:
                        range_fetches, retries = self._fetch_missing(
                            missing,
                            station_id=station_id,
                            api_key=api_key,
                            timeout=timeout,
                            days=days,
                            gaps=gaps,
                        )
                        fetched_ranges += range_fetches
                        retried_dates += retries
                    remaining = [
                        day
                        for day in required
                        if not _valid_total(days.get(day.isoformat()))
                        and not _confirmed_gap(gaps.get(day.isoformat()))
                    ]
                    meta["coverage_complete"] = not remaining
            else:
                meta["coverage_complete"] = False

            _save_cache(self._archive_path, cache)
            calculation = self._calculate(
                station_id=station_id,
                configured_start=configured_start,
                today=today,
                cache=cache,
            )
            ready = calculation["discovery_complete"] and calculation["coverage_complete"]
            with self._lock:
                self._status.update(
                    status="ready" if ready else "backfilling",
                    last_error=None,
                    last_refresh_at=now_text,
                    last_success_at=now_text,
                    fetched_ranges=fetched_ranges,
                    retried_dates=retried_dates,
                )
                self._status.update(calculation)
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

    def calculation(self) -> dict[str, Any]:
        station_id, _api_key, _timeout, configured_start = self._provider_config()
        cache = _load_cache(self._archive_path)
        return self._calculate(
            station_id=station_id,
            configured_start=configured_start,
            today=self._today(),
            cache=cache,
        )

    def snapshot(self) -> dict[str, Any]:
        calculation = self.calculation()
        with self._lock:
            status = dict(self._status)
        status.update(calculation)
        return status

    def wake(self) -> None:
        self._wake.set()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="weather-rainfall-lifetime", daemon=True)
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


def register_weather_rainfall_lifetime(app: Any, service: WeatherRainfallLifetimeService) -> None:
    try:
        from flask import jsonify, request
    except ImportError:  # pragma: no cover
        return

    if "api_weather_rainfall_lifetime" in app.view_functions:
        return

    @app.route("/api/weather/rainfall/lifetime", methods=["GET", "POST"])
    def api_weather_rainfall_lifetime():
        if request.method == "POST":
            return jsonify(service.refresh(force=True))
        return jsonify(service.snapshot())
