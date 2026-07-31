from __future__ import annotations

import threading
from copy import deepcopy
from datetime import timedelta
from typing import Any

try:
    from .playback_coordinator import PlaybackCoordinator, _parse_time, _safe_status, _text
    from .playback_handoff import BidirectionalHandoffPlaybackCoordinator
except ImportError:  # Supports direct execution imports.
    from playback_coordinator import PlaybackCoordinator, _parse_time, _safe_status, _text
    from playback_handoff import BidirectionalHandoffPlaybackCoordinator


class RetainedBidirectionalHandoffCoordinator(BidirectionalHandoffPlaybackCoordinator):
    """Keep a ceded AirPlay sender resumable without letting it own Plexamp audio."""

    authority = "playback-handoff-owner"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._alarm_takeover_lock = threading.RLock()
        self._alarm_plexamp_playing_latched = False
        self._alarm_airplay_playing_latched = False
        self._alarm_takeover_sequence = 0
        self._alarm_takeover_runtime: dict[str, Any] = {
            "sequence": 0,
            "status": "idle",
            "active": False,
            "occurrence_key": None,
            "started_at": None,
            "completed_at": None,
            "plexamp_pause_count": 0,
            "airplay_pause_count": 0,
            "resume_policy": "manual",
            "last_action": None,
            "last_error": None,
        }

    def alarm_takeover_snapshot(self) -> dict[str, Any]:
        with self._alarm_takeover_lock:
            return deepcopy(self._alarm_takeover_runtime)

    def _update_alarm_takeover(self, **updates: Any) -> dict[str, Any]:
        with self._alarm_takeover_lock:
            self._alarm_takeover_runtime.update(updates)
            return deepcopy(self._alarm_takeover_runtime)

    def _scheduled_alarm_priority(self) -> tuple[bool, str | None]:
        scheduler = _safe_status(self._alarm_status, "Alarm scheduler")
        audio = _safe_status(self._alarm_audio_status, "Alarm audio")
        active = (
            scheduler.get("active_occurrence")
            if isinstance(scheduler.get("active_occurrence"), dict)
            else None
        )
        real_ringing = bool(
            active
            and _text(active.get("phase"), "idle") == "ringing"
            and not bool(active.get("test_mode"))
        )
        scheduled_sound_enabled = audio.get("scheduled_playback_enabled") is True
        occurrence_key = str(active.get("occurrence_key") or "") if active else ""
        return real_ringing and scheduled_sound_enabled, occurrence_key or None

    def _reconcile_alarm_takeover(self, playback: dict[str, Any]) -> str:
        alarm_active, occurrence_key = self._scheduled_alarm_priority()
        sources = playback.get("sources") if isinstance(playback.get("sources"), dict) else {}
        plexamp = sources.get("plexamp") if isinstance(sources.get("plexamp"), dict) else {}
        airplay = sources.get("airplay") if isinstance(sources.get("airplay"), dict) else {}
        plexamp_raw = _safe_status(self._plexamp_status, "Plexamp")
        airplay_raw = _safe_status(self._airplay_status, "AirPlay")
        plexamp_state = _text(
            plexamp_raw.get("playback_state") or plexamp.get("state"),
            "unknown",
        )
        airplay_state = _text(
            airplay_raw.get("playback_status")
            or airplay_raw.get("raw_playback_status")
            or airplay.get("state"),
            "unknown",
        )
        plexamp_playing = plexamp_state == "playing"
        airplay_playing = airplay_raw.get("available") is not False and airplay_state == "playing"

        with self._alarm_takeover_lock:
            was_active = bool(self._alarm_takeover_runtime.get("active"))
            if not alarm_active:
                self._alarm_plexamp_playing_latched = False
                self._alarm_airplay_playing_latched = False
                if was_active:
                    self._alarm_takeover_runtime.update(
                        {
                            "status": "released",
                            "active": False,
                            "completed_at": self._timestamp(),
                            "last_action": "alarm-priority-released",
                        }
                    )
                    return "alarm-released"
                self._alarm_takeover_runtime.update(
                    {
                        "status": "idle",
                        "active": False,
                        "occurrence_key": None,
                        "started_at": None,
                        "completed_at": None,
                        "last_action": None,
                        "last_error": None,
                    }
                )
                return "idle"

            if not was_active or self._alarm_takeover_runtime.get("occurrence_key") != occurrence_key:
                self._alarm_takeover_sequence += 1
                self._alarm_takeover_runtime = {
                    "sequence": self._alarm_takeover_sequence,
                    "status": "claiming-priority",
                    "active": True,
                    "occurrence_key": occurrence_key,
                    "started_at": self._timestamp(),
                    "completed_at": None,
                    "plexamp_pause_count": 0,
                    "airplay_pause_count": 0,
                    "resume_policy": "manual",
                    "last_action": "alarm-priority-started",
                    "last_error": None,
                }
                self._alarm_plexamp_playing_latched = False
                self._alarm_airplay_playing_latched = False

            if not plexamp_playing:
                self._alarm_plexamp_playing_latched = False
            if not airplay_playing:
                self._alarm_airplay_playing_latched = False

            pause_plexamp = plexamp_playing and not self._alarm_plexamp_playing_latched
            pause_airplay = airplay_playing and not self._alarm_airplay_playing_latched
            if pause_plexamp:
                self._alarm_plexamp_playing_latched = True
            if pause_airplay:
                self._alarm_airplay_playing_latched = True

        actions: list[str] = []
        errors: list[str] = []

        if pause_plexamp:
            ok, error = self._plexamp_pause()
            if ok:
                with self._alarm_takeover_lock:
                    self._alarm_takeover_runtime["plexamp_pause_count"] = int(
                        self._alarm_takeover_runtime.get("plexamp_pause_count") or 0
                    ) + 1
                actions.append("paused-plexamp")
            else:
                errors.append(error or "Plexamp Pause command failed during alarm takeover.")

        if pause_airplay:
            ok, error = self._airplay_command("pause")
            if ok:
                with self._alarm_takeover_lock:
                    self._alarm_takeover_runtime["airplay_pause_count"] = int(
                        self._alarm_takeover_runtime.get("airplay_pause_count") or 0
                    ) + 1
                    sequence = int(self._alarm_takeover_runtime.get("sequence") or 0)
                self._record_event(
                    "airplay",
                    "paused",
                    {
                        "origin": "alarm-takeover",
                        "alarm_takeover_sequence": sequence,
                        "occurrence_key": occurrence_key,
                    },
                    kind="coordinator",
                )
                actions.append("paused-airplay")
            else:
                errors.append(error or "AirPlay Pause command failed during alarm takeover.")

        existing_error = self.alarm_takeover_snapshot().get("last_error")
        status = "holding-priority"
        if actions:
            status = "paused-sources"
        if errors:
            status = "partial-failure" if actions else "failed"
        elif not actions and existing_error:
            status = "failed"

        self._update_alarm_takeover(
            status=status,
            active=True,
            occurrence_key=occurrence_key,
            completed_at=None,
            last_action="+".join(actions) if actions else "alarm-priority-held",
            last_error=(
                "; ".join(errors)
                if errors
                else None if actions else existing_error
            ),
        )
        if errors:
            return "alarm-pause-failed"
        if actions:
            return "alarm-" + "+".join(actions)
        return "alarm-active"

    def _cede_airplay_to_plexamp(self, *, reason: str) -> None:
        runtime = self._runtime_airplay()
        hold_started_at = runtime.get("hold_started_at")
        hold_until = runtime.get("hold_until")
        parsed_until = _parse_time(hold_until)

        # Preserve an existing user-pause deadline. A takeover during a 600-second
        # hold must not restart the clock merely because Plexamp began playing.
        if runtime.get("phase") not in {"holding", "action_failed", self.CEDED_PHASE} or parsed_until is None:
            now = self._now()
            hold_started_at = now.isoformat(timespec="milliseconds")
            hold_until = (now + timedelta(seconds=self._airplay_hold_seconds)).isoformat(timespec="milliseconds")

        self._save_airplay_runtime(
            phase=self.CEDED_PHASE,
            hold_started_at=hold_started_at,
            hold_until=hold_until,
            reason=reason,
        )

    def _apply_airplay_runtime_event(self, event: str, *, reason: str) -> None:
        runtime = self._runtime_airplay()
        if event == "paused" and (reason == "plexamp-takeover" or runtime.get("phase") == self.CEDED_PHASE):
            self._cede_airplay_to_plexamp(reason=reason)
            return
        super()._apply_airplay_runtime_event(event, reason=reason)

    def _reconcile_ceded_session(self) -> str:
        runtime = self._runtime_airplay()
        if runtime.get("phase") != self.CEDED_PHASE:
            return "idle"

        remote = _safe_status(self._airplay_status, "AirPlay")
        if remote.get("available") is False:
            self._record_event(
                "airplay",
                "disconnected",
                {"origin": "coordinator-ceded-monitor"},
                kind="coordinator",
            )
            self._finish_airplay_session(
                "sender-disconnected-after-plexamp-takeover",
                success_phase="disconnected",
            )
            return "disconnected"

        hold_until = _parse_time(runtime.get("hold_until"))
        if hold_until is not None and self._now() >= hold_until:
            self._record_event(
                "airplay",
                "hold_expired",
                {
                    "origin": "playback-coordinator-ceded",
                    "hold_seconds": self._airplay_hold_seconds,
                },
                kind="coordinator",
            )
            self._finish_airplay_session(
                "ceded-session-expired",
                success_phase="expired",
            )
            return "expired"

        return "ceded"

    def reconcile_once(self) -> str:
        # Alarm priority is evaluated before ordinary music-source handoff so an
        # alarm cannot be mistaken for a new Plexamp/AirPlay ownership episode.
        playback = PlaybackCoordinator.snapshot(self)
        alarm_result = self._reconcile_alarm_takeover(playback)
        if self.alarm_takeover_snapshot().get("active") is True:
            return alarm_result

        parent_result = super().reconcile_once()
        ceded_result = self._reconcile_ceded_session()
        for result in (alarm_result, parent_result, ceded_result):
            if result not in {"idle", "primed"}:
                return result
        return "idle"

    @staticmethod
    def _latest_playing_token(snapshot: dict[str, Any], source: str) -> str | None:
        events = snapshot.get("events") if isinstance(snapshot.get("events"), dict) else {}
        recent = events.get("recent_events") if isinstance(events.get("recent_events"), list) else []
        for item in reversed(recent):
            if not isinstance(item, dict):
                continue
            if item.get("source") == source and item.get("event") == "playing":
                return f"{source}-playing:{item.get('sequence')}"
        return None

    def snapshot(self) -> dict[str, Any]:
        snapshot = super().snapshot()
        sources = snapshot.get("sources") if isinstance(snapshot.get("sources"), dict) else {}
        plexamp = sources.get("plexamp") if isinstance(sources.get("plexamp"), dict) else {}
        airplay = sources.get("airplay") if isinstance(sources.get("airplay"), dict) else {}
        plexamp_observed = plexamp.get("observed") if isinstance(plexamp.get("observed"), dict) else {}

        plexamp_token = plexamp_observed.get("activity_token") or self._latest_playing_token(snapshot, "plexamp")
        airplay_token = self._latest_playing_token(snapshot, "airplay")
        if airplay_token is None and airplay.get("started_at"):
            airplay_token = f"airplay-session:{airplay.get('started_at')}"

        plexamp["activity_token"] = plexamp_token
        plexamp["media_token"] = plexamp_observed.get("media_token")
        airplay["activity_token"] = airplay_token
        snapshot["sources"] = sources

        active_source = str(snapshot.get("active_source") or "none")
        active = sources.get(active_source) if isinstance(sources.get(active_source), dict) else {}
        snapshot["playback_activity"] = {
            "source": active_source,
            "token": active.get("activity_token") if isinstance(active, dict) else None,
        }
        capabilities = snapshot.setdefault("command_capabilities", {})
        capabilities["alarm_audio_takeover"] = True
        handoffs = snapshot.setdefault("handoffs", {})
        handoffs["alarm_takeover"] = self.alarm_takeover_snapshot()
        return snapshot
