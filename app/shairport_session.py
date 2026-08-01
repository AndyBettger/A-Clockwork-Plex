from __future__ import annotations

import subprocess
from copy import deepcopy
from typing import Any, Callable


SHAIRPORT_REMOTE_SERVICE = "org.gnome.ShairportSync"
SHAIRPORT_REMOTE_OBJECT = "/org/gnome/ShairportSync"
SHAIRPORT_REMOTE_INTERFACE = "org.gnome.ShairportSync.RemoteControl"

StatusProvider = Callable[[], dict[str, Any]]
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def parse_busctl_bool(value: str) -> bool | None:
    text = str(value or "").strip().lower()
    if text == "b true":
        return True
    if text == "b false":
        return False
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

    return status
