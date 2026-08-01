from __future__ import annotations

import subprocess
from copy import deepcopy
from typing import Any, Callable


SHAIRPORT_REMOTE_SERVICE = "org.gnome.ShairportSync"
SHAIRPORT_REMOTE_OBJECT = "/org/gnome/ShairportSync"
SHAIRPORT_REMOTE_INTERFACE = "org.gnome.ShairportSync.RemoteControl"
MPRIS_SERVICE = "org.mpris.MediaPlayer2.ShairportSync"
MPRIS_OBJECT = "/org/mpris/MediaPlayer2"
MPRIS_PLAYER_INTERFACE = "org.mpris.MediaPlayer2.Player"

StatusProvider = Callable[[], dict[str, Any]]
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def parse_busctl_bool(value: str) -> bool | None:
    text = str(value or "").strip().lower()
    if text == "b true":
        return True
    if text == "b false":
        return False
    return None


def parse_busctl_int64(value: str) -> int | None:
    parts = str(value or "").strip().split()
    if len(parts) != 2 or parts[0] not in {"x", "t"}:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


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


def mpris_position_us(
    *,
    runner: CommandRunner = subprocess.run,
    timeout: float = 1.5,
) -> tuple[int | None, str | None]:
    """Read the sender position used to distinguish stale Playing from real audio."""
    command = [
        "/usr/bin/busctl",
        "--system",
        "get-property",
        MPRIS_SERVICE,
        MPRIS_OBJECT,
        MPRIS_PLAYER_INTERFACE,
        "Position",
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
        return None, "Shairport MPRIS Position timed out."
    except OSError as exc:
        return None, f"Could not query Shairport MPRIS Position: {exc}"

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        return None, detail or "busctl get-property failed for Shairport MPRIS Position."

    position = parse_busctl_int64(result.stdout)
    if position is None:
        return None, f"Unexpected Shairport MPRIS Position value: {result.stdout.strip()}"
    return max(0, position), None


def shairport_remote_status(
    mpris_status_provider: StatusProvider,
    *,
    runner: CommandRunner = subprocess.run,
) -> dict[str, Any]:
    """Combine MPRIS playback evidence with sender-session availability.

    The MPRIS object remains present while Shairport Sync is running, even when no
    iPhone is connected. RemoteControl.Available describes the sender session and
    is therefore the signal PlaybackCoordinator should use during a pause hold.
    Position is diagnostic evidence only: the handoff owner uses movement across
    spaced samples to distinguish a real rapid resume from a stale Playing label.
    """
    base = mpris_status_provider()
    if not isinstance(base, dict):
        return {
            "available": False,
            "mpris_service_available": False,
            "sender_available": None,
            "availability_source": "invalid-mpris-status",
            "sender_error": "MPRIS status provider returned a non-object value.",
            "position_us": None,
            "position_error": None,
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

    position_us: int | None = None
    position_error: str | None = None
    if status.get("mpris_service_available") is True and sender_available is not False:
        position_us, position_error = mpris_position_us(runner=runner)
    status["position_us"] = position_us
    status["position_error"] = position_error

    return status
