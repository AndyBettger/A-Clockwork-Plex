from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

try:
    from .configuration_backup import PLEXAMP_HEADLESS_SPECS
except ImportError:  # Supports direct execution imports from app/runner.py.
    from configuration_backup import PLEXAMP_HEADLESS_SPECS


DEFAULT_HELPER_PATH = "/usr/local/bin/a-clockwork-plex-plexamp-preferences"
MAX_REQUEST_BYTES = 4096
Runner = Callable[..., subprocess.CompletedProcess[str]]


class PlexampPreferenceRestoreError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        rolled_back: bool | None = None,
        rollback_failures: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.rolled_back = rolled_back
        self.rollback_failures = list(rollback_failures or [])


def _validated_preferences(preferences: Any) -> dict[str, bool | int]:
    if not isinstance(preferences, dict) or not preferences:
        raise ValueError("At least one Plexamp Headless preference is required.")
    unknown = sorted(set(preferences) - set(PLEXAMP_HEADLESS_SPECS))
    if unknown:
        raise ValueError(f"Unsupported Plexamp Headless preference: {unknown[0]}")

    result: dict[str, bool | int] = {}
    for key, value in preferences.items():
        expected = PLEXAMP_HEADLESS_SPECS[key]
        if expected == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"Plexamp preference {key} must be boolean.")
            result[key] = value
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"Plexamp preference {key} must be an integer.")
        if not -(2**31) <= value <= 2**31 - 1:
            raise ValueError(f"Plexamp preference {key} is outside the supported integer range.")
        result[key] = value
    return result


class PlexampPreferenceManager:
    """Unprivileged client for the narrow root-owned Plexamp preference helper."""

    def __init__(
        self,
        helper_path: str | Path = DEFAULT_HELPER_PATH,
        *,
        runner: Runner | None = None,
    ) -> None:
        self.helper_path = Path(helper_path)
        self.runner = runner or subprocess.run

    def _base_status(self) -> dict[str, Any]:
        installed = self.helper_path.exists() and os.access(self.helper_path, os.X_OK)
        return {
            "available": False,
            "restore_ready": False,
            "installed": installed,
            "helper_path": str(self.helper_path),
            "installed_version": None,
            "service_active": None,
            "allowlisted_preferences_present": 0,
            "allowlisted_preferences_expected": len(PLEXAMP_HEADLESS_SPECS),
            "error": None if installed else (
                "The managed Plexamp preference helper is not installed. "
                "Run the supported appliance helper installer."
            ),
        }

    def _invoke(
        self,
        action: str,
        *,
        input_text: str | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        if action not in {"status", "apply"}:
            raise ValueError("Unsupported Plexamp preference helper action.")
        if not self.helper_path.exists() or not os.access(self.helper_path, os.X_OK):
            raise PlexampPreferenceRestoreError(self._base_status()["error"])
        command = ["sudo", "-n", str(self.helper_path), action]
        try:
            result = self.runner(
                command,
                check=False,
                capture_output=True,
                text=True,
                input=input_text,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PlexampPreferenceRestoreError(
                f"Could not run the Plexamp preference helper: {exc}"
            ) from exc

        output = (result.stdout or "").strip()
        error = (result.stderr or "").strip()
        try:
            payload = json.loads(output or "{}")
        except json.JSONDecodeError as exc:
            raise PlexampPreferenceRestoreError(
                error or output or "The Plexamp preference helper returned invalid JSON."
            ) from exc
        if not isinstance(payload, dict):
            raise PlexampPreferenceRestoreError(
                "The Plexamp preference helper returned an invalid response."
            )
        if result.returncode or payload.get("ok") is False:
            failures = payload.get("rollback_failures")
            rollback_failures = [str(item) for item in failures] if isinstance(failures, list) else []
            rolled_back = payload.get("rolled_back")
            raise PlexampPreferenceRestoreError(
                str(payload.get("error") or error or "The Plexamp preference helper failed."),
                rolled_back=rolled_back if isinstance(rolled_back, bool) else None,
                rollback_failures=rollback_failures,
            )
        return payload

    def status(self) -> dict[str, Any]:
        status = self._base_status()
        if not status["installed"]:
            return status
        try:
            payload = self._invoke("status", timeout=8)
        except PlexampPreferenceRestoreError as exc:
            status["error"] = str(exc)
            return status
        status.update(payload)
        status["installed"] = True
        status["helper_path"] = str(self.helper_path)
        status["available"] = payload.get("restore_ready") is True
        return status

    def apply(
        self,
        preferences: Any,
        *,
        source_version: str,
    ) -> dict[str, Any]:
        source = str(source_version or "").strip()
        if not source or len(source) > 80:
            raise ValueError("Backup Plexamp version is required for Headless preference restore.")
        checked = _validated_preferences(preferences)
        request = json.dumps(
            {"source_version": source, "preferences": checked},
            sort_keys=True,
            separators=(",", ":"),
        )
        if len(request.encode("utf-8")) > MAX_REQUEST_BYTES:
            raise ValueError("Plexamp preference restore request is too large.")
        payload = self._invoke("apply", input_text=request, timeout=45)
        if payload.get("verified") is not True:
            raise PlexampPreferenceRestoreError(
                "The Plexamp preference helper did not return a verified result."
            )
        return payload
