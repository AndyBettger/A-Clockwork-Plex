"""Opt-in Phase B3 loopback, one-use native-to-Chromium navigation mailbox.

No background process, persistent state or external navigation URLs. The
local native GTK test sends a short allowlisted command, the existing local
Chromium dashboard consumes it once and uses its ordinary ACPNavigate owner.
"""
from __future__ import annotations

from ipaddress import ip_address
from threading import Lock
from time import monotonic

ALLOWED_DESTINATIONS = frozenset({"clock", "weather", "news", "airplay", "settings", "audio"})
MAX_AGE_SECONDS = 12.0
MAX_BODY_BYTES = 96
SOURCE_HEADER = "native-gtk-b3-dev"


class NavigationError(ValueError):
    pass


class NavigationMailbox:
    def __init__(self, clock=monotonic):
        self._clock = clock
        self._guard = Lock()
        self._number = 0
        self._pending = None
        self._current = None

    def offer(self, payload):
        if (type(payload) is not dict or set(payload) != {"destination"}
                or type(payload["destination"]) is not str
                or payload["destination"] not in ALLOWED_DESTINATIONS):
            raise NavigationError("Unrecognised native navigation destination")
        with self._guard:
            self._number += 1
            self._pending = {
                "sequence": self._number,
                "destination": payload["destination"],
                "issued_at": self._clock(),
            }
            self._current = {**self._pending, "phase": "queued"}
            return self._number

    def take(self):
        with self._guard:
            pending = self._pending
            self._pending = None
            if pending is None:
                return None
            elapsed = self._clock() - pending["issued_at"]
            if elapsed < 0 or elapsed > MAX_AGE_SECONDS:
                return None
            if self._current and self._current["sequence"] == pending["sequence"]:
                self._current["phase"] = "taken"
            return {
                "sequence": pending["sequence"],
                "destination": pending["destination"],
            }

    def confirm_ready(self, sequence, destination):
        """Only the current consumed command may be marked as ready."""
        with self._guard:
            current = self._current
            if (type(sequence) is not int or type(destination) is not str
                    or not current or current["sequence"] != sequence
                    or current["destination"] != destination
                    or current["phase"] not in ("taken", "ready")):
                return False
            elapsed = self._clock() - current["issued_at"]
            if elapsed < 0 or elapsed > MAX_AGE_SECONDS:
                return False
            current["phase"] = "ready"
            return True

    def confirm_painted(self, sequence, destination):
        """Confirm Chromium got focus and rendered after the ready state."""
        with self._guard:
            current = self._current
            if (type(sequence) is not int or type(destination) is not str
                    or not current or current["sequence"] != sequence
                    or current["destination"] != destination
                    or current["phase"] not in ("ready", "painted")):
                return False
            age = self._clock() - current["issued_at"]
            if age < 0 or age > MAX_AGE_SECONDS:
                return False
            current["phase"] = "painted"
            return True

    def status(self, sequence):
        """Bounded read-only status for the requesting native GTK process."""
        with self._guard:
            current = self._current
            if type(sequence) is not int or not current or current["sequence"] != sequence:
                return "expired"
            elapsed = self._clock() - current["issued_at"]
            if elapsed < 0 or elapsed > MAX_AGE_SECONDS:
                return "expired"
            return current["phase"]


mailbox = NavigationMailbox()


def local_browser_request(req) -> bool:
    """Accept the actual Pi loopback kiosk, not a LAN/proxied browser."""
    try:
        peer = ip_address(req.remote_addr)
    except (ValueError, TypeError):
        return False
    host = str(req.host or "").lower()
    loopback_hosts = {"localhost", "127.0.0.1", "[::1]"}
    hostname = host.rsplit(":", 1)[0] if not host.startswith("[") else host.split("]", 1)[0] + "]"
    if not peer.is_loopback or hostname not in loopback_hosts:
        return False
    if any(req.headers.get(k) for k in (
        "X-Forwarded-Host", "X-Forwarded-For", "X-Forwarded-Proto", "Forwarded",
    )):
        return False
    return True


def browser_ready_allowed(req) -> bool:
    """Same-origin local Chromium acknowledgment, never external websites."""
    return (
        local_browser_request(req)
        and req.mimetype == "application/json"
        and req.content_length is not None
        and 0 < req.content_length <= MAX_BODY_BYTES
        and req.headers.get("Origin") == f"{req.scheme}://{req.host}"
        and req.headers.get("Sec-Fetch-Site") in (None, "same-origin")
    )


def native_status_allowed(req) -> bool:
    return (
        local_browser_request(req)
        and req.headers.get("X-ACP-B3-Source") == SOURCE_HEADER
        and not req.headers.get("Origin")
        and not req.headers.get("Sec-Fetch-Site")
    )


def native_submit_allowed(req) -> bool:
    """Never treat a normal web page or HTML form as a native touch action."""
    return (
        local_browser_request(req)
        and req.headers.get("X-ACP-B3-Source") == SOURCE_HEADER
        and not req.headers.get("Origin")
        and not req.headers.get("Sec-Fetch-Site")
        and req.mimetype == "application/json"
        and req.content_length is not None
        and 0 < req.content_length <= MAX_BODY_BYTES
    )
