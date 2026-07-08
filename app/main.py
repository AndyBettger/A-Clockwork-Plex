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

VALID_MODES = {"clock", "airplay", "plexamp", "settings"}


def load_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return fallback
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return fallback


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


def pick_weather_fields(weather: dict[str, Any]) -> dict[str, Any]:
    """Return common Ecowitt/WU-style fields with friendly names for the UI."""
    mappings = {
        "Outdoor temp": ["tempf", "tempc", "outtemp", "outdoor_temperature"],
        "Indoor temp": ["indoortempf", "indoortempc", "intemp", "indoor_temperature"],
        "Humidity": ["humidity", "outhumi", "outdoor_humidity"],
        "Indoor humidity": ["indoorhumidity", "inhumi", "indoor_humidity"],
        "Wind": ["windspeedmph", "wind_speed", "windspdmph_avg10m"],
        "Gust": ["windgustmph", "wind_gust", "maxdailygust"],
        "Rain today": ["dailyrainin", "rainratein", "rain_daily", "eventrainin"],
        "Pressure": ["baromrelin", "baromabsin", "pressure", "barometer"],
        "Solar": ["solarradiation", "solar"],
        "UV": ["uv", "uvi"],
    }

    picked: dict[str, Any] = {}
    lower_weather = {str(k).lower(): v for k, v in weather.items()}

    for label, keys in mappings.items():
        for key in keys:
            if key.lower() in lower_weather:
                picked[label] = lower_weather[key.lower()]
                break

    return picked


app = Flask(__name__)


@app.context_processor
def inject_globals() -> dict[str, Any]:
    config = load_config()
    state = load_state(config)
    return {
        "config": config,
        "state": state,
        "now": datetime.now(),
        "picked_weather": pick_weather_fields(state.get("weather", {})),
    }


@app.route("/")
def index():
    return redirect(url_for("clock"))


@app.route("/clock")
def clock():
    set_mode("clock")
    return render_template("clock.html")


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
    return jsonify({"state": state, "config": config, "weather_display": pick_weather_fields(state.get("weather", {}))})


@app.route("/api/mode/<mode>", methods=["GET", "POST"])
def api_mode(mode: str):
    try:
        state = set_mode(mode)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "state": state})


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
            "weather_display": pick_weather_fields(state.get("weather", {})),
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
