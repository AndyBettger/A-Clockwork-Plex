from __future__ import annotations

import threading
from copy import deepcopy
from typing import Any

try:
    from .playback_coordinator import _dict, _parse_time, _text
    from .playback_handoff_retention import RetainedBidirectionalHandoffCoordinator
except ImportError:  # Supports direct execution imports.
    from playback_coordinator import _dict, _parse_time, _text
    from playback_handoff_retention import RetainedBidirectionalHandoffCoordinator


class MetadataResumeRetainedCoordinator(RetainedBidirectionalHandoffCoordinator):
    """Use Shairport's metadata resume event as authoritative user intent.

    Shairport's MPRIS PlaybackStatus can remain ``Playing`` across a remote Pause
    command, and its Position property is not implemented on every build.  The
    metadata FIFO, however, emits ``prsm``/``pres``/``pbeg`` when the sender
    resumes.  The existing metadata listener stores those as ``play_resume``,
    ``resume`` and ``play_start`` in ``state.json``.
    """

    RESUME_METADATA_EVENTS = {"play_resume", "resume", "play_start"}

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._metadata_resume_lock = threading.RLock()
        self._metadata_resume_runtime: dict[str, Any] = {
            "takeover_requested_at": None,
            "baseline_token": None,
            "last_token": None,
            "last_event": None,
            "last_updated_at": None,
            "last_evidence": None,
            "resume_count": 0,
            "last_resume_at": None,
        }

    def metadata_resume_snapshot(self) -> dict[str, Any]:
        with self._metadata_resume_lock:
            return deepcopy(self._metadata_resume_runtime)

    def _reset_metadata_probe(self) -> None:
        with self._metadata_resume_lock:
            self._metadata_resume_runtime.update(
                {
                    "takeover_requested_at": None,
                    "baseline_token": None,
                    "last_token": None,
                    "last_event": None,
                    "last_updated_at": None,
                }
            )

    def _metadata_resume_evidence(self) -> str | None:
        runtime = self._runtime_airplay()
        if runtime.get("phase") != self.CEDED_PHASE:
            self._reset_metadata_probe()
            return None

        handoff = self.reverse_handoff_snapshot()
        requested_text = str(handoff.get("requested_at") or runtime.get("updated_at") or "")
        requested_at = _parse_time(requested_text)

        config = self._load_config()
        stored = self._load_state(config)
        stored_airplay = _dict(stored.get("airplay"))
        metadata = _dict(stored_airplay.get("metadata"))
        event = _text(metadata.get("last_event"), "")
        updated_text = str(metadata.get("updated_at") or "")
        updated_at = _parse_time(updated_text)
        token = f"{event}:{updated_text}"

        with self._metadata_resume_lock:
            probe = self._metadata_resume_runtime
            new_takeover = probe.get("takeover_requested_at") != requested_text
            if new_takeover:
                probe.update(
                    {
                        "takeover_requested_at": requested_text,
                        "baseline_token": token,
                        "last_token": token,
                        "last_event": event or None,
                        "last_updated_at": updated_text or None,
                    }
                )

                # The first coordinator sample can occur after an extremely fast
                # iPhone resume.  Metadata timestamps have one-second precision,
                # so compare against the takeover rounded down to that precision.
                if (
                    event in self.RESUME_METADATA_EVENTS
                    and requested_at is not None
                    and updated_at is not None
                    and updated_at >= requested_at.replace(microsecond=0)
                ):
                    return f"metadata-{event}"
                return None

            previous_token = str(probe.get("last_token") or "")
            probe.update(
                {
                    "last_token": token,
                    "last_event": event or None,
                    "last_updated_at": updated_text or None,
                }
            )

        if event in self.RESUME_METADATA_EVENTS and token != previous_token:
            return f"metadata-{event}"
        return None

    def _accept_metadata_resume(self, evidence: str) -> str:
        # AirPlay was latched during the original episode.  A FIFO resume event is
        # a new sender action and must be allowed to start a fresh takeover episode.
        with self._handoff_lock:
            self._airplay_playing_latched = False

        self._record_event(
            "airplay",
            "playing",
            {
                "origin": "shairport-metadata-resume",
                "evidence": evidence,
                "takeover_requested_at": self.reverse_handoff_snapshot().get("requested_at"),
            },
            kind="coordinator",
        )
        self._update_reverse_handoff(
            status="superseded-by-airplay-resume",
            completed_at=self._timestamp(),
            airplay_after="playing",
            last_error=None,
        )
        with self._ceded_resume_lock:
            self._ceded_resume_runtime.update(
                {
                    "status": "resumed",
                    "resume_count": int(self._ceded_resume_runtime.get("resume_count") or 0) + 1,
                    "last_resume_at": self._timestamp(),
                    "last_evidence": evidence,
                    "progress_samples": 0,
                }
            )
        with self._metadata_resume_lock:
            self._metadata_resume_runtime.update(
                {
                    "last_evidence": evidence,
                    "resume_count": int(self._metadata_resume_runtime.get("resume_count") or 0) + 1,
                    "last_resume_at": self._timestamp(),
                }
            )
        return "airplay-resumed"

    def _reconcile_ceded_resume(self) -> str:
        evidence = self._metadata_resume_evidence()
        if evidence is not None:
            return self._accept_metadata_resume(evidence)
        return super()._reconcile_ceded_resume()

    def snapshot(self) -> dict[str, Any]:
        payload = super().snapshot()
        handoffs = payload.setdefault("handoffs", {})
        handoffs["metadata_airplay_resume"] = self.metadata_resume_snapshot()
        capabilities = payload.setdefault("command_capabilities", {})
        capabilities["metadata_airplay_resume"] = True
        return payload
