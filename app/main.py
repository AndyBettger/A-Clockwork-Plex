from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"
EXAMPLE_CONFIG_PATH = BASE_DIR / "config.example.json"
STATE_PATH = BASE_DIR / "state.json"

VALID_MODES = {"clock", "weather", "airplay", "plexamp", "settings"}
SENSITIVE_WEATHER_KEYS = {"passkey", "password", "secret", "token", "api_key", "apikey"}
PRESSURE_HISTORY_HOURS = 24
PRESSURE_TREND_MINUTES = 180
PRESSURE_TREND_MINIMUM_MINUTES = 30

COMPASS_POINTS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]

WEATHER_FIELDS: dict[str, dict[str, Any]] = {
    "outdoor_temp": {"label": "Outdoor temp", "keys": ["tempf", "tempc", "outtemp"], "type": "temperature"},
    "indoor_temp": {"label": "Indoor temp", "keys": ["tempinf", "indoortempf", "indoortempc", "intemp"], "type": "temperature"},
    "humidity": {"label": "Humidity", "keys": ["humidity", "outhumi", "outdoor_humidity"], "type": "percent"},
    "indoor_humidity": {"label": "Indoor humidity", "keys": ["humidityin", "indoorhumidity", "inhumi"], "type": "percent"},
    "pressure": {"label": "Pressure", "keys": ["baromrelin", "pressure", "barometer"], "type": "pressure"},
    "absolute_pressure": {"label": "Absolute pressure", "keys": ["baromabsin"], "type": "pressure"},
    "wind_speed": {"label": "Wind", "keys": ["windspeedmph", "wind_speed", "windspdmph_avg10m"], "type": "wind"},
    "wind_gust": {"label": "Gust", "keys": ["windgustmph", "wind_gust"], "type": "wind"},
    "max_daily_gust": {"label": "Max gust today", "keys": ["maxdailygust"], "type": "wind"},
    "wind_direction": {"label": "Direction", "keys": ["winddir"], "type": "direction"},
    "rain_rate": {"label": "Rain rate", "keys": ["rainratein"], "type": "rain_rate"},
    "hourly_rain": {"label": "Hourly rain", "keys": ["hourlyrainin"], "type": "rain"},
    "daily_rain": {"label": "Rain today", "keys": ["dailyrainin"], "type": "rain"},
    "weekly_rain": {"label": "Rain this week", "keys": ["weeklyrainin"], "type": "rain"},
    "monthly_rain": {"label": "Rain this month", "keys": ["monthlyrainin"], "type": "rain"},
    "yearly_rain": {"label": "Rain this year", "keys": ["yearlyrainin"], "type": "rain"},
    "total_rain": {"label": "Total rain", "keys": ["totalrainin"], "type": "rain"},
    "event_rain": {"label": "Event rain", "keys": ["eventrainin"], "type": "rain"},
    "solar": {"label": "Solar", "keys": ["solarradiation", "solar"], "type": "solar"},
    "uv": {"label": "UV", "keys": ["uv", "uvi"], "type": "uv"},
    "vpd": {"label": "VPD", "keys": ["vpd"], "type": "vpd"},
    "station_type": {"label": "Station type", "keys": ["stationtype"], "type": "text"},
    "model": {"label": "Model", "keys": ["model"], "type": "text"},
    "frequency": {"label": "Frequency", "keys": ["freq"], "type": "text"},
    "upload_interval": {"label": "Upload interval", "keys": ["interval"], "type": "seconds"},
    "last_station_update": {"label": "Station timestamp", "keys": ["dateutc"], "type": "station_datetime"},
    "sensor_battery": {"label": "Sensor battery", "keys": ["wh65batt"], "type": "battery"},
}

CONDITION_EXTREME_FIELDS = ["outdoor_temp", "indoor_temp", "humidity", "indoor_humidity"]
CLOCK_CARD_FIELD_IDS = [
    "outdoor_temp", "indoor_temp", "humidity", "indoor_humidity",
    "wind_speed", "wind_gust", "max_daily_gust", "daily_rain",
    "hourly_rain", "event_rain", "pressure", "barometer", "solar", "uv",
]
DEFAULT_CLOCK_CARDS = ["outdoor_temp", "humidity", "wind_speed", "wind_gust", "daily_rain", "pressure"]


def load_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return fallback
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"A Clockwork Plex: failed to load JSON from {path}: {exc}", flush=True)
        return fallback


def save_json(path: Path, data: dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp_path.replace(path)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config() -> dict[str, Any]:
    return deep_merge(load_json(EXAMPLE_CONFIG_PATH, {}), load_json(CONFIG_PATH, {}))


def json_file_status(path: Path) -> dict[str, Any]:
    status: dict[str, Any] = {"path": str(path), "exists": path.exists(), "valid": False, "error": None}
    if not path.exists():
        status["error"] = "File does not exist."
        return status
    try:
        with path.open("r", encoding="utf-8") as handle:
            json.load(handle)
        status["valid"] = True
    except json.JSONDecodeError as exc:
        status["error"] = f"Invalid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}."
    except OSError as exc:
        status["error"] = f"Could not read file: {exc}"
    return status


def config_diagnostics() -> dict[str, Any]:
    return {
        "base_dir": str(BASE_DIR),
        "config": json_file_status(CONFIG_PATH),
        "example_config": json_file_status(EXAMPLE_CONFIG_PATH),
    }


def default_state(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": config.get("dashboard", {}).get("default_mode", "clock"),
        "last_mode_change": datetime.now().isoformat(timespec="seconds"),
        "weather": {},
        "weather_extremes": {"date": datetime.now().date().isoformat(), "fields": {}},
        "pressure_history": [],
        "last_weather_update": None,
    }


def load_state(config: dict[str, Any]) -> dict[str, Any]:
    state = load_json(STATE_PATH, default_state(config))
    if state.get("mode") not in VALID_MODES:
        state["mode"] = "clock"
    if not isinstance(state.get("weather_extremes"), dict):
        state["weather_extremes"] = {"date": datetime.now().date().isoformat(), "fields": {}}
    if not isinstance(state.get("pressure_history"), list):
        state["pressure_history"] = []
    return state


def set_mode(mode: str) -> dict[str, Any]:
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid mode: {mode}")
    config = load_config()
    state = load_state(config)
    state["mode"] = mode
    state["last_mode_change"] = datetime.now().isoformat(timespec="seconds")
    save_json(STATE_PATH, state)
    return state


def normalise_weather_payload() -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if request.is_json:
        payload.update(request.get_json(silent=True) or {})
    payload.update(request.args.to_dict(flat=True))
    payload.update(request.form.to_dict(flat=True))

    clean: dict[str, Any] = {}
    for key, value in payload.items():
        key_text = str(key).strip()
        if not key_text or not str(value).strip() or key_text.lower() in SENSITIVE_WEATHER_KEYS:
            continue
        clean[key_text] = value
    return clean


def redacted_weather(weather: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key): "[redacted]" if str(key).lower() in SENSITIVE_WEATHER_KEYS else value
        for key, value in weather.items()
    }


def safe_state(state: dict[str, Any]) -> dict[str, Any]:
    safe = dict(state)
    safe["weather"] = redacted_weather(state.get("weather", {}))
    return safe


def lower_weather(weather: dict[str, Any]) -> dict[str, Any]:
    return {str(k).lower(): v for k, v in weather.items()}


def get_weather_value(weather: dict[str, Any], keys: list[str]) -> tuple[str | None, Any | None]:
    lookup = lower_weather(weather)
    for key in keys:
        normalised_key = key.lower()
        if normalised_key in lookup:
            return normalised_key, lookup[normalised_key]
    return None, None


def parse_float(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def format_display_datetime(value: Any) -> str:
    parsed = parse_datetime(value)
    if parsed:
        return parsed.strftime("%d/%m/%Y %H:%M:%S")
    return str(value) if value else ""


def weather_units(config: dict[str, Any]) -> dict[str, str]:
    weather_config = config.get("weather", {})
    unit_config = weather_config.get("units", {}) if isinstance(weather_config.get("units", {}), dict) else {}
    display_units = str(weather_config.get("display_units", "metric")).lower()
    defaults = {
        "temperature": "c" if display_units == "metric" else "f",
        "pressure": "hpa" if display_units == "metric" else "inhg",
        "rain": "mm" if display_units == "metric" else "in",
        "wind": "mph",
    }
    return {
        "temperature": str(unit_config.get("temperature", defaults["temperature"])).lower(),
        "pressure": str(unit_config.get("pressure", defaults["pressure"])).lower(),
        "rain": str(unit_config.get("rain", defaults["rain"])).lower(),
        "wind": str(unit_config.get("wind", defaults["wind"])).lower(),
    }


def fahrenheit_to_celsius(value: float) -> float:
    return (value - 32) * 5 / 9


def celsius_to_fahrenheit(value: float) -> float:
    return (value * 9 / 5) + 32


def inches_to_mm(value: float) -> float:
    return value * 25.4


def mm_to_inches(value: float) -> float:
    return value / 25.4


def inhg_to_hpa(value: float) -> float:
    return value * 33.8638866667


def hpa_to_inhg(value: float) -> float:
    return value / 33.8638866667


def mph_to_kmh(value: float) -> float:
    return value * 1.609344


def mph_to_ms(value: float) -> float:
    return value * 0.44704


def format_float(value: float, places: int) -> str:
    return f"{value:.{places}f}"


def compass_label(degrees: float) -> str:
    return COMPASS_POINTS[round((degrees % 360) / 22.5) % len(COMPASS_POINTS)]


def source_key_is_fahrenheit(source_key: str | None) -> bool:
    return bool(source_key and source_key.endswith("f"))


def source_key_is_celsius(source_key: str | None) -> bool:
    return bool(source_key and source_key.endswith("c"))


def pressure_hpa_from_weather(weather: dict[str, Any]) -> float | None:
    source_key, raw_value = get_weather_value(weather, WEATHER_FIELDS["pressure"]["keys"])
    numeric = parse_float(raw_value)
    if numeric is None:
        return None
    return inhg_to_hpa(numeric) if source_key and source_key.endswith("in") else numeric


def format_weather_value(field_id: str, weather: dict[str, Any], config: dict[str, Any]) -> dict[str, Any] | None:
    field = WEATHER_FIELDS[field_id]
    source_key, raw_value = get_weather_value(weather, field["keys"])
    if raw_value is None:
        return None

    field_type = field["type"]
    units = weather_units(config)
    numeric = parse_float(raw_value)
    numeric_value: float | None = numeric
    unit = ""
    value = str(raw_value)

    if field_type == "temperature" and numeric is not None:
        target = units["temperature"]
        converted = fahrenheit_to_celsius(numeric) if target == "c" and source_key_is_fahrenheit(source_key) else numeric
        converted = celsius_to_fahrenheit(numeric) if target == "f" and source_key_is_celsius(source_key) else converted
        unit = "°C" if target == "c" else "°F"
        numeric_value = converted
        value = f"{format_float(converted, 1)}{unit}"
    elif field_type == "pressure" and numeric is not None:
        source_is_inhg = bool(source_key and source_key.endswith("in"))
        if units["pressure"] in {"hpa", "mbar"}:
            converted = inhg_to_hpa(numeric) if source_is_inhg else numeric
            unit = "hPa"
            value = f"{format_float(converted, 1)} {unit}"
        else:
            converted = numeric if source_is_inhg else hpa_to_inhg(numeric)
            unit = "inHg"
            value = f"{format_float(converted, 3)} {unit}"
        numeric_value = converted
    elif field_type in {"rain", "rain_rate"} and numeric is not None:
        source_is_inches = bool(source_key and source_key.endswith("in"))
        if units["rain"] == "mm":
            converted = inches_to_mm(numeric) if source_is_inches else numeric
            unit = "mm/hr" if field_type == "rain_rate" else "mm"
            value = f"{format_float(converted, 1)} {unit}"
        else:
            converted = numeric if source_is_inches else mm_to_inches(numeric)
            unit = "in/hr" if field_type == "rain_rate" else "in"
            value = f"{format_float(converted, 3)} {unit}"
        numeric_value = converted
    elif field_type == "wind" and numeric is not None:
        target = units["wind"]
        if target == "kmh":
            converted, unit = mph_to_kmh(numeric), "km/h"
        elif target in {"ms", "mps", "m/s"}:
            converted, unit = mph_to_ms(numeric), "m/s"
        else:
            converted, unit = numeric, "mph"
        numeric_value = converted
        value = f"{format_float(converted, 1)} {unit}"
    elif field_type == "direction" and numeric is not None:
        degrees = numeric % 360
        numeric_value = degrees
        unit = "°"
        value = f"{round(degrees)}° {compass_label(degrees)}"
    elif field_type == "percent" and numeric is not None:
        numeric_value = numeric
        unit = "%"
        value = f"{round(numeric)}%"
    elif field_type == "solar" and numeric is not None:
        numeric_value = numeric
        unit = "W/m²"
        value = f"{format_float(numeric, 1)} {unit}"
    elif field_type == "uv" and numeric is not None:
        numeric_value = numeric
        value = format_float(numeric, 1).rstrip("0").rstrip(".")
    elif field_type == "vpd" and numeric is not None:
        numeric_value = numeric
        unit = "kPa"
        value = f"{format_float(numeric, 2)} {unit}"
    elif field_type == "seconds" and numeric is not None:
        numeric_value = numeric
        unit = "sec"
        value = f"{round(numeric)} sec"
    elif field_type == "battery" and numeric is not None:
        numeric_value = numeric
        value = "OK" if numeric == 0 else str(raw_value)
    elif field_type == "station_datetime":
        value = format_display_datetime(raw_value)

    return {
        "id": field_id,
        "label": field["label"],
        "value": value,
        "raw_value": raw_value,
        "source_key": source_key,
        "numeric": numeric_value,
        "unit": unit,
    }


def weather_item(field_id: str, config: dict[str, Any], weather: dict[str, Any]) -> dict[str, Any] | None:
    if field_id not in WEATHER_FIELDS:
        return None
    return format_weather_value(field_id, weather, config)


def weather_items(field_ids: list[str], config: dict[str, Any], weather: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for field_id in field_ids if (item := weather_item(field_id, config, weather))]


def normalise_clock_cards(config: dict[str, Any]) -> list[str]:
    configured = config.get("weather", {}).get("clock_cards", [])
    if not isinstance(configured, list):
        configured = []
    cards = [str(field_id) for field_id in configured if str(field_id) in CLOCK_CARD_FIELD_IDS]
    return list(dict.fromkeys(cards)) or DEFAULT_CLOCK_CARDS


def clock_weather_items(config: dict[str, Any], weather: dict[str, Any], state: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for field_id in normalise_clock_cards(config):
        if field_id == "barometer":
            status = barometer_status(config, weather, state)
            trend = status.get("trend")
            forecast = status.get("forecast_title")
            if trend:
                items.append({"label": "Barometer", "value": f"{forecast} · {trend}" if forecast else str(trend)})
            continue

        item = weather_item(field_id, config, weather)
        if item:
            items.append({"label": item["label"], "value": item["value"]})
    return items


def pick_weather_fields(config: dict[str, Any], weather: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return {item["label"]: item["value"] for item in clock_weather_items(config, weather, state)}


def canonical_extreme_value(field_id: str, weather: dict[str, Any]) -> float | None:
    field = WEATHER_FIELDS.get(field_id)
    if not field:
        return None
    source_key, raw_value = get_weather_value(weather, field["keys"])
    numeric = parse_float(raw_value)
    if numeric is None:
        return None
    if field["type"] == "temperature":
        return fahrenheit_to_celsius(numeric) if source_key_is_fahrenheit(source_key) else numeric
    if field["type"] == "percent":
        return numeric
    return None


def update_weather_extremes(state: dict[str, Any], weather: dict[str, Any]) -> None:
    today = datetime.now().date().isoformat()
    extremes = state.get("weather_extremes")
    if not isinstance(extremes, dict) or extremes.get("date") != today:
        extremes = {"date": today, "fields": {}}
    fields = extremes.setdefault("fields", {})
    if not isinstance(fields, dict):
        fields = {}
        extremes["fields"] = fields

    for field_id in CONDITION_EXTREME_FIELDS:
        value = canonical_extreme_value(field_id, weather)
        if value is None:
            continue
        existing = fields.get(field_id)
        if not isinstance(existing, dict):
            existing = {"min": value, "max": value}
        existing["current"] = value
        existing["min"] = min(float(existing.get("min", value)), value)
        existing["max"] = max(float(existing.get("max", value)), value)
        existing["updated"] = datetime.now().isoformat(timespec="seconds")
        fields[field_id] = existing
    state["weather_extremes"] = extremes


def update_pressure_history(state: dict[str, Any], weather: dict[str, Any]) -> None:
    pressure_hpa = pressure_hpa_from_weather(weather)
    if pressure_hpa is None:
        return
    now = datetime.now()
    cutoff = now - timedelta(hours=PRESSURE_HISTORY_HOURS)
    cleaned: list[dict[str, Any]] = []
    history = state.get("pressure_history", [])
    if isinstance(history, list):
        for entry in history:
            if not isinstance(entry, dict):
                continue
            timestamp = parse_datetime(entry.get("time"))
            value = parse_float(entry.get("hpa"))
            if timestamp and value is not None and timestamp >= cutoff:
                cleaned.append({"time": timestamp.isoformat(timespec="seconds"), "hpa": round(value, 3)})
    cleaned.append({"time": now.isoformat(timespec="seconds"), "hpa": round(pressure_hpa, 3)})
    state["pressure_history"] = cleaned[-(PRESSURE_HISTORY_HOURS * 60 + 5):]


def format_extreme_value(field_id: str, value: Any, config: dict[str, Any]) -> str:
    numeric = parse_float(value)
    if numeric is None:
        return "—"
    field_type = WEATHER_FIELDS.get(field_id, {}).get("type")
    units = weather_units(config)
    if field_type == "temperature":
        if units["temperature"] == "f":
            return f"{format_float(celsius_to_fahrenheit(numeric), 1)}°F"
        return f"{format_float(numeric, 1)}°C"
    if field_type == "percent":
        return f"{round(numeric)}%"
    return str(value)


def condition_cell(field_id: str, config: dict[str, Any], weather: dict[str, Any], extremes: dict[str, Any]) -> dict[str, str]:
    current = weather_item(field_id, config, weather)
    fields = extremes.get("fields", {}) if isinstance(extremes.get("fields"), dict) else {}
    field_extremes = fields.get(field_id, {}) if isinstance(fields.get(field_id, {}), dict) else {}
    return {
        "current": current["value"] if current else "—",
        "min": format_extreme_value(field_id, field_extremes.get("min"), config) if field_extremes else "—",
        "max": format_extreme_value(field_id, field_extremes.get("max"), config) if field_extremes else "—",
    }


def condition_rows(config: dict[str, Any], weather: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    extremes = state.get("weather_extremes", {}) if isinstance(state.get("weather_extremes"), dict) else {}
    return [
        {
            "location": "Outdoor",
            "temperature": condition_cell("outdoor_temp", config, weather, extremes),
            "humidity": condition_cell("humidity", config, weather, extremes),
        },
        {
            "location": "Indoor",
            "temperature": condition_cell("indoor_temp", config, weather, extremes),
            "humidity": condition_cell("indoor_humidity", config, weather, extremes),
        },
    ]


def rain_amount_mm(field_id: str, weather: dict[str, Any]) -> float | None:
    field = WEATHER_FIELDS[field_id]
    source_key, raw_value = get_weather_value(weather, field["keys"])
    numeric = parse_float(raw_value)
    if numeric is None:
        return None
    return inches_to_mm(numeric) if source_key and source_key.endswith("in") else numeric


def dynamic_rain_max_mm(amount_mm: float) -> float:
    if amount_mm <= 0:
        return 5
    if amount_mm <= 25:
        step = 5
    elif amount_mm <= 100:
        step = 10
    elif amount_mm <= 1000:
        step = 50
    else:
        step = 100
    maximum = math.ceil(amount_mm / step) * step
    if maximum <= amount_mm:
        maximum += step
    return max(5, maximum)


def format_rain_mm(amount_mm: float, config: dict[str, Any], is_rate: bool = False) -> str:
    if weather_units(config)["rain"] == "mm":
        unit = "mm/hr" if is_rate else "mm"
        return f"{format_float(amount_mm, 1)} {unit}"
    unit = "in/hr" if is_rate else "in"
    return f"{format_float(mm_to_inches(amount_mm), 3)} {unit}"


def rain_gauge(field_id: str, config: dict[str, Any], weather: dict[str, Any]) -> dict[str, Any] | None:
    item = weather_item(field_id, config, weather)
    amount_mm = rain_amount_mm(field_id, weather)
    if not item or amount_mm is None:
        return None
    max_mm = dynamic_rain_max_mm(amount_mm)
    percent = max(0, min(100, (amount_mm / max_mm) * 100)) if max_mm else 0
    return {
        "label": item["label"],
        "value": item["value"],
        "percent": round(percent, 1),
        "max_label": format_rain_mm(max_mm, config, WEATHER_FIELDS[field_id]["type"] == "rain_rate"),
    }


def rain_gauges(field_ids: list[str], config: dict[str, Any], weather: dict[str, Any]) -> list[dict[str, Any]]:
    return [gauge for field_id in field_ids if (gauge := rain_gauge(field_id, config, weather))]


def weather_compass(config: dict[str, Any], weather: dict[str, Any]) -> dict[str, Any]:
    direction = weather_item("wind_direction", config, weather)
    degrees = direction.get("numeric") if direction else None
    return {
        "available": degrees is not None,
        "degrees": round(float(degrees or 0), 1),
        "label": direction["value"] if direction else "Waiting for wind direction",
        "speed": weather_item("wind_speed", config, weather),
        "gust": weather_item("wind_gust", config, weather),
        "max_gust": weather_item("max_daily_gust", config, weather),
    }


def pressure_prediction(current_hpa: float, rate_3h: float) -> tuple[str, str]:
    if rate_3h >= 3:
        return "Rising quickly", "Pressure is climbing quickly; conditions may improve, although blustery leftovers can linger."
    if rate_3h >= 0.8:
        return "Rising", "Pressure is rising; becoming more settled is the barometer's best guess."
    if rate_3h <= -3:
        return "Falling quickly", "Pressure is dropping quickly; rain or wind may be on the way."
    if rate_3h <= -0.8:
        return "Falling", "Pressure is falling; conditions may become more unsettled."
    if current_hpa >= 1020:
        return "Steady high", "Pressure is high and steady; fair or settled weather is likely."
    if current_hpa <= 1000:
        return "Steady low", "Pressure is low and steady; dull or unsettled weather may hang around."
    return "Steady", "Pressure is fairly steady; little change expected."


def barometer_visual(status: str) -> dict[str, str]:
    status_text = status.lower()
    if "rising quickly" in status_text:
        return {"icon": "↗", "forecast_title": "Improving", "tone": "rising"}
    if "rising" in status_text:
        return {"icon": "↗", "forecast_title": "Settling", "tone": "rising"}
    if "falling quickly" in status_text:
        return {"icon": "↘", "forecast_title": "Turning wet", "tone": "falling"}
    if "falling" in status_text:
        return {"icon": "↘", "forecast_title": "Unsettled", "tone": "falling"}
    if "steady high" in status_text:
        return {"icon": "☀", "forecast_title": "Settled", "tone": "settled"}
    if "steady low" in status_text:
        return {"icon": "☁", "forecast_title": "Dull", "tone": "low"}
    if "gathering" in status_text:
        return {"icon": "…", "forecast_title": "Learning", "tone": "waiting"}
    return {"icon": "⛅", "forecast_title": "Steady", "tone": "steady"}


def pressure_history_points(state: dict[str, Any]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    history = state.get("pressure_history", [])
    if not isinstance(history, list):
        return points
    for entry in history:
        if not isinstance(entry, dict):
            continue
        timestamp = parse_datetime(entry.get("time"))
        value = parse_float(entry.get("hpa"))
        if timestamp and value is not None:
            points.append({"time": timestamp, "hpa": value})
    return sorted(points, key=lambda point: point["time"])


def barometer_status(config: dict[str, Any], weather: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    pressure = weather_item("pressure", config, weather)
    absolute_pressure = weather_item("absolute_pressure", config, weather)
    current_hpa = pressure_hpa_from_weather(weather)
    points = pressure_history_points(state)
    base_status = {
        "pressure": pressure,
        "absolute_pressure": absolute_pressure,
        "history_points": len(points),
        "trend": "Gathering history",
        "prediction": "Pressure history has started; the barometer estimate becomes useful after about 30 minutes and much better after 3 hours.",
        **barometer_visual("Gathering history"),
    }
    if current_hpa is None:
        return {**base_status, "trend": "No pressure reading", "prediction": "Waiting for a pressure reading from the weather station.", **barometer_visual("gathering")}
    if len(points) < 2:
        return base_status

    latest = points[-1]
    target_start = latest["time"] - timedelta(minutes=PRESSURE_TREND_MINUTES)
    baseline = next((point for point in points if point["time"] >= target_start), points[0])
    elapsed_minutes = max((latest["time"] - baseline["time"]).total_seconds() / 60, 0)
    if elapsed_minutes < PRESSURE_TREND_MINIMUM_MINUTES:
        trend = f"Gathering history ({round(elapsed_minutes)} min)"
        return {
            **base_status,
            "trend": trend,
            "prediction": "Still collecting readings. Give it about 30 minutes for an early trend, and around 3 hours for a proper barometer-style estimate.",
            **barometer_visual(trend),
        }

    change_hpa = latest["hpa"] - baseline["hpa"]
    rate_3h = change_hpa / (elapsed_minutes / 180)
    trend, prediction = pressure_prediction(current_hpa, rate_3h)
    trend_text = f"{trend} {rate_3h:+.1f} hPa / 3h"
    return {
        "pressure": pressure,
        "absolute_pressure": absolute_pressure,
        "history_points": len(points),
        "trend": trend_text,
        "prediction": prediction,
        "change_hpa": round(change_hpa, 2),
        "rate_3h": round(rate_3h, 2),
        "history_span_minutes": round(elapsed_minutes),
        **barometer_visual(trend),
    }


def weather_detail_data(config: dict[str, Any], weather: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return {
        "issued_at": format_display_datetime(state.get("last_weather_update")),
        "condition_rows": condition_rows(config, weather, state),
        "atmosphere": weather_items(["solar", "uv", "vpd"], config, weather),
        "rain_today_gauges": rain_gauges(["rain_rate", "hourly_rain", "daily_rain", "event_rain"], config, weather),
        "rain_longer_gauges": rain_gauges(["weekly_rain", "monthly_rain", "yearly_rain", "total_rain"], config, weather),
        "station_status": weather_items(
            ["station_type", "model", "frequency", "upload_interval", "last_station_update", "sensor_battery"],
            config,
            weather,
        ),
        "compass": weather_compass(config, weather),
        "barometer": barometer_status(config, weather, state),
    }


def form_text(name: str, fallback: Any) -> str:
    return str(request.form.get(name, fallback)).strip()


def form_int(name: str, fallback: Any, minimum: int, maximum: int) -> int:
    try:
        value = int(str(request.form.get(name, fallback)).strip())
    except (TypeError, ValueError):
        value = int(fallback)
    return max(minimum, min(maximum, value))


def form_choice(name: str, fallback: str, allowed: set[str]) -> str:
    value = str(request.form.get(name, fallback)).strip().lower()
    return value if value in allowed else fallback


def ordered_clock_cards_from_form() -> list[str]:
    ordered_cards: list[str] = []
    for field_id in request.form.getlist("clock_cards"):
        field_id = str(field_id)
        if field_id in CLOCK_CARD_FIELD_IDS and field_id not in ordered_cards:
            ordered_cards.append(field_id)
    return ordered_cards or DEFAULT_CLOCK_CARDS


def clock_card_option_label(field_id: str) -> str:
    if field_id == "barometer":
        return "Barometer"
    return WEATHER_FIELDS[field_id]["label"]


def save_settings_from_form(config: dict[str, Any]) -> dict[str, Any]:
    dashboard = config.setdefault("dashboard", {})
    weather = config.setdefault("weather", {})
    units = weather.setdefault("units", {})
    plexamp = config.setdefault("plexamp", {})
    airplay = config.setdefault("airplay", {})
    alarm = config.setdefault("alarm", {})

    dashboard["default_mode"] = form_choice("default_mode", str(dashboard.get("default_mode", "clock")), VALID_MODES - {"settings"})
    dashboard["idle_timeout_seconds"] = form_int("idle_timeout_seconds", dashboard.get("idle_timeout_seconds", 180), 0, 86400)
    dashboard["night_dim_start"] = form_text("night_dim_start", dashboard.get("night_dim_start", "02:00"))[:5]
    dashboard["night_dim_end"] = form_text("night_dim_end", dashboard.get("night_dim_end", "11:00"))[:5]

    weather["station_name"] = form_text("station_name", weather.get("station_name", "Weather or Not"))
    weather["reporting_station_name"] = form_text("reporting_station_name", weather.get("reporting_station_name", "Weather Station Name"))
    weather["auto_refresh_seconds"] = form_int("auto_refresh_seconds", weather.get("auto_refresh_seconds", 60), 0, 3600)
    weather["display_units"] = form_choice("display_units", str(weather.get("display_units", "metric")), {"metric", "imperial"})
    units["temperature"] = form_choice("unit_temperature", str(units.get("temperature", "c")), {"c", "f"})
    units["pressure"] = form_choice("unit_pressure", str(units.get("pressure", "hpa")), {"hpa", "inhg"})
    units["rain"] = form_choice("unit_rain", str(units.get("rain", "mm")), {"mm", "in"})
    units["wind"] = form_choice("unit_wind", str(units.get("wind", "mph")), {"mph", "kmh", "m/s"})
    weather["clock_cards"] = ordered_clock_cards_from_form()

    plexamp["url"] = form_text("plexamp_url", plexamp.get("url", "http://localhost:32500"))
    plexamp["pause_url"] = form_text("plexamp_pause_url", plexamp.get("pause_url", "http://localhost:32500/player/playback/pause"))
    plexamp["service_name"] = form_text("plexamp_service_name", plexamp.get("service_name", "plexamp.service"))
    airplay["display_name"] = form_text("airplay_display_name", airplay.get("display_name", "Bedroom Plexamp"))

    alarm["enabled"] = request.form.get("alarm_enabled") == "on"
    alarm["default_time"] = form_text("alarm_default_time", alarm.get("default_time", "11:00"))[:5]
    alarm["snooze_minutes"] = form_int("alarm_snooze_minutes", alarm.get("snooze_minutes", 10), 1, 120)

    save_json(CONFIG_PATH, config)
    return config


def settings_page_context(config: dict[str, Any], saved: bool = False, error: str | None = None) -> dict[str, Any]:
    return {
        "settings_saved": saved,
        "settings_error": error,
        "clock_card_options": [{"id": field_id, "label": clock_card_option_label(field_id)} for field_id in CLOCK_CARD_FIELD_IDS],
        "mode_options": [
            {"id": "clock", "label": "Clock"},
            {"id": "weather", "label": "Weather"},
            {"id": "plexamp", "label": "Plexamp"},
            {"id": "airplay", "label": "AirPlay"},
        ],
    }


app = Flask(__name__)


@app.context_processor
def inject_globals() -> dict[str, Any]:
    config = load_config()
    state = load_state(config)
    weather = state.get("weather", {})
    return {
        "config": config,
        "state": safe_state(state),
        "now": datetime.now(),
        "picked_weather": pick_weather_fields(config, weather, state),
        "weather_detail": weather_detail_data(config, weather, state),
    }


@app.route("/")
def index():
    return redirect(url_for("clock"))


@app.route("/clock")
def clock():
    set_mode("clock")
    return render_template("clock.html")


@app.route("/weather")
def weather():
    set_mode("weather")
    return render_template("weather.html")


@app.route("/airplay")
def airplay():
    set_mode("airplay")
    return render_template("airplay.html")


@app.route("/settings", methods=["GET", "POST"])
def settings():
    set_mode("settings")
    config = load_config()
    if request.method == "POST":
        try:
            save_settings_from_form(config)
            return redirect(url_for("settings", saved="1"))
        except OSError as exc:
            return render_template(
                "settings.html",
                **settings_page_context(config, saved=False, error=f"Could not save settings: {exc}"),
            ), 500
    return render_template("settings.html", **settings_page_context(config, saved=request.args.get("saved") == "1"))


@app.route("/plexamp")
def plexamp():
    set_mode("plexamp")
    plexamp_url = load_config().get("plexamp", {}).get("url", "http://localhost:32500")
    return render_template("plexamp.html", plexamp_url=plexamp_url)


@app.route("/api/status")
def api_status():
    config = load_config()
    state = load_state(config)
    weather = state.get("weather", {})
    return jsonify(
        {
            "state": safe_state(state),
            "config": config,
            "config_diagnostics": config_diagnostics(),
            "weather_display": pick_weather_fields(config, weather, state),
            "weather_detail": weather_detail_data(config, weather, state),
        }
    )


@app.route("/api/mode/<mode>", methods=["GET", "POST"])
def api_mode(mode: str):
    try:
        state = set_mode(mode)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "state": safe_state(state)})


@app.route("/api/weather/ecowitt", methods=["GET", "POST"])
def api_weather_ecowitt():
    config = load_config()
    state = load_state(config)
    payload = normalise_weather_payload()
    if payload:
        state["weather"] = payload
        state["last_weather_update"] = datetime.now().isoformat(timespec="seconds")
        update_weather_extremes(state, payload)
        update_pressure_history(state, payload)
        save_json(STATE_PATH, state)
        return jsonify(
            {
                "ok": True,
                "stored": True,
                "received_fields": len(payload),
                "last_weather_update": state["last_weather_update"],
            }
        )
    return jsonify(
        {
            "ok": True,
            "stored": False,
            "received_fields": 0,
            "message": "No weather fields received; existing cached weather was left unchanged.",
            "cached_fields": len(state.get("weather", {})),
            "last_weather_update": state.get("last_weather_update"),
            "weather_display": pick_weather_fields(config, state.get("weather", {}), state),
            "weather_detail": weather_detail_data(config, state.get("weather", {}), state),
        }
    )


if __name__ == "__main__":
    cfg = load_config()
    dashboard_cfg = cfg.get("dashboard", {})
    app.run(
        host=dashboard_cfg.get("host", "0.0.0.0"),
        port=int(dashboard_cfg.get("port", 8088)),
        debug=False,
    )
