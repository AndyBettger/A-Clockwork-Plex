from __future__ import annotations

import re
from collections import Counter
from copy import deepcopy
from typing import Any, Callable

from flask import Flask, jsonify, request

try:
    from .configuration_backup import (
        BACKUP_SCHEMA_VERSION,
        MIXER_CHANNELS,
        PLEXAMP_HEADLESS_SPECS,
    )
except ImportError:  # Supports direct execution imports.
    from configuration_backup import (
        BACKUP_SCHEMA_VERSION,
        MIXER_CHANNELS,
        PLEXAMP_HEADLESS_SPECS,
    )


CurrentBackupProvider = Callable[[], dict[str, Any]]

MAX_BACKUP_BYTES = 1_000_000
MAX_PREVIEW_PATHS = 200
MAX_BROWSER_ITEMS = 128
SAFE_HUB_ID_RE = re.compile(r"^[A-Za-z0-9_./-]{1,220}$")

FORBIDDEN_KEYS = {
    "api_key",
    "api_key_env",
    "auth_token",
    "claim_token",
    "access_token",
    "password",
    "cookie",
    "cookies",
    "hardware_device",
    "alsa_device",
    "pause_url",
    "service_name",
    "audioDeviceUuid",
    "playerName",
    "premium",
}

TOP_LEVEL_KEYS = {
    "schema_version",
    "created_at",
    "source",
    "a_clockwork_plex",
    "plexamp",
    "export_report",
}
ACP_KEYS = {"settings", "audio"}
SETTINGS_DOMAINS = {"dashboard", "display", "weather", "alarms", "airplay"}
AUDIO_DOMAINS = {"eq", "mixer"}
PLEXAMP_KEYS = {"source_version", "headless_preferences", "browser_preferences"}
BROWSER_KEYS = {"schema_version", "home"}
BROWSER_HOME_KEYS = {"order", "hidden"}


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object.")
    return value


def _reject_unknown(mapping: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise ValueError(f"{label} contains unsupported field: {unknown[0]}")


def _reject_forbidden(value: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            name = str(key)
            if name in FORBIDDEN_KEYS:
                location = ".".join((*path, name))
                raise ValueError(
                    f"Backup contains non-portable or credential-owned field: {location}"
                )
            _reject_forbidden(child, (*path, name))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_forbidden(child, (*path, str(index)))


def _validate_json_bounds(value: Any, path: str = "backup", depth: int = 0) -> None:
    if depth > 12:
        raise ValueError(f"{path} exceeds the supported nesting depth.")
    if isinstance(value, dict):
        if len(value) > 256:
            raise ValueError(f"{path} contains too many fields.")
        for key, child in value.items():
            if not isinstance(key, str) or len(key) > 240:
                raise ValueError(f"{path} contains an invalid field name.")
            _validate_json_bounds(child, f"{path}.{key}", depth + 1)
        return
    if isinstance(value, list):
        if len(value) > 512:
            raise ValueError(f"{path} contains too many list items.")
        for index, child in enumerate(value):
            _validate_json_bounds(child, f"{path}[{index}]", depth + 1)
        return
    if isinstance(value, str) and len(value) > 16_384:
        raise ValueError(f"{path} contains an oversized string.")
    if value is not None and not isinstance(value, (str, int, float, bool)):
        raise ValueError(f"{path} contains an unsupported JSON value.")


def _validate_mixer(value: Any) -> dict[str, int]:
    mixer = _object(value, "a_clockwork_plex.audio.mixer")
    _reject_unknown(mixer, set(MIXER_CHANNELS), "a_clockwork_plex.audio.mixer")
    result: dict[str, int] = {}
    for channel, raw in mixer.items():
        if isinstance(raw, bool) or not isinstance(raw, int) or not 0 <= raw <= 100:
            raise ValueError(f"Mixer value {channel} must be an integer from 0 to 100.")
        result[channel] = raw
    return result


def _validate_headless(value: Any) -> dict[str, bool | int]:
    preferences = _object(value, "plexamp.headless_preferences")
    _reject_unknown(
        preferences,
        set(PLEXAMP_HEADLESS_SPECS),
        "plexamp.headless_preferences",
    )
    result: dict[str, bool | int] = {}
    for key, raw in preferences.items():
        expected = PLEXAMP_HEADLESS_SPECS[key]
        if expected == "boolean":
            if not isinstance(raw, bool):
                raise ValueError(f"Plexamp preference {key} must be a boolean.")
            result[key] = raw
            continue
        if expected == "integer":
            if isinstance(raw, bool) or not isinstance(raw, int):
                raise ValueError(f"Plexamp preference {key} must be an integer.")
            if not -(2**31) <= raw <= 2**31 - 1:
                raise ValueError(f"Plexamp preference {key} is outside the supported range.")
            result[key] = raw
            continue
        raise ValueError(f"Plexamp preference {key} has an unsupported type contract.")
    return result


def _validate_browser_list(value: Any, label: str, *, nullable: bool = False) -> list[str] | None:
    if value is None and nullable:
        return None
    if not isinstance(value, list) or len(value) > MAX_BROWSER_ITEMS:
        raise ValueError(f"{label} must be a list of at most {MAX_BROWSER_ITEMS} items.")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not SAFE_HUB_ID_RE.fullmatch(item):
            raise ValueError(f"{label} contains an unsupported Plexamp Home identifier.")
        result.append(item)
    return result


def _validate_browser(value: Any) -> dict[str, Any]:
    browser = _object(value, "plexamp.browser_preferences")
    _reject_unknown(browser, BROWSER_KEYS, "plexamp.browser_preferences")
    if browser.get("schema_version") != 1:
        raise ValueError("Plexamp browser preference schema must be version 1.")
    home = _object(browser.get("home"), "plexamp.browser_preferences.home")
    _reject_unknown(home, BROWSER_HOME_KEYS, "plexamp.browser_preferences.home")
    return {
        "schema_version": 1,
        "home": {
            "order": _validate_browser_list(
                home.get("order"),
                "Plexamp Home order",
                nullable=True,
            ),
            "hidden": _validate_browser_list(
                home.get("hidden", []),
                "Plexamp hidden items",
            ),
        },
    }


def _normalise_restore_model(payload: Any) -> dict[str, Any]:
    backup = _object(payload, "Backup")
    _validate_json_bounds(backup)
    _reject_unknown(backup, TOP_LEVEL_KEYS, "Backup")
    _reject_forbidden(backup)
    if backup.get("schema_version") != BACKUP_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported backup schema version; expected {BACKUP_SCHEMA_VERSION}."
        )

    acp = _object(backup.get("a_clockwork_plex"), "a_clockwork_plex")
    _reject_unknown(acp, ACP_KEYS, "a_clockwork_plex")
    settings = _object(acp.get("settings"), "a_clockwork_plex.settings")
    _reject_unknown(settings, SETTINGS_DOMAINS, "a_clockwork_plex.settings")

    audio_source = acp.get("audio", {})
    audio = _object(audio_source, "a_clockwork_plex.audio")
    _reject_unknown(audio, AUDIO_DOMAINS, "a_clockwork_plex.audio")
    normalised_audio: dict[str, Any] = {}
    if "eq" in audio:
        normalised_audio["eq"] = deepcopy(_object(audio["eq"], "a_clockwork_plex.audio.eq"))
    if "mixer" in audio:
        normalised_audio["mixer"] = _validate_mixer(audio["mixer"])

    plexamp_source = backup.get("plexamp", {})
    plexamp = _object(plexamp_source, "plexamp")
    _reject_unknown(plexamp, PLEXAMP_KEYS, "plexamp")
    normalised_plexamp: dict[str, Any] = {}
    if "source_version" in plexamp:
        version = plexamp["source_version"]
        if not isinstance(version, str) or len(version) > 80:
            raise ValueError("plexamp.source_version must be a short string.")
        normalised_plexamp["source_version"] = version
    if "headless_preferences" in plexamp:
        normalised_plexamp["headless_preferences"] = _validate_headless(
            plexamp["headless_preferences"]
        )
    if "browser_preferences" in plexamp:
        normalised_plexamp["browser_preferences"] = _validate_browser(
            plexamp["browser_preferences"]
        )

    source = backup.get("source", {})
    if source is not None and not isinstance(source, dict):
        raise ValueError("source must be a JSON object when present.")

    return {
        "schema_version": BACKUP_SCHEMA_VERSION,
        "source": deepcopy(source) if isinstance(source, dict) else {},
        "a_clockwork_plex": {
            "settings": deepcopy(settings),
            "audio": normalised_audio,
        },
        "plexamp": normalised_plexamp,
    }


def _flatten(value: Any, prefix: str) -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key in sorted(value):
            result.update(_flatten(value[key], f"{prefix}.{key}" if prefix else key))
        return result
    if isinstance(value, list):
        return {prefix: deepcopy(value)}
    return {prefix: value}


def _comparison_domains(model: dict[str, Any]) -> dict[str, Any]:
    acp = model.get("a_clockwork_plex", {})
    plexamp = model.get("plexamp", {})
    return {
        "a_clockwork_plex": {
            "settings": deepcopy(acp.get("settings", {})),
            "audio": deepcopy(acp.get("audio", {})),
        },
        "plexamp": {
            "headless_preferences": deepcopy(plexamp.get("headless_preferences", {})),
        },
    }


def _section_for_path(path: str) -> str:
    parts = path.split(".")
    if len(parts) >= 3 and parts[:2] == ["a_clockwork_plex", "settings"]:
        return f"settings.{parts[2]}"
    if len(parts) >= 3 and parts[:2] == ["a_clockwork_plex", "audio"]:
        return f"audio.{parts[2]}"
    if len(parts) >= 2 and parts[0] == "plexamp":
        return f"plexamp.{parts[1]}"
    return parts[0] if parts else "unknown"


class ConfigurationRestorePlanner:
    """Validate and compare portable backups without applying any change."""

    def __init__(self, *, current_backup: CurrentBackupProvider) -> None:
        self._current_backup = current_backup

    def plan(self, payload: Any) -> dict[str, Any]:
        candidate = _normalise_restore_model(payload)
        current = _normalise_restore_model(self._current_backup())

        candidate_flat = _flatten(_comparison_domains(candidate), "")
        current_flat = _flatten(_comparison_domains(current), "")
        changed_paths = [
            path
            for path in sorted(candidate_flat)
            if candidate_flat[path] != current_flat.get(path)
        ]

        sections = Counter(_section_for_path(path) for path in changed_paths)
        warnings: list[str] = []
        confirmations: list[str] = []

        source_version = str(candidate.get("source", {}).get("app_version") or "").strip()
        current_version = str(current.get("source", {}).get("app_version") or "").strip()
        if source_version and current_version and source_version != current_version:
            warnings.append(
                f"Backup application version {source_version} differs from this appliance version {current_version}."
            )

        candidate_plexamp = candidate.get("plexamp", {})
        current_plexamp = current.get("plexamp", {})
        source_plexamp = str(candidate_plexamp.get("source_version") or "").strip()
        current_plexamp_version = str(current_plexamp.get("source_version") or "").strip()
        if (
            source_plexamp
            and current_plexamp_version
            and source_plexamp != current_plexamp_version
        ):
            warnings.append(
                "Backup Plexamp version differs from the installed Plexamp version; preference restore must remain version-aware."
            )

        browser = candidate_plexamp.get("browser_preferences")
        browser_summary = {
            "present": isinstance(browser, dict),
            "order_items": 0,
            "hidden_items": 0,
            "comparison": "not-present",
        }
        if isinstance(browser, dict):
            home = browser["home"]
            order = home.get("order")
            hidden = home.get("hidden", [])
            browser_summary.update(
                {
                    "order_items": len(order) if isinstance(order, list) else 0,
                    "hidden_items": len(hidden),
                    "comparison": "deferred-to-live-browser",
                }
            )
            warnings.append(
                "Plexamp Home layout is valid and portable, but comparison/application belongs to the live browser restore stage after Plexamp is commissioned."
            )

        if "a_clockwork_plex.settings.airplay.receiver_name" in changed_paths:
            confirmations.append("airplay_restart")

        return {
            "ok": True,
            "schema_version": BACKUP_SCHEMA_VERSION,
            "read_only": True,
            "apply_enabled": False,
            "change_count": len(changed_paths),
            "changed_paths": changed_paths[:MAX_PREVIEW_PATHS],
            "changed_paths_truncated": len(changed_paths) > MAX_PREVIEW_PATHS,
            "sections": dict(sorted(sections.items())),
            "plexamp_browser": browser_summary,
            "warnings": warnings,
            "confirmations_required": confirmations,
            "credentials": {
                "included": False,
                "restore_policy": "recommission-separately",
            },
        }


def register_configuration_restore_preview_api(
    app: Flask,
    planner: ConfigurationRestorePlanner,
) -> None:
    if "api_configuration_restore_preview" in app.view_functions:
        return

    @app.post("/api/settings/restore/preview")
    def api_configuration_restore_preview():
        if request.content_length is not None and request.content_length > MAX_BACKUP_BYTES:
            return jsonify({"ok": False, "error": "Backup file is too large."}), 413
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({"ok": False, "error": "Select a valid JSON backup file."}), 400
        try:
            result = planner.plan(payload)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 503
        response = jsonify(result)
        response.headers["Cache-Control"] = "no-store"
        return response
