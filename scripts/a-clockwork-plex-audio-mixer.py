#!/usr/bin/python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

CONFIG_PATH = Path("/etc/default/a-clockwork-plex-audio")
CHANNELS = {
    "master": {"control": "A Clockwork Master", "pcm": "acp_master"},
    "plexamp": {"control": "A Clockwork Plexamp", "pcm": "acp_plexamp"},
    "airplay": {"control": "A Clockwork AirPlay", "pcm": "acp_airplay"},
    "alarm": {"control": "A Clockwork Alarm", "pcm": "acp_alarm"},
}


def emit(payload: dict[str, Any], code: int = 0) -> None:
    print(json.dumps(payload, sort_keys=True))
    raise SystemExit(code)


def load_config() -> dict[str, str]:
    values = {
        "ALSA_CARD": "Pro",
        "ALSA_DEVICE": "0",
        "SAMPLE_RATE": "44100",
        "CHANNELS": "2",
    }
    try:
        lines = CONFIG_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in values:
            values[key] = value
    return values


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=8, check=False)


def pcm_names() -> set[str]:
    result = run(["/usr/bin/aplay", "-L"])
    if result.returncode:
        return set()
    return {
        line.strip()
        for line in result.stdout.splitlines()
        if line and not line[0].isspace()
    }


def control_status(card: str, control: str) -> dict[str, Any]:
    result = run(["/usr/bin/amixer", "-c", card, "sget", control])
    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    if result.returncode:
        return {"available": False, "percent": None, "error": output or "Mixer control unavailable."}
    matches = re.findall(r"\[(\d{1,3})%\]", output)
    if not matches:
        return {"available": False, "percent": None, "error": "Mixer control returned no percentage."}
    return {"available": True, "percent": max(0, min(100, int(matches[0]))), "error": None}


def full_status() -> dict[str, Any]:
    config = load_config()
    card = config["ALSA_CARD"]
    names = pcm_names()
    channels: dict[str, dict[str, Any]] = {}
    all_ready = True
    for channel_id, metadata in CHANNELS.items():
        status = control_status(card, metadata["control"])
        status["pcm_available"] = metadata["pcm"] in names
        if not status["pcm_available"]:
            status["error"] = status.get("error") or f"PCM {metadata['pcm']} is not registered."
        status["control"] = metadata["control"]
        status["pcm"] = metadata["pcm"]
        channels[channel_id] = status
        all_ready = all_ready and status["available"] and status["pcm_available"]
    return {
        "available": all_ready,
        "configured": all_ready,
        "card": card,
        "hardware_pcm": f"hw:CARD={card},DEV={config['ALSA_DEVICE']}",
        "sample_rate_hz": int(config["SAMPLE_RATE"]),
        "channels_count": int(config["CHANNELS"]),
        "channels": channels,
        "error": None if all_ready else "One or more shared ALSA controls are unavailable.",
    }


def set_volume(channel_id: str, percent_text: str) -> dict[str, Any]:
    if channel_id not in CHANNELS:
        emit({"ok": False, "error": f"Unknown mixer channel: {channel_id}"}, 64)
    try:
        percent = int(percent_text)
    except ValueError:
        emit({"ok": False, "error": "Volume must be an integer."}, 64)
    if not 0 <= percent <= 100:
        emit({"ok": False, "error": "Volume must be from 0 to 100 percent."}, 64)

    config = load_config()
    card = config["ALSA_CARD"]
    control = CHANNELS[channel_id]["control"]
    result = run(["/usr/bin/amixer", "-c", card, "sset", control, f"{percent}%"])
    if result.returncode:
        error = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
        emit({"ok": False, "error": error or "amixer failed."}, 70)

    store = run(["/usr/sbin/alsactl", "store", card])
    payload = full_status()
    payload.update({"ok": True, "changed_channel": channel_id, "requested_percent": percent})
    if store.returncode:
        payload["warning"] = (store.stderr or store.stdout or "Could not persist ALSA state.").strip()
    return payload


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "status" and len(sys.argv) == 2:
        emit(full_status())
    if action == "set" and len(sys.argv) == 4:
        emit(set_volume(sys.argv[2].strip().lower(), sys.argv[3].strip()))
    emit({"ok": False, "error": "Usage: a-clockwork-plex-audio-mixer {status|set <channel> <0-100>}"}, 64)


if __name__ == "__main__":
    main()
