from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from flask import jsonify, request

try:
    from .playback_coordinator import PlaybackCoordinator
    from .shairport_session import shairport_remote_status
except ImportError:  # Supports direct execution imports.
    from playback_coordinator import PlaybackCoordinator
    from shairport_session import shairport_remote_status


StateProvider = Callable[[], dict[str, Any]]
MIN_AIRPLAY_HOLD_SECONDS = 15
MAX_AIRPLAY_HOLD_SECONDS = 86400
DEFAULT_AIRPLAY_HOLD_SECONDS = 600


class ApplicationStateHub:
    """Combine isolated domain snapshots behind one interface-facing authority."""

    schema_version = "1.0"

    def __init__(self) -> None:
        self._providers: dict[str, StateProvider] = {}
        self._services: dict[str, Any] = {}
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

    def register_service(self, name: str, service: Any) -> None:
        key = str(name or "").strip().lower()
        if not key:
            raise ValueError("Application services require a name.")
        with self._lock:
            self._services[key] = service

    def service(self, name: str) -> Any | None:
        key = str(name or "").strip().lower()
        with self._lock:
            return self._services.get(key)

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


def configured_airplay_hold_seconds(config: dict[str, Any]) -> int:
    """Return a bounded pause-hold duration from the AirPlay configuration."""
    airplay = config.get("airplay") if isinstance(config.get("airplay"), dict) else {}
    try:
        seconds = int(airplay.get("pause_hold_seconds", DEFAULT_AIRPLAY_HOLD_SECONDS))
    except (TypeError, ValueError):
        seconds = DEFAULT_AIRPLAY_HOLD_SECONDS
    return max(MIN_AIRPLAY_HOLD_SECONDS, min(MAX_AIRPLAY_HOLD_SECONDS, seconds))


def build_default_application_state_hub(dashboard: Any) -> ApplicationStateHub:
    """Build the playback hub with persisted AirPlay pause-hold ownership."""
    try:
        from . import audio_mixer
    except ImportError:  # Supports direct execution imports.
        import audio_mixer

    runtime_path = Path(dashboard.BASE_DIR) / "playback-runtime.json"
    startup_config = dashboard.load_config()
    hold_seconds = configured_airplay_hold_seconds(startup_config)

    def complete_airplay_hold(_reason: str) -> None:
        config = dashboard.load_config()
        dashboard_config = config.get("dashboard", {}) if isinstance(config.get("dashboard"), dict) else {}
        idle_screen = str(dashboard_config.get("default_mode", "clock")).strip().lower()
        if idle_screen not in dashboard.VALID_MODES:
            idle_screen = "clock"
        dashboard.set_airplay_session(False)
        if idle_screen != "clock":
            dashboard.set_mode(idle_screen)

    coordinator = PlaybackCoordinator(
        load_config=dashboard.load_config,
        load_state=dashboard.load_state,
        plexamp_status=lambda: audio_mixer._plexamp_controller().status(),
        airplay_status=lambda: shairport_remote_status(dashboard.mpris_remote_status),
        alarm_status=dashboard.alarm_scheduler.status,
        alarm_audio_status=dashboard.alarm_audio.status,
        runtime_path=runtime_path,
        airplay_hold_seconds=hold_seconds,
        hold_completion=complete_airplay_hold,
    )

    hub = ApplicationStateHub()
    hub.register_service("playback", coordinator)
    hub.register_provider("playback", coordinator.snapshot)
    return hub


def _register_legacy_playback_event_wrappers(app: Any, coordinator: PlaybackCoordinator) -> None:
    """Translate existing AirPlay routes into coordinator events without changing their behaviour."""
    mappings = {
        "api_airplay_start": ("airplay", "playing", "legacy-airplay-start-route"),
        "api_airplay_end": ("airplay", "disconnected", "legacy-airplay-end-route"),
    }
    for endpoint, (source, event, origin) in mappings.items():
        view = app.view_functions.get(endpoint)
        if view is None or getattr(view, "_acp_playback_event_wrapped", False):
            continue

        def wrapped_view(*args: Any, _view=view, _source=source, _event=event, _origin=origin, **kwargs: Any):
            response = _view(*args, **kwargs)
            coordinator.record_event(_source, _event, {"origin": _origin})
            return response

        wrapped_view._acp_playback_event_wrapped = True  # type: ignore[attr-defined]
        app.view_functions[endpoint] = wrapped_view


def register_application_state_api(app: Any, hub: ApplicationStateHub) -> None:
    """Expose shared state plus validated playback event ingestion."""
    coordinator = hub.service("playback")

    if "api_application_state" not in app.view_functions:
        @app.route("/api/state", methods=["GET"])
        def api_application_state():
            return jsonify(hub.snapshot())

    if "api_playback_state" not in app.view_functions:
        @app.route("/api/playback/state", methods=["GET"])
        def api_playback_state():
            if not isinstance(coordinator, PlaybackCoordinator):
                return jsonify({"ok": False, "error": "Playback coordinator is unavailable."}), 503
            return jsonify({"ok": True, "playback": coordinator.snapshot()})

    if "api_playback_events" not in app.view_functions:
        @app.route("/api/playback/events", methods=["GET", "POST"])
        def api_playback_events():
            if not isinstance(coordinator, PlaybackCoordinator):
                return jsonify({"ok": False, "error": "Playback coordinator is unavailable."}), 503
            if request.method == "GET":
                return jsonify({"ok": True, "events": coordinator.event_snapshot()})

            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                return jsonify({"ok": False, "error": "Playback event must be a JSON object."}), 400
            details = payload.get("details", {})
            try:
                event = coordinator.record_event(
                    str(payload.get("source", "")),
                    str(payload.get("event", "")),
                    details,
                )
            except ValueError as exc:
                return jsonify({"ok": False, "error": str(exc)}), 400
            return jsonify({"ok": True, "event": event, "playback": coordinator.snapshot()})

    if isinstance(coordinator, PlaybackCoordinator):
        _register_legacy_playback_event_wrappers(app, coordinator)
