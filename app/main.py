from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"
EXAMPLE_CONFIG_PATH = BASE_DIR / "config.example.json"
STATE_PATH = BASE_DIR / "state.json"

VALID_MODES = {"clock", "weather", "airplay", "plexamp", "settings"}
SENSITIVE_WEATHER_KEYS = {"passkey", "password", "secret", "token", "api_key", "apikey"}

COMPASS_POINTS = [
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
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
    "last_station_update": {"label": "Station timestamp", "keys": ["dateutc"], "type": "text"},
    "sensor_battery": {"label": "Sensor battery", "keys": ["wh65batt"], "type": "battery"},
}

RAIN_GAUGE_LIMITS_MM = {
    "hourly_rain": 10,
    "daily_rain": 25,
    "weekly_rain": 75,
    "monthly_rain": 150,
    "yearly_rain": 1000,
}


def load_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return fallback
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"A Clockwork Plex: failed to load JSON from {path}: {exc}", flush=True)
        return fallback


def json_file_status(path: Path) -> dict[str, Any]:
    status: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "valid": False,
        "error": None,
    }

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


def save_json(path: Path, data: dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp_path.replace(path)


def load_config() -> dict[str, Any]:
    fallback = load_json(EXAMPLE_CONFIG_PATH, {})
    user_config = load_json(CONFIG_PATH, {})
    return deep_merge(fallback, user_config)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def default_state(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": config.get("dashboard", {}).get("default_mode", "clock"),
        "last_mode_change": datetime.now().isoformat(timespec="seconds"),
        "weather": {},
        "last_weather_update": None,
    }


def load_state(config: dict[str, Any]) -> dict[str, Any]:
    state = load_json(STATE_PATH, default_state(config))
    if state.get("mode") not in VALID_MODES:
        state["mode"] = "clock"
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

    # Ecowitt/WU-style posts sometimes include blank values. Keep meaningful keys only.
    return {str(key): value for key, value in payload.items() if str(key).strip() and str(value).strip()}


def redacted_weather(weather: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in weather.items():
        key_text = str(key)
        if key_text.lower() in SENSITIVE_WEATHER_KEYS:
            redacted[key_text] = "[redacted]"
        else:
            redacted[key_text] = value
    return redacted


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


def inches_to_mm(value: float) -> float:
    return value * 25.4


def inhg_to_hpa(value: float) -> float:
    return value * 33.8638866667


def mph_to_kmh(value: float) -> float:
    return value * 1.609344


def mph_to_ms(value: float) -> float:
    return value * 0.44704


def format_float(value: float, places: int) -> str:
    return f"{value:.{places}f}"


def compass_label(degrees: float) -> str:
    index = round((degrees % 360) / 22.5) % len(COMPASS_POINTS)
    return COMPASS_POINTS[index]


def format_weather_value(field_id: str, weather: dict[str, Any], config: dict[str, Any]) -> dict[str, Any] | None:
    field = WEATHER_FIELDS[field_id]
    source_key, raw_value = get_weather_value(weather, field["keys"])
    if raw_value is None:
        return None

    field_type = field["type"]
    units = weather_units(config)
    numeric = parse_float(raw_value)
    value = str(raw_value)
    numeric_value: float | None = numeric
    unit = ""

    if field_type == "temperature" and numeric is not None:
        target = units["temperature"]
        source_is_f = source_key.endswith("f") if source_key else True
        converted = fahrenheit_to_celsius(numeric) if source_is_f and target == "c" else numeric
        numeric_value = converted
        unit = "°C" if target == "c" else "°F"
        value = f"{format_float(converted, 1)}{unit}"

    elif field_type == "pressure" and numeric is not None:
        target = units["pressure"]
        source_is_inhg = bool(source_key and source_key.endswith("in"))
        converted = inhg_to_hpa(numeric) if source_is_inhg and target in {"hpa", "mbar"} else numeric
        numeric_value = converted
        if target in {"hpa", "mbar"}:
            unit = "hPa"
            value = f"{format_float(converted, 1)} {unit}"
        else:
            unit = "inHg"
            value = f"{format_float(converted, 3)} {unit}"

    elif field_type in {"rain", "rain_rate"} and numeric is not None:
        target = units["rain"]
        source_is_inches = bool(source_key and source_key.endswith("in"))
        converted = inches_to_mm(numeric) if source_is_inches and target == "mm" else numeric
        numeric_value = converted
        suffix = "/hr" if field_type == "rain_rate" else ""
        if target == "mm":
            unit = f"mm{suffix}"
            value = f"{format_float(converted, 1)} {unit}"
        else:
            unit = f"in{suffix}"
            value = f"{format_float(converted, 3)} {unit}"

    elif field_type == "wind" and numeric is not None:
        target = units["wind"]
        if target == "kmh":
            converted = mph_to_kmh(numeric)
            unit = "km/h"
        elif target in {"ms", "mps", "m/s"}:
            converted = mph_to_ms(numeric)
            unit = "m/s"
        else:
            converted = numeric
            unit = "mph"
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
        # Ecowitt WH65 reports 0 as OK on many models.
        numeric_value = numeric
        value = "OK" if numeric == 0 else str(raw_value)

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
    items: list[dict[str, Any]] = []
    for field_id in field_ids:
        item = weather_item(field_id, config, weather)
        if item:
            items.append(item)
    return items


def pick_weather_fields(config: dict[str, Any], weather: dict[str, Any]) -> dict[str, Any]:
    """Return formatted, friendly fields for the compact clock page."""
    clock_cards = config.get("weather", {}).get(
        "clock_cards",
        ["outdoor_temp", "humidity", "wind_speed", "wind_gust", "daily_rain", "pressure"],
    )
    if not isinstance(clock_cards, list):
        clock_cards = ["outdoor_temp", "humidity", "wind_speed", "wind_gust", "daily_rain", "pressure"]

    return {
        item["label"]: item["value"]
        for item in weather_items([str(field_id) for field_id in clock_cards], config, weather)
    }


def rain_gauge(field_id: str, config: dict[str, Any], weather: dict[str, Any]) -> dict[str, Any] | None:
    item = weather_item(field_id, config, weather)
    raw_item = weather_item(field_id, {"weather": {"display_units": "metric", "units": {"rain": "mm"}}}, weather)
    if not item or not raw_item or raw_item.get("numeric") is None:
        return None

    max_mm = RAIN_GAUGE_LIMITS_MM.get(field_id, 25)
    amount_mm = float(raw_item["numeric"])
    percent = max(0, min(100, (amount_mm / max_mm) * 100)) if max_mm else 0

    return {
        "label": item["label"],
        "value": item["value"],
        "percent": round(percent, 1),
        "max_label": f"{max_mm:g} mm",
    }


def rain_gauges(config: dict[str, Any], weather: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        gauge
        for field_id in ["hourly_rain", "daily_rain", "weekly_rain", "monthly_rain", "yearly_rain"]
        if (gauge := rain_gauge(field_id, config, weather))
    ]


def weather_compass(config: dict[str, Any], weather: dict[str, Any]) -> dict[str, Any]:
    direction = weather_item("wind_direction", config, weather)
    speed = weather_item("wind_speed", config, weather)
    gust = weather_item("wind_gust", config, weather)
    max_gust = weather_item("max_daily_gust", config, weather)

    degrees = direction.get("numeric") if direction else None
    return {
        "available": degrees is not None,
        "degrees": round(float(degrees or 0), 1),
        "label": direction["value"] if direction else "Waiting for wind direction",
        "speed": speed,
        "gust": gust,
        "max_gust": max_gust,
    }


def barometer_status(config: dict[str, Any], weather: dict[str, Any]) -> dict[str, Any]:
    pressure = weather_item("pressure", config, weather)
    absolute_pressure = weather_item("absolute_pressure", config, weather)

    return {
        "pressure": pressure,
        "absolute_pressure": absolute_pressure,
        "trend": "History needed",
        "prediction": "Pressure trend will be calculated once the app starts storing past readings.",
    }


def weather_detail_data(config: dict[str, Any], weather: dict[str, Any]) -> dict[str, Any]:
    return {
        "main_conditions": weather_items(
            ["outdoor_temp", "indoor_temp", "humidity", "indoor_humidity", "pressure", "solar", "uv", "vpd"],
            config,
            weather,
        ),
        "rain_totals": weather_items(
            ["rain_rate", "hourly_rain", "daily_rain", "weekly_rain", "monthly_rain", "yearly_rain", "total_rain", "event_rain"],
            config,
            weather,
        ),
        "station_status": weather_items(
            ["station_type", "model", "frequency", "upload_interval", "last_station_update", "sensor_battery"],
            config,
            weather,
        ),
        "compass": weather_compass(config, weather),
        "rain_gauges": rain_gauges(config, weather),
        "barometer": barometer_status(config, weather),
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
        "picked_weather": pick_weather_fields(config, weather),
        "weather_detail": weather_detail_data(config, weather),
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


@app.route("/settings")
def settings():
    set_mode("settings")
    return render_template("settings.html")


@app.route("/plexamp")
def plexamp():
    set_mode("plexamp")
    plexamp_url = load_config().get("plexamp", {}).get("url", "http://localhost:32500")
    return redirect(plexamp_url)


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
            "weather_display": pick_weather_fields(config, weather),
            "weather_detail": weather_detail_data(config, weather),
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
        save_json(STATE_PATH, state)
        return jsonify(
            {
                "ok": True,
                "stored": True,
                "received_fields": len(payload),
                "last_weather_update": state["last_weather_update"],
            }
        )

    # Do not clear cached weather when a browser/manual request hits the receiver URL.
    return jsonify(
        {
            "ok": True,
            "stored": False,
            "received_fields": 0,
            "message": "No weather fields received; existing cached weather was left unchanged.",
            "cached_fields": len(state.get("weather", {})),
            "last_weather_update": state.get("last_weather_update"),
            "weather_display": pick_weather_fields(config, state.get("weather", {})),
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
