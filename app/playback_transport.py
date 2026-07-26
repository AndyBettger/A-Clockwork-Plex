from __future__ import annotations

import threading
from copy import deepcopy
from datetime import datetime
from typing import Any, Callable

from flask import jsonify, request

try:
    from .playback_coordinator import (
        PlaybackCoordinator,
        _parse_time,
        _safe_status,
        _text,
    )
except ImportError:  # Supports direct execution imports.
    from playback_coordinator import PlaybackCoordinator, _parse_time, _safe_status, _text


AirPlayCommand = Callable[[str], tuple[bool, str | None]]
DEFAULT_COMMAND_VERIFY_SECONDS = 20


class TransportPlaybackCoordinator(PlaybackCoordinator):
    """Own explicit AirPlay transport intent while automatic arbitration stays disabled."""

    authority = "airplay-transport-owner"

    def __init__(
        self,
        *,
        airplay_command: AirPlayCommand,
        command_verify_seconds: int = DEFAULT_COMMAND_VERIFY_SECONDS,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._airplay_command = airplay_command
        self._command_verify_seconds = max(2, int(command_verify_seconds))
        self._command_lock = threading.RLock()
        self._command_sequence = 0
        self._command_runtime: dict[str, Any] = {
            "sequence": 0,
            "source": None,
            "action": None,
            "target_state": None,
            "status": "idle",
            "requested_at": None,
            "accepted_at": None,
            "completed_at": None,
            "observed_state": None,
            "observed_source": None,
            "last_error": None,
            "noop": False,
        }

    def _timestamp(self) -> str:
        return self._now().isoformat(timespec="milliseconds")

    def _update_command(self, **updates: Any) -> dict[str, Any]:
        with self._command_lock:
            self._command_runtime.update(updates)
            return deepcopy(self._command_runtime)

    def command_snapshot(self) -> dict[str, Any]:
        with self._command_lock:
            return deepcopy(self._command_runtime)

    def _new_command(self, source: str, action: str, target_state: str) -> dict[str, Any]:
        with self._command_lock:
            self._command_sequence += 1
            self._command_runtime = {
                "sequence": self._command_sequence,
                "source": source,
                "action": action,
                "target_state": target_state,
                "status": "requested",
                "requested_at": self._timestamp(),
                "accepted_at": None,
                "completed_at": None,
                "observed_state": None,
                "observed_source": None,
                "last_error": None,
                "noop": False,
            }
            return deepcopy(self._command_runtime)

    def _apply_airplay_runtime_event(self, event: str, *, reason: str) -> None:
        # A Pi Pause records intent immediately. Shairport's active-state END arrives
        # about ten seconds later and must not restart an already-running hold.
        if event == "paused" and self._runtime_airplay().get("phase") in {"holding", "action_failed"}:
            return
        super()._apply_airplay_runtime_event(event, reason=reason)

    def _matching_external_transition(self, target_state: str, requested_at: datetime) -> dict[str, Any] | None:
        events = self._events.snapshot().get("recent_events") or []
        for event in reversed(events):
            if event.get("source") != "airplay" or event.get("event") != target_state:
                continue
            # Observed journal entries may be projections of the coordinator's own
            # hold state. They are useful diagnostics but are not independent command
            # confirmation. Only an explicit adapter event can confirm here.
            if event.get("kind") != "explicit":
                continue
            occurred_at = _parse_time(event.get("at"))
            if occurred_at is None or occurred_at < requested_at:
                continue
            details = event.get("details") if isinstance(event.get("details"), dict) else {}
            if details.get("origin") == "playback-coordinator-command":
                continue
            return event
        return None

    def _later_authoritative_pause(self, requested_at: datetime) -> bool:
        """Return whether a real pause arrived after the current Play request."""
        events = self._events.snapshot().get("recent_events") or []
        for event in reversed(events):
            if event.get("source") != "airplay" or event.get("event") != "paused":
                continue
            if event.get("kind") not in {"explicit", "coordinator"}:
                continue
            occurred_at = _parse_time(event.get("at"))
            if occurred_at is None or occurred_at < requested_at:
                continue
            details = event.get("details") if isinstance(event.get("details"), dict) else {}
            if details.get("origin") == "playback-coordinator-command":
                continue
            return True
        return False

    def _heal_stale_observed_pause(self, payload: dict[str, Any]) -> None:
        """Prevent a late observed snapshot from undoing a confirmed Play command.

        A snapshot can begin while paused, then finish after the Play command and append
        an observed pause later in the journal. That entry is not new user intent. When
        live MPRIS and the confirmed command both say Playing, replace that stale
        projection and journal the healed state. Fresh metadata pauses and later explicit
        adapter pauses remain authoritative and are deliberately not changed here.
        """
        command = self.command_snapshot()
        if (
            command.get("status") != "confirmed"
            or command.get("action") != "play"
            or command.get("target_state") != "playing"
        ):
            return

        requested_at = _parse_time(command.get("requested_at"))
        if requested_at is None or self._later_authoritative_pause(requested_at):
            return

        sources = payload.get("sources") if isinstance(payload.get("sources"), dict) else {}
        airplay = sources.get("airplay") if isinstance(sources.get("airplay"), dict) else {}
        hold = airplay.get("hold") if isinstance(airplay.get("hold"), dict) else {}
        observed = airplay.get("observed") if isinstance(airplay.get("observed"), dict) else {}
        raw_state = _text(observed.get("raw_playback_status"), "unknown")
        effective_state = _text(observed.get("effective_playback_status"), "unknown")

        if (
            airplay.get("connected") is not True
            or hold.get("active") is True
            or airplay.get("state") != "paused"
            or airplay.get("state_source") != "coordinator-event-journal"
            or raw_state != "playing"
            or effective_state != "playing"
        ):
            return

        airplay["state"] = "playing"
        airplay["state_source"] = "transport-confirmed-mpris"
        payload["active_source"] = "airplay"
        payload["decision_reason"] = "airplay-session-connected"
        self._events.observe(
            "airplay",
            "playing",
            {"state": "playing", "state_source": "transport-confirmed-mpris"},
        )
        payload["events"] = self._events.snapshot()

    def _reconcile_transport_command(self) -> str:
        command = self.command_snapshot()
        if command.get("status") != "accepted-awaiting-observation":
            return "idle"

        requested_at = _parse_time(command.get("requested_at"))
        target_state = str(command.get("target_state") or "")
        if requested_at is None or target_state not in {"playing", "paused"}:
            return "idle"

        remote = _safe_status(self._airplay_status, "AirPlay")
        raw_state = _text(remote.get("playback_status"), "unknown")
        external = self._matching_external_transition(target_state, requested_at)

        if remote.get("available") is False:
            self._update_command(
                status="failed",
                completed_at=self._timestamp(),
                observed_state="disconnected",
                observed_source="sender-availability",
                last_error="The AirPlay sender disconnected before the command was confirmed.",
            )
            return "failed"

        if raw_state == target_state:
            self._update_command(
                status="confirmed",
                completed_at=self._timestamp(),
                observed_state=target_state,
                observed_source="mpris",
                last_error=None,
            )
            return "confirmed"

        if external is not None:
            details = external.get("details") if isinstance(external.get("details"), dict) else {}
            self._update_command(
                status="confirmed",
                completed_at=self._timestamp(),
                observed_state=target_state,
                observed_source=str(details.get("origin") or external.get("kind") or "adapter-event"),
                last_error=None,
            )
            return "confirmed"

        age = (self._now() - requested_at).total_seconds()
        if age >= self._command_verify_seconds:
            self._update_command(
                status="accepted-unconfirmed",
                completed_at=self._timestamp(),
                observed_state=raw_state,
                observed_source="verification-timeout",
                last_error="The transport adapter accepted the command, but no independent confirmation arrived.",
            )
            return "unconfirmed"

        self._update_command(observed_state=raw_state, observed_source="awaiting-observation")
        return "waiting"

    def command(self, source: Any, action: Any) -> dict[str, Any]:
        source_key = _text(source, "")
        action_key = _text(action, "")
        if source_key != "airplay":
            raise ValueError("Only AirPlay transport is promoted to PlaybackCoordinator.")
        if action_key not in {"play", "pause"}:
            raise ValueError("AirPlay transport action must be play or pause.")

        target_state = "playing" if action_key == "play" else "paused"
        current = super().snapshot().get("sources", {}).get("airplay", {})
        live_remote = _safe_status(self._airplay_status, "AirPlay")
        if current.get("connected") is not True or live_remote.get("available") is not True:
            raise ValueError("AirPlay transport is available only while a sender is connected.")

        current_state = _text(current.get("state"), "unknown")
        command = self._new_command(source_key, action_key, target_state)
        if current_state == target_state:
            command = self._update_command(
                status="noop",
                accepted_at=self._timestamp(),
                completed_at=self._timestamp(),
                observed_state=current_state,
                observed_source="coordinator-state",
                noop=True,
            )
            return {"ok": True, "command": command, "playback": self.snapshot()}

        self._update_command(status="executing")
        ok, error = self._airplay_command(action_key)
        if not ok:
            command = self._update_command(
                status="failed",
                completed_at=self._timestamp(),
                last_error=error or f"AirPlay {action_key} command failed.",
            )
            raise RuntimeError(str(command.get("last_error")))

        self.record_event(
            "airplay",
            target_state,
            {
                "origin": "playback-coordinator-command",
                "command_sequence": command["sequence"],
                "action": action_key,
            },
        )
        self._update_command(
            status="accepted-awaiting-observation",
            accepted_at=self._timestamp(),
            last_error=None,
        )
        self._reconcile_transport_command()
        return {"ok": True, "command": self.command_snapshot(), "playback": self.snapshot()}

    def reconcile_once(self) -> str:
        command_result = self._reconcile_transport_command()
        hold_result = super().reconcile_once()
        return hold_result if hold_result != "idle" else command_result

    def snapshot(self) -> dict[str, Any]:
        self._reconcile_transport_command()
        payload = super().snapshot()
        self._heal_stale_observed_pause(payload)
        payload["authority"] = self.authority
        payload["commands_enabled"] = True
        capabilities = payload.setdefault("command_capabilities", {})
        capabilities.update(
            {
                "source_control": True,
                "airplay_transport": True,
                "airplay_actions": ["play", "pause"],
                "plexamp_transport": False,
                "automatic_arbitration": False,
                "service_restarts": False,
            }
        )
        payload["commands"] = {"airplay": self.command_snapshot()}
        return payload


def promote_playback_transport(hub: Any, dashboard: Any) -> TransportPlaybackCoordinator:
    """Replace the observational coordinator with an explicit AirPlay transport owner."""
    existing = hub.service("playback")
    if isinstance(existing, TransportPlaybackCoordinator):
        return existing
    if not isinstance(existing, PlaybackCoordinator):
        raise RuntimeError("PlaybackCoordinator is unavailable for transport promotion.")

    methods = {"play": "Play", "pause": "Pause"}

    def airplay_command(action: str) -> tuple[bool, str | None]:
        method = methods.get(action)
        if method is None:
            return False, f"Unsupported AirPlay transport action: {action}"
        return dashboard.mpris_call(method)

    promoted = TransportPlaybackCoordinator(
        load_config=existing._load_config,
        load_state=existing._load_state,
        plexamp_status=existing._plexamp_status,
        airplay_status=existing._airplay_status,
        alarm_status=existing._alarm_status,
        alarm_audio_status=existing._alarm_audio_status,
        event_journal=existing._events,
        runtime_path=existing._runtime_store.path,
        airplay_hold_seconds=existing._airplay_hold_seconds,
        reconcile_seconds=existing._reconcile_seconds,
        hold_completion=existing._hold_completion,
        now_provider=existing._now,
        airplay_command=airplay_command,
    )
    hub.register_service("playback", promoted)
    hub.register_provider("playback", promoted.snapshot)
    return promoted


def register_playback_command_api(app: Any, hub: Any) -> None:
    coordinator = hub.service("playback")
    if "api_playback_command" in app.view_functions:
        return

    @app.route("/api/playback/command", methods=["POST"])
    def api_playback_command():
        if not isinstance(coordinator, TransportPlaybackCoordinator):
            return jsonify({"ok": False, "error": "AirPlay transport coordinator is unavailable."}), 503
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "Playback command must be a JSON object."}), 400
        try:
            result = coordinator.command(payload.get("source"), payload.get("action"))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc), "playback": coordinator.snapshot()}), 409
        except RuntimeError as exc:
            return jsonify({"ok": False, "error": str(exc), "playback": coordinator.snapshot()}), 502
        return jsonify(result)
