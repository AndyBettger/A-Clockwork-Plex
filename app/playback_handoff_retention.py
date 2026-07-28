from __future__ import annotations

from datetime import timedelta

try:
    from .playback_coordinator import _parse_time, _safe_status
    from .playback_handoff import BidirectionalHandoffPlaybackCoordinator
except ImportError:  # Supports direct execution imports.
    from playback_coordinator import _parse_time, _safe_status
    from playback_handoff import BidirectionalHandoffPlaybackCoordinator


class RetainedBidirectionalHandoffCoordinator(BidirectionalHandoffPlaybackCoordinator):
    """Keep a ceded AirPlay sender resumable without letting it own Plexamp audio."""

    authority = "playback-handoff-owner"

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
        parent_result = super().reconcile_once()
        ceded_result = self._reconcile_ceded_session()
        if parent_result not in {"idle", "primed"}:
            return parent_result
        return ceded_result
