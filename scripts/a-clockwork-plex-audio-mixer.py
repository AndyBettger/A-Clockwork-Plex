#!/usr/bin/python3
from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

CONFIG_PATH = Path("/etc/default/a-clockwork-plex-audio")
MANAGED_CONFIG_PATH = Path("/etc/default/a-clockwork-plex-split-bus")
ACTIVE_ALSA_CONFIG = Path("/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf")
ROUTE_STATE_PATH = Path("/var/lib/a-clockwork-plex/split-bus/route-state.json")
MIN_DB = -51.0
MAX_DB = 0.0
PERSISTENT_CHANNELS = {"master", "plexamp", "airplay", "alarm"}
CHANNELS = {
    "master": {"control": "A Clockwork Master", "pcm": "acp_master"},
    "plexamp": {"control": "A Clockwork Plexamp", "pcm": "acp_plexamp"},
    "airplay": {"control": "A Clockwork AirPlay", "pcm": "acp_airplay"},
    "airplay_live": {"control": "A Clockwork AirPlay Live", "pcm": "acp_airplay"},
    "alarm": {"control": "A Clockwork Alarm", "pcm": "acp_alarm"},
}


def emit(payload: dict[str, Any], code: int = 0) -> None:
    print(json.dumps(payload, sort_keys=True))
    raise SystemExit(code)


def _read_key_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_config(
    config_path: Path = CONFIG_PATH,
    managed_config_path: Path = MANAGED_CONFIG_PATH,
) -> dict[str, str]:
    values = {
        "ALSA_CARD": "Pro",
        "ALSA_DEVICE": "0",
        "SAMPLE_RATE": "44100",
        "FORMAT": "S16_LE",
        "CHANNELS": "2",
    }

    legacy = _read_key_values(config_path)
    for key in values:
        if key in legacy:
            values[key] = legacy[key]

    # The shared-mixer defaults still own control creation and the stereo
    # hardware shape, but the selected managed audio profile owns the active
    # DAC/rate metadata.  In particular, guarded hi-res rehearsals update the
    # split-bus defaults while deliberately leaving the helper defaults alone.
    managed = _read_key_values(managed_config_path)
    if "DAC_CARD" in managed:
        values["ALSA_CARD"] = managed["DAC_CARD"]
    if "DAC_DEVICE" in managed:
        values["ALSA_DEVICE"] = managed["DAC_DEVICE"]
    if "SAMPLE_RATE" in managed:
        values["SAMPLE_RATE"] = managed["SAMPLE_RATE"]
    if "FORMAT" in managed:
        values["FORMAT"] = managed["FORMAT"]
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


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _acp_dmix_block(path: Path) -> str:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    start = source.find("pcm.acp_dmix")
    if start < 0:
        return ""
    next_pcm = source.find("\npcm.", start + len("pcm.acp_dmix"))
    return source[start:] if next_pcm < 0 else source[start:next_pcm]


def active_processing_status(path: Path = ACTIVE_ALSA_CONFIG) -> dict[str, Any]:
    block = _acp_dmix_block(path)
    format_match = re.search(r"(?m)^\s*format\s+([A-Za-z0-9_]+)\s*$", block)
    rate_match = re.search(r"(?m)^\s*rate\s+(\d+)\s*$", block)
    channels_match = re.search(r"(?m)^\s*channels\s+(\d+)\s*$", block)
    available = bool(block and format_match and rate_match)
    return {
        "available": available,
        "format": format_match.group(1) if format_match else None,
        "rate_hz": int(rate_match.group(1)) if rate_match else None,
        "channels": int(channels_match.group(1)) if channels_match else None,
        "authority": "active-alsa-route",
        "error": None if available else "Active ACP processing format/rate could not be read.",
    }


def dac_playback_status(
    card: str,
    device: str,
    *,
    path: Path | None = None,
) -> dict[str, Any]:
    hw_path = path or Path(f"/proc/asound/{card}/pcm{device}p/sub0/hw_params")
    try:
        source = hw_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        return {
            "available": False,
            "open": False,
            "format": None,
            "rate_hz": None,
            "channels": None,
            "period_size": None,
            "buffer_size": None,
            "authority": "alsa-hw-params",
            "error": str(exc),
        }
    if not source or source == "closed":
        return {
            "available": True,
            "open": False,
            "format": None,
            "rate_hz": None,
            "channels": None,
            "period_size": None,
            "buffer_size": None,
            "authority": "alsa-hw-params",
            "error": None,
        }

    def text_value(name: str) -> str | None:
        match = re.search(rf"(?m)^{re.escape(name)}:\s*([^\s]+)", source)
        return match.group(1) if match else None

    def int_value(name: str) -> int | None:
        value = text_value(name)
        if value is None:
            return None
        match = re.match(r"(\d+)", value)
        return int(match.group(1)) if match else None

    format_value = text_value("format")
    rate_value = int_value("rate")
    return {
        "available": format_value is not None and rate_value is not None,
        "open": True,
        "format": format_value,
        "rate_hz": rate_value,
        "channels": int_value("channels"),
        "period_size": int_value("period_size"),
        "buffer_size": int_value("buffer_size"),
        "authority": "alsa-hw-params",
        "error": None if format_value is not None and rate_value is not None
        else "DAC hw_params did not expose format/rate.",
    }


def audio_path_status(
    config: dict[str, str],
    *,
    active_alsa_path: Path = ACTIVE_ALSA_CONFIG,
    route_state_path: Path = ROUTE_STATE_PATH,
    dac_hw_params_path: Path | None = None,
) -> dict[str, Any]:
    route_state = _read_json_object(route_state_path)
    processing = active_processing_status(active_alsa_path)
    dac = dac_playback_status(
        config["ALSA_CARD"],
        config["ALSA_DEVICE"],
        path=dac_hw_params_path,
    )
    return {
        "route_mode": route_state.get("mode"),
        "source": {
            "available": False,
            "format": None,
            "rate_hz": None,
            "authority": "source-observer",
            "note": (
                "The current Plexamp/AirPlay runtime observers do not expose a "
                "trustworthy source format/rate."
            ),
        },
        "processing": processing,
        "dac": dac,
    }


def db_to_loudness_percent(db_value: float) -> int:
    """Convert attenuation in dB to a human-facing amplitude percentage."""
    if db_value <= MIN_DB:
        return 0
    if db_value >= MAX_DB:
        return 100
    amplitude = 10 ** (db_value / 20.0)
    return max(0, min(100, round(amplitude * 100)))


def loudness_percent_to_db(percent: int) -> float | None:
    """Map a human-facing percentage to dB; zero is handled as hard minimum."""
    if percent <= 0:
        return None
    db_value = 20.0 * math.log10(percent / 100.0)
    return max(MIN_DB, min(MAX_DB, db_value))


def db_to_raw_percent(db_value: float | None) -> int:
    """Convert dB to ALSA softvol's positive raw control percentage.

    Passing a negative dB token directly to amixer is ambiguous because amixer
    parses it as command-line switches. Softvol's raw percentage is linear
    across its configured dB range, so a positive percentage is equivalent and
    avoids that parser trap.
    """
    if db_value is None or db_value <= MIN_DB:
        return 0
    if db_value >= MAX_DB:
        return 100
    span = MAX_DB - MIN_DB
    return max(0, min(100, round(((db_value - MIN_DB) / span) * 100)))


def control_status(card: str, control: str) -> dict[str, Any]:
    result = run(["/usr/bin/amixer", "-c", card, "sget", control])
    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    if result.returncode:
        return {
            "available": False,
            "percent": None,
            "raw_percent": None,
            "db": None,
            "error": output or "Mixer control unavailable.",
        }

    raw_matches = re.findall(r"\[(\d{1,3})%\]", output)
    db_matches = re.findall(r"\[(-?\d+(?:\.\d+)?)dB\]", output)
    if not raw_matches:
        return {
            "available": False,
            "percent": None,
            "raw_percent": None,
            "db": None,
            "error": "Mixer control returned no percentage.",
        }

    raw_percent = max(0, min(100, int(raw_matches[0])))
    db_value = float(db_matches[0]) if db_matches else None
    if raw_percent == 0:
        loudness_percent = 0
    elif db_value is not None:
        loudness_percent = db_to_loudness_percent(db_value)
    else:
        loudness_percent = raw_percent

    return {
        "available": True,
        "percent": loudness_percent,
        "raw_percent": raw_percent,
        "db": round(db_value, 2) if db_value is not None else None,
        "scale": "perceptual-amplitude",
        "error": None,
    }


def full_status() -> dict[str, Any]:
    config = load_config()
    card = config["ALSA_CARD"]
    names = pcm_names()
    audio_path = audio_path_status(config)
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
        "sample_rate_hz": (
            audio_path["processing"]["rate_hz"]
            if audio_path["processing"]["available"]
            else int(config["SAMPLE_RATE"])
        ),
        "channels_count": int(config["CHANNELS"]),
        "audio_path": audio_path,
        "scale": {
            "name": "perceptual-amplitude",
            "minimum_db": MIN_DB,
            "maximum_db": MAX_DB,
            "examples": {"50_percent_db": -6.02, "25_percent_db": -12.04, "10_percent_db": -20.0},
        },
        "channels": channels,
        "error": None if all_ready else "One or more shared ALSA controls are unavailable.",
    }


def set_volume(channel_id: str, percent_text: str, *, persist: bool) -> dict[str, Any]:
    if channel_id not in CHANNELS:
        emit({"ok": False, "error": f"Unknown mixer channel: {channel_id}"}, 64)
    try:
        percent = int(percent_text)
    except ValueError:
        emit({"ok": False, "error": "Volume must be an integer."}, 64)
    if not 0 <= percent <= 100:
        emit({"ok": False, "error": "Volume must be from 0 to 100 percent."}, 64)

    if persist and channel_id not in PERSISTENT_CHANNELS:
        emit({"ok": False, "error": f"Mixer channel {channel_id} is runtime-only."}, 64)

    config = load_config()
    card = config["ALSA_CARD"]
    control = CHANNELS[channel_id]["control"]
    db_value = loudness_percent_to_db(percent)
    raw_percent = db_to_raw_percent(db_value)
    result = run(["/usr/bin/amixer", "-c", card, "sset", control, f"{raw_percent}%"])
    if result.returncode:
        error = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
        emit({"ok": False, "error": error or "amixer failed."}, 70)

    payload = full_status()
    payload.update(
        {
            "ok": True,
            "changed_channel": channel_id,
            "requested_percent": percent,
            "requested_db": round(db_value, 2) if db_value is not None else MIN_DB,
            "requested_raw_percent": raw_percent,
            "persisted": persist,
        }
    )
    if persist:
        store = run(["/usr/sbin/alsactl", "store", card])
        if store.returncode:
            payload["warning"] = (store.stderr or store.stdout or "Could not persist ALSA state.").strip()
    return payload


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "status" and len(sys.argv) == 2:
        emit(full_status())
    if action in {"set", "live"} and len(sys.argv) == 4:
        emit(set_volume(sys.argv[2].strip().lower(), sys.argv[3].strip(), persist=action == "set"))
    emit(
        {
            "ok": False,
            "error": "Usage: a-clockwork-plex-audio-mixer {status|set <channel> <0-100>|live <channel> <0-100>}",
        },
        64,
    )


if __name__ == "__main__":
    main()
