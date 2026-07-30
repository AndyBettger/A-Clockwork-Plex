from __future__ import annotations

import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Callable


ConfigProvider = Callable[[], dict[str, Any]]


class PlexampTimelineObserver:
    """Observe Plexamp Headless without owning any playback command.

    The queue token changes when a new play queue is loaded, including an NFC
    album launch, but remains stable while tracks advance naturally inside that
    queue. The media token identifies the current track for diagnostics only.
    """

    def __init__(
        self,
        load_config: ConfigProvider,
        *,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self._load_config = load_config
        self._opener = opener or urllib.request.urlopen
        self._command_lock = threading.Lock()
        self._command_id = int(time.time() * 1000) % 2_000_000_000

    def _next_command_id(self) -> int:
        with self._command_lock:
            self._command_id = (self._command_id + 1) % 2_000_000_000
            return self._command_id

    def _base_url(self) -> str:
        config = self._load_config()
        plexamp = config.get("plexamp") if isinstance(config.get("plexamp"), dict) else {}
        return str(plexamp.get("url", "http://localhost:32500")).rstrip("/")

    @staticmethod
    def _token(prefix: str, attributes: dict[str, str], names: tuple[str, ...]) -> str | None:
        parts = [f"{name}={attributes[name]}" for name in names if attributes.get(name)]
        return f"{prefix}:{'|'.join(parts)}" if parts else None

    @classmethod
    def parse_timeline(cls, payload: bytes) -> dict[str, Any]:
        snapshot: dict[str, Any] = {
            "percent": None,
            "playback_state": None,
            "activity_token": None,
            "media_token": None,
        }
        try:
            root = ET.fromstring(payload)
        except (ET.ParseError, ValueError):
            return snapshot

        for element in root.iter():
            tag = str(element.tag).rsplit("}", 1)[-1]
            if tag != "Timeline" or str(element.attrib.get("type", "")).lower() != "music":
                continue

            attributes = {str(key): str(value) for key, value in element.attrib.items()}
            value = attributes.get("volume")
            if value is not None:
                try:
                    snapshot["percent"] = max(0, min(100, round(float(value))))
                except (TypeError, ValueError):
                    pass

            state = attributes.get("state", "").strip().lower()
            snapshot["playback_state"] = state or None

            # A new NFC launch normally creates a new Plex play queue. Prefer
            # queue/container identifiers so ordinary next-track progression does
            # not steal a manually selected dashboard page.
            snapshot["activity_token"] = cls._token(
                "queue",
                attributes,
                ("playQueueID", "containerKey"),
            )
            snapshot["media_token"] = cls._token(
                "media",
                attributes,
                ("ratingKey", "key", "guid", "playQueueItemID"),
            )
            if snapshot["activity_token"] is None:
                snapshot["activity_token"] = snapshot["media_token"]
            break
        return snapshot

    def status(self) -> dict[str, Any]:
        command_id = self._next_command_id()
        query = urllib.parse.urlencode({"commandID": command_id, "type": "music", "wait": 0})
        url = f"{self._base_url()}/player/timeline/poll?{query}"
        request_object = urllib.request.Request(
            url,
            headers={"Accept": "application/xml, application/json, */*"},
        )
        try:
            with self._opener(request_object, timeout=2.0) as response:
                payload = response.read()
        except (OSError, TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            return {
                "available": False,
                "percent": None,
                "playback_state": None,
                "activity_token": None,
                "media_token": None,
                "source": "plexamp-timeline-observer",
                "error": str(exc),
            }

        snapshot = self.parse_timeline(payload)
        percent = snapshot.get("percent")
        return {
            "available": percent is not None,
            **snapshot,
            "source": "plexamp-timeline-observer",
            "error": None if percent is not None else "Plexamp timeline did not report a music volume.",
        }
