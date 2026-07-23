from __future__ import annotations

import json
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from .alarm_scheduler import (
        SilentAlarmScheduler,
        ensure_aware,
        parse_iso_datetime,
        timezone_name,
    )
except ImportError:  # Supports direct execution imports.
    from alarm_scheduler import (
        SilentAlarmScheduler,
        ensure_aware,
        parse_iso_datetime,
        timezone_name,
    )


class ActiveAlarmScheduler(SilentAlarmScheduler):
    """Interactive alarm runtime with persistent snooze/dismiss state.

    The scheduler may take over the touchscreen, but audio playback deliberately
    remains disabled until the following playback-ownership phase.
    """

    def __init__(
        self,
        config_loader: Callable[[], dict[str, Any]],
        runtime_path: Path,
        **kwargs: Any,
    ) -> None:
        super().__init__(config_loader, runtime_path, **kwargs)

    def _default_runtime_state(self) -> dict[str, Any]:
        state = super()._default_runtime_state()
        state.update(
            {
                "mode": "active-runtime",
                "ui_enabled": True,
                "playback_enabled": False,
                "screen_required": False,
                "active_occurrence": None,
                "snoozed_until": None,
                "queued_occurrences": [],
                "completed_occurrence_keys": [],
                "pending_test_occurrence": None,
                "last_action": None,
            }
        )
        return state

    def _load_runtime_state(self) -> dict[str, Any]:
        state = self._default_runtime_state()
        try:
            loaded = json.loads(self._runtime_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return state
        except (OSError, json.JSONDecodeError) as exc:
            state["last_error"] = f"Could not load alarm runtime state: {exc}"
            return state

        if isinstance(loaded, dict):
            state.update(loaded)

        for key in ("observed_occurrences", "queued_occurrences", "completed_occurrence_keys"):
            if not isinstance(state.get(key), list):
                state[key] = []

        if not isinstance(state.get("active_occurrence"), dict):
            state["active_occurrence"] = None
        if not isinstance(state.get("pending_test_occurrence"), dict):
            state["pending_test_occurrence"] = None

        state["mode"] = "active-runtime"
        state["ui_enabled"] = True
        state["playback_enabled"] = False
        state["timezone"] = timezone_name(self._timezone)
        state["poll_seconds"] = self._poll_seconds
        state["missed_alarm_grace_minutes"] = self._missed_grace_minutes
        state["screen_required"] = bool(
            isinstance(state.get("active_occurrence"), dict)
            and not state.get("snoozed_until")
        )
        return state

    def _update_observed_record_locked(self, occurrence_key: str, **changes: Any) -> None:
        records = self._state.get("observed_occurrences", [])
        for record in records:
            if isinstance(record, dict) and record.get("occurrence_key") == occurrence_key:
                record.update(changes)

    def _mark_completed_locked(self, occurrence_key: str) -> None:
        keys = [str(value) for value in self._state.get("completed_occurrence_keys", []) if value]
        if occurrence_key not in keys:
            keys.append(occurrence_key)
        self._state["completed_occurrence_keys"] = keys[-256:]

    def _occurrence_expired(self, occurrence: dict[str, Any], now: datetime) -> bool:
        scheduled = parse_iso_datetime(occurrence.get("scheduled_for"), self._timezone)
        if scheduled is None:
            return False
        try:
            expiry_minutes = max(15, int(occurrence.get("occurrence_expiry_minutes", 120)))
        except (TypeError, ValueError):
            expiry_minutes = 120
        return now >= scheduled + timedelta(minutes=expiry_minutes)

    def _activate_occurrence_locked(self, occurrence: dict[str, Any], now: datetime) -> None:
        active = deepcopy(occurrence)
        active.update(
            {
                "phase": "ringing",
                "activated_at": now.isoformat(timespec="seconds"),
                "ring_cycle_started_at": now.isoformat(timespec="seconds"),
                "snooze_count": int(active.get("snooze_count", 0) or 0),
                "playback_attempted": False,
            }
        )
        self._state["active_occurrence"] = active
        self._state["snoozed_until"] = None
        self._state["screen_required"] = True
        self._state["last_action"] = {
            "action": "activated",
            "at": now.isoformat(timespec="seconds"),
            "occurrence_key": active.get("occurrence_key"),
        }
        key = str(active.get("occurrence_key", ""))
        if key:
            self._update_observed_record_locked(
                key,
                status="active-screen",
                activated_at=active["activated_at"],
                playback_attempted=False,
            )
        print(
            "A Clockwork Plex scheduler: activating alarm screen for "
            f"{active.get('label', 'Alarm')} (audio remains disabled).",
            flush=True,
        )

    def _activate_next_queued_locked(self, now: datetime) -> bool:
        if isinstance(self._state.get("active_occurrence"), dict):
            return False

        queue = [item for item in self._state.get("queued_occurrences", []) if isinstance(item, dict)]
        completed = set(str(value) for value in self._state.get("completed_occurrence_keys", []) if value)
        changed = False

        while queue:
            occurrence = queue.pop(0)
            key = str(occurrence.get("occurrence_key", ""))
            if not key or key in completed:
                changed = True
                continue
            if self._occurrence_expired(occurrence, now):
                self._mark_completed_locked(key)
                self._update_observed_record_locked(
                    key,
                    status="expired-before-display",
                    expired_at=now.isoformat(timespec="seconds"),
                )
                changed = True
                continue
            self._state["queued_occurrences"] = queue
            self._activate_occurrence_locked(occurrence, now)
            return True

        self._state["queued_occurrences"] = queue
        return changed

    def _snooze_locked(self, now: datetime, *, automatic: bool) -> None:
        active = self._state.get("active_occurrence")
        if not isinstance(active, dict):
            raise ValueError("There is no active alarm to snooze.")

        try:
            snooze_minutes = max(1, min(60, int(active.get("snooze_minutes", 8))))
        except (TypeError, ValueError):
            snooze_minutes = 8

        snoozed_until = now + timedelta(minutes=snooze_minutes)
        active["phase"] = "snoozed"
        active["ring_cycle_started_at"] = None
        active["snooze_count"] = int(active.get("snooze_count", 0) or 0) + 1
        active["last_snoozed_at"] = now.isoformat(timespec="seconds")
        active["last_snooze_was_automatic"] = automatic
        self._state["active_occurrence"] = active
        self._state["snoozed_until"] = snoozed_until.isoformat(timespec="seconds")
        self._state["screen_required"] = False
        self._state["last_action"] = {
            "action": "auto-snoozed" if automatic else "snoozed",
            "at": now.isoformat(timespec="seconds"),
            "occurrence_key": active.get("occurrence_key"),
            "until": self._state["snoozed_until"],
        }
        key = str(active.get("occurrence_key", ""))
        if key:
            self._update_observed_record_locked(
                key,
                status="snoozed",
                snoozed_until=self._state["snoozed_until"],
                snooze_count=active["snooze_count"],
            )

    def _dismiss_locked(self, now: datetime, *, reason: str) -> dict[str, Any]:
        active = self._state.get("active_occurrence")
        if not isinstance(active, dict):
            raise ValueError("There is no active alarm to dismiss.")

        key = str(active.get("occurrence_key", ""))
        if key:
            self._mark_completed_locked(key)
            self._update_observed_record_locked(
                key,
                status=reason,
                dismissed_at=now.isoformat(timespec="seconds"),
                playback_attempted=False,
            )

        dismissed = deepcopy(active)
        self._state["active_occurrence"] = None
        self._state["snoozed_until"] = None
        self._state["screen_required"] = False
        self._state["last_action"] = {
            "action": reason,
            "at": now.isoformat(timespec="seconds"),
            "occurrence_key": key,
        }
        self._activate_next_queued_locked(now)
        return dismissed

    def _process_active_locked(self, now: datetime) -> bool:
        active = self._state.get("active_occurrence")
        if not isinstance(active, dict):
            self._state["screen_required"] = False
            return False

        if self._occurrence_expired(active, now):
            self._dismiss_locked(now, reason="expired")
            return True

        snoozed_until = parse_iso_datetime(self._state.get("snoozed_until"), self._timezone)
        if snoozed_until is not None:
            if now >= snoozed_until:
                active["phase"] = "ringing"
                active["ring_cycle_started_at"] = now.isoformat(timespec="seconds")
                active["resumed_at"] = now.isoformat(timespec="seconds")
                self._state["active_occurrence"] = active
                self._state["snoozed_until"] = None
                self._state["screen_required"] = True
                self._state["last_action"] = {
                    "action": "snooze-ended",
                    "at": now.isoformat(timespec="seconds"),
                    "occurrence_key": active.get("occurrence_key"),
                }
                return True
            self._state["screen_required"] = False
            active["phase"] = "snoozed"
            return False

        active["phase"] = "ringing"
        self._state["screen_required"] = True
        ring_started = parse_iso_datetime(active.get("ring_cycle_started_at"), self._timezone)
        if ring_started is None:
            active["ring_cycle_started_at"] = now.isoformat(timespec="seconds")
            return True

        try:
            ring_minutes = max(1, min(10, int(active.get("ring_minutes", 3))))
        except (TypeError, ValueError):
            ring_minutes = 3
        if now >= ring_started + timedelta(minutes=ring_minutes):
            self._snooze_locked(now, automatic=True)
            return True
        return False

    def tick(
        self,
        *,
        now: datetime | None = None,
        startup: bool | None = None,
        force_persist: bool = False,
    ) -> dict[str, Any]:
        current = ensure_aware(now, self._timezone) if now is not None else self._now()
        with self._lock:
            before_keys = {
                str(record.get("occurrence_key"))
                for record in self._state.get("observed_occurrences", [])
                if isinstance(record, dict) and record.get("occurrence_key")
            }

        super().tick(
            now=current,
            startup=startup,
            force_persist=force_persist,
        )

        with self._lock:
            changed = self._process_active_locked(current)
            completed = set(str(value) for value in self._state.get("completed_occurrence_keys", []) if value)
            queue = [item for item in self._state.get("queued_occurrences", []) if isinstance(item, dict)]
            queued_keys = {str(item.get("occurrence_key")) for item in queue if item.get("occurrence_key")}

            for record in self._state.get("observed_occurrences", []):
                if not isinstance(record, dict):
                    continue
                key = str(record.get("occurrence_key", ""))
                if not key or key in before_keys or key in completed or key in queued_keys:
                    continue
                queue.append(deepcopy(record))
                queued_keys.add(key)
                changed = True

            pending = self._state.get("pending_test_occurrence")
            if isinstance(pending, dict):
                trigger_at = parse_iso_datetime(pending.get("trigger_at"), self._timezone)
                if trigger_at is not None and current >= trigger_at:
                    key = str(pending.get("occurrence_key", ""))
                    if key and key not in completed and key not in queued_keys:
                        record = deepcopy(pending)
                        record["observed_at"] = current.isoformat(timespec="seconds")
                        record["status"] = "test-due"
                        record["playback_attempted"] = False
                        self._state.setdefault("observed_occurrences", []).append(record)
                        queue.append(deepcopy(record))
                    self._state["pending_test_occurrence"] = None
                    changed = True

            self._state["queued_occurrences"] = queue
            if self._activate_next_queued_locked(current):
                changed = True

            self._state["mode"] = "active-runtime"
            self._state["ui_enabled"] = True
            self._state["playback_enabled"] = False
            if changed or force_persist:
                self._persist_locked(current, force=True)
            return self.status()

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            self._wake_event.clear()
            now = self._now()
            self._state["scheduler_started_at"] = now.isoformat(timespec="seconds")
            self._state["mode"] = "active-runtime"
            self._state["ui_enabled"] = True
            self._state["playback_enabled"] = False

        self.tick(now=now, startup=True, force_persist=True)
        self._thread = threading.Thread(
            target=self._thread_main,
            name="a-clockwork-plex-alarm-scheduler",
            daemon=True,
        )
        self._thread.start()
        print(
            "A Clockwork Plex scheduler: interactive alarm runtime ready in "
            f"{timezone_name(self._timezone)}; audio playback is still disabled.",
            flush=True,
        )

    def snooze(self) -> dict[str, Any]:
        now = self._now()
        with self._lock:
            self._snooze_locked(now, automatic=False)
            self._persist_locked(now, force=True)
        self.wake()
        return self.status()

    def dismiss(self) -> dict[str, Any]:
        now = self._now()
        with self._lock:
            self._dismiss_locked(now, reason="dismissed")
            self._persist_locked(now, force=True)
        self.wake()
        return self.status()

    def schedule_test(self, *, delay_seconds: int = 10, alarm_id: str | None = None) -> dict[str, Any]:
        delay_seconds = max(1, min(300, int(delay_seconds)))
        now = self._now()
        trigger_at = now + timedelta(seconds=delay_seconds)

        config = self._config_loader()
        alarm_config = config.get("alarm", {}) if isinstance(config, dict) else {}
        alarms = alarm_config.get("alarms", []) if isinstance(alarm_config, dict) else []
        selected = None
        for alarm in alarms:
            if not isinstance(alarm, dict):
                continue
            if alarm_id and str(alarm.get("id")) != str(alarm_id):
                continue
            selected = alarm
            break
        if selected is None and alarms:
            selected = next((alarm for alarm in alarms if isinstance(alarm, dict)), None)

        defaults = alarm_config.get("defaults", {}) if isinstance(alarm_config, dict) else {}
        selected = selected or {}
        source = selected.get("source") if isinstance(selected.get("source"), dict) else {
            "type": "tone",
            "tone_id": defaults.get("tone_id", "classic-klaxon"),
            "fallback_tone_id": defaults.get("fallback_tone_id", "emergency-buzzer"),
        }
        volume = selected.get("volume") if isinstance(selected.get("volume"), dict) else {
            "start_percent": 60,
            "target_percent": 85,
            "fade_seconds": 10,
        }
        test_key = f"test|{uuid.uuid4().hex}"
        occurrence = {
            "occurrence_key": test_key,
            "alarm_id": str(selected.get("id", "visual-test")),
            "label": str(selected.get("label", "Visual alarm test")),
            "scheduled_for": trigger_at.isoformat(timespec="seconds"),
            "scheduled_utc": trigger_at.astimezone(timezone.utc).isoformat(timespec="seconds"),
            "wall_date": trigger_at.date().isoformat(),
            "wall_time": trigger_at.strftime("%H:%M"),
            "timezone": timezone_name(self._timezone),
            "snooze_minutes": int(selected.get("snooze_minutes", defaults.get("snooze_minutes", 8))),
            "ring_minutes": int(selected.get("ring_minutes", defaults.get("ring_minutes", 3))),
            "occurrence_expiry_minutes": int(
                selected.get("occurrence_expiry_minutes", defaults.get("occurrence_expiry_minutes", 120))
            ),
            "source": deepcopy(source),
            "volume": deepcopy(volume),
            "test_mode": True,
            "trigger_at": trigger_at.isoformat(timespec="seconds"),
        }

        with self._lock:
            self._state["pending_test_occurrence"] = occurrence
            self._state["last_action"] = {
                "action": "test-scheduled",
                "at": now.isoformat(timespec="seconds"),
                "occurrence_key": test_key,
                "trigger_at": occurrence["trigger_at"],
            }
            self._persist_locked(now, force=True)
        self.wake()
        return self.status()

    def clear_test(self) -> dict[str, Any]:
        now = self._now()
        with self._lock:
            self._state["pending_test_occurrence"] = None
            self._state["queued_occurrences"] = [
                item
                for item in self._state.get("queued_occurrences", [])
                if isinstance(item, dict) and not item.get("test_mode")
            ]
            active = self._state.get("active_occurrence")
            if isinstance(active, dict) and active.get("test_mode"):
                self._dismiss_locked(now, reason="test-cleared")
            self._state["last_action"] = {
                "action": "test-cleared",
                "at": now.isoformat(timespec="seconds"),
            }
            self._persist_locked(now, force=True)
        self.wake()
        return self.status()

    def status(self) -> dict[str, Any]:
        status = super().status()
        status["mode"] = "active-runtime"
        status["ui_enabled"] = True
        status["silent_mode"] = False
        status["playback_enabled"] = False
        status["health"] = (
            "running-ui-ready"
            if status.get("running") and not status.get("last_error")
            else "error"
            if status.get("last_error")
            else "stopped"
        )

        active = status.get("active_occurrence")
        status["screen_required"] = bool(
            isinstance(active, dict)
            and active.get("phase") == "ringing"
            and not status.get("snoozed_until")
        )
        status["active_phase"] = active.get("phase") if isinstance(active, dict) else "idle"

        now = self._now()
        snoozed_until = parse_iso_datetime(status.get("snoozed_until"), self._timezone)
        status["seconds_until_snooze_end"] = (
            max(0, round((snoozed_until - now).total_seconds()))
            if snoozed_until is not None
            else None
        )
        status["queued_occurrence_count"] = len(status.get("queued_occurrences", []))
        status["playback_lockout_reason"] = (
            "The alarm runtime and full-screen controls are active, but sound playback "
            "remains deliberately disabled during this UI-validation pass."
        )
        return status
