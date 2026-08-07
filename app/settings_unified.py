from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Callable
from urllib.parse import urlparse

from flask import Flask, jsonify, request

try:
    from .alarm_audio import normalise_audio_settings
    from .alarm_config import validate_submitted_alarm_config
    from .audio_eq import MasterEqualizer
    from .shairport_name import ShairportNameManager, validate_receiver_name
    from .weather_forecast import WeatherForecastService
    from .weather_forecast_settings import public_forecast_config, submitted_forecast_config
except ImportError:  # Supports direct execution imports.
    from alarm_audio import normalise_audio_settings
    from alarm_config import validate_submitted_alarm_config
    from audio_eq import MasterEqualizer
    from shairport_name import ShairportNameManager, validate_receiver_name
    from weather_forecast import WeatherForecastService
    from weather_forecast_settings import public_forecast_config, submitted_forecast_config


ConfigProvider = Callable[[], dict[str, Any]]
ConfigSaver = Callable[[dict[str, Any]], None]
StatusProvider = Callable[[], dict[str, Any]]
Action = Callable[[], Any]
ScreenModeSetter = Callable[[str], Any]

VALID_MODES = {"clock", "weather", "plexamp", "airplay"}
VALID_CLOCK_FORMATS = {"12h", "24h"}
VALID_TRANSITIONS = {
    "grow-fade",
    "crossfade",
    "instant",
    "none",
    "horizontal-slide",
    "vertical-lift",
    "cover-reveal",
    "zoom",
    "blur-dissolve",
}
VALID_TEMPERATURE_UNITS = {"c", "f"}
VALID_PRESSURE_UNITS = {"hpa", "inhg"}
VALID_RAIN_UNITS = {"mm", "in"}
VALID_WIND_UNITS = {"mph", "kmh", "m/s"}
SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9_.@:-]{1,120}$")


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any, fallback: str = "", *, maximum: int = 240) -> str:
    text = str(value if value is not None else fallback).strip()
    return text[:maximum]


def _choice(value: Any, fallback: str, allowed: set[str]) -> str:
    candidate = str(value if value is not None else fallback).strip().lower()
    return candidate if candidate in allowed else fallback


def _integer(value: Any, fallback: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        parsed = fallback
    else:
        try:
            parsed = int(str(value).strip())
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


def _validated_url(value: Any, fallback: str, label: str) -> str:
    candidate = _text(value, fallback, maximum=500)
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"{label} must be a complete http:// or https:// URL.")
    if parsed.username or parsed.password:
        raise ValueError(f"{label} must not contain embedded credentials.")
    return candidate.rstrip("/") if parsed.path in {"", "/"} else candidate


def _validated_service_name(value: Any, fallback: str) -> str:
    name = _text(value, fallback, maximum=120)
    if not SERVICE_NAME_RE.fullmatch(name):
        raise ValueError("Plexamp service name contains unsupported characters.")
    return name


def _eq_band_value(model: dict[str, Any], band: str, fallback: float = 0.0) -> float:
    bands = _object(model.get("bands"))
    raw = bands.get(band, fallback)
    if isinstance(raw, dict):
        raw = raw.get("db", raw.get("stored_db", fallback))
    try:
        value = round(float(raw) * 2) / 2
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{band.title()} EQ gain must be a number.") from exc
    if not -6.0 <= value <= 6.0:
        raise ValueError(f"{band.title()} EQ gain must be from -6 dB to +6 dB.")
    return value


def normalise_eq_model(value: Any, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    """Normalise the legacy EQ shape for compatibility callers.

    Unified Settings no longer owns or applies this model. Runtime EQ state is
    authoritative through MasterEqualizer and /api/audio/eq.
    """
    source = _object(value)
    previous = _object(fallback)
    previous_bands = _object(previous.get("bands"))
    return {
        "enabled": _boolean(source.get("enabled"), _boolean(previous.get("enabled"), False)),
        "bands": {
            band: _eq_band_value(source, band, _eq_band_value({"bands": previous_bands}, band, 0.0))
            for band in ("bass", "mid", "treble")
        },
    }


def eq_model_from_status(config: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
    """Return the live EQ model; saved config.audio.eq is intentionally ignored."""
    _ = config  # Compatibility parameter for existing callers/tests.
    bands = _object(status.get("bands"))
    return {
        "enabled": status.get("bypassed") is not True and status.get("available") is True,
        "bands": {
            band: _eq_band_value({"bands": bands}, band, 0.0)
            for band in ("bass", "mid", "treble")
        },
    }


def _revision(settings: dict[str, Any]) -> str:
    encoded = json.dumps(settings, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


class UnifiedSettingsService:
    """Validate and commit appliance configuration as one transaction.

    Configuration is staged here. Runtime actions such as tests, live volume,
    EQ, diagnostic refreshes and forecast refresh-now remain separate endpoints.
    """

    def __init__(
        self,
        *,
        load_config: ConfigProvider,
        save_config: ConfigSaver,
        tone_manifest: StatusProvider,
        clock_card_ids: set[str],
        forecast: WeatherForecastService,
        equalizer: MasterEqualizer,
        shairport_name: ShairportNameManager,
        alarm_scheduler: Any = None,
        alarm_audio: Any = None,
        screen_idle_mode: ScreenModeSetter | None = None,
    ) -> None:
        self._load_config = load_config
        self._save_config = save_config
        self._tone_manifest = tone_manifest
        self._clock_card_ids = set(clock_card_ids)
        self._forecast = forecast
        self._equalizer = equalizer
        self._shairport_name = shairport_name
        self._alarm_scheduler = alarm_scheduler
        self._alarm_audio = alarm_audio
        self._screen_idle_mode = screen_idle_mode

    def _public_settings(
        self,
        config: dict[str, Any],
        *,
        eq_status: dict[str, Any] | None = None,
        receiver_status: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        dashboard = _object(config.get("dashboard"))
        weather = _object(config.get("weather"))
        units = _object(weather.get("units"))
        airplay = _object(config.get("airplay"))
        plexamp = _object(config.get("plexamp"))
        alarm_audio = normalise_audio_settings(config.get("alarm_audio"))
        eq = eq_status if isinstance(eq_status, dict) else self._equalizer.status()
        receiver = receiver_status if isinstance(receiver_status, dict) else self._shairport_name.status()
        default_mode = _choice(dashboard.get("default_mode"), "clock", VALID_MODES)
        startup_mode = _choice(dashboard.get("startup_mode"), default_mode, VALID_MODES)
        idle_mode = _choice(dashboard.get("idle_return_mode"), default_mode, VALID_MODES)
        configured_cards = weather.get("clock_cards") if isinstance(weather.get("clock_cards"), list) else []
        clock_cards = [
            str(item)
            for item in configured_cards
            if str(item) in self._clock_card_ids
        ]

        return {
            "dashboard": {
                "startup_mode": startup_mode,
                "idle_return_mode": idle_mode,
                "idle_timeout_seconds": _integer(
                    dashboard.get("idle_timeout_seconds"), 180, 5, 86400
                ),
            },
            "display": {
                "clock_format": _choice(
                    dashboard.get("clock_format"), "24h", VALID_CLOCK_FORMATS
                ),
                "transition_style": _choice(
                    dashboard.get("transition_style"), "grow-fade", VALID_TRANSITIONS
                ),
                "transition_duration_ms": _integer(
                    dashboard.get("transition_duration_ms"), 300, 0, 2000
                ),
            },
            "weather": {
                "station_name": _text(weather.get("station_name"), "Weather or Not", maximum=80),
                "reporting_station_name": _text(
                    weather.get("reporting_station_name"), "Weather Station", maximum=80
                ),
                "auto_refresh_seconds": _integer(
                    weather.get("auto_refresh_seconds"), 60, 0, 3600
                ),
                "units": {
                    "temperature": _choice(units.get("temperature"), "c", VALID_TEMPERATURE_UNITS),
                    "pressure": _choice(units.get("pressure"), "hpa", VALID_PRESSURE_UNITS),
                    "rain": _choice(units.get("rain"), "mm", VALID_RAIN_UNITS),
                    "wind": _choice(units.get("wind"), "mph", VALID_WIND_UNITS),
                },
                "clock_cards": clock_cards,
                "forecast": public_forecast_config(config),
            },
            "alarms": deepcopy(_object(config.get("alarm"))),
            "alarm_audio": {
                "master_enabled": alarm_audio["master_enabled"],
                "scheduled_enabled": alarm_audio.get("scheduled_enabled", False),
                "shared_mixer_enabled": alarm_audio["shared_mixer_enabled"],
                "hardware_device": alarm_audio["hardware_device"],
                "alsa_device": alarm_audio["alsa_device"],
                "test_duration_seconds": alarm_audio["test_duration_seconds"],
            },
            "airplay": {
                "receiver_name": _text(
                    airplay.get("display_name") or receiver.get("receiver_name"),
                    "Bedroom Plexamp",
                    maximum=50,
                ),
                "default_volume_percent": _integer(
                    airplay.get("default_volume_percent"), 60, 0, 100
                ),
                "apply_default_volume_on_start": airplay.get(
                    "apply_default_volume_on_start", True
                ) is not False,
                "pause_hold_seconds": _integer(
                    airplay.get("pause_hold_seconds"), 600, 30, 3600
                ),
            },
            "audio": {
                "eq": eq_model_from_status(config, eq),
            },
            "plexamp": {
                "url": _text(plexamp.get("url"), "http://localhost:32500", maximum=500),
                "pause_url": _text(
                    plexamp.get("pause_url"),
                    "http://localhost:32500/player/playback/pause",
                    maximum=500,
                ),
                "service_name": _text(
                    plexamp.get("service_name"), "plexamp.service", maximum=120
                ),
            },
        }

    def snapshot(self) -> dict[str, Any]:
        config = self._load_config()
        eq_status = self._equalizer.status()
        receiver_status = self._shairport_name.status()
        settings = self._public_settings(
            config,
            eq_status=eq_status,
            receiver_status=receiver_status,
        )
        return {
            "ok": True,
            "revision": _revision(settings),
            "settings": settings,
            "capabilities": {
                "transactional_save": True,
                "actions_are_separate": True,
                "airplay_receiver_management": receiver_status.get("installed") is True,
                "eq_configuration": False,
                "eq_runtime_control": True,
                "eq_backend_available": eq_status.get("available") is True,
                "persistent_mixer_trims_are_immediate": True,
            },
            "status": {
                "airplay_receiver": receiver_status,
                "eq": eq_status,
                "forecast": self._forecast.snapshot(),
            },
        }

    def _normalise_dashboard(self, config: dict[str, Any], payload: Any) -> None:
        source = _object(payload)
        dashboard = config.setdefault("dashboard", {})
        startup = _choice(source.get("startup_mode"), "clock", VALID_MODES)
        idle = _choice(source.get("idle_return_mode"), startup, VALID_MODES)
        dashboard.update(
            {
                "startup_mode": startup,
                "idle_return_mode": idle,
                # Compatibility until all consumers have migrated.
                "default_mode": startup,
                "idle_timeout_seconds": _integer(
                    source.get("idle_timeout_seconds"),
                    dashboard.get("idle_timeout_seconds", 180),
                    5,
                    86400,
                ),
            }
        )

    def _normalise_display(self, config: dict[str, Any], payload: Any) -> None:
        source = _object(payload)
        dashboard = config.setdefault("dashboard", {})
        dashboard.update(
            {
                "clock_format": _choice(
                    source.get("clock_format"),
                    str(dashboard.get("clock_format", "24h")),
                    VALID_CLOCK_FORMATS,
                ),
                "transition_style": _choice(
                    source.get("transition_style"),
                    str(dashboard.get("transition_style", "grow-fade")),
                    VALID_TRANSITIONS,
                ),
                "transition_duration_ms": _integer(
                    source.get("transition_duration_ms"),
                    dashboard.get("transition_duration_ms", 300),
                    0,
                    2000,
                ),
            }
        )

    def _normalise_weather(self, config: dict[str, Any], payload: Any) -> None:
        source = _object(payload)
        weather = config.setdefault("weather", {})
        units = weather.setdefault("units", {})
        weather["station_name"] = _text(
            source.get("station_name"), weather.get("station_name", "Weather or Not"), maximum=80
        )
        weather["reporting_station_name"] = _text(
            source.get("reporting_station_name"),
            weather.get("reporting_station_name", "Weather Station"),
            maximum=80,
        )
        weather["auto_refresh_seconds"] = _integer(
            source.get("auto_refresh_seconds"), weather.get("auto_refresh_seconds", 60), 0, 3600
        )
        submitted_units = _object(source.get("units"))
        units.update(
            {
                "temperature": _choice(
                    submitted_units.get("temperature"),
                    str(units.get("temperature", "c")),
                    VALID_TEMPERATURE_UNITS,
                ),
                "pressure": _choice(
                    submitted_units.get("pressure"),
                    str(units.get("pressure", "hpa")),
                    VALID_PRESSURE_UNITS,
                ),
                "rain": _choice(
                    submitted_units.get("rain"),
                    str(units.get("rain", "mm")),
                    VALID_RAIN_UNITS,
                ),
                "wind": _choice(
                    submitted_units.get("wind"),
                    str(units.get("wind", "mph")),
                    VALID_WIND_UNITS,
                ),
            }
        )
        # The old metric/imperial switch becomes a compatibility hint only.
        weather["display_units"] = (
            "imperial"
            if units["temperature"] == "f" and units["pressure"] == "inhg" and units["rain"] == "in"
            else "metric"
        )
        submitted_cards = source.get("clock_cards")
        if not isinstance(submitted_cards, list):
            raise ValueError("Clock weather cards must be an ordered list.")
        cards: list[str] = []
        for item in submitted_cards:
            card_id = str(item)
            if card_id not in self._clock_card_ids:
                raise ValueError(f"Unknown Clock weather card: {card_id}")
            if card_id not in cards:
                cards.append(card_id)
        weather["clock_cards"] = cards

        forecast_payload = source.get("forecast")
        if isinstance(forecast_payload, dict):
            updated, _normalised = submitted_forecast_config(config, forecast_payload)
            config.clear()
            config.update(updated)

    def _normalise_airplay(self, config: dict[str, Any], payload: Any) -> None:
        source = _object(payload)
        airplay = config.setdefault("airplay", {})
        receiver_name = validate_receiver_name(
            source.get("receiver_name", airplay.get("display_name", "Bedroom Plexamp"))
        )
        airplay.update(
            {
                "display_name": receiver_name,
                "default_volume_percent": _integer(
                    source.get("default_volume_percent"),
                    airplay.get("default_volume_percent", 60),
                    0,
                    100,
                ),
                "apply_default_volume_on_start": _boolean(
                    source.get("apply_default_volume_on_start"),
                    airplay.get("apply_default_volume_on_start", True) is not False,
                ),
                "pause_hold_seconds": _integer(
                    source.get("pause_hold_seconds"),
                    airplay.get("pause_hold_seconds", 600),
                    30,
                    3600,
                ),
            }
        )

    def _normalise_plexamp(self, config: dict[str, Any], payload: Any) -> None:
        source = _object(payload)
        plexamp = config.setdefault("plexamp", {})
        base_url = _validated_url(
            source.get("url"), str(plexamp.get("url", "http://localhost:32500")), "Plexamp URL"
        )
        pause_fallback = f"{base_url.rstrip('/')}/player/playback/pause"
        plexamp.update(
            {
                "url": base_url,
                "pause_url": _validated_url(
                    source.get("pause_url"),
                    str(plexamp.get("pause_url", pause_fallback)),
                    "Plexamp pause URL",
                ),
                "service_name": _validated_service_name(
                    source.get("service_name"),
                    str(plexamp.get("service_name", "plexamp.service")),
                ),
            }
        )

    @staticmethod
    def _remove_legacy_eq_config(config: dict[str, Any]) -> None:
        audio = config.get("audio")
        if not isinstance(audio, dict):
            return
        audio.pop("eq", None)
        if not audio:
            config.pop("audio", None)

    def apply(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Settings request must be a JSON object.")
        submitted = payload.get("settings")
        if not isinstance(submitted, dict):
            raise ValueError("Settings request is missing its settings object.")

        before_config = self._load_config()
        before_snapshot = self.snapshot()
        requested_revision = str(payload.get("revision") or "").strip()
        if requested_revision and requested_revision != before_snapshot["revision"]:
            raise RuntimeError(
                "Settings changed elsewhere after this page was opened. Reload before saving."
            )

        candidate = deepcopy(before_config)
        self._normalise_dashboard(candidate, submitted.get("dashboard"))
        self._normalise_display(candidate, submitted.get("display"))
        self._normalise_weather(candidate, submitted.get("weather"))

        if "alarms" in submitted:
            candidate["alarm"] = validate_submitted_alarm_config(
                submitted.get("alarms"), self._tone_manifest()
            )
        if "alarm_audio" in submitted:
            current_audio = _object(candidate.get("alarm_audio"))
            candidate["alarm_audio"] = normalise_audio_settings(
                {**current_audio, **_object(submitted.get("alarm_audio"))}
            )

        self._normalise_airplay(candidate, submitted.get("airplay"))
        self._normalise_plexamp(candidate, submitted.get("plexamp"))
        self._remove_legacy_eq_config(candidate)

        before_public = before_snapshot["settings"]
        candidate_public = self._public_settings(
            candidate,
            eq_status=before_snapshot["status"]["eq"],
            receiver_status=before_snapshot["status"]["airplay_receiver"],
        )
        receiver_changed = (
            candidate_public["airplay"]["receiver_name"]
            != before_public["airplay"]["receiver_name"]
        )
        forecast_changed = (
            candidate_public["weather"]["forecast"]
            != before_public["weather"]["forecast"]
        )
        alarms_changed = candidate_public["alarms"] != before_public["alarms"]
        alarm_audio_changed = (
            candidate_public["alarm_audio"] != before_public["alarm_audio"]
        )

        if receiver_changed and payload.get("confirm_airplay_restart") is not True:
            raise PermissionError(
                "Changing the AirPlay receiver name briefly restarts Shairport Sync. Confirm the restart before saving."
            )

        receiver_applied = False
        previous_receiver_name = before_public["airplay"]["receiver_name"]
        try:
            if receiver_changed:
                self._shairport_name.apply(candidate_public["airplay"]["receiver_name"])
                receiver_applied = True
            self._save_config(candidate)
        except Exception:
            if receiver_applied:
                try:
                    self._shairport_name.apply(previous_receiver_name)
                except Exception:
                    pass
            raise

        if alarms_changed and self._alarm_scheduler is not None:
            try:
                self._alarm_scheduler.wake()
                if self._alarm_scheduler.status().get("running"):
                    self._alarm_scheduler.recalculate()
            except Exception:
                pass

        if alarm_audio_changed and self._alarm_audio is not None:
            new_audio = normalise_audio_settings(candidate.get("alarm_audio"))
            if not new_audio.get("master_enabled") or not new_audio.get("scheduled_enabled"):
                try:
                    self._alarm_audio.stop_playback(
                        reason="settings-audio-safety-disabled", restore=True
                    )
                    self._alarm_audio.disarm_occurrence()
                except Exception:
                    pass

        if forecast_changed:
            self._forecast.wake()
            if public_forecast_config(candidate).get("enabled"):
                self._forecast.refresh(force=True)
            else:
                self._forecast.refresh(force=False)

        if self._screen_idle_mode is not None:
            try:
                self._screen_idle_mode(candidate_public["dashboard"]["idle_return_mode"])
            except Exception:
                pass

        result = self.snapshot()
        result.update(
            {
                "message": "Settings saved as one validated transaction.",
                "changed": {
                    "airplay_receiver_restarted": receiver_changed,
                    "eq_applied": False,
                    "forecast_refreshed": forecast_changed,
                    "alarms_recalculated": alarms_changed,
                    "alarm_audio_safety_updated": alarm_audio_changed,
                },
            }
        )
        return result


def register_unified_settings_api(app: Flask, service: UnifiedSettingsService) -> None:
    if "api_unified_settings" in app.view_functions:
        return

    @app.route("/api/settings", methods=["GET", "POST"])
    def api_unified_settings():
        if request.method == "GET":
            return jsonify(service.snapshot())
        payload = request.get_json(silent=True)
        try:
            return jsonify(service.apply(payload))
        except PermissionError as exc:
            return jsonify(
                {
                    "ok": False,
                    "error": str(exc),
                    "confirmation_required": "airplay_restart",
                }
            ), 409
        except RuntimeError as exc:
            return jsonify({"ok": False, "error": str(exc), "reload_required": True}), 409
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except OSError as exc:
            return jsonify({"ok": False, "error": f"Could not save settings: {exc}"}), 500
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
