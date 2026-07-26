from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import datetime
from typing import Any, Callable

from flask import jsonify

try:
    from .playback_coordinator import PlaybackCoordinator
except ImportError:  # Supports direct execution imports.
    from playback_coordinator import PlaybackCoordinator


StateProvider = Callable[[], dict[str, Any]]


class ApplicationStateHub:
    """Combine isolated domain snapshots behind one interface-facing authority."""

    schema_version = "1.0"

    def __init__(self) -> None:
        self._providers: dict[str, StateProvider] = {}
        self._lock = threading.RLock()
        self._revision = 0
        self._last_signature: str | None = None

    def register_provider(self, name: str, provider: StateProvider) -> None:
        key = str(name or "").strip().lower()
        if not key:
            raise ValueError("Application-state providers require a name.")
        if not callable(provider):
            raise ValueError(f"Application-state provider {key} is not callable.")
        with self._lock:
            self._providers[key] = provider

    def _read_provider(self, name: str, provider: StateProvider) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            value = provider()
            if not isinstance(value, dict):
                raise TypeError("provider returned a non-object value")
            return deepcopy(value), {"healthy": True, "error": None}
        except Exception as exc:
            return (
                {
                    "available": False,
                    "error": f"{name} provider failed: {exc}",
                },
                {"healthy": False, "error": str(exc)},
            )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            providers = list(self._providers.items())

        state: dict[str, Any] = {}
        components: dict[str, Any] = {}
        for name, provider in providers:
            value, health = self._read_provider(name, provider)
            state[name] = value
            components[name] = health

        signature = json.dumps(state, sort_keys=True, separators=(",", ":"), default=str)
        with self._lock:
            if signature != self._last_signature:
                self._revision += 1
                self._last_signature = signature
            revision = self._revision

        return {
            "ok": True,
            "schema_version": self.schema_version,
            "revision": revision,
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "state": state,
            "components": components,
        }


def build_default_application_state_hub(dashboard: Any) -> ApplicationStateHub:
    """Build the first read-only hub from the application's established observers."""
    try:
        from . import audio_mixer
    except ImportError:  # Supports direct execution imports.
        import audio_mixer

    coordinator = PlaybackCoordinator(
        load_config=dashboard.load_config,
        load_state=dashboard.load_state,
        plexamp_status=lambda: audio_mixer._plexamp_controller().status(),
        airplay_status=dashboard.mpris_remote_status,
        alarm_status=dashboard.alarm_scheduler.status,
        alarm_audio_status=dashboard.alarm_audio.status,
    )

    hub = ApplicationStateHub()
    hub.register_provider("playback", coordinator.snapshot)
    return hub


def register_application_state_api(app: Any, hub: ApplicationStateHub) -> None:
    """Expose the hub without transferring command ownership yet."""
    if "api_application_state" in app.view_functions:
        return

    @app.route("/api/state", methods=["GET"])
    def api_application_state():
        return jsonify(hub.snapshot())
