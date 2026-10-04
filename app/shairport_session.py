from __future__ import annotations

import subprocess
from copy import deepcopy
from typing import Any, Callable


SHAIRPORT_REMOTE_SERVICE = "org.gnome.ShairportSync"
SHAIRPORT_REMOTE_OBJECT = "/org/gnome/ShairportSync"
SHAIRPORT_REMOTE_INTERFACE = "org.gnome.ShairportSync.RemoteControl"
AIRPLAY_VOLUME_MIN_DB = -30.0
AIRPLAY_VOLUME_MAX_DB = 0.0
AIRPLAY_VOLUME_MUTE_DB = -144.0

StatusProvider = Callable[[], dict[str, Any]]
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def parse_busctl_bool(value: str) -> bool | None:
    text = str(value or "").strip().lower()
    if text == "b true":
        return True
    if text == "b false":
        return False
    return None


def parse_busctl_double(value: str) -> float | None:
    parts = str(value or "").strip().split()
    if len(parts) != 2 or parts[0] != "d":
        return None
    try:
        return float(parts[1])
    except ValueError:
        return None


def airplay_db_to_percent(value: Any) -> int:
    try:
        db = float(value)
    except (TypeError, ValueError):
        raise ValueError("AirPlay volume must be a number.") from None
    if db <= AIRPLAY_VOLUME_MUTE_DB:
        return 0
    db = max(AIRPLAY_VOLUME_MIN_DB, min(AIRPLAY_VOLUME_MAX_DB, db))
    return max(0, min(100, round(
        100 * (db - AIRPLAY_VOLUME_MIN_DB)
        / (AIRPLAY_VOLUME_MAX_DB - AIRPLAY_VOLUME_MIN_DB)
    )))


def sender_remote_available(
    *,
    runner: CommandRunner = subprocess.run,
    timeout: float = 1.5,
) -> tuple[bool | None, str | None]:
    """Read whether Shairport currently has a controllable sender session."""
    command = [
        "/usr/bin/busctl",
        "--system",
        "get-property",
        SHAIRPORT_REMOTE_SERVICE,
        SHAIRPORT_REMOTE_OBJECT,
        SHAIRPORT_REMOTE_INTERFACE,
        "Available",
    ]
    try:
        result = runner(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, "Shairport RemoteControl.Available timed out."
    except OSError as exc:
        return None, f"Could not query Shairport RemoteControl.Available: {exc}"

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        return None, detail or "busctl get-property failed for Shairport RemoteControl.Available."

    available = parse_busctl_bool(result.stdout)
    if available is None:
        return None, f"Unexpected Shairport RemoteControl.Available value: {result.stdout.strip()}"
    return available, None


def sender_airplay_volume(
    *,
    runner: CommandRunner = subprocess.run,
    timeout: float = 1.5,
) -> tuple[float | None, str | None]:
    command = [
        "/usr/bin/busctl",
        "--system",
        "get-property",
        SHAIRPORT_REMOTE_SERVICE,
        SHAIRPORT_REMOTE_OBJECT,
        SHAIRPORT_REMOTE_INTERFACE,
        "AirplayVolume",
    ]
    try:
        result = runner(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, "Shairport RemoteControl.AirplayVolume timed out."
    except OSError as exc:
        return None, f"Could not query Shairport RemoteControl.AirplayVolume: {exc}"

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        return None, detail or "busctl get-property failed for Shairport RemoteControl.AirplayVolume."

    volume = parse_busctl_double(result.stdout)
    if volume is None:
        return None, f"Unexpected Shairport RemoteControl.AirplayVolume value: {result.stdout.strip()}"
    return volume, None


def shairport_remote_status(
    mpris_status_provider: StatusProvider,
    *,
    runner: CommandRunner = subprocess.run,
) -> dict[str, Any]:
    """Combine MPRIS playback evidence with sender-session availability.

    The MPRIS object remains present while Shairport Sync is running, even when no
    iPhone is connected. RemoteControl.Available describes the sender session and
    is therefore the signal PlaybackCoordinator should use during a pause hold.
    """
    base = mpris_status_provider()
    if not isinstance(base, dict):
        return {
            "available": False,
            "mpris_service_available": False,
            "sender_available": None,
            "availability_source": "invalid-mpris-status",
            "sender_error": "MPRIS status provider returned a non-object value.",
        }

    status = deepcopy(base)
    status["mpris_service_available"] = status.get("available") is True
    sender_available, sender_error = sender_remote_available(runner=runner)
    status["sender_available"] = sender_available
    status["sender_error"] = sender_error

    if sender_available is not None:
        status["available"] = sender_available
        status["availability_source"] = "shairport-remote-control"
    else:
        status["availability_source"] = "mpris-service-fallback"

    status["airplay_volume_db"] = None
    status["volume_source"] = "mpris-fallback"
    status["volume_error"] = None
    if sender_available is True:
        airplay_volume, volume_error = sender_airplay_volume(runner=runner)
        status["volume_error"] = volume_error
        if airplay_volume is not None:
            sender_percent = airplay_db_to_percent(airplay_volume)
            status["airplay_volume_db"] = airplay_volume
            status["volume_percent"] = sender_percent
            status["volume"] = sender_percent / 100
            status["volume_source"] = "shairport-remote-control-airplay"

    return status
