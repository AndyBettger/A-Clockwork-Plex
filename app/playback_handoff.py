from __future__ import annotations

import threading
import urllib.error
import urllib.request
from copy import deepcopy
from typing import Any, Callable

try:
    from .playback_coordinator import _parse_time, _safe_status, _text
    from .playback_navigation import NavigationTransportPlaybackCoordinator
except ImportError:  # Supports direct execution imports.
    from playback_coordinator import _parse_time, _safe_status, _text
    from playback_navigation import NavigationTransportPlaybackCoordinator


PlexampPause = Callable[[], tuple[bool, str | None]]


class AirPlayTakeoverPlaybackCoordinator(NavigationTransportPlaybackCoordinator):
    """Own the one-way AirPlay-start takeover of an already-playing Plexamp."""

    authority = "airplay-takeover-owner"

    def __init__(self, *, plexamp_pause: PlexampPause, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._plexamp_pause = plexamp_pause
        self._handoff_lock = threading.RLock()
        self._airplay_playing_latched = False
        self._handoff_sequence = 0
        self._handoff_runtime: dict[str, Any] = {
            "sequence": 0,
            "direction": "airplay-to-plexamp",
            "status": "idle",
            "trigger": None,
            "requested_at": None,
            "accepted_at": None,
            "completed_at": None,
            "plexamp_before": None,
            "plexamp_after": None,
            "command_count": 0,
            "completion_policy": "plexamp-observation",
            "screen_policy": "preserve-open-plexamp-surface",
            "last_error": None,
        }

    def handoff_snapshot(self) -> dict[str, Any]:
        with self._handoff_lock:
            return deepcopy(self._handoff_runtime)

    def _update_handoff(self, **updates: Any) -> dict[str, Any]:
        with self._handoff_lock:
            self._handoff_runtime.update(updates)
            return deepcopy(self._handoff_runtime)

    def _start_handoff(self, *, trigger: str, plexamp_state: str) -> dict[str, Any]:
        with self._handoff_lock:
            self._handoff_sequence += 1
            command_count = int(self._handoff_runtime.get("command_count") or 0)
            self._handoff_runtime = {
                "sequence": self._handoff_sequence,
                "direction": "airplay-to-plexamp",
                "status": "requested",
                "trigger": trigger,
                "requested_at": self._timestamp(),
                "accepted_at": None,
                "completed_at": None,
                "plexamp_before": plexamp_state,
                "plexamp_after": None,
                "command_count": command_count,
                "completion_policy": "plexamp-observation",
                "screen_policy": "preserve-open-plexamp-surface",
                "last_error": None,
            }
            return deepcopy(self._handoff_runtime)

    def _reconcile_airplay_takeover(self, playback: dict[str, Any] | None = None) -> str:
        state = playback if isinstance(playback, dict) else super().snapshot()
        sources = state.get("sources") if isinstance(state.get("sources"), dict) else {}
        airplay = sources.get("airplay") if isinstance(sources.get("airplay"), dict) else {}
        plexamp = sources.get("plexamp") if isinstance(sources.get("plexamp"), dict) else {}
        airplay_playing = airplay.get("connected") is True and _text(airplay.get("state"), "unknown") == "playing"
        plexamp_state = _text(plexamp.get("state"), "unknown")

        with self._handoff_lock:
            if not airplay_playing:
                self._airplay_playing_latched = False
                return "idle"

            if self._airplay_playing_latched:
                if self._handoff_runtime.get("status") == "accepted-awaiting-observation" and plexamp_state != "playing":
                    self._handoff_runtime.update(
                        {
                            "status": "confirmed",
                            "completed_at": self._timestamp(),
                            "plexamp_after": plexamp_state,
                            "last_error": None,
                        }
                    )
                    return "confirmed"
                return "waiting" if self._handoff_runtime.get("status") == "accepted-awaiting-observation" else "idle"

            self._airplay_playing_latched = True

        trigger = str(airplay.get("state_source") or "coordinator-playing-observation")
        self._start_handoff(trigger=trigger, plexamp_state=plexamp_state)

        if plexamp_state != "playing":
            self._update_handoff(
                status="not-needed",
                completed_at=self._timestamp(),
                plexamp_after=plexamp_state,
                last_error=None,
            )
            return "not-needed"

        self._update_handoff(status="executing")
        ok, error = self._plexamp_pause()
        if not ok:
            self._update_handoff(
                status="failed",
                completed_at=self._timestamp(),
                plexamp_after=plexamp_state,
                last_error=error or "Plexamp pause command failed.",
            )
            return "failed"

        with self._handoff_lock:
            self._handoff_runtime["command_count"] = int(self._handoff_runtime.get("command_count") or 0) + 1

        after = _safe_status(self._plexamp_status, "Plexamp")
        after_state = _text(after.get("playback_state"), "unknown")
        confirmed = after_state != "playing"
        self._update_handoff(
            status="confirmed" if confirmed else "accepted-awaiting-observation",
            accepted_at=self._timestamp(),
            completed_at=self._timestamp() if confirmed else None,
            plexamp_after=after_state,
            last_error=None,
        )
        return "confirmed" if confirmed else "accepted"

    def record_event(self, source: str, event: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        item = super().record_event(source, event, details)
        if _text(source, "") == "airplay":
            self._reconcile_airplay_takeover(super().snapshot())
        return item

    def reconcile_once(self) -> str:
        parent_result = super().reconcile_once()
        handoff_result = self._reconcile_airplay_takeover(super().snapshot())
        return parent_result if parent_result != "idle" else handoff_result

    def snapshot(self) -> dict[str, Any]:
        payload = super().snapshot()
        self._reconcile_airplay_takeover(payload)
        payload["authority"] = self.authority
        capabilities = payload.setdefault("command_capabilities", {})
        capabilities.update(
            {
                "airplay_to_plexamp_handoff": True,
                "plexamp_to_airplay_handoff": False,
                "screen_projection": False,
                "preserve_open_plexamp_surface": True,
                "service_restarts": False,
            }
        )
        handoffs = payload.setdefault("handoffs", {})
        handoffs["airplay_to_plexamp"] = self.handoff_snapshot()
        return payload


class BidirectionalHandoffPlaybackCoordinator(AirPlayTakeoverPlaybackCoordinator):
    """Own both playback handoff directions without assigning transport intent to the UI."""

    authority = "playback-handoff-owner"
    CEDED_PHASE = "ceded-to-plexamp"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._reverse_handoff_lock = threading.RLock()
        self._last_plexamp_state: str | None = None
        self._reverse_handoff_sequence = 0
        self._reverse_handoff_runtime: dict[str, Any] = {
            "sequence": 0,
            "direction": "plexamp-to-airplay",
            "status": "idle",
            "trigger": None,
            "requested_at": None,
            "accepted_at": None,
            "completed_at": None,
            "airplay_before": None,
            "airplay_after": None,
            "command_count": 0,
            "completion_policy": "airplay-observation",
            "ownership_policy": "pause-and-cede-to-plexamp",
            "screen_policy": "keep-plexamp-surface",
            "last_error": None,
        }

    def reverse_handoff_snapshot(self) -> dict[str, Any]:
        with self._reverse_handoff_lock:
            return deepcopy(self._reverse_handoff_runtime)

    def _update_reverse_handoff(self, **updates: Any) -> dict[str, Any]:
        with self._reverse_handoff_lock:
            self._reverse_handoff_runtime.update(updates)
            return deepcopy(self._reverse_handoff_runtime)

    def _start_reverse_handoff(self, *, trigger: str, airplay_state: str) -> dict[str, Any]:
        with self._reverse_handoff_lock:
            self._reverse_handoff_sequence += 1
            command_count = int(self._reverse_handoff_runtime.get("command_count") or 0)
            self._reverse_handoff_runtime = {
                "sequence": self._reverse_handoff_sequence,
                "direction": "plexamp-to-airplay",
                "status": "requested",
                "trigger": trigger,
                "requested_at": self._timestamp(),
                "accepted_at": None,
                "completed_at": None,
                "airplay_before": airplay_state,
                "airplay_after": None,
                "command_count": command_count,
                "completion_policy": "airplay-observation",
                "ownership_policy": "pause-and-cede-to-plexamp",
                "screen_policy": "keep-plexamp-surface",
                "last_error": None,
            }
            return deepcopy(self._reverse_handoff_runtime)

    def _apply_airplay_runtime_event(self, event: str, *, reason: str) -> None:
        runtime = self._runtime_airplay()
        if event == "paused" and (reason == "plexamp-takeover" or runtime.get("phase") == self.CEDED_PHASE):
            self._save_airplay_runtime(
                phase=self.CEDED_PHASE,
                hold_started_at=None,
                hold_until=None,
                reason=reason,
            )
            return
        super()._apply_airplay_runtime_event(event, reason=reason)

    def _cede_airplay_to_plexamp(self, *, reason: str) -> None:
        self._save_airplay_runtime(
            phase=self.CEDED_PHASE,
            hold_started_at=None,
            hold_until=None,
            reason=reason,
        )

    def _matching_external_pause(self, requested_at: Any) -> str | None:
        parsed_request = _parse_time(requested_at)
        if parsed_request is None:
            return None
        events = self._events.snapshot().get("recent_events") or []
        for event in reversed(events):
            if event.get("source") != "airplay" or event.get("event") != "paused":
                continue
            if event.get("kind") != "explicit":
                continue
            occurred_at = _parse_time(event.get("at"))
            if occurred_at is None or occurred_at < parsed_request:
                continue
            details = event.get("details") if isinstance(event.get("details"), dict) else {}
            origin = str(details.get("origin") or "explicit-airplay-pause")
            if origin == "plexamp-takeover":
                continue
            return origin
        return None

    def _reconcile_reverse_confirmation(self, playback: dict[str, Any]) -> str:
        handoff = self.reverse_handoff_snapshot()
        if handoff.get("status") != "accepted-awaiting-observation":
            return "idle"

        sources = playback.get("sources") if isinstance(playback.get("sources"), dict) else {}
        airplay = sources.get("airplay") if isinstance(sources.get("airplay"), dict) else {}
        observed = airplay.get("observed") if isinstance(airplay.get("observed"), dict) else {}
        raw_state = _text(observed.get("raw_playback_status"), "unknown")
        external_source = self._matching_external_pause(handoff.get("requested_at"))

        if airplay.get("connected") is not True:
            self._update_reverse_handoff(
                status="confirmed",
                completed_at=self._timestamp(),
                airplay_after="disconnected",
                last_error=None,
            )
            return "confirmed"

        if raw_state in {"paused", "stopped"} or external_source is not None:
            self._update_reverse_handoff(
                status="confirmed",
                completed_at=self._timestamp(),
                airplay_after="paused" if raw_state == "unknown" else raw_state,
                last_error=None,
            )
            return "confirmed"

        requested_at = _parse_time(handoff.get("requested_at"))
        if requested_at is not None and (self._now() - requested_at).total_seconds() >= self._command_verify_seconds:
            self._update_reverse_handoff(
                status="accepted-unconfirmed",
                completed_at=self._timestamp(),
                airplay_after=raw_state,
                last_error="AirPlay accepted Pause, but no independent paused observation arrived.",
            )
            return "unconfirmed"

        self._update_reverse_handoff(airplay_after=raw_state)
        return "waiting"

    def _reconcile_plexamp_takeover(self, playback: dict[str, Any]) -> str:
        sources = playback.get("sources") if isinstance(playback.get("sources"), dict) else {}
        plexamp = sources.get("plexamp") if isinstance(sources.get("plexamp"), dict) else {}
        airplay = sources.get("airplay") if isinstance(sources.get("airplay"), dict) else {}
        plexamp_state = _text(plexamp.get("state"), "unknown")

        with self._reverse_handoff_lock:
            previous = self._last_plexamp_state
            self._last_plexamp_state = plexamp_state

        if previous is None:
            return "primed"
        if previous not in {"paused", "stopped"} or plexamp_state != "playing":
            return "idle"
        if airplay.get("connected") is not True:
            return "idle"

        airplay_state = _text(airplay.get("state"), "unknown")
        trigger = f"plexamp-{previous}-to-playing"
        self._start_reverse_handoff(trigger=trigger, airplay_state=airplay_state)

        if airplay_state != "playing":
            self._cede_airplay_to_plexamp(reason="plexamp-takeover-already-quiet")
            self._update_reverse_handoff(
                status="not-needed",
                completed_at=self._timestamp(),
                airplay_after=airplay_state,
                last_error=None,
            )
            return "not-needed"

        self._update_reverse_handoff(status="executing")
        ok, error = self._airplay_command("pause")
        if not ok:
            self._update_reverse_handoff(
                status="failed",
                completed_at=self._timestamp(),
                airplay_after=airplay_state,
                last_error=error or "AirPlay Pause command failed during Plexamp takeover.",
            )
            return "failed"

        with self._reverse_handoff_lock:
            self._reverse_handoff_runtime["command_count"] = int(
                self._reverse_handoff_runtime.get("command_count") or 0
            ) + 1

        self._record_event(
            "airplay",
            "paused",
            {
                "origin": "plexamp-takeover",
                "handoff_sequence": self._reverse_handoff_sequence,
            },
            kind="coordinator",
        )
        self._update_reverse_handoff(
            status="accepted-awaiting-observation",
            accepted_at=self._timestamp(),
            airplay_after="playing",
            last_error=None,
        )
        return "accepted"

    def _project_ceded_state(self, payload: dict[str, Any]) -> None:
        if self._runtime_airplay().get("phase") != self.CEDED_PHASE:
            return

        sources = payload.get("sources") if isinstance(payload.get("sources"), dict) else {}
        airplay = sources.get("airplay") if isinstance(sources.get("airplay"), dict) else {}
        plexamp = sources.get("plexamp") if isinstance(sources.get("plexamp"), dict) else {}
        alarm = sources.get("alarm") if isinstance(sources.get("alarm"), dict) else {}
        airplay["ownership"] = "ceded-to-plexamp"

        if alarm.get("active") is True:
            return

        if _text(plexamp.get("state"), "unknown") == "playing":
            payload["active_source"] = "plexamp"
            payload["decision_reason"] = "plexamp-takeover"
        else:
            payload["active_source"] = "none"
            payload["decision_reason"] = "airplay-session-ceded"

        payload["recommended_screen"] = "plexamp"
        payload["screen_in_sync"] = payload.get("current_screen") == "plexamp"

    def record_event(self, source: str, event: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        item = super().record_event(source, event, details)
        return item

    def reconcile_once(self) -> str:
        parent_result = super().reconcile_once()
        payload = super().snapshot()
        reverse_result = self._reconcile_plexamp_takeover(payload)
        if reverse_result in {"accepted", "not-needed"}:
            payload = super().snapshot()
        confirmation_result = self._reconcile_reverse_confirmation(payload)
        for result in (parent_result, reverse_result, confirmation_result):
            if result not in {"idle", "primed"}:
                return result
        return "idle"

    def snapshot(self) -> dict[str, Any]:
        payload = super().snapshot()
        reverse_result = self._reconcile_plexamp_takeover(payload)
        if reverse_result in {"accepted", "not-needed"}:
            payload = super().snapshot()
        self._reconcile_reverse_confirmation(payload)
        self._project_ceded_state(payload)
        payload["authority"] = self.authority
        capabilities = payload.setdefault("command_capabilities", {})
        capabilities.update(
            {
                "airplay_to_plexamp_handoff": True,
                "plexamp_to_airplay_handoff": True,
                "automatic_arbitration": True,
                "screen_projection": False,
                "preserve_open_plexamp_surface": True,
                "airplay_ceded_to_plexamp": self._runtime_airplay().get("phase") == self.CEDED_PHASE,
                "service_restarts": False,
            }
        )
        policy = payload.setdefault("policy", {})
        policy["handoff_priority"] = ["alarm", "newest-playing-source", "manual-screen-lease", "idle"]
        handoffs = payload.setdefault("handoffs", {})
        handoffs["plexamp_to_airplay"] = self.reverse_handoff_snapshot()
        return payload


def _install_screen_preserving_airplay_start(app: Any, dashboard: Any) -> None:
    """Keep an explicitly open Plexamp surface visible when AirPlay starts."""

    current = app.view_functions.get("api_airplay_start")
    if current is None or getattr(current, "_acp_preserves_plexamp_screen", False):
        return

    def airplay_start_preserving_plexamp(*args: Any, **kwargs: Any):
        before = dashboard.load_state(dashboard.load_config())
        preserve_plexamp = _text(before.get("mode"), "clock") == "plexamp"
        response = current(*args, **kwargs)
        if preserve_plexamp:
            dashboard.set_mode("plexamp")
        return response

    airplay_start_preserving_plexamp._acp_preserves_plexamp_screen = True  # type: ignore[attr-defined]
    app.view_functions["api_airplay_start"] = airplay_start_preserving_plexamp


def _remove_page_open_handoff(app: Any, dashboard: Any) -> None:
    """Opening Plexamp is screen intent only and must not arm source arbitration."""

    current = app.view_functions.get("plexamp")
    original = getattr(dashboard, "plexamp", None)
    if current is not None and getattr(current, "_acp_airplay_handoff_wrapped", False) and callable(original):
        app.view_functions["plexamp"] = original


def promote_airplay_takeover(hub: Any, dashboard: Any) -> AirPlayTakeoverPlaybackCoordinator:
    """Promote coordinator-owned AirPlay→Plexamp pause and retire page-open intent."""

    existing = hub.service("playback")
    if isinstance(existing, AirPlayTakeoverPlaybackCoordinator):
        return existing
    if not isinstance(existing, NavigationTransportPlaybackCoordinator):
        raise RuntimeError("AirPlay navigation coordinator is unavailable for handoff promotion.")

    def pause_plexamp() -> tuple[bool, str | None]:
        config = dashboard.load_config()
        plexamp = config.get("plexamp") if isinstance(config.get("plexamp"), dict) else {}
        base_url = str(plexamp.get("url", "http://localhost:32500")).rstrip("/")
        pause_url = str(plexamp.get("pause_url", f"{base_url}/player/playback/pause"))
        request_object = urllib.request.Request(pause_url, headers={"Accept": "*/*"})
        try:
            with urllib.request.urlopen(request_object, timeout=2.0) as response:
                response.read(1)
        except (OSError, TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            return False, str(exc)
        return True, None

    promoted = AirPlayTakeoverPlaybackCoordinator(
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
        airplay_command=existing._airplay_command,
        command_verify_seconds=existing._command_verify_seconds,
        plexamp_pause=pause_plexamp,
    )

    promoted._command_sequence = existing._command_sequence
    promoted._command_runtime = existing.command_snapshot()
    promoted._navigation_sequence = existing._navigation_sequence
    promoted._navigation_runtime = existing.navigation_snapshot()

    _remove_page_open_handoff(dashboard.app, dashboard)
    _install_screen_preserving_airplay_start(dashboard.app, dashboard)
    hub.register_service("playback", promoted)
    hub.register_provider("playback", promoted.snapshot)
    return promoted


def promote_bidirectional_handoff(hub: Any) -> BidirectionalHandoffPlaybackCoordinator:
    """Promote Plexamp-start takeover after the one-way AirPlay takeover is installed."""

    existing = hub.service("playback")
    if isinstance(existing, BidirectionalHandoffPlaybackCoordinator):
        return existing
    if not isinstance(existing, AirPlayTakeoverPlaybackCoordinator):
        raise RuntimeError("AirPlay takeover coordinator is unavailable for reverse handoff promotion.")

    promoted = BidirectionalHandoffPlaybackCoordinator(
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
        airplay_command=existing._airplay_command,
        command_verify_seconds=existing._command_verify_seconds,
        plexamp_pause=existing._plexamp_pause,
    )

    promoted._command_sequence = existing._command_sequence
    promoted._command_runtime = existing.command_snapshot()
    promoted._navigation_sequence = existing._navigation_sequence
    promoted._navigation_runtime = existing.navigation_snapshot()
    promoted._handoff_sequence = existing._handoff_sequence
    promoted._handoff_runtime = existing.handoff_snapshot()
    promoted._airplay_playing_latched = existing._airplay_playing_latched

    hub.register_service("playback", promoted)
    hub.register_provider("playback", promoted.snapshot)
    return promoted
