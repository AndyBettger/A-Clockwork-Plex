from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote

from flask import Flask, Response


BACKUP_SCHEMA_VERSION = 1
PLEXAMP_SETTINGS_PREFIX = "@Plexamp:settings:"
PLEXAMP_HEADLESS_SPECS = {
    "audioConversionBitrate": "integer",
    "autoPlayEnabled": "boolean",
    "cacheSize": "integer",
    "cachingWiFi": "integer",
    "loudnessLeveling": "boolean",
    "precacheNetworkSpeed": "integer",
    "sampleRateConversionQuality": "integer",
    "sampleRateMatching": "integer",
}
MIXER_CHANNELS = ("master", "plexamp", "airplay", "alarm")

SettingsSnapshot = Callable[[], dict[str, Any]]
MixerSnapshot = Callable[[], dict[str, Any]]
NowProvider = Callable[[], datetime]


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _pick(source: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    mapping = _object(source)
    return {key: deepcopy(mapping[key]) for key in keys if key in mapping}


def _decode_plexamp_scalar(text: str, expected: str) -> bool | int:
    value = str(text).strip()
    if expected == "boolean":
        if value == "Btrue":
            return True
        if value == "Bfalse":
            return False
        raise ValueError("unexpected Plexamp boolean encoding")
    if expected == "integer":
        if not value.startswith("N"):
            raise ValueError("unexpected Plexamp numeric encoding")
        number = value[1:]
        if not re.fullmatch(r"-?(?:0|[1-9][0-9]{0,15})", number):
            raise ValueError("unexpected Plexamp integer encoding")
        return int(number)
    raise ValueError("unsupported Plexamp preference type")


def read_plexamp_headless_preferences(home: Path) -> tuple[dict[str, Any], list[str]]:
    """Read only the approved non-auth Plexamp Headless preference allow-list."""
    settings_dir = home / ".local" / "share" / "Plexamp" / "Settings"
    if not settings_dir.is_dir():
        return {}, ["Plexamp Settings directory is unavailable."]

    paths: dict[str, Path] = {}
    try:
        entries = list(settings_dir.iterdir())
    except OSError as exc:
        return {}, [f"Plexamp Settings directory could not be read: {exc}"]

    for entry in entries:
        if not entry.is_file():
            continue
        decoded = unquote(entry.name)
        if not decoded.startswith(PLEXAMP_SETTINGS_PREFIX):
            continue
        key = decoded[len(PLEXAMP_SETTINGS_PREFIX) :]
        if key in PLEXAMP_HEADLESS_SPECS:
            paths[key] = entry

    result: dict[str, Any] = {}
    warnings: list[str] = []
    for key in sorted(PLEXAMP_HEADLESS_SPECS, key=str.casefold):
        path = paths.get(key)
        if path is None:
            continue
        try:
            if path.stat().st_size > 64:
                raise ValueError("value exceeds 64-byte limit")
            raw = path.read_bytes()
            text = raw.decode("utf-8", errors="strict")
            result[key] = _decode_plexamp_scalar(text, PLEXAMP_HEADLESS_SPECS[key])
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            warnings.append(f"Plexamp preference {key} was skipped: {exc}")
    return result, warnings


def read_plexamp_version(home: Path) -> str | None:
    """Read non-sensitive runtime package metadata when available."""
    package_path = home / "plexamp" / "package.json"
    try:
        if not package_path.is_file() or package_path.stat().st_size > 1_000_000:
            return None
        payload = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    value = str(payload.get("version") or "").strip()
    return value[:80] or None


def portable_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Reduce the public Settings model to the portable user-owned subset."""
    dashboard = _pick(
        settings.get("dashboard"),
        ("startup_mode", "idle_return_mode", "idle_timeout_seconds"),
    )
    display = _pick(
        settings.get("display"),
        (
            "clock_format",
            "transition_style",
            "transition_duration_ms",
            "daytime_theme",
            "alarm_indicator_mode",
            "night_dim_enabled",
            "night_dim_start",
            "night_dim_end",
            "night_dim_level_percent",
            "night_dim_active_level_percent",
            "night_dim_wake_seconds",
            "night_clock_mode",
            "night_burn_in_shift",
            "night_dim_style",
            "night_dim_active_style",
        ),
    )

    source_weather = _object(settings.get("weather"))
    weather = _pick(
        source_weather,
        (
            "station_name",
            "reporting_station_name",
            "auto_refresh_seconds",
            "units",
            "clock_cards",
            "forecast",
            "historical_rainfall",
        ),
    )
    observations = _object(source_weather.get("observations"))
    if observations:
        portable_observations = _pick(observations, ("provider",))
        ecowitt = _pick(observations.get("ecowitt_push"), ("path", "fresh_seconds"))
        wunderground = _pick(
            observations.get("weather_underground"),
            (
                "station_id",
                "refresh_seconds",
                "stale_seconds",
                "request_timeout_seconds",
                "pressure_history_hours",
            ),
        )
        if ecowitt:
            portable_observations["ecowitt_push"] = ecowitt
        if wunderground:
            portable_observations["weather_underground"] = wunderground
        weather["observations"] = portable_observations

    return {
        "dashboard": dashboard,
        "display": display,
        "weather": weather,
        "alarms": deepcopy(_object(settings.get("alarms"))),
        "airplay": _pick(
            settings.get("airplay"),
            (
                "receiver_name",
                "default_volume_percent",
                "apply_default_volume_on_start",
                "pause_hold_seconds",
            ),
        ),
    }


def portable_eq(settings: dict[str, Any]) -> dict[str, Any]:
    eq = _object(_object(settings.get("audio")).get("eq"))
    bands = _pick(eq.get("bands"), ("bass", "mid", "treble"))
    result = _pick(eq, ("enabled",))
    if bands:
        result["bands"] = bands
    return result


def portable_mixer(status: dict[str, Any]) -> dict[str, int]:
    channels = _object(status.get("channels"))
    result: dict[str, int] = {}
    for channel_id in MIXER_CHANNELS:
        channel = _object(channels.get(channel_id))
        value = channel.get("percent")
        if isinstance(value, bool):
            continue
        try:
            numeric = int(round(float(value)))
        except (TypeError, ValueError):
            continue
        if 0 <= numeric <= 100:
            result[channel_id] = numeric
    return result


class ConfigurationBackupService:
    """Build a versioned read-only export from existing appliance authorities."""

    def __init__(
        self,
        *,
        settings_snapshot: SettingsSnapshot,
        app_version_path: Path,
        home: Path | None = None,
        mixer_snapshot: MixerSnapshot | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._settings_snapshot = settings_snapshot
        self._app_version_path = Path(app_version_path)
        self._home = Path.home() if home is None else Path(home)
        self._mixer_snapshot = mixer_snapshot
        self._now = now_provider or (lambda: datetime.now().astimezone())

    def _version_metadata(self) -> dict[str, Any]:
        try:
            payload = json.loads(self._app_version_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Application version metadata is unavailable: {exc}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Application version metadata must be a JSON object.")
        return payload

    def build(self) -> dict[str, Any]:
        snapshot = self._settings_snapshot()
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("settings"), dict):
            raise RuntimeError("Unified Settings did not return a valid snapshot.")
        settings = snapshot["settings"]
        version = self._version_metadata()
        now = self._now()
        if now.tzinfo is None:
            now = now.astimezone()

        headless, headless_warnings = read_plexamp_headless_preferences(self._home)
        plexamp: dict[str, Any] = {"headless_preferences": headless}
        plexamp_version = read_plexamp_version(self._home)
        if plexamp_version:
            plexamp["source_version"] = plexamp_version

        audio: dict[str, Any] = {"eq": portable_eq(settings)}
        omissions: list[dict[str, str]] = [
            {
                "section": "plexamp.browser_preferences",
                "reason": "Home-layout export awaits a live browser-side allow-listed authority; Chromium profile/LevelDB files are never copied.",
            },
            {
                "section": "credentials",
                "reason": "Managed secrets and authentication are deliberately excluded and must be recommissioned.",
            },
        ]
        if self._mixer_snapshot is not None:
            try:
                mixer = portable_mixer(self._mixer_snapshot())
            except Exception as exc:
                mixer = {}
                headless_warnings.append(f"Persistent mixer levels were skipped: {exc}")
            if mixer:
                audio["mixer"] = mixer
            else:
                omissions.append(
                    {
                        "section": "a_clockwork_plex.audio.mixer",
                        "reason": "Persistent mixer levels were unavailable at export time.",
                    }
                )
        else:
            omissions.append(
                {
                    "section": "a_clockwork_plex.audio.mixer",
                    "reason": "Persistent mixer provider is unavailable.",
                }
            )

        return {
            "schema_version": BACKUP_SCHEMA_VERSION,
            "created_at": now.isoformat(timespec="seconds"),
            "source": {
                "application": str(version.get("name") or "A Clockwork Plex"),
                "app_version": str(version.get("version") or ""),
                "release_tag": str(version.get("tag") or ""),
                "release_name": str(version.get("release_name") or ""),
            },
            "a_clockwork_plex": {
                "settings": portable_settings(settings),
                "audio": audio,
            },
            "plexamp": plexamp,
            "export_report": {
                "warnings": headless_warnings,
                "omitted": omissions,
            },
        }

    def filename(self) -> str:
        stamp = self._now().astimezone().strftime("%Y-%m-%d_%H%M%S")
        return f"A-Clockwork-Plex-backup-{stamp}.json"


def register_configuration_backup_api(
    app: Flask,
    service: ConfigurationBackupService,
) -> None:
    if "api_configuration_backup" in app.view_functions:
        return

    @app.get("/api/settings/backup")
    def api_configuration_backup() -> Response:
        try:
            backup = service.build()
        except RuntimeError as exc:
            return Response(
                json.dumps({"ok": False, "error": str(exc)}),
                status=503,
                mimetype="application/json",
            )
        response = Response(
            json.dumps(backup, indent=2, ensure_ascii=False) + "\n",
            mimetype="application/json",
        )
        response.headers["Content-Disposition"] = (
            f'attachment; filename="{service.filename()}"'
        )
        response.headers["Cache-Control"] = "no-store"
        return response
