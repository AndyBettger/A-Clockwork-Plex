from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


INDOOR_FIELDS = ("tempinf", "humidityin")
DEFAULT_INDOOR_FRESH_SECONDS = 180
RAIN_EVENT_RESET_IN = 1.0 / 25.4
RAIN_EPSILON_IN = 0.000001


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone().replace(tzinfo=None)
    return parsed


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


def indoor_fresh_seconds(config: dict[str, Any] | Any) -> int:
    if not isinstance(config, dict):
        return DEFAULT_INDOOR_FRESH_SECONDS
    weather = config.get("weather") if isinstance(config.get("weather"), dict) else {}
    ecowitt = weather.get("ecowitt_push") if isinstance(weather.get("ecowitt_push"), dict) else {}
    try:
        seconds = int(ecowitt.get("fresh_seconds", DEFAULT_INDOOR_FRESH_SECONDS))
    except (TypeError, ValueError):
        seconds = DEFAULT_INDOOR_FRESH_SECONDS
    return max(30, min(3600, seconds))


def extract_indoor_observation(payload: dict[str, Any] | Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return {
        key: payload[key]
        for key in INDOOR_FIELDS
        if key in payload and payload[key] is not None and str(payload[key]).strip()
    }


def update_supplemental_indoor_state(
    state: dict[str, Any],
    payload: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    indoor = extract_indoor_observation(payload)
    if not indoor:
        return {}
    state["weather_indoor"] = dict(indoor)
    state["last_weather_indoor_update"] = _iso(now)
    return indoor


def fresh_supplemental_indoor(
    state: dict[str, Any],
    now: datetime,
    *,
    fresh_seconds: int = DEFAULT_INDOOR_FRESH_SECONDS,
) -> dict[str, Any]:
    indoor = state.get("weather_indoor")
    updated = _parse_time(state.get("last_weather_indoor_update"))
    if not isinstance(indoor, dict) or not updated:
        return {}
    age = (now - updated).total_seconds()
    if age < 0 or age > max(30, int(fresh_seconds)):
        return {}
    return extract_indoor_observation(indoor)


def weather_underground_station_id(config: dict[str, Any] | Any) -> str:
    if not isinstance(config, dict):
        return ""
    weather = config.get("weather") if isinstance(config.get("weather"), dict) else {}
    wunderground = (
        weather.get("weather_underground")
        if isinstance(weather.get("weather_underground"), dict)
        else {}
    )
    return str(wunderground.get("station_id") or "").strip().upper()


def _clean_increments(raw: Any, now: datetime) -> list[dict[str, Any]]:
    cutoff = now - timedelta(hours=24)
    increments: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return increments
    for item in raw:
        if not isinstance(item, dict):
            continue
        timestamp = _parse_time(item.get("time"))
        amount = _number(item.get("amount_in"))
        if not timestamp or amount is None or amount <= RAIN_EPSILON_IN:
            continue
        if cutoff <= timestamp <= now + timedelta(minutes=5):
            increments.append({"time": _iso(timestamp), "amount_in": round(amount, 6)})
    increments.sort(key=lambda item: item["time"])
    return increments


def augment_derived_rain(
    state: dict[str, Any],
    weather: dict[str, Any],
    now: datetime,
    *,
    station_id: str = "",
) -> dict[str, Any]:
    """Add WU-compatible Hourly/Event rain while retaining a small persisted state.

    WU provides rain rate and the station's running daily total but not Ecowitt's
    Hourly Rain or Event Rain fields. Successive daily totals provide rainfall
    increments. Hourly Rain is the trailing 60-minute sum. Event Rain follows
    Ecowitt's reset semantics: reset only when the trailing hour is dry, current
    rain rate is zero and the preceding 24 hours contain less than 1 mm of rain.

    Native ``hourlyrainin``/``eventrainin`` values are never replaced.
    """
    result = dict(weather)
    daily = _number(result.get("dailyrainin"))
    if daily is None:
        return result

    raw_state = state.get("weather_rain_derived")
    model = dict(raw_state) if isinstance(raw_state, dict) else {}
    requested_station = str(station_id or "").strip().upper()
    previous_station = str(model.get("station_id") or "").strip().upper()
    if previous_station and requested_station and previous_station != requested_station:
        model = {}

    increments = _clean_increments(model.get("increments"), now)
    previous_daily = _number(model.get("last_daily_in"))
    previous_date = str(model.get("last_date") or "")
    today = now.date().isoformat()
    event_total = _number(model.get("event_total_in")) or 0.0
    current_rate = _number(result.get("rainratein")) or 0.0

    baseline_amount = _number(model.get("baseline_amount_in")) or 0.0
    baseline_at = _parse_time(model.get("baseline_at"))
    if previous_daily is None:
        # First observation cannot reveal when today's earlier rain fell. Keep
        # it as an event/24h baseline without pretending it all fell this hour.
        baseline_amount = daily
        baseline_at = now if daily > RAIN_EPSILON_IN else None
        event_total = max(event_total, daily)
        delta = 0.0
    elif previous_date and previous_date != today:
        # WU's daily counter rolls over at the station day boundary.
        delta = daily
    elif daily >= previous_daily:
        delta = daily - previous_daily
    else:
        # Same-day negative jumps are station correction/reset events, not
        # negative rainfall. Rebase without manufacturing a rain increment.
        delta = 0.0

    if delta > RAIN_EPSILON_IN:
        increments.append({"time": _iso(now), "amount_in": round(delta, 6)})
        event_total += delta

    one_hour_ago = now - timedelta(hours=1)
    one_day_ago = now - timedelta(hours=24)

    def amount_since(cutoff: datetime) -> float:
        total = 0.0
        for item in increments:
            timestamp = _parse_time(item.get("time"))
            amount = _number(item.get("amount_in"))
            if timestamp and amount is not None and timestamp > cutoff:
                total += amount
        return total

    hourly = amount_since(one_hour_ago)
    rolling_24h = amount_since(one_day_ago)
    if baseline_at and baseline_at > one_day_ago:
        rolling_24h += baseline_amount
    elif baseline_at and baseline_at <= one_day_ago:
        baseline_amount = 0.0
        baseline_at = None

    if (
        current_rate <= RAIN_EPSILON_IN
        and hourly <= RAIN_EPSILON_IN
        and rolling_24h < RAIN_EVENT_RESET_IN
    ):
        event_total = 0.0

    state["weather_rain_derived"] = {
        "station_id": requested_station,
        "last_observed_at": _iso(now),
        "last_date": today,
        "last_daily_in": round(daily, 6),
        "baseline_amount_in": round(baseline_amount, 6),
        "baseline_at": _iso(baseline_at) if baseline_at else None,
        "increments": increments,
        "event_total_in": round(max(0.0, event_total), 6),
    }

    if "hourlyrainin" not in result:
        result["hourlyrainin"] = round(max(0.0, hourly), 6)
    if "eventrainin" not in result:
        result["eventrainin"] = round(max(0.0, event_total), 6)
    return result
