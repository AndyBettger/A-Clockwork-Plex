from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


INDOOR_FIELDS = ("tempinf", "humidityin")
DEFAULT_INDOOR_FRESH_SECONDS = 180
RAIN_EVENT_DRY_GAP = timedelta(hours=2)
RAIN_STATE_SCHEMA_VERSION = 2
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


def augment_daily_max_gust(
    state: dict[str, Any],
    weather: dict[str, Any],
    now: datetime,
    *,
    station_id: str = "",
) -> dict[str, Any]:
    """Add a WU-compatible daily maximum gust from successive current gusts.

    Ecowitt may provide ``maxdailygust`` directly, while WU current observations
    expose only ``windgustmph``. The locally derived value is scoped to the WU
    station and local calendar day, survives dashboard restarts, and never
    replaces a native provider value.
    """

    result = dict(weather)
    native_max = _number(result.get("maxdailygust"))
    current_gust = _number(result.get("windgustmph"))
    if native_max is not None:
        return result
    if current_gust is None:
        return result

    requested_station = str(station_id or "").strip().upper()
    today = now.date().isoformat()
    raw_state = state.get("weather_daily_max_gust")
    model = dict(raw_state) if isinstance(raw_state, dict) else {}
    previous_station = str(model.get("station_id") or "").strip().upper()
    previous_date = str(model.get("date") or "")
    previous_max = _number(model.get("max_gust_mph"))

    if previous_date != today or (
        previous_station and requested_station and previous_station != requested_station
    ):
        previous_max = None

    maximum = current_gust if previous_max is None else max(previous_max, current_gust)
    state["weather_daily_max_gust"] = {
        "station_id": requested_station,
        "date": today,
        "max_gust_mph": round(maximum, 3),
        "updated_at": _iso(now),
    }
    result["maxdailygust"] = round(maximum, 3)
    return result


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
    """Add WU-compatible Hourly/Event rain with station-time chronology.

    The current WU daily counter is a counter baseline, not proof that all rain
    already accumulated today belongs to one event. Fresh/legacy state therefore
    starts with zero derived Hourly/Event rain and learns subsequent increments.
    """
    result = dict(weather)
    daily = _number(result.get("dailyrainin"))
    if daily is None:
        return result

    raw_state = state.get("weather_rain_derived")
    model = dict(raw_state) if isinstance(raw_state, dict) else {}
    if model.get("schema_version") != RAIN_STATE_SCHEMA_VERSION:
        # Older state used receipt-time rollover and different event semantics;
        # its counter/event/increment provenance is not safe to relabel as v2.
        model = {}

    requested_station = str(station_id or "").strip().upper()
    previous_station = str(model.get("station_id") or "").strip().upper()
    if previous_station and requested_station and previous_station != requested_station:
        model = {}

    parsed_observed_at = _parse_time(result.get("dateutc"))
    observed_at = parsed_observed_at or now
    previous_observed_at = _parse_time(model.get("last_observed_at"))
    stale_observation = bool(previous_observed_at and observed_at < previous_observed_at)
    effective_at = previous_observed_at if stale_observation and previous_observed_at else observed_at

    increments = _clean_increments(model.get("increments"), effective_at)
    previous_daily = _number(model.get("last_daily_in"))
    previous_date = str(model.get("last_date") or "")
    observed_date = observed_at.date().isoformat()
    current_rate = _number(result.get("rainratein")) or 0.0

    event_total = _number(model.get("event_total_in")) or 0.0
    event_started_at = _parse_time(model.get("event_started_at"))
    event_last_rain_at = _parse_time(model.get("event_last_rain_at"))
    if event_total > RAIN_EPSILON_IN and event_last_rain_at is None:
        # Malformed v2 event state cannot prove a dry-gap boundary truthfully.
        event_total = 0.0
        event_started_at = None

    last_event_total = _number(model.get("last_event_total_in"))
    last_event_started_at = _parse_time(model.get("last_event_started_at"))
    last_event_ended_at = _parse_time(model.get("last_event_ended_at"))
    last_event_closed_at = _parse_time(model.get("last_event_closed_at"))

    tracking_started_at = _parse_time(model.get("tracking_started_at")) or effective_at
    observation_gap = (
        observed_at - previous_observed_at
        if previous_observed_at and not stale_observation
        else timedelta(0)
    )
    history_gap = observation_gap >= RAIN_EVENT_DRY_GAP

    if previous_daily is None or history_gap:
        # First observation, station change, legacy migration or a >=2h
        # observation gap is a counter rebaseline. Missing history cannot be
        # assigned to one event without inventing continuity.
        delta = 0.0
    elif stale_observation:
        # Older station observations may arrive after newer ones; never move
        # the rain counters backwards or manufacture a rollover.
        delta = 0.0
    elif previous_date and previous_date != observed_date:
        # A continuously observed station-date rollover means the new daily
        # counter itself is the amount since local midnight.
        delta = daily
    elif daily >= previous_daily:
        delta = daily - previous_daily
    else:
        # Same-day negative changes are station correction/reset events.
        delta = 0.0

    def close_event(closed_at: datetime) -> None:
        nonlocal event_total, event_started_at, event_last_rain_at
        nonlocal last_event_total, last_event_started_at, last_event_ended_at, last_event_closed_at
        if event_total <= RAIN_EPSILON_IN or event_last_rain_at is None:
            event_total = 0.0
            event_started_at = None
            event_last_rain_at = None
            return
        last_event_total = event_total
        last_event_started_at = event_started_at
        last_event_ended_at = event_last_rain_at
        last_event_closed_at = closed_at
        event_total = 0.0
        event_started_at = None
        event_last_rain_at = None

    if event_total > RAIN_EPSILON_IN and event_last_rain_at:
        dry_gap_elapsed = effective_at - event_last_rain_at >= RAIN_EVENT_DRY_GAP
        if dry_gap_elapsed and (history_gap or delta > RAIN_EPSILON_IN or current_rate <= RAIN_EPSILON_IN):
            close_event(event_last_rain_at + RAIN_EVENT_DRY_GAP)

    if delta > RAIN_EPSILON_IN:
        increments.append({"time": _iso(effective_at), "amount_in": round(delta, 6)})
        if event_total <= RAIN_EPSILON_IN:
            event_started_at = effective_at
        event_total += delta
        event_last_rain_at = effective_at

    one_hour_ago = effective_at - timedelta(hours=1)
    hourly = 0.0
    for item in increments:
        timestamp = _parse_time(item.get("time"))
        amount = _number(item.get("amount_in"))
        if timestamp and amount is not None and timestamp > one_hour_ago:
            hourly += amount

    persisted_date = previous_date if stale_observation and previous_date else observed_date
    persisted_daily = previous_daily if stale_observation and previous_daily is not None else daily

    state["weather_rain_derived"] = {
        "schema_version": RAIN_STATE_SCHEMA_VERSION,
        "station_id": requested_station,
        "chronology_source": "dateutc" if parsed_observed_at else "receipt_time",
        "tracking_started_at": _iso(tracking_started_at),
        "last_received_at": _iso(now),
        "last_payload_observed_at": _iso(observed_at),
        "last_observed_at": _iso(effective_at),
        "last_date": persisted_date,
        "last_daily_in": round(persisted_daily, 6),
        "increments": increments,
        "event_active": event_total > RAIN_EPSILON_IN,
        "event_total_in": round(max(0.0, event_total), 6),
        "event_started_at": _iso(event_started_at) if event_started_at else None,
        "event_last_rain_at": _iso(event_last_rain_at) if event_last_rain_at else None,
        "event_dry_gap_seconds": int(RAIN_EVENT_DRY_GAP.total_seconds()),
        "last_event_total_in": round(last_event_total, 6) if last_event_total is not None else None,
        "last_event_started_at": _iso(last_event_started_at) if last_event_started_at else None,
        "last_event_ended_at": _iso(last_event_ended_at) if last_event_ended_at else None,
        "last_event_closed_at": _iso(last_event_closed_at) if last_event_closed_at else None,
    }

    if "hourlyrainin" not in result:
        result["hourlyrainin"] = round(max(0.0, hourly), 6)
    if "eventrainin" not in result:
        result["eventrainin"] = round(max(0.0, event_total), 6)
    return result
