from __future__ import annotations

import re
import shutil
import subprocess
from typing import Any, Callable

from flask import Flask, jsonify


Runner = Callable[..., subprocess.CompletedProcess[str]]
PCM_NAME_RE = re.compile(r"^[A-Za-z0-9_.:-]+(?:=[A-Za-z0-9_.:,=-]+)?$")


def _friendly_label(name: str, description: str | None = None) -> str:
    detail = str(description or "").strip()
    if detail:
        return f"{name} — {detail}"
    if name.startswith("hw:"):
        return f"{name} — Direct hardware device"
    if name.startswith("plughw:"):
        return f"{name} — Hardware device with format conversion"
    if name == "default":
        return "default — ALSA default output"
    return name


def discover_audio_devices(
    *,
    runner: Runner | None = None,
    current_device: str | None = None,
) -> dict[str, Any]:
    """Return safe, read-only ALSA PCM choices from ``aplay -L``.

    Only top-level PCM identifiers are accepted. Indented description lines are
    attached to the preceding identifier and never interpreted as a command or
    editable path.
    """

    command = shutil.which("aplay")
    current = str(current_device or "").strip()
    devices: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(name: str, description: str | None = None) -> None:
        candidate = str(name or "").strip()
        if not candidate or candidate in seen:
            return
        if not PCM_NAME_RE.fullmatch(candidate):
            return
        seen.add(candidate)
        devices.append({"id": candidate, "label": _friendly_label(candidate, description)})

    if current:
        add(current, "Currently configured")
    add("default")

    if not command:
        return {
            "ok": True,
            "available": False,
            "devices": devices,
            "error": "aplay was not found; showing the configured output only.",
        }

    run = runner or subprocess.run
    try:
        result = run(
            [command, "-L"],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "ok": True,
            "available": False,
            "devices": devices,
            "error": f"Could not enumerate ALSA outputs: {exc}",
        }

    pending_name: str | None = None
    pending_description: list[str] = []

    def flush() -> None:
        nonlocal pending_name, pending_description
        if pending_name:
            add(pending_name, " ".join(pending_description))
        pending_name = None
        pending_description = []

    for raw_line in (result.stdout or "").splitlines():
        if not raw_line.strip():
            continue
        if raw_line[:1].isspace():
            if pending_name:
                pending_description.append(raw_line.strip())
            continue
        flush()
        candidate = raw_line.strip()
        if PCM_NAME_RE.fullmatch(candidate):
            pending_name = candidate
    flush()

    return {
        "ok": True,
        "available": result.returncode == 0,
        "devices": devices,
        "error": None if result.returncode == 0 else (
            (result.stderr or "").strip() or "aplay could not enumerate ALSA outputs."
        ),
    }


def register_audio_devices_api(
    app: Flask,
    *,
    config_loader: Callable[[], dict[str, Any]],
    runner: Runner | None = None,
) -> None:
    if "api_audio_devices" in app.view_functions:
        return

    @app.get("/api/audio/devices")
    def api_audio_devices():
        config = config_loader()
        audio = config.get("alarm_audio") if isinstance(config, dict) else {}
        current = audio.get("hardware_device") if isinstance(audio, dict) else None
        return jsonify(discover_audio_devices(runner=runner, current_device=current))
