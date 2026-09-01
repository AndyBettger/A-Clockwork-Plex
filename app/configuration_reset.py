from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from flask import Flask, jsonify, request

try:
    from .audio_mixer import MIXER_CHANNELS
    from .configuration_backup import BACKUP_SCHEMA_VERSION, portable_settings
    from .configuration_restore import (
        ConfigurationRestoreExecutor,
        ConfigurationRestorePlanner,
        RestoreConflict,
        RestoreExecutionError,
    )
except ImportError:  # Supports direct execution imports.
    from audio_mixer import MIXER_CHANNELS
    from configuration_backup import BACKUP_SCHEMA_VERSION, portable_settings
    from configuration_restore import (
        ConfigurationRestoreExecutor,
        ConfigurationRestorePlanner,
        RestoreConflict,
        RestoreExecutionError,
    )


CurrentBackupProvider = Callable[[], dict[str, Any]]
DefaultSettingsProvider = Callable[[], dict[str, Any]]
StatusProvider = Callable[[], dict[str, Any]]

MAX_RESET_REQUEST_BYTES = 32_768

PRESERVED_OWNERS = (
    "Weather Underground API key and other managed credentials",
    "Plex/Plexamp login, claim, authentication and browser session state",
    "Plexamp player identity and Headless preferences",
    "Chromium profile and browser cache/session data",
    "DAC, ALSA, mixer topology and installer-owned hardware configuration",
    "Installed runtimes, systemd units and appliance service ownership",
    "Weather/news caches, rainfall history and other runtime data",
)


def _default_eq() -> dict[str, Any]:
    return {
        "enabled": True,
        "bands": {"bass": 0.0, "mid": 0.0, "treble": 0.0},
    }


def _default_mixer() -> dict[str, int]:
    return {
        channel: int(metadata["default_percent"])
        for channel, metadata in MIXER_CHANNELS.items()
    }


class ConfigurationResetPlanner:
    """Build a server-owned defaults target and compare it without mutation.

    The browser never supplies replacement values. The target is generated from
    the running application's own default Settings projection, then narrowed by
    the same portable ownership boundary used by backup/restore. Specialist EQ
    and mixer defaults are included only while those owners are available.
    """

    def __init__(
        self,
        *,
        restore_planner: ConfigurationRestorePlanner,
        current_backup: CurrentBackupProvider,
        default_settings: DefaultSettingsProvider,
        eq_status: StatusProvider,
        mixer_status: StatusProvider,
    ) -> None:
        self._restore_planner = restore_planner
        self._current_backup = current_backup
        self._default_settings = default_settings
        self._eq_status = eq_status
        self._mixer_status = mixer_status

    def build_target(self) -> tuple[dict[str, Any], list[str]]:
        current = self._current_backup()
        defaults = self._default_settings()
        if not isinstance(current, dict) or not isinstance(defaults, dict):
            raise RuntimeError("Reset defaults could not read the current Settings ownership model.")

        warnings: list[str] = []
        audio: dict[str, Any] = {}

        try:
            eq = self._eq_status()
        except Exception:
            eq = {}
        if isinstance(eq, dict) and eq.get("available") is True:
            audio["eq"] = _default_eq()
        else:
            warnings.append("Master EQ is unavailable and will be left unchanged.")

        try:
            mixer = self._mixer_status()
        except Exception:
            mixer = {}
        if (
            isinstance(mixer, dict)
            and mixer.get("available") is True
            and mixer.get("configured") is True
        ):
            audio["mixer"] = _default_mixer()
        else:
            warnings.append("Persistent mixer is unavailable and will be left unchanged.")

        target = {
            "schema_version": BACKUP_SCHEMA_VERSION,
            "source": deepcopy(current.get("source") or {}),
            "a_clockwork_plex": {
                "settings": portable_settings(defaults),
                "audio": audio,
            },
            # Plexamp is deliberately empty here. Home customisation is a
            # separate browser-owned optional target; Headless/auth are preserved.
            "plexamp": {},
        }
        return target, warnings

    def plan(self) -> dict[str, Any]:
        target, owner_warnings = self.build_target()
        restore = self._restore_planner.plan(target)
        changed_paths = list(restore.get("server_changed_paths") or [])
        sections = {
            key: value
            for key, value in (restore.get("sections") or {}).items()
            if str(key).startswith(("settings.", "audio."))
        }
        return {
            "ok": True,
            "schema_version": BACKUP_SCHEMA_VERSION,
            "read_only": True,
            "apply_enabled": False,
            "reset_available": bool(changed_paths),
            "reset_token": str(restore.get("preview_token") or ""),
            "change_count": len(changed_paths),
            "changed_paths": changed_paths,
            "sections": sections,
            "warnings": [*list(restore.get("warnings") or []), *owner_warnings],
            "confirmations_required": list(restore.get("confirmations_required") or []),
            "defaults_source": "config.example.json + production Settings normalisers",
            "preserved": list(PRESERVED_OWNERS),
            "plexamp_home": {
                "included": False,
                "policy": "optional-browser-owner",
            },
        }


class ConfigurationResetExecutor:
    """Apply the freshly rebuilt server-owned defaults target via #90 restore."""

    def __init__(
        self,
        *,
        planner: ConfigurationResetPlanner,
        restore_executor: ConfigurationRestoreExecutor,
    ) -> None:
        self._planner = planner
        self._restore_executor = restore_executor

    def apply(
        self,
        *,
        reset_token: str,
        confirm_reset: bool,
        confirmations: list[str] | None = None,
    ) -> dict[str, Any]:
        if confirm_reset is not True:
            raise RestoreConflict("Explicit reset confirmation is required.")
        target, _warnings = self._planner.build_target()
        restored = self._restore_executor.apply(
            target,
            preview_token=str(reset_token or ""),
            confirm_restore=True,
            confirmations=confirmations or [],
        )
        return {
            "ok": True,
            "reset": True,
            "schema_version": BACKUP_SCHEMA_VERSION,
            "applied_change_count": int(restored.get("applied_change_count") or 0),
            "applied_sections": list(restored.get("applied_sections") or []),
            "credentials_preserved": True,
            "plexamp_auth_preserved": True,
            "plexamp_home_reset": False,
            "message": "A Clockwork Plex settings were reset to application defaults and verified.",
        }


def register_configuration_reset_preview_api(
    app: Flask,
    planner: ConfigurationResetPlanner,
) -> None:
    if "api_configuration_reset_preview" in app.view_functions:
        return

    @app.post("/api/settings/reset/preview")
    def api_configuration_reset_preview():
        try:
            result = planner.plan()
        except RuntimeError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 503
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
        response = jsonify(result)
        response.headers["Cache-Control"] = "no-store"
        return response


def register_configuration_reset_apply_api(
    app: Flask,
    executor: ConfigurationResetExecutor,
) -> None:
    if "api_configuration_reset_apply" in app.view_functions:
        return

    @app.post("/api/settings/reset/apply")
    def api_configuration_reset_apply():
        if request.content_length is not None and request.content_length > MAX_RESET_REQUEST_BYTES:
            return jsonify({"ok": False, "error": "Reset request is too large."}), 413
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "Reset request must be a JSON object."}), 400
        try:
            result = executor.apply(
                reset_token=str(payload.get("reset_token") or ""),
                confirm_reset=payload.get("confirm_reset") is True,
                confirmations=(
                    payload.get("confirmations")
                    if isinstance(payload.get("confirmations"), list)
                    else []
                ),
            )
        except RestoreConflict as exc:
            return jsonify({"ok": False, "error": str(exc), "fresh_preview_required": True}), 409
        except RestoreExecutionError as exc:
            return jsonify(
                {
                    "ok": False,
                    "error": str(exc),
                    "failed_stage": exc.stage,
                    "rolled_back": not exc.rollback_failures,
                    "rollback_failures": exc.rollback_failures,
                    "fresh_preview_required": True,
                }
            ), 500
        except (ValueError, RuntimeError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        response = jsonify(result)
        response.headers["Cache-Control"] = "no-store"
        return response
