from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable


DEFAULT_HELPER_PATH = "/usr/local/bin/a-clockwork-plex-shairport-name"
MAX_RECEIVER_NAME_LENGTH = 50
Runner = Callable[..., subprocess.CompletedProcess[str]]


def validate_receiver_name(value: Any) -> str:
    name = str(value or "").strip()
    if not name:
        raise ValueError("AirPlay receiver name cannot be blank.")
    if len(name) > MAX_RECEIVER_NAME_LENGTH:
        raise ValueError(
            f"AirPlay receiver name must be {MAX_RECEIVER_NAME_LENGTH} characters or fewer."
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise ValueError("AirPlay receiver name cannot contain control characters.")
    if "\n" in name or "\r" in name:
        raise ValueError("AirPlay receiver name must fit on one line.")
    return name


class ShairportNameManager:
    """Restricted client for the root-owned Shairport receiver-name helper."""

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
            "available": installed,
            "installed": installed,
            "helper_path": str(self.helper_path),
            "receiver_name": None,
            "service_active": None,
            "config_path": "/etc/shairport-sync.conf",
            "error": None if installed else (
                "The managed Shairport receiver-name helper is not installed. "
                "Run scripts/install-shairport-name-helper.sh on the Pi."
            ),
        }

    def _invoke(self, *arguments: str, timeout: int = 20) -> dict[str, Any]:
        if not self.helper_path.exists() or not os.access(self.helper_path, os.X_OK):
            raise RuntimeError(self._base_status()["error"])
        command = ["sudo", "-n", str(self.helper_path), *arguments]
        try:
            result = self.runner(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"Could not run the Shairport name helper: {exc}") from exc

        output = (result.stdout or "").strip()
        error = (result.stderr or "").strip()
        try:
            payload = json.loads(output or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError(error or output or "The Shairport name helper returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("The Shairport name helper returned an invalid response.")
        if result.returncode or payload.get("ok") is False:
            raise RuntimeError(str(payload.get("error") or error or "The Shairport name helper failed."))
        return payload

    def status(self) -> dict[str, Any]:
        status = self._base_status()
        if not status["installed"]:
            return status
        try:
            payload = self._invoke("status", timeout=8)
        except RuntimeError as exc:
            status["available"] = False
            status["error"] = str(exc)
            return status
        status.update(payload)
        status["available"] = payload.get("ok") is True
        status["installed"] = True
        status["helper_path"] = str(self.helper_path)
        return status

    def apply(self, receiver_name: Any) -> dict[str, Any]:
        name = validate_receiver_name(receiver_name)
        payload = self._invoke("set", name)
        payload.setdefault("receiver_name", name)
        return payload
