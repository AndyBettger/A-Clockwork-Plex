from __future__ import annotations

import hashlib
import hmac
import json
import math
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
CommissioningPlanProvider = Callable[[], dict[str, Any]]
CommissioningApply = Callable[..., dict[str, Any]]

MAX_RESET_REQUEST_BYTES = 32_768
MIXER_MIN_DB = -51.0
MIXER_MAX_DB = 0.0

PRESERVED_OWNERS = (
    "Weather Underground API key and other managed credentials",
    "Plex/Plexamp login, claim, authentication and browser session state",
    "Plexamp Headless preferences, account capability and machine/claim identity",
    "Plexamp Home layout (factory-baseline ownership remains a separate browser decision)",
    "Chromium profile and browser cache/session data",
    "Alarm sound master/scheduled safety switches (reset never silently changes the arming state)",
    "DAC, ALSA, mixer topology and installer-owned hardware configuration",
    "Installed runtimes, systemd units and appliance service ownership",
    "Weather/news caches, rainfall history and other runtime data",
)


def _default_eq() -> dict[str, Any]:
    return {"enabled": True, "bands": {"bass": 0.0, "mid": 0.0, "treble": 0.0}}


def _observable_mixer_percent(value: Any) -> int:
    try:
        requested = max(0, min(100, int(value)))
    except (TypeError, ValueError):
        requested = 0
    if requested <= 0:
        return 0
    desired_db = max(MIXER_MIN_DB, min(MIXER_MAX_DB, 20.0 * math.log10(requested / 100.0)))
    raw_percent = round(100.0 * (desired_db - MIXER_MIN_DB) / (MIXER_MAX_DB - MIXER_MIN_DB))
    represented_db = MIXER_MIN_DB + ((MIXER_MAX_DB - MIXER_MIN_DB) * raw_percent / 100.0)
    if represented_db <= MIXER_MIN_DB:
        return 0
    return max(0, min(100, round(100.0 * (10.0 ** (represented_db / 20.0)))))


def _default_mixer() -> dict[str, int]:
    return {
        channel: _observable_mixer_percent(metadata["default_percent"])
        for channel, metadata in MIXER_CHANNELS.items()
    }


def _combined_reset_token(restore_token: str, commissioning_fingerprint: str | None) -> str:
    restore = str(restore_token or "").strip()
    commissioning = str(commissioning_fingerprint or "").strip()
    if not commissioning and len(restore) == 32 and all(
        char in "0123456789abcdef" for char in restore
    ):
        return restore
    encoded = json.dumps(
        {"a_clockwork_plex": restore, "plexamp_commissioning": commissioning},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:32]


def _acp_owner_token(target: dict[str, Any], current: dict[str, Any]) -> str:
    """Fingerprint only ACP-owned state for the browser/server hand-off.

    The portable #90 restore token also fingerprints Plexamp Headless preferences.
    Native Plexamp Reset is allowed to change those preferences before the server
    participant runs, so that broader token must not masquerade as the ACP owner
    token used to decide whether ACP itself changed after Review.
    """

    encoded = json.dumps(
        {
            "target": deepcopy(target.get("a_clockwork_plex") or {}),
            "current": deepcopy(current.get("a_clockwork_plex") or {}),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:32]


class ConfigurationResetPlanner:
    """Build shipped ACP defaults plus the narrow Plexamp commissioning baseline."""

    def __init__(
        self,
        *,
        restore_planner: ConfigurationRestorePlanner,
        current_backup: CurrentBackupProvider,
        default_settings: DefaultSettingsProvider,
        eq_status: StatusProvider,
        mixer_status: StatusProvider,
        plexamp_commissioning_plan: CommissioningPlanProvider | None = None,
    ) -> None:
        self._restore_planner = restore_planner
        self._current_backup = current_backup
        self._default_settings = default_settings
        self._eq_status = eq_status
        self._mixer_status = mixer_status
        self._plexamp_commissioning_plan = plexamp_commissioning_plan

    def current_backup(self) -> dict[str, Any]:
        current = self._current_backup()
        if not isinstance(current, dict):
            raise RuntimeError("Reset defaults could not read the current backup ownership model.")
        return current

    def restore_plan(self, target: dict[str, Any]) -> dict[str, Any]:
        return self._restore_planner.plan(target)

    def build_target(self) -> tuple[dict[str, Any], list[str]]:
        current = self.current_backup()
        defaults = self._default_settings()
        if not isinstance(defaults, dict):
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
        if isinstance(mixer, dict) and mixer.get("available") is True and mixer.get("configured") is True:
            audio["mixer"] = _default_mixer()
        else:
            warnings.append("Persistent mixer is unavailable and will be left unchanged.")
        return {
            "schema_version": BACKUP_SCHEMA_VERSION,
            "source": deepcopy(current.get("source") or {}),
            "a_clockwork_plex": {
                "settings": portable_settings(defaults),
                "audio": audio,
            },
            "plexamp": {},
        }, warnings

    def _commissioning_plan(self) -> tuple[dict[str, Any], list[str]]:
        unavailable = {
            "ready": False,
            "baseline_present": False,
            "change_count": 0,
            "player_name_changed": False,
            "audio_output_changed": False,
            "audio_output_label": "A Clockwork Plex - Plexamp",
            "fingerprint": None,
            "reason": "owner-unavailable",
        }
        if self._plexamp_commissioning_plan is None:
            return unavailable, [
                "Plexamp commissioning owner is unavailable; player name and audio output will be left unchanged."
            ]
        try:
            candidate = self._plexamp_commissioning_plan()
        except Exception:
            return unavailable, [
                "Plexamp commissioning state could not be inspected safely; player name and audio output will be left unchanged."
            ]
        if not isinstance(candidate, dict):
            return unavailable, [
                "Plexamp commissioning owner returned an invalid plan; player name and audio output will be left unchanged."
            ]
        ready = candidate.get("ready") is True
        count = candidate.get("change_count")
        fingerprint = candidate.get("fingerprint")
        if ready:
            if (
                isinstance(count, bool)
                or not isinstance(count, int)
                or not 0 <= count <= 2
                or not isinstance(fingerprint, str)
                or len(fingerprint) != 32
                or any(char not in "0123456789abcdef" for char in fingerprint)
            ):
                return unavailable, [
                    "Plexamp commissioning owner returned an invalid safety fingerprint; player name and audio output will be left unchanged."
                ]
            player_changed = candidate.get("player_name_changed") is True
            audio_changed = candidate.get("audio_output_changed") is True
            if count != int(player_changed) + int(audio_changed):
                return unavailable, [
                    "Plexamp commissioning owner returned an inconsistent change count; player name and audio output will be left unchanged."
                ]
            return {
                "ready": True,
                "baseline_present": candidate.get("baseline_present") is True,
                "change_count": count,
                "player_name_changed": player_changed,
                "audio_output_changed": audio_changed,
                "audio_output_label": str(candidate.get("audio_output_label") or "A Clockwork Plex - Plexamp")[:120],
                "fingerprint": fingerprint,
                "reason": None,
            }, []
        reason = str(candidate.get("reason") or "not-ready")[:80]
        warning = (
            "Plexamp commissioning baseline has not been captured yet; player name and managed audio output will be left unchanged until setup is run once."
            if reason == "baseline-missing"
            else "Plexamp commissioning owner is not ready; player name and managed audio output will be left unchanged."
        )
        return {**unavailable, "baseline_present": candidate.get("baseline_present") is True, "reason": reason}, [warning]

    def plan(self) -> dict[str, Any]:
        target, owner_warnings = self.build_target()
        restore = self.restore_plan(target)
        current = self.current_backup()
        acp_changed_paths = list(restore.get("server_changed_paths") or [])
        sections = {
            key: value
            for key, value in (restore.get("sections") or {}).items()
            if str(key).startswith(("settings.", "audio."))
        }
        commissioning, commissioning_warnings = self._commissioning_plan()
        commissioning_paths: list[str] = []
        if commissioning.get("ready") is True:
            if commissioning.get("player_name_changed") is True:
                commissioning_paths.append("plexamp.commissioning.player_name")
            if commissioning.get("audio_output_changed") is True:
                commissioning_paths.append("plexamp.commissioning.audio_output")
        if commissioning_paths:
            sections["plexamp.commissioning"] = len(commissioning_paths)
        changed_paths = [*acp_changed_paths, *commissioning_paths]
        restore_token = str(restore.get("preview_token") or "")
        acp_owner_token = _acp_owner_token(target, current)
        commissioning_fingerprint = (
            str(commissioning.get("fingerprint")) if commissioning.get("ready") is True else None
        )
        return {
            "ok": True,
            "schema_version": BACKUP_SCHEMA_VERSION,
            "read_only": True,
            "apply_enabled": False,
            "reset_available": bool(changed_paths),
            "reset_token": _combined_reset_token(restore_token, commissioning_fingerprint),
            "restore_preview_token": restore_token,
            "owner_tokens": {
                "a_clockwork_plex": acp_owner_token,
                "plexamp_commissioning": commissioning_fingerprint,
            },
            "change_count": len(changed_paths),
            "acp_change_count": len(acp_changed_paths),
            "plexamp_commissioning_change_count": len(commissioning_paths),
            "changed_paths": changed_paths,
            "sections": dict(sorted(sections.items())),
            "warnings": [*list(restore.get("warnings") or []), *owner_warnings, *commissioning_warnings],
            "confirmations_required": list(restore.get("confirmations_required") or []),
            "defaults_source": (
                "config.example.json + production Settings normalisers + "
                "commissioned Plexamp player baseline/live managed audio-device resolution"
            ),
            "preserved": list(PRESERVED_OWNERS),
            "plexamp_commissioning": commissioning,
            "plexamp_home": {"included": False, "policy": "optional-browser-owner"},
        }


class ConfigurationResetExecutor:
    """Apply ACP defaults then Plexamp commissioning, rolling ACP back on late failure."""

    def __init__(
        self,
        *,
        planner: ConfigurationResetPlanner,
        restore_executor: ConfigurationRestoreExecutor,
        restore_planner: ConfigurationRestorePlanner | None = None,
        plexamp_commissioning_apply: CommissioningApply | None = None,
    ) -> None:
        self._planner = planner
        self._restore_planner = restore_planner or planner._restore_planner
        self._restore_executor = restore_executor
        self._plexamp_commissioning_apply = plexamp_commissioning_apply

    def _rollback_acp(self, before_backup: dict[str, Any]) -> None:
        rollback = self._restore_planner.plan(before_backup)
        if not rollback.get("restore_available"):
            return
        self._restore_executor.apply(
            before_backup,
            preview_token=str(rollback.get("preview_token") or ""),
            confirm_restore=True,
            confirmations=list(rollback.get("confirmations_required") or []),
        )

    def apply(
        self,
        *,
        reset_token: str,
        confirm_reset: bool,
        confirmations: list[str] | None = None,
    ) -> dict[str, Any]:
        if confirm_reset is not True:
            raise RestoreConflict("Explicit reset confirmation is required.")
        current_plan = self._planner.plan()
        supplied_token = str(reset_token or "").strip()
        if not supplied_token or not hmac.compare_digest(
            supplied_token, str(current_plan.get("reset_token") or "")
        ):
            raise RestoreConflict("The appliance changed after Preview. Run Preview reset again.")
        if current_plan.get("reset_available") is not True:
            raise RestoreConflict("No currently supported changes need resetting.")
        accepted_confirmations = {
            str(item) for item in (confirmations or []) if isinstance(item, str)
        }
        missing = [
            item
            for item in (current_plan.get("confirmations_required") or [])
            if item not in accepted_confirmations
        ]
        if missing:
            raise RestoreConflict(f"Reset confirmation is required for: {missing[0]}")
        acp_count = int(current_plan.get("acp_change_count") or 0)
        commissioning_count = int(current_plan.get("plexamp_commissioning_change_count") or 0)
        restore_token = str(current_plan.get("restore_preview_token") or "")
        owner_tokens = current_plan.get("owner_tokens") or {}
        commissioning_fingerprint = str(owner_tokens.get("plexamp_commissioning") or "")
        if commissioning_count and (
            self._plexamp_commissioning_apply is None or not commissioning_fingerprint
        ):
            raise RestoreConflict(
                "Plexamp commissioning owner is unavailable; no reset changes were applied."
            )
        target, _warnings = self._planner.build_target()
        before_backup = deepcopy(self._planner.current_backup()) if acp_count else {}
        restored: dict[str, Any] = {"applied_change_count": 0, "applied_sections": []}
        acp_applied = False
        if acp_count:
            restored = self._restore_executor.apply(
                target,
                preview_token=restore_token,
                confirm_restore=True,
                confirmations=list(accepted_confirmations),
            )
            acp_applied = True
        commissioning_result: dict[str, Any] = {"changed_count": 0, "verified": True}
        if commissioning_count:
            try:
                commissioning_result = self._plexamp_commissioning_apply(
                    fingerprint=commissioning_fingerprint
                )
                if (
                    not isinstance(commissioning_result, dict)
                    or commissioning_result.get("verified") is not True
                    or int(commissioning_result.get("changed_count") or 0) != commissioning_count
                ):
                    raise RuntimeError(
                        "Plexamp commissioning owner did not return the reviewed verified result."
                    )
            except Exception as exc:
                rollback_failures: list[str] = []
                helper_failures = getattr(exc, "rollback_failures", None)
                helper_rolled_back = getattr(exc, "rolled_back", None)
                if helper_rolled_back is False or (
                    isinstance(helper_failures, list) and helper_failures
                ):
                    rollback_failures.extend(
                        f"Plexamp commissioning:{item}"
                        for item in (helper_failures or ["helper rollback"])
                    )
                if acp_applied:
                    try:
                        self._rollback_acp(before_backup)
                    except Exception:
                        rollback_failures.append("A Clockwork Plex")
                raise RestoreExecutionError(
                    "Plexamp commissioning", rollback_failures=rollback_failures
                ) from exc
        applied_sections = set(restored.get("applied_sections") or [])
        if commissioning_count:
            applied_sections.add("plexamp.commissioning")
        applied_count = int(restored.get("applied_change_count") or 0) + int(
            commissioning_result.get("changed_count") or 0
        )
        return {
            "ok": True,
            "reset": True,
            "schema_version": BACKUP_SCHEMA_VERSION,
            "applied_change_count": applied_count,
            "applied_sections": sorted(applied_sections),
            "acp_applied_change_count": int(restored.get("applied_change_count") or 0),
            "plexamp_commissioning_applied_change_count": int(
                commissioning_result.get("changed_count") or 0
            ),
            "credentials_preserved": True,
            "plexamp_auth_preserved": True,
            "plexamp_headless_preferences_preserved": True,
            "plexamp_home_reset": False,
            "message": (
                "A Clockwork Plex defaults and supported Plexamp commissioning baselines were reset and verified."
            ),
        }


def register_configuration_reset_preview_api(app: Flask, planner: ConfigurationResetPlanner) -> None:
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


def register_configuration_reset_apply_api(app: Flask, executor: ConfigurationResetExecutor) -> None:
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
