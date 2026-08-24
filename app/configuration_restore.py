from __future__ import annotations

import hashlib
import hmac
import json
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
SettingsSnapshot = Callable[[], dict[str, Any]]
SettingsApply = Callable[[dict[str, Any]], dict[str, Any]]
EqStatus = Callable[[], dict[str, Any]]
EqSetBypass = Callable[[bool], dict[str, Any]]
MixerStatus = Callable[[], dict[str, Any]]
MixerSetVolumes = Callable[[dict[str, int]], dict[str, Any]]

MAX_BACKUP_BYTES = 1_000_000
MAX_APPLY_REQUEST_BYTES = 1_100_000
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
    "audiodeviceuuid",
    "playername",
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
EQ_KEYS = {"enabled", "bands"}
EQ_BANDS = {"bass", "mid", "treble"}
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
            if name.casefold() in FORBIDDEN_KEYS:
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


def _validate_eq(value: Any) -> dict[str, Any]:
    eq = _object(value, "a_clockwork_plex.audio.eq")
    _reject_unknown(eq, EQ_KEYS, "a_clockwork_plex.audio.eq")
    result: dict[str, Any] = {}
    if "enabled" in eq:
        if not isinstance(eq["enabled"], bool):
            raise ValueError("EQ enabled state must be a boolean.")
        result["enabled"] = eq["enabled"]
    if "bands" in eq:
        bands = _object(eq["bands"], "a_clockwork_plex.audio.eq.bands")
        _reject_unknown(bands, EQ_BANDS, "a_clockwork_plex.audio.eq.bands")
        result_bands: dict[str, float] = {}
        for band, raw in bands.items():
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise ValueError(f"{band.title()} EQ gain must be a number.")
            gain = float(raw)
            if not -6.0 <= gain <= 6.0:
                raise ValueError(f"{band.title()} EQ gain must be from -6 dB to +6 dB.")
            quantised = round(gain * 2) / 2
            if abs(quantised - gain) > 1e-9:
                raise ValueError(f"{band.title()} EQ gain must use 0.5 dB steps.")
            result_bands[band] = quantised
        result["bands"] = result_bands
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

    audio = _object(acp.get("audio", {}), "a_clockwork_plex.audio")
    _reject_unknown(audio, AUDIO_DOMAINS, "a_clockwork_plex.audio")
    normalised_audio: dict[str, Any] = {}
    if "eq" in audio:
        normalised_audio["eq"] = _validate_eq(audio["eq"])
    if "mixer" in audio:
        normalised_audio["mixer"] = _validate_mixer(audio["mixer"])

    plexamp = _object(backup.get("plexamp", {}), "plexamp")
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


def _preview_token(candidate: dict[str, Any], current: dict[str, Any]) -> str:
    encoded = json.dumps(
        {
            "candidate": candidate,
            "current": _comparison_domains(current),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:32]


def _deep_merge(base: Any, overlay: Any) -> Any:
    if not isinstance(base, dict) or not isinstance(overlay, dict):
        return deepcopy(overlay)
    result = deepcopy(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


class RestoreConflict(RuntimeError):
    pass


class RestoreExecutionError(RuntimeError):
    def __init__(self, stage: str, *, rollback_failures: list[str] | None = None) -> None:
        self.stage = stage
        self.rollback_failures = list(rollback_failures or [])
        super().__init__(f"Restore failed during {stage}.")


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
        apply_paths = [
            path for path in changed_paths if path.startswith("a_clockwork_plex.")
        ]
        deferred_paths = [
            path for path in changed_paths if path.startswith("plexamp.")
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

        if deferred_paths:
            warnings.append(
                "Plexamp Headless preferences differ but remain deferred until the version-aware Plexamp restore stage."
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
            "apply_enabled": bool(apply_paths),
            "preview_token": _preview_token(candidate, current),
            "change_count": len(changed_paths),
            "changed_paths": changed_paths[:MAX_PREVIEW_PATHS],
            "changed_paths_truncated": len(changed_paths) > MAX_PREVIEW_PATHS,
            "apply_change_count": len(apply_paths),
            "apply_changed_paths": apply_paths[:MAX_PREVIEW_PATHS],
            "deferred_change_count": len(deferred_paths),
            "deferred_changed_paths": deferred_paths[:MAX_PREVIEW_PATHS],
            "sections": dict(sorted(sections.items())),
            "plexamp_browser": browser_summary,
            "warnings": warnings,
            "confirmations_required": confirmations,
            "credentials": {
                "included": False,
                "restore_policy": "recommission-separately",
            },
        }


class ConfigurationRestoreExecutor:
    """Apply only ACP Settings/EQ/mixer owners with rollback and verification."""

    def __init__(
        self,
        *,
        planner: ConfigurationRestorePlanner,
        current_backup: CurrentBackupProvider,
        settings_snapshot: SettingsSnapshot,
        settings_apply: SettingsApply,
        eq_status: EqStatus,
        eq_set_band: Callable[[str, float], dict[str, Any]],
        eq_set_bypass: EqSetBypass,
        mixer_status: MixerStatus,
        mixer_set_volumes: MixerSetVolumes,
    ) -> None:
        self._planner = planner
        self._current_backup = current_backup
        self._settings_snapshot = settings_snapshot
        self._settings_apply = settings_apply
        self._eq_status = eq_status
        self._eq_set_band = eq_set_band
        self._eq_set_bypass = eq_set_bypass
        self._mixer_status = mixer_status
        self._mixer_set_volumes = mixer_set_volumes

    @staticmethod
    def _logical_eq(model: dict[str, Any]) -> dict[str, Any]:
        return _validate_eq(
            model.get("a_clockwork_plex", {}).get("audio", {}).get("eq", {})
        )

    @staticmethod
    def _logical_mixer(model: dict[str, Any]) -> dict[str, int]:
        raw = model.get("a_clockwork_plex", {}).get("audio", {}).get("mixer", {})
        return _validate_mixer(raw) if isinstance(raw, dict) else {}

    def _rollback_settings(self, before_snapshot: dict[str, Any]) -> None:
        current = self._settings_snapshot()
        revision = str(current.get("revision") or "")
        settings = deepcopy(before_snapshot.get("settings"))
        if not revision or not isinstance(settings, dict):
            raise RuntimeError("Settings rollback snapshot is unavailable.")
        self._settings_apply(
            {
                "revision": revision,
                "settings": settings,
                "confirm_airplay_restart": True,
            }
        )

    def _rollback_eq(self, before_eq: dict[str, Any]) -> None:
        for band, value in before_eq.get("bands", {}).items():
            self._eq_set_band(str(band), float(value))
        if "enabled" in before_eq:
            self._eq_set_bypass(not bool(before_eq["enabled"]))

    def apply(
        self,
        backup: Any,
        *,
        preview_token: str,
        confirm_restore: bool,
        confirmations: list[str] | None = None,
    ) -> dict[str, Any]:
        if confirm_restore is not True:
            raise RestoreConflict("Explicit restore confirmation is required.")

        plan = self._planner.plan(backup)
        supplied_token = str(preview_token or "").strip()
        if not supplied_token or not hmac.compare_digest(supplied_token, plan["preview_token"]):
            raise RestoreConflict(
                "The appliance or backup changed after preview. Run Preview restore again."
            )

        accepted_confirmations = {
            str(item) for item in (confirmations or []) if isinstance(item, str)
        }
        missing = [
            item for item in plan["confirmations_required"] if item not in accepted_confirmations
        ]
        if missing:
            raise RestoreConflict(f"Restore confirmation is required for: {missing[0]}")

        apply_paths = list(plan.get("apply_changed_paths") or [])
        if not apply_paths:
            raise RestoreConflict("No currently supported server-owned changes need restoring.")

        before_backup = _normalise_restore_model(self._current_backup())
        candidate = _normalise_restore_model(backup)
        before_settings = self._settings_snapshot()
        if not isinstance(before_settings.get("settings"), dict) or not before_settings.get("revision"):
            raise RestoreConflict("Unified Settings snapshot is unavailable.")

        settings_changed = any(
            path.startswith("a_clockwork_plex.settings.") for path in apply_paths
        )
        eq_changed = any(path.startswith("a_clockwork_plex.audio.eq") for path in apply_paths)
        mixer_changed = any(
            path.startswith("a_clockwork_plex.audio.mixer") for path in apply_paths
        )

        before_eq = self._logical_eq(before_backup)
        before_mixer = self._logical_mixer(before_backup)

        if eq_changed and self._eq_status().get("available") is not True:
            raise RestoreConflict("Master EQ is unavailable; no restore changes were applied.")
        if mixer_changed:
            mixer = self._mixer_status()
            if mixer.get("available") is not True or mixer.get("configured") is not True:
                raise RestoreConflict("Persistent audio mixer is unavailable; no restore changes were applied.")
            if not before_mixer:
                raise RestoreConflict("Persistent mixer rollback state is unavailable.")

        settings_applied = False
        eq_touched = False
        mixer_touched = False
        stage = "preparation"

        try:
            if settings_changed:
                stage = "Settings"
                target_settings = deepcopy(before_settings["settings"])
                for domain, values in candidate["a_clockwork_plex"]["settings"].items():
                    target_settings[domain] = _deep_merge(target_settings.get(domain, {}), values)
                self._settings_apply(
                    {
                        "revision": before_settings["revision"],
                        "settings": target_settings,
                        "confirm_airplay_restart": "airplay_restart" in accepted_confirmations,
                    }
                )
                settings_applied = True

            if eq_changed:
                stage = "Master EQ"
                target_eq = _deep_merge(before_eq, candidate["a_clockwork_plex"]["audio"].get("eq", {}))
                for band, value in target_eq.get("bands", {}).items():
                    if before_eq.get("bands", {}).get(band) != value:
                        eq_touched = True
                        self._eq_set_band(str(band), float(value))
                if before_eq.get("enabled") != target_eq.get("enabled"):
                    eq_touched = True
                    self._eq_set_bypass(not bool(target_eq.get("enabled")))

            if mixer_changed:
                stage = "persistent mixer"
                target_mixer = _deep_merge(
                    before_mixer,
                    candidate["a_clockwork_plex"]["audio"].get("mixer", {}),
                )
                mixer_touched = True
                self._mixer_set_volumes(target_mixer)

            stage = "verification"
            after_plan = self._planner.plan(backup)
            remaining_apply_paths = list(after_plan.get("apply_changed_paths") or [])
            if remaining_apply_paths:
                raise RuntimeError("Restored owners did not verify against the requested backup.")
        except Exception as exc:
            rollback_failures: list[str] = []
            if mixer_touched:
                try:
                    self._mixer_set_volumes(before_mixer)
                except Exception:
                    rollback_failures.append("persistent mixer")
            if eq_touched:
                try:
                    self._rollback_eq(before_eq)
                except Exception:
                    rollback_failures.append("Master EQ")
            if settings_applied:
                try:
                    self._rollback_settings(before_settings)
                except Exception:
                    rollback_failures.append("Settings")

            if not rollback_failures:
                try:
                    restored = _normalise_restore_model(self._current_backup())
                    before_flat = _flatten(_comparison_domains(before_backup), "")
                    restored_flat = _flatten(_comparison_domains(restored), "")
                    if any(
                        restored_flat.get(path) != before_flat.get(path)
                        for path in apply_paths
                    ):
                        rollback_failures.append("verification")
                except Exception:
                    rollback_failures.append("verification")

            raise RestoreExecutionError(
                stage,
                rollback_failures=rollback_failures,
            ) from exc

        return {
            "ok": True,
            "restored": True,
            "schema_version": BACKUP_SCHEMA_VERSION,
            "applied_change_count": len(apply_paths),
            "applied_sections": sorted({_section_for_path(path) for path in apply_paths}),
            "deferred_change_count": int(plan.get("deferred_change_count") or 0),
            "deferred_changed_paths": list(plan.get("deferred_changed_paths") or []),
            "plexamp_browser": deepcopy(plan.get("plexamp_browser") or {}),
            "credentials": {
                "included": False,
                "restore_policy": "recommission-separately",
            },
            "message": "Supported server-owned settings were restored and verified.",
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


def register_configuration_restore_apply_api(
    app: Flask,
    executor: ConfigurationRestoreExecutor,
) -> None:
    if "api_configuration_restore_apply" in app.view_functions:
        return

    @app.post("/api/settings/restore/apply")
    def api_configuration_restore_apply():
        if request.content_length is not None and request.content_length > MAX_APPLY_REQUEST_BYTES:
            return jsonify({"ok": False, "error": "Restore request is too large."}), 413
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "Restore request must be a JSON object."}), 400
        try:
            result = executor.apply(
                payload.get("backup"),
                preview_token=str(payload.get("preview_token") or ""),
                confirm_restore=payload.get("confirm_restore") is True,
                confirmations=payload.get("confirmations") if isinstance(payload.get("confirmations"), list) else [],
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except RestoreConflict as exc:
            return jsonify({"ok": False, "error": str(exc), "fresh_preview_required": True}), 409
        except RestoreExecutionError as exc:
            response = {
                "ok": False,
                "error": str(exc),
                "failed_stage": exc.stage,
                "rolled_back": not exc.rollback_failures,
                "rollback_failures": exc.rollback_failures,
                "fresh_preview_required": True,
            }
            return jsonify(response), 500
        response = jsonify(result)
        response.headers["Cache-Control"] = "no-store"
        return response
